"""
Tests for lib/llm_provider.py — LLM Provider Module

Tests the multi-backend LLM provider:
    - MockProvider behavior
    - Cost calculation
    - ProviderStats tracking
    - AdaptiveProvider tier selection
    - Factory function (create_provider)
    - Error handling and retries

Note: Anthropic and OpenAI providers are tested with mocked HTTP
to avoid needing live API keys in CI.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from lib.llm_provider import (
    AdaptiveProvider,
    AnthropicProvider,
    Backend,
    LLMCallMetrics,
    MockProvider,
    OpenAIProvider,
    ProviderStats,
    MODEL_PRICING,
    TIER_MODELS,
    calculate_cost,
    create_provider,
)


# ═══════════════════════════════════════════════════════════════════
# Cost Calculation
# ═══════════════════════════════════════════════════════════════════


class TestCostCalculation:
    def test_sonnet_pricing(self):
        cost = calculate_cost("claude-sonnet-4-20250514", 1_000_000, 1_000_000)
        assert cost == 3.0 + 15.0  # $3/M input + $15/M output

    def test_haiku_pricing(self):
        cost = calculate_cost("claude-haiku-4-5-20250514", 1_000_000, 1_000_000)
        assert cost == 1.0 + 5.0

    def test_gpt4o_mini_pricing(self):
        cost = calculate_cost("gpt-4o-mini", 1_000_000, 1_000_000)
        assert cost == 0.15 + 0.60

    def test_gpt4_1_nano_pricing(self):
        cost = calculate_cost("gpt-4.1-nano", 1_000_000, 1_000_000)
        assert cost == 0.10 + 0.40

    def test_small_token_count(self):
        # 1000 input, 500 output with sonnet pricing
        cost = calculate_cost("claude-sonnet-4-20250514", 1000, 500)
        expected = (1000 / 1_000_000) * 3.0 + (500 / 1_000_000) * 15.0
        assert abs(cost - expected) < 0.0001

    def test_unknown_model_defaults_sonnet(self):
        cost = calculate_cost("unknown-model", 1_000_000, 1_000_000)
        assert cost == 3.0 + 15.0  # defaults to sonnet pricing

    def test_zero_tokens(self):
        cost = calculate_cost("claude-sonnet-4-20250514", 0, 0)
        assert cost == 0.0

    def test_all_models_have_pricing(self):
        for model in MODEL_PRICING:
            input_price, output_price = MODEL_PRICING[model]
            assert input_price >= 0
            assert output_price >= 0


# ═══════════════════════════════════════════════════════════════════
# ProviderStats
# ═══════════════════════════════════════════════════════════════════


class TestProviderStats:
    def test_empty_stats(self):
        stats = ProviderStats()
        assert stats.total_calls == 0
        assert stats.avg_latency_ms == 0.0
        d = stats.to_dict()
        assert d["total_calls"] == 0

    def test_avg_latency(self):
        stats = ProviderStats(total_calls=5, total_latency_ms=500)
        assert stats.avg_latency_ms == 100.0

    def test_to_dict(self):
        stats = ProviderStats(
            total_calls=10,
            total_input_tokens=5000,
            total_output_tokens=2000,
            total_cost_usd=0.123456789,
            total_latency_ms=1500,
            errors=2,
        )
        d = stats.to_dict()
        assert d["total_calls"] == 10
        assert d["total_cost_usd"] == 0.123457  # rounded to 6 decimal places
        assert d["avg_latency_ms"] == 150.0
        assert d["errors"] == 2


# ═══════════════════════════════════════════════════════════════════
# MockProvider
# ═══════════════════════════════════════════════════════════════════


class TestMockProvider:
    @pytest.mark.asyncio
    async def test_default_response(self):
        provider = MockProvider(latency_ms=0)
        result = await provider("Tell me about X")
        assert "mock provider" in result.lower() or "task" in result.lower()

    @pytest.mark.asyncio
    async def test_custom_default_response(self):
        provider = MockProvider(default_response="Custom output", latency_ms=0)
        result = await provider("Any prompt")
        assert result == "Custom output"

    @pytest.mark.asyncio
    async def test_sequential_responses(self):
        provider = MockProvider(
            responses=["First", "Second", "Third"],
            default_response="Default",
            latency_ms=0,
        )
        assert await provider("a") == "First"
        assert await provider("b") == "Second"
        assert await provider("c") == "Third"
        assert await provider("d") == "Default"  # falls back

    @pytest.mark.asyncio
    async def test_call_tracking(self):
        provider = MockProvider(latency_ms=0)
        await provider("Prompt 1", max_tokens=100)
        await provider("Prompt 2", max_tokens=200)

        assert provider.stats.total_calls == 2
        assert len(provider.call_log) == 2
        assert provider.call_log[0]["max_tokens"] == 100
        assert provider.call_log[1]["max_tokens"] == 200

    @pytest.mark.asyncio
    async def test_fail_after(self):
        provider = MockProvider(fail_after=2, latency_ms=0)
        await provider("ok 1")
        await provider("ok 2")
        with pytest.raises(RuntimeError, match="configured to fail"):
            await provider("should fail")

    @pytest.mark.asyncio
    async def test_token_estimation(self):
        provider = MockProvider(default_response="Short reply", latency_ms=0)
        await provider("A prompt with several words in it")
        assert provider.stats.total_input_tokens > 0
        assert provider.stats.total_output_tokens > 0

    @pytest.mark.asyncio
    async def test_zero_cost(self):
        provider = MockProvider(latency_ms=0)
        await provider("test")
        assert provider.stats.total_cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_stats_accumulate(self):
        provider = MockProvider(latency_ms=0)
        for _ in range(5):
            await provider("test")
        assert provider.stats.total_calls == 5
        assert len(provider.call_log) == 5


# ═══════════════════════════════════════════════════════════════════
# OpenAI Provider (mocked HTTP)
# ═══════════════════════════════════════════════════════════════════


class TestOpenAIProvider:
    def test_creation_without_key_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            env_backup = os.environ.pop("OPENAI_API_KEY", None)
            try:
                with pytest.raises(ValueError, match="OPENAI_API_KEY"):
                    OpenAIProvider()
            finally:
                if env_backup:
                    os.environ["OPENAI_API_KEY"] = env_backup

    def test_creation_with_key(self):
        provider = OpenAIProvider(api_key="test-key-12345")
        assert provider.model == "gpt-4o-mini"
        assert provider.stats.total_calls == 0

    @pytest.mark.asyncio
    async def test_successful_call(self):
        provider = OpenAIProvider(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "The answer is 42"}}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 20},
        }

        with patch.object(provider._http, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            result = await provider("What is the meaning of life?")

        assert result == "The answer is 42"
        assert provider.stats.total_calls == 1
        assert provider.stats.total_input_tokens == 50
        assert provider.stats.total_output_tokens == 20

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        provider = OpenAIProvider(api_key="test-key", max_retries=2)

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Network error")
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            resp.json.return_value = {
                "choices": [{"message": {"content": "Retry success"}}],
                "usage": {"prompt_tokens": 30, "completion_tokens": 10},
            }
            return resp

        with patch.object(provider._http, "post", side_effect=mock_post):
            result = await provider("test")

        assert result == "Retry success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_fail(self):
        provider = OpenAIProvider(api_key="test-key", max_retries=2)

        with patch.object(
            provider._http, "post",
            new_callable=AsyncMock,
            side_effect=ConnectionError("down"),
        ):
            with pytest.raises(RuntimeError, match="failed after 2 attempts"):
                await provider("test")

        assert provider.stats.errors == 2

    @pytest.mark.asyncio
    async def test_cost_tracking(self):
        provider = OpenAIProvider(api_key="test-key", model="gpt-4o-mini")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50},
        }

        with patch.object(provider._http, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            await provider("test")

        expected_cost = calculate_cost("gpt-4o-mini", 100, 50)
        assert abs(provider.stats.total_cost_usd - expected_cost) < 0.0001


# ═══════════════════════════════════════════════════════════════════
# Anthropic Provider (mocked SDK)
# ═══════════════════════════════════════════════════════════════════


class TestAnthropicProvider:
    def test_creation_without_key_raises(self):
        with patch.dict(os.environ, {}, clear=True):
            env_backup = os.environ.pop("ANTHROPIC_API_KEY", None)
            try:
                with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                    AnthropicProvider()
            finally:
                if env_backup:
                    os.environ["ANTHROPIC_API_KEY"] = env_backup

    @pytest.mark.asyncio
    async def test_successful_call(self):
        # Create provider with real key (anthropic SDK is installed)
        provider = AnthropicProvider(api_key="test-key")

        # Mock the client's messages.create method
        mock_response = MagicMock()
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_response.content = [MagicMock(text="Claude says hello")]

        provider._client.messages.create = AsyncMock(return_value=mock_response)
        result = await provider("Hello")

        assert result == "Claude says hello"
        assert provider.stats.total_calls == 1
        assert provider.stats.total_input_tokens == 100
        assert provider.stats.total_output_tokens == 50


# ═══════════════════════════════════════════════════════════════════
# AdaptiveProvider
# ═══════════════════════════════════════════════════════════════════


class TestAdaptiveProvider:
    def test_tier_selection_cheap(self):
        # Short prompt → cheap tier
        provider = AdaptiveProvider.__new__(AdaptiveProvider)
        provider.cheap_threshold = 500
        provider.powerful_threshold = 3000
        assert provider._select_tier("short prompt here") == "cheap"

    def test_tier_selection_balanced(self):
        provider = AdaptiveProvider.__new__(AdaptiveProvider)
        provider.cheap_threshold = 10
        provider.powerful_threshold = 3000
        assert provider._select_tier("a " * 200) == "balanced"

    def test_tier_selection_powerful(self):
        provider = AdaptiveProvider.__new__(AdaptiveProvider)
        provider.cheap_threshold = 10
        provider.powerful_threshold = 100
        assert provider._select_tier("a " * 500) == "powerful"

    def test_tier_models_exist(self):
        for tier in ("cheap", "balanced", "powerful"):
            assert "anthropic" in TIER_MODELS[tier]
            assert "openai" in TIER_MODELS[tier]


# ═══════════════════════════════════════════════════════════════════
# Factory: create_provider
# ═══════════════════════════════════════════════════════════════════


class TestCreateProvider:
    def test_mock_provider(self):
        provider = create_provider(backend="mock")
        assert isinstance(provider, MockProvider)

    def test_auto_detect_openai(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test123"}):
            # Remove ANTHROPIC_API_KEY if it exists
            env = dict(os.environ)
            env.pop("ANTHROPIC_API_KEY", None)
            with patch.dict(os.environ, env, clear=True):
                os.environ["OPENAI_API_KEY"] = "test123"
                provider = create_provider()
                assert isinstance(provider, OpenAIProvider)

    def test_auto_detect_no_keys(self):
        with patch.dict(os.environ, {}, clear=True):
            provider = create_provider()
            assert isinstance(provider, MockProvider)

    def test_explicit_openai(self):
        provider = create_provider(backend="openai", api_key="test-key")
        assert isinstance(provider, OpenAIProvider)

    def test_explicit_model(self):
        provider = create_provider(backend="openai", model="gpt-4o", api_key="key")
        assert provider.model == "gpt-4o"

    def test_adaptive_openai(self):
        provider = create_provider(
            backend="openai", adaptive=True, api_key="test-key"
        )
        assert isinstance(provider, AdaptiveProvider)


# ═══════════════════════════════════════════════════════════════════
# LLMCallMetrics
# ═══════════════════════════════════════════════════════════════════


class TestLLMCallMetrics:
    def test_defaults(self):
        m = LLMCallMetrics()
        assert m.model == ""
        assert m.cost_usd == 0.0
        assert m.retries == 0
        assert m.cached_tokens == 0

    def test_populated(self):
        m = LLMCallMetrics(
            model="gpt-4o-mini",
            backend="openai",
            input_tokens=500,
            output_tokens=200,
            cost_usd=0.0003,
            latency_ms=150,
            retries=1,
        )
        assert m.model == "gpt-4o-mini"
        assert m.input_tokens == 500
        assert m.retries == 1


# ═══════════════════════════════════════════════════════════════════
# Integration: MockProvider with TaskExecutor
# ═══════════════════════════════════════════════════════════════════


class TestProviderTaskExecutorIntegration:
    """Verify that providers work with the TaskExecutor's LLMProvider protocol."""

    @pytest.mark.asyncio
    async def test_mock_provider_as_executor_llm(self):
        from services.task_executor import TaskExecutor

        provider = MockProvider(
            default_response="This is a thorough analysis of the data.",
            latency_ms=0,
        )

        executor = TaskExecutor(
            agent_name="test-agent",
            llm_provider=provider,
        )

        task = {
            "id": "test-123",
            "title": "Analyze crypto market trends",
            "instructions": "Provide a summary of current market trends.",
            "category": "analysis",
            "bounty_usd": 0.25,
            "evidence_required": ["text_response"],
        }

        result = await executor.execute_task(task)
        assert result.success
        assert result.strategy_used.value == "llm_direct"
        assert "analysis" in result.output.lower() or "thorough" in result.output.lower()
        assert provider.stats.total_calls == 1

    @pytest.mark.asyncio
    async def test_mock_provider_composite_task(self):
        from services.task_executor import TaskExecutor

        call_count = 0
        responses = [
            "Step 1 result: gathered data",
            "Step 2 result: analyzed patterns",
            "Step 3 result: generated recommendations",
        ]
        provider = MockProvider(responses=responses, latency_ms=0)

        executor = TaskExecutor(
            agent_name="test-agent",
            llm_provider=provider,
        )

        task = {
            "id": "test-456",
            "title": "Multi-step research",
            "instructions": (
                "1. Gather relevant data from sources\n"
                "2. Analyze patterns and trends\n"
                "3. Generate actionable recommendations\n"
            ),
            "category": "research",
            "bounty_usd": 0.50,
        }

        result = await executor.execute_task(task)
        assert result.success
        assert result.strategy_used.value == "composite"
        assert provider.stats.total_calls == 3  # one per step
