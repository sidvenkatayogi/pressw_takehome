import logging

from langchain_openai import ChatOpenAI

from config import AVAILABLE_COOKWARE, CLASSIFICATION_TEMPERATURE, MODEL_NAME
from prompts.cookware import COOKWARE_CHECK_PROMPT
from schemas.graph_state import CookwareCheckResult, GraphState

logger = logging.getLogger(__name__)


async def cookware_check(state: GraphState) -> dict:
    """Check if the recipe can be made with available cookware."""
    logger.info("[cookware_check] Starting cookware analysis")

    research_result = state.get("research_result", "")
    cookware_list = ", ".join(AVAILABLE_COOKWARE)

    prompt = COOKWARE_CHECK_PROMPT.format(
        cookware_list=cookware_list,
        recipe=research_result,
    )

    llm = ChatOpenAI(
        model=MODEL_NAME,
        temperature=CLASSIFICATION_TEMPERATURE,
    ).with_structured_output(CookwareCheckResult)

    result = await llm.ainvoke(
        [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Analyze the cookware requirements."},
        ]
    )

    logger.info(
        "[cookware_check] Result: sufficient=%s, missing=%s",
        result.cookware_sufficient,
        result.missing_cookware,
    )

    return {
        "cookware_check_result": result,
        "debug_info": state.get("debug_info", [])
        + [f"cookware_check: sufficient={result.cookware_sufficient}"],
    }
