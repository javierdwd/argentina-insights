"""LangGraph agent: classify → respond (with tool loop) → END.

Node map:
  classify  — fast/cheap model; assigns query_type (finance | politics | unknown)
  respond   — default model with fetch_argentinadatos bound; may emit tool calls
  tools     — ToolNode that executes fetch_argentinadatos and appends results

Flow:
  classify → respond ──(has tool calls?)──► tools → respond → … → END
                      └──(no tool calls)──► END
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from .catalog import catalog
from .models import get_model
from .state import AgentState
from .tools import fetch_argentinadatos

# ── System prompt template ────────────────────────────────────────────────────

_RESPOND_SYSTEM = """\
You are Argentina Insights, an assistant for Argentine public and financial data.
Query domain: {domain}.

Use the fetch_argentinadatos tool to retrieve live data before answering.
Choose the most specific endpoint from the catalog below and supply all required \
params exactly as listed.

Available endpoints ({domain}):
{catalog}

Rules:
- Always call at least one tool before giving a final answer that includes data.
- After receiving tool results, compose a concise, accurate answer.
- For 'unknown' domain queries you have access to the full catalog — pick the \
most relevant endpoint.
- Do not invent data; if no suitable endpoint exists, say so.
"""


def _system_message(query_type: str) -> SystemMessage:
    catalog_text = catalog.as_prompt_text(query_type)
    content = _RESPOND_SYSTEM.format(domain=query_type, catalog=catalog_text)
    return SystemMessage(content=content)


def _clean_history(messages: list) -> list:
    """Strip tool-call/tool-result messages from client-echoed conversation history.

    The client echoes back the full ag-ui message list on every run, which
    includes internal LangGraph messages (AIMessage with tool_calls, ToolMessage).
    Sending those to a fresh LLM call confuses the model and causes OpenAI 400
    errors ("tool_calls must be followed by tool messages").

    Strategy:
    - Everything *from* the last HumanMessage onward is the CURRENT run's context
      (the user's new question, plus any tool-call/tool-result turns the graph
      accumulated in this same run).  Leave it untouched.
    - Everything *before* the last HumanMessage is PRIOR-TURN history.  Keep only
      HumanMessages and text-only AIMessages (drop AIMessages with tool_calls and
      all ToolMessages — those are implementation details the LLM needn't see).
    """
    last_human = next(
        (i for i in range(len(messages) - 1, -1, -1) if isinstance(messages[i], HumanMessage)),
        -1,
    )
    if last_human <= 0:
        return messages

    history = messages[:last_human]
    current = messages[last_human:]

    clean = [
        m for m in history
        if isinstance(m, HumanMessage)
        or (isinstance(m, AIMessage) and not m.tool_calls and m.content)
    ]
    return clean + current


# ── Nodes ─────────────────────────────────────────────────────────────────────


def classify_node(state: AgentState) -> dict:
    """Classify the user query domain using the fast (cheap) model.

    The ``emit-messages: False`` metadata flag suppresses TEXT_MESSAGE events
    for this internal LLM call so the classification label ("finance", "politics",
    etc.) never reaches the client as an assistant message.
    """
    llm = get_model("fast")
    response = llm.invoke(
        [
            (
                "system",
                "Classify the user query into exactly one word: "
                "finance, politics, or unknown.",
            ),
            *_clean_history(state["messages"]),
        ],
        config={"metadata": {"emit-messages": False}},
    )
    return {"query_type": response.content.strip().lower()}


def respond_node(state: AgentState) -> dict:
    """Generate a response with the default model and the fetch tool.

    Binds fetch_argentinadatos and injects the domain-filtered catalog into
    the system prompt.  Returns tool calls when the model needs data, or a
    plain AIMessage when the answer is ready.
    """
    llm = get_model("default")
    query_type = state.get("query_type", "unknown")

    llm_with_tools = llm.bind_tools([fetch_argentinadatos])
    response = llm_with_tools.invoke(
        [
            _system_message(query_type),
            *_clean_history(state["messages"]),
        ]
    )
    return {"messages": [response]}


# ── Tool execution node ───────────────────────────────────────────────────────

_tool_node = ToolNode([fetch_argentinadatos])


# ── Graph assembly ────────────────────────────────────────────────────────────


def build_graph() -> StateGraph:
    """Build and compile the agent graph with MemorySaver checkpointer."""
    builder = StateGraph(AgentState)

    builder.add_node("classify", classify_node)
    builder.add_node("respond", respond_node)
    builder.add_node("tools", _tool_node)

    builder.set_entry_point("classify")
    builder.add_edge("classify", "respond")

    # tools_condition routes to "tools" when the last message has tool_calls,
    # and to END when the model returns a plain response.
    builder.add_conditional_edges("respond", tools_condition)
    builder.add_edge("tools", "respond")

    # TODO: Only for demo purposes; swap for PostgresSaver before launch.
    return builder.compile(checkpointer=MemorySaver())


# Compiled singleton imported by app.py
graph = build_graph()
