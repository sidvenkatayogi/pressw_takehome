import logging

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config import CREATIVE_TEMPERATURE, MODEL_NAME
from prompts.research import RESEARCH_PROMPT
from schemas.graph_state import GraphState
from tools.search import get_search_tool

logger = logging.getLogger(__name__)


async def research_agent(state: GraphState) -> dict:
    """Research cooking query, optionally using web search tools."""
    logger.info("[research_agent] Starting research")

    search_tool = get_search_tool()
    tools = [search_tool]

    llm = ChatOpenAI(
        model=MODEL_NAME,
        temperature=CREATIVE_TEMPERATURE,
    ).bind_tools(tools)

    # Build message list from conversation history
    langchain_messages = [SystemMessage(content=RESEARCH_PROMPT)]
    for msg in state["messages"]:
        if hasattr(msg, "role"):
            if msg.role == "user":
                langchain_messages.append(HumanMessage(content=msg.content))
            else:
                langchain_messages.append(AIMessage(content=msg.content))
        elif hasattr(msg, "type"):
            langchain_messages.append(msg)
        else:
            langchain_messages.append(HumanMessage(content=str(msg)))

    tools_used = list(state.get("tools_used", []))
    debug_info = list(state.get("debug_info", []))

    # Agentic tool loop — let the LLM decide if it needs to search
    max_iterations = 3
    for i in range(max_iterations):
        response = await llm.ainvoke(langchain_messages)
        langchain_messages.append(response)

        if not response.tool_calls:
            break

        # Execute tool calls
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            logger.info(
                "[research_agent] Tool call: %s with args %s", tool_name, tool_args
            )
            tools_used.append(tool_name)
            debug_info.append(f"research_agent: tool_call {tool_name}")

            try:
                tool_result = await search_tool.ainvoke(tool_args)
                tool_result_str = str(tool_result)
            except Exception as e:
                logger.error("[research_agent] Tool error: %s", e)
                tool_result_str = f"Search failed: {e}"
                debug_info.append(f"research_agent: tool_error {e}")

            from langchain_core.messages import ToolMessage

            langchain_messages.append(
                ToolMessage(content=tool_result_str, tool_call_id=tool_call["id"])
            )

        # Get final response after tool results
        if i < max_iterations - 1:
            continue

    # Extract final text content
    final_content = (
        response.content if response.content else "No research results found."
    )

    logger.info("[research_agent] Research complete, tools_used=%s", tools_used)
    debug_info.append("research_agent: complete")

    return {
        "research_result": final_content,
        "tools_used": tools_used,
        "debug_info": debug_info,
    }
