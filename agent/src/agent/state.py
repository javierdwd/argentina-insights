"""LangGraph state definition for the Argentina Insights agent.

MessagesState provides the built-in `messages` field with an append reducer.
Custom fields are added here as the graph grows.
"""

from langgraph.graph import MessagesState


class AgentState(MessagesState):
    """Graph state.

    Attributes:
        messages: Conversation history (inherited from MessagesState).
        query_type: Domain label assigned by the classify node.
                    One of: "finance" | "politics" | "unknown"
    """

    query_type: str
