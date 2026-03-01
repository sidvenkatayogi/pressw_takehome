import logging

from langchain_openai import ChatOpenAI

from config import CREATIVE_TEMPERATURE, MODEL_NAME
from prompts.generate import GENERATE_PROMPT
from schemas.graph_state import GraphState

logger = logging.getLogger(__name__)


async def generate_response(state: GraphState) -> dict:
    """Synthesize final user-facing response from research and cookware check."""
    logger.info("[generate_response] Generating final response")

    research_result = state.get("research_result", "No research available.")
    cookware_result = state.get("cookware_check_result")

    cookware_analysis = "No cookware analysis available."
    if cookware_result:
        missing = cookware_result.missing_cookware
        missing_str = ", ".join(missing) if missing else "None"
        cookware_analysis = (
            f"Cookware sufficient: {cookware_result.cookware_sufficient}\n"
            f"Missing: {missing_str}\n"
            f"Substitutions: {cookware_result.substitutions}\n"
            f"Analysis: {cookware_result.analysis}"
        )

    prompt = GENERATE_PROMPT.format(
        research_result=research_result,
        cookware_analysis=cookware_analysis,
    )

    # Build conversation context
    messages_for_llm = [{"role": "system", "content": prompt}]
    for msg in state["messages"]:
        if hasattr(msg, "role"):
            messages_for_llm.append({"role": msg.role, "content": msg.content})
        elif hasattr(msg, "type"):
            role = "user" if msg.type == "human" else "assistant"
            messages_for_llm.append({"role": role, "content": msg.content})

    llm = ChatOpenAI(
        model=MODEL_NAME,
        temperature=CREATIVE_TEMPERATURE,
    )

    response = await llm.ainvoke(messages_for_llm)

    logger.info("[generate_response] Response generated")

    return {
        "final_response": response.content,
        "debug_info": state.get("debug_info", []) + ["generate_response: complete"],
    }
