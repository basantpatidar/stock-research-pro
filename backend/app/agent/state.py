from typing import Annotated, Literal

from langgraph.graph.message import add_messages
from pydantic import BaseModel


class AgentState(BaseModel):
    """
    State passed through the LangGraph agent loop.
    add_messages reducer appends new messages — never overwrites.
    """

    messages: Annotated[list, add_messages] = []
    ticker: str = ""
    mode: Literal["day_trade", "long_term", "both"] = "both"
    research_depth: Literal["quick", "deep"] = "quick"

    class Config:
        arbitrary_types_allowed = True
