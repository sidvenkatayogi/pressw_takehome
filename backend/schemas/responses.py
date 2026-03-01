from pydantic import BaseModel


class DebugInfo(BaseModel):
    classification_reasoning: str
    nodes_visited: list[str]
    tool_calls: list[dict]
    cookware_analysis: str | None = None


class ChatResponse(BaseModel):
    answer: str
    query_type: str
    tools_used: list[str] = []
    cookware_sufficient: bool | None = None
    missing_cookware: list[str] = []
    debug: DebugInfo | None = None
