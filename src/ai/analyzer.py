"""Claude-powered market analysis.

Uses the Anthropic Claude API to analyze prediction market questions,
assess fair probabilities, and identify mispriced markets.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

import anthropic

from config.settings import AnthropicConfig

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """\
You are an expert prediction market analyst. Your job is to assess the fair \
probability of outcomes in prediction markets.

You will be given:
1. A market question and description
2. The current market price (which represents the market's implied probability)
3. The available outcomes

Your task:
- Analyze the question using your knowledge
- Estimate the fair probability for each outcome
- Compare your estimate to the market price
- Identify if the market is overpriced or underpriced

Respond ONLY with valid JSON in this exact format:
{
  "fair_probability": <float 0.0-1.0 for YES outcome>,
  "confidence": <float 0.0-1.0 how confident you are in your estimate>,
  "edge": <float, your_probability minus market_price>,
  "direction": "<BUY_YES|BUY_NO|HOLD>",
  "reasoning": "<brief 2-3 sentence explanation>",
  "key_factors": ["<factor1>", "<factor2>", "<factor3>"],
  "risks": ["<risk1>", "<risk2>"]
}

Guidelines:
- Be calibrated. A 70% confidence means you'd be wrong 30% of the time.
- Only suggest BUY_YES/BUY_NO when your edge is significant (>5% difference).
- Consider base rates, reference classes, and historical patterns.
- Account for uncertainty — prediction markets aggregate information efficiently.
- If you don't have enough information, set confidence low and direction to HOLD.
"""


@dataclass
class MarketAnalysis:
    """Result of AI analysis on a market."""

    market_question: str
    market_price: float
    fair_probability: float
    confidence: float
    edge: float
    direction: str  # BUY_YES, BUY_NO, HOLD
    reasoning: str
    key_factors: list[str]
    risks: list[str]
    raw_response: dict[str, Any]

    @property
    def has_signal(self) -> bool:
        """Whether this analysis suggests a trade."""
        return self.direction in ("BUY_YES", "BUY_NO")

    @property
    def signal_strength(self) -> float:
        """Combined signal strength (edge * confidence)."""
        return abs(self.edge) * self.confidence


class MarketAnalyzer:
    """Uses Claude to analyze prediction markets."""

    def __init__(self, config: AnthropicConfig) -> None:
        self._client = anthropic.Anthropic(api_key=config.api_key)
        self._model = config.model

    def analyze(
        self,
        question: str,
        description: str,
        current_price: float,
        outcomes: list[str] | None = None,
        additional_context: str = "",
    ) -> MarketAnalysis:
        """Analyze a market and return a probability assessment.

        Args:
            question: The market question (e.g., "Will X happen by Y date?")
            description: Full market description with resolution criteria.
            current_price: Current YES token price (0.0 - 1.0).
            outcomes: List of outcome names (default: ["Yes", "No"]).
            additional_context: Extra context to provide to Claude.
        """
        if outcomes is None:
            outcomes = ["Yes", "No"]

        user_prompt = f"""Analyze this prediction market:

**Question:** {question}

**Description:** {description}

**Current Market Price (YES):** {current_price:.4f} ({current_price * 100:.1f}% implied probability)

**Outcomes:** {', '.join(outcomes)}
"""
        if additional_context:
            user_prompt += f"\n**Additional Context:** {additional_context}\n"

        logger.info("Analyzing market: %s (price: %.4f)", question[:60], current_price)

        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=ANALYSIS_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )

            text = response.content[0].text.strip()

            # Parse JSON response (handle markdown code blocks)
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            data = json.loads(text)

            analysis = MarketAnalysis(
                market_question=question,
                market_price=current_price,
                fair_probability=float(data["fair_probability"]),
                confidence=float(data["confidence"]),
                edge=float(data["edge"]),
                direction=data["direction"],
                reasoning=data["reasoning"],
                key_factors=data.get("key_factors", []),
                risks=data.get("risks", []),
                raw_response=data,
            )

            logger.info(
                "Analysis complete: fair=%.4f, edge=%.4f, direction=%s, confidence=%.2f",
                analysis.fair_probability, analysis.edge,
                analysis.direction, analysis.confidence,
            )
            return analysis

        except json.JSONDecodeError as e:
            logger.error("Failed to parse Claude response as JSON: %s", e)
            return MarketAnalysis(
                market_question=question,
                market_price=current_price,
                fair_probability=current_price,
                confidence=0.0,
                edge=0.0,
                direction="HOLD",
                reasoning=f"Failed to parse AI response: {e}",
                key_factors=[],
                risks=["AI analysis failed"],
                raw_response={"error": str(e), "raw_text": text},
            )
        except Exception as e:
            logger.error("Claude analysis failed: %s", e)
            return MarketAnalysis(
                market_question=question,
                market_price=current_price,
                fair_probability=current_price,
                confidence=0.0,
                edge=0.0,
                direction="HOLD",
                reasoning=f"AI analysis error: {e}",
                key_factors=[],
                risks=["AI analysis failed"],
                raw_response={"error": str(e)},
            )

    async def analyze_batch(
        self,
        markets: list[dict[str, Any]],
    ) -> list[MarketAnalysis]:
        """Analyze multiple markets sequentially.

        Args:
            markets: List of dicts with keys: question, description, price, outcomes.
        """
        results: list[MarketAnalysis] = []
        for market in markets:
            analysis = self.analyze(
                question=market["question"],
                description=market.get("description", ""),
                current_price=market["price"],
                outcomes=market.get("outcomes"),
                additional_context=market.get("context", ""),
            )
            results.append(analysis)
        return results
