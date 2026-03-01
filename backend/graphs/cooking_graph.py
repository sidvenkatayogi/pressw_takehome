import logging

from langgraph.graph import END, StateGraph

from nodes.classify import classify_query
from nodes.cookware import cookware_check
from nodes.generate import generate_response
from nodes.refuse import refuse_response
from nodes.research import research_agent
from schemas.graph_state import GraphState

logger = logging.getLogger(__name__)


def route_after_classification(state: GraphState) -> str:
    """Route to refuse or research based on classification result."""
    classification = state.get("classification")
    if classification and classification.is_cooking_related:
        return "research_agent"
    return "refuse_response"


def build_cooking_graph():
    """Build and compile the cooking Q&A LangGraph."""
    graph = StateGraph(GraphState)

    # Add nodes
    graph.add_node("classify_query", classify_query)
    graph.add_node("research_agent", research_agent)
    graph.add_node("cookware_check", cookware_check)
    graph.add_node("generate_response", generate_response)
    graph.add_node("refuse_response", refuse_response)

    # Set entry point
    graph.set_entry_point("classify_query")

    # Conditional edge after classification
    graph.add_conditional_edges(
        "classify_query",
        route_after_classification,
        {
            "research_agent": "research_agent",
            "refuse_response": "refuse_response",
        },
    )

    # Linear edges for cooking path
    graph.add_edge("research_agent", "cookware_check")
    graph.add_edge("cookware_check", "generate_response")
    graph.add_edge("generate_response", END)
    graph.add_edge("refuse_response", END)

    return graph.compile()


# Singleton compiled graph
cooking_graph = build_cooking_graph()
