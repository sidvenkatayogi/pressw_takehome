import logging

from schemas.graph_state import GraphState

logger = logging.getLogger(__name__)

REFUSAL_MESSAGE = (
    "I'm a cooking assistant and can only help with food-related questions. "
    "Try asking me about recipes, cooking techniques, or ingredients!"
)


async def refuse_response(state: GraphState) -> dict:
    """Return a polite refusal for off-topic queries. Deterministic — no LLM call."""
    logger.info("[refuse_response] Refusing off-topic query")

    return {
        "final_response": REFUSAL_MESSAGE,
        "debug_info": state.get("debug_info", []) + ["refuse_response: off-topic"],
    }
