"""Stateless graph; complete session snapshots are persisted by DebateService."""

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.graph.nodes import debate_node, fallacy_node, grader_node, memory_node
from app.models.session import SessionState


def _entry(state: SessionState) -> str:
    return "grader_node" if state.get("is_ended") else "debate_node"


def build_debate_graph() -> Any:
    builder: StateGraph = StateGraph(SessionState)  # type: ignore[type-arg]
    builder.add_node("debate_node", debate_node)
    builder.add_node("fallacy_node", fallacy_node)
    builder.add_node("memory_node", memory_node)
    builder.add_node("grader_node", grader_node)
    builder.add_conditional_edges(START, _entry, ["debate_node", "grader_node"])
    builder.add_edge("debate_node", "fallacy_node")
    builder.add_edge("debate_node", "memory_node")
    builder.add_edge("fallacy_node", END)
    builder.add_edge("memory_node", END)
    builder.add_edge("grader_node", END)
    return builder.compile()
