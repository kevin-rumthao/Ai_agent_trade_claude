from pydantic import BaseModel, Field
from typing import Literal

class GeminiRegimeResponse(BaseModel):
    """Schema for Gemini regime classification response."""
    regime: Literal["TRENDING", "RANGING", "HIGH_VOLATILITY", "LOW_VOLATILITY", "UNKNOWN"]
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
