import logging

from langchain_openai import ChatOpenAI

from config import CLASSIFICATION_TEMPERATURE, MODEL_NAME
from prompts.classify import CLASSIFY_PROMPT
from schemas.graph_state import ClassificationResult, GraphState

logger = logging.getLogger(__name__)


async def classify_query(state: GraphState) -> dict:
    """Classify whether the user's query is cooking-related."""
    logger.info("[classify_query] Starting classification")

    messages = state["messages"]
    user_message = (
        messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1])
    )

    llm = ChatOpenAI(
        model=MODEL_NAME,
        temperature=CLASSIFICATION_TEMPERATURE,
    ).with_structured_output(ClassificationResult)

    result = await llm.ainvoke(
        [
            {"role": "system", "content": CLASSIFY_PROMPT},
            {"role": "user", "content": user_message},
        ]
    )

    logger.info(
        "[classify_query] Result: category=%s, is_cooking=%s, reason=%s",
        result.category,
        result.is_cooking_related,
        result.reasoning,
    )

    return {
        "classification": result,
        "debug_info": state.get("debug_info", [])
        + [f"classify_query: {result.category} ({result.reasoning})"],
    }
