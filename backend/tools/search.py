import logging

from config import TAVILY_API_KEY

logger = logging.getLogger(__name__)


def get_search_tool():
    """Return Tavily search tool if API key available, else DuckDuckGo fallback."""
    if TAVILY_API_KEY:
        logger.info("Using Tavily search tool")
        from langchain_community.tools.tavily_search import TavilySearchResults

        return TavilySearchResults(max_results=3)

    logger.info("No TAVILY_API_KEY found, using DuckDuckGo fallback")
    from langchain_community.tools import DuckDuckGoSearchRun

    return DuckDuckGoSearchRun()
