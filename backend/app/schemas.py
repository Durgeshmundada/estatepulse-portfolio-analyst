from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionCreate(StrictModel):
    user_id: str
    access_code: str


class MessageCreate(StrictModel):
    request_id: str = Field(min_length=8, max_length=64)
    text: str = Field(min_length=1, max_length=2000)


class ConversationCreate(StrictModel):
    pass


class ConfirmRequest(StrictModel):
    request_id: str = Field(min_length=8, max_length=64)


class AgentPlan(StrictModel):
    intent: Literal[
        "summary", "insights", "list", "exposure", "highest_rent", "highest_yield", "compare",
        "scenario_exclude", "scenario_value_change", "scenario_reset", "propose_add",
        "propose_update", "greeting", "thanks", "help", "unsupported", "human_help"
    ]
    property_type: str | None = None
    second_property_type: str | None = None
    location: str | None = None
    property_ref: str | None = None
    value_inr: int | None = None
    value_change_pct: float | None = None
    area_sqft: int | None = None
    sub_type: str | None = None
    reason: str | None = None


class AgentState(StrictModel):
    user_id: str
    conversation_id: str
    request_id: str
    text: str
    context: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, str]] = Field(default_factory=list)
    plan: AgentPlan | None = None
    reply_text: str = ""
    cards: list[dict[str, Any]] = Field(default_factory=list)
    context_update: dict[str, Any] = Field(default_factory=dict)
    attention: str | None = None
