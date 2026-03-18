"""Signal generation from AI analysis.

Combines AI market analysis with market data to produce
actionable trading signals with confidence scores.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.ai.analyzer import MarketAnalysis, MarketAnalyzer
from src.markets import MarketInfo

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """A trading signal generated from AI analysis."""

    market_question: str
    token_id: str
    condition_id: str
    direction: str  # BUY_YES, BUY_NO, HOLD
    confidence: float
    edge: float
    signal_strength: float
    fair_probability: float
    market_price: float
    reasoning: str
    risks: list[str]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_actionable(self) -> bool:
        """Whether this signal warrants a trade."""
        return self.direction in ("BUY_YES", "BUY_NO") and self.confidence > 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize for logging / storage."""
        return {
            "market_question": self.market_question,
            "token_id": self.token_id,
            "condition_id": self.condition_id,
            "direction": self.direction,
            "confidence": self.confidence,
            "edge": self.edge,
            "signal_strength": self.signal_strength,
            "fair_probability": self.fair_probability,
            "market_price": self.market_price,
            "reasoning": self.reasoning,
            "risks": self.risks,
            "timestamp": self.timestamp,
        }


class SignalGenerator:
    """Generates trading signals by combining AI analysis with market data."""

    def __init__(
        self,
        analyzer: MarketAnalyzer,
        min_confidence: float = 0.7,
        min_edge: float = 0.05,
    ) -> None:
        self._analyzer = analyzer
        self._min_confidence = min_confidence
        self._min_edge = min_edge
        self._signal_log: list[Signal] = []

    def generate_signal(self, market: MarketInfo) -> Signal:
        """Analyze a market and generate a trading signal.

        Args:
            market: Parsed market info from the scanner.

        Returns:
            A Signal object (may be HOLD if no edge found).
        """
        if not market.tokens:
            return self._hold_signal(market, "No tokens available")

        # Use the YES token price as the market price
        market_price = market.outcome_prices[0] if market.outcome_prices else 0.5
        yes_token_id = market.tokens[0].get("token_id", "") if market.tokens else ""

        # Run Claude analysis
        analysis = self._analyzer.analyze(
            question=market.question,
            description=market.description,
            current_price=market_price,
            outcomes=market.outcomes,
        )

        # Apply filters
        signal = self._analysis_to_signal(analysis, market, yes_token_id)

        # Log signal
        self._signal_log.append(signal)
        self._log_signal(signal)

        return signal

    def _analysis_to_signal(
        self,
        analysis: MarketAnalysis,
        market: MarketInfo,
        yes_token_id: str,
    ) -> Signal:
        """Convert an AI analysis into a filtered signal."""
        # Check minimum thresholds
        if analysis.confidence < self._min_confidence:
            return Signal(
                market_question=market.question,
                token_id=yes_token_id,
                condition_id=market.condition_id,
                direction="HOLD",
                confidence=analysis.confidence,
                edge=analysis.edge,
                signal_strength=analysis.signal_strength,
                fair_probability=analysis.fair_probability,
                market_price=analysis.market_price,
                reasoning=f"Confidence {analysis.confidence:.2f} below threshold {self._min_confidence:.2f}",
                risks=analysis.risks,
            )

        if abs(analysis.edge) < self._min_edge:
            return Signal(
                market_question=market.question,
                token_id=yes_token_id,
                condition_id=market.condition_id,
                direction="HOLD",
                confidence=analysis.confidence,
                edge=analysis.edge,
                signal_strength=analysis.signal_strength,
                fair_probability=analysis.fair_probability,
                market_price=analysis.market_price,
                reasoning=f"Edge {analysis.edge:.4f} below threshold {self._min_edge:.4f}",
                risks=analysis.risks,
            )

        return Signal(
            market_question=market.question,
            token_id=yes_token_id,
            condition_id=market.condition_id,
            direction=analysis.direction,
            confidence=analysis.confidence,
            edge=analysis.edge,
            signal_strength=analysis.signal_strength,
            fair_probability=analysis.fair_probability,
            market_price=analysis.market_price,
            reasoning=analysis.reasoning,
            risks=analysis.risks,
        )

    def _hold_signal(self, market: MarketInfo, reason: str) -> Signal:
        """Create a HOLD signal."""
        return Signal(
            market_question=market.question,
            token_id="",
            condition_id=market.condition_id,
            direction="HOLD",
            confidence=0.0,
            edge=0.0,
            signal_strength=0.0,
            fair_probability=0.5,
            market_price=0.5,
            reasoning=reason,
            risks=[],
        )

    def _log_signal(self, signal: Signal) -> None:
        """Log a signal for debugging and backtesting."""
        if signal.is_actionable:
            logger.info(
                "SIGNAL: %s | %s | edge=%.4f | conf=%.2f | strength=%.4f | %s",
                signal.direction,
                signal.market_question[:50],
                signal.edge,
                signal.confidence,
                signal.signal_strength,
                signal.reasoning[:80],
            )
        else:
            logger.debug(
                "HOLD: %s | edge=%.4f | conf=%.2f | %s",
                signal.market_question[:50],
                signal.edge,
                signal.confidence,
                signal.reasoning[:60],
            )

    @property
    def signal_history(self) -> list[Signal]:
        """Get all generated signals for backtesting."""
        return list(self._signal_log)

    @property
    def actionable_signals(self) -> list[Signal]:
        """Get only actionable signals from history."""
        return [s for s in self._signal_log if s.is_actionable]

    def clear_history(self) -> None:
        """Clear the signal log."""
        self._signal_log.clear()
