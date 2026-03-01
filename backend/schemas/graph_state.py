from typing import TypedDict

from pydantic import BaseModel


class ClassificationResult(BaseModel):
    is_cooking_related: bool
    category: (
        str  # "general_cooking", "recipe_request", "ingredient_query", "off_topic"
    )
    reasoning: str


class CookwareCheckResult(BaseModel):
    cookware_sufficient: bool
    missing_cookware: list[str] = []
    substitutions: str = ""
    analysis: str = ""


class GraphState(TypedDict):
    messages: list
    classification: ClassificationResult | None
    research_result: str | None
    tools_used: list[str]
    cookware_check_result: CookwareCheckResult | None
    final_response: str | None
    debug_info: list[str]
