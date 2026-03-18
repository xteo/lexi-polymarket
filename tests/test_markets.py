"""Tests for market scanning and filtering."""

from unittest.mock import MagicMock

import pytest

from src.markets import MarketInfo, MarketScanner


@pytest.fixture
def scanner() -> MarketScanner:
    mock_client = MagicMock()
    return MarketScanner(mock_client)


@pytest.fixture
def sample_market_data() -> list[dict]:
    return [
        {
            "conditionId": "0xabc123",
            "question": "Will Bitcoin reach $100k by end of 2026?",
            "description": "Resolves YES if BTC >= $100,000 on any major exchange.",
            "category": "Crypto",
            "endDate": "2026-12-31T23:59:59Z",
            "tokens": [
                {"outcome": "Yes", "price": 0.72, "token_id": "token_yes"},
                {"outcome": "No", "price": 0.28, "token_id": "token_no"},
            ],
            "volume": 150000,
            "liquidity": 25000,
            "active": True,
        },
        {
            "conditionId": "0xdef456",
            "question": "Will it rain in London tomorrow?",
            "description": "Resolves based on Met Office data.",
            "category": "Weather",
            "endDate": "2026-03-20T00:00:00Z",
            "tokens": [
                {"outcome": "Yes", "price": 0.60, "token_id": "token_yes2"},
                {"outcome": "No", "price": 0.40, "token_id": "token_no2"},
            ],
            "volume": 500,
            "liquidity": 200,
            "active": True,
        },
        {
            "conditionId": "0xghi789",
            "question": "Will the Fed cut rates in June 2026?",
            "description": "Resolves based on FOMC announcement.",
            "category": "Economics",
            "endDate": "2026-06-15T00:00:00Z",
            "tokens": [
                {"outcome": "Yes", "price": 0.45, "token_id": "token_yes3"},
                {"outcome": "No", "price": 0.55, "token_id": "token_no3"},
            ],
            "volume": 80000,
            "liquidity": 15000,
            "active": True,
        },
    ]


class TestMarketScanner:
    def test_parse_market(self, scanner: MarketScanner, sample_market_data: list[dict]) -> None:
        """parse_market correctly extracts fields."""
        info = scanner.parse_market(sample_market_data[0])

        assert info.condition_id == "0xabc123"
        assert info.question == "Will Bitcoin reach $100k by end of 2026?"
        assert info.category == "Crypto"
        assert info.volume == 150000
        assert info.liquidity == 25000
        assert info.outcomes == ["Yes", "No"]
        assert info.outcome_prices == [0.72, 0.28]
        assert info.active is True

    def test_parse_market_midpoint(self, scanner: MarketScanner, sample_market_data: list[dict]) -> None:
        """midpoint property returns YES token price."""
        info = scanner.parse_market(sample_market_data[0])
        assert info.midpoint == 0.72

    def test_filter_by_volume(self, scanner: MarketScanner, sample_market_data: list[dict]) -> None:
        """Filter markets by minimum volume."""
        results = scanner.filter_markets(sample_market_data, min_volume=10000)
        assert len(results) == 2
        questions = [m.question for m in results]
        assert "Will it rain in London tomorrow?" not in questions

    def test_filter_by_liquidity(self, scanner: MarketScanner, sample_market_data: list[dict]) -> None:
        """Filter markets by minimum liquidity."""
        results = scanner.filter_markets(sample_market_data, min_liquidity=20000)
        assert len(results) == 1
        assert results[0].question == "Will Bitcoin reach $100k by end of 2026?"

    def test_filter_by_category(self, scanner: MarketScanner, sample_market_data: list[dict]) -> None:
        """Filter markets by category."""
        results = scanner.filter_markets(sample_market_data, category="Crypto")
        assert len(results) == 1
        assert results[0].category == "Crypto"

    def test_filter_combined(self, scanner: MarketScanner, sample_market_data: list[dict]) -> None:
        """Multiple filters combine correctly."""
        results = scanner.filter_markets(
            sample_market_data,
            min_volume=1000,
            min_liquidity=10000,
        )
        assert len(results) == 2

    def test_filter_no_results(self, scanner: MarketScanner, sample_market_data: list[dict]) -> None:
        """Filters that match nothing return empty list."""
        results = scanner.filter_markets(sample_market_data, min_volume=1_000_000)
        assert results == []

    def test_filter_no_filters(self, scanner: MarketScanner, sample_market_data: list[dict]) -> None:
        """No filters returns all markets."""
        results = scanner.filter_markets(sample_market_data)
        assert len(results) == 3


class TestMarketInfo:
    def test_midpoint_empty_prices(self) -> None:
        """midpoint returns None when no prices available."""
        info = MarketInfo(
            condition_id="test",
            question="Test?",
            description="",
            category="",
            end_date="",
            tokens=[],
            volume=0,
            liquidity=0,
            active=True,
            outcomes=[],
            outcome_prices=[],
        )
        assert info.midpoint is None
