"""Hello-world LangGraph: classify → respond.

Two-node graph that demonstrates the multi-model pattern.
The classify node uses MODEL_FAST; the respond node uses MODEL_DEFAULT.
MemorySaver is wired as the checkpointer so HITL is ready to add later.
"""

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from .models import get_model
from .state import AgentState


# ── Nodes ─────────────────────────────────────────────────────────────────────


def classify_node(state: AgentState) -> dict:
    """Classify the user query domain using the fast (cheap) model."""
    llm = get_model("fast")
    response = llm.invoke(
        [
            (
                "system",
                "Classify the user query into exactly one word: "
                "finance, politics, or unknown.",
            ),
            *state["messages"],
        ]
    )
    return {"query_type": response.content.strip().lower()}


def respond_node(state: AgentState) -> dict:
    """Generate a stub response using the default model."""
    llm = get_model("default")
    query_type = state.get("query_type", "unknown")
    response = llm.invoke(
        [
            (
                "system",
                f"You are Argentina Insights, an assistant for Argentine public data. "
                f"Query domain: {query_type}. Respond concisely and helpfully.",
            ),
            *state["messages"],
        ]
    )
    return {"messages": [AIMessage(content=response.content)]}


# ── Graph assembly ────────────────────────────────────────────────────────────


def build_graph() -> StateGraph:
    """Build and compile the agent graph with MemorySaver checkpointer."""
    builder = StateGraph(AgentState)

    builder.add_node("classify", classify_node)
    builder.add_node("respond", respond_node)

    builder.set_entry_point("classify")
    builder.add_edge("classify", "respond")
    builder.add_edge("respond", END)

    # TODO: Only for demo porpuses, it must be updated to PostgresSaver before launch
    return builder.compile(checkpointer=MemorySaver())


# Compiled singleton imported by app.py
graph = build_graph()
