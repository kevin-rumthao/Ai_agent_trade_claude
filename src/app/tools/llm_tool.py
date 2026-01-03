"""LLM tool for regime classification and decision support (Gemini-based)."""
from typing import Optional
import google.generativeai as genai

from app.config import settings
from app.schemas.models import MarketFeatures, MarketRegime
from app.schemas.llm import GeminiRegimeResponse
import json
import logging

logger = logging.getLogger(__name__)


class LLMTool:
    """Tool for LLM-based analysis and decision making using Gemini."""

    def __init__(self) -> None:
        # Configure Gemini with API key
        genai.configure(api_key=settings.gemini_api_key)
        # Use gemini-pro-latest model (most stable, maps to latest gemini-pro version)
        self.model = genai.GenerativeModel('gemini-pro-latest')

    async def classify_regime_with_llm(
        self,
        features: MarketFeatures,
        ambiguity_score: float,
    ) -> MarketRegime:
        """Use Gemini to classify market regime when rules are uncertain."""

        system_prompt = """You are an expert quantitative trader analyzing market regimes.
Based on the provided market features, classify the current regime as one of:
- TRENDING (strong directional movement)
- RANGING (sideways, mean-reverting)
- HIGH_VOLATILITY (elevated volatility)
- LOW_VOLATILITY (calm market)
- UNKNOWN (insufficient data)

Provide your classification and confidence score (0-1).
Be concise and analytical."""

        user_message = f"""Analyze these market features and classify the regime:

Symbol: {features.symbol}
Current Price: {features.price}
EMA(9): {features.ema_9}
EMA(50): {features.ema_50}
ATR: {features.atr}
Realized Volatility: {features.realized_volatility}
Orderbook Imbalance: {features.orderbook_imbalance}
Spread: {features.spread}

The rule-based classifier has ambiguity score of {ambiguity_score:.2f}.

OUTPUT IN JSON FORMAT ONLY.
{{
    "regime": "enum(TRENDING, RANGING, HIGH_VOLATILITY, LOW_VOLATILITY, UNKNOWN)",
    "confidence": 0.0-1.0,
    "reasoning": "string"
}}"""

        # Combine system and user messages
        full_prompt = f"{system_prompt}\n\n{user_message}"

        logger.info(json.dumps({
            "event": "LLM_REQUEST",
            "function": "classify_regime_with_llm",
            "symbol": features.symbol,
            "ambiguity_score": ambiguity_score
        }))

        # Generate response using Gemini
        try:
            response = self.model.generate_content(full_prompt)
            content = response.text
            
            # Clean markdown code blocks if present
            clean_content = content
            if "```json" in clean_content:
                clean_content = clean_content.split("```json")[1].split("```")[0]
            elif "```" in clean_content:
                clean_content = clean_content.split("```")[1].split("```")[0]

            data = json.loads(clean_content)
            validated = GeminiRegimeResponse(**data)
            
            # Log readable decision
            logger.info(f"LLM Decision: {validated.regime} (Conf: {validated.confidence:.2f})")
            if hasattr(validated, 'reasoning'):
                logger.info(f"LLM Reasoning: {validated.reasoning}")

            return MarketRegime(
                regime=validated.regime,
                confidence=validated.confidence,
                timestamp=features.timestamp,
                # Store reasoning somehow if needed
            )
        except Exception as e:
            logger.error(f"LLM Parse Error: {e}")
            return MarketRegime(
                regime="UNKNOWN", 
                confidence=0.0,
                timestamp=features.timestamp
            )

    async def get_trading_advice(
        self,
        features: MarketFeatures,
        regime: MarketRegime,
        current_position: Optional[str] = None,
    ) -> str:
        """Get trading advice from Gemini for complex scenarios."""

        system_prompt = """You are an expert algorithmic trader providing concise trading advice.
Consider the market regime, features, and current position to suggest optimal actions.
Be specific and actionable. Keep responses under 100 words."""

        user_message = f"""Current Market State:

Symbol: {features.symbol}
Price: {features.price}
Regime: {regime.regime} (confidence: {regime.confidence:.2f})

Features:
- EMA(9): {features.ema_9}, EMA(50): {features.ema_50}
- ATR: {features.atr}
- Volatility: {features.realized_volatility}
- OB Imbalance: {features.orderbook_imbalance}

Current Position: {current_position or 'None'}

What action should be taken? Consider entry, exit, or hold."""

        # Combine system and user messages
        full_prompt = f"{system_prompt}\n\n{user_message}"

        # Generate response using Gemini
        response = self.model.generate_content(full_prompt)

        if response.text:
            return response.text.strip()
        return "Unable to generate advice"


# Global instance
llm_tool = LLMTool()
