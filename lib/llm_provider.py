"""
Karma Kadabra V2 — LLM Provider

Multi-backend LLM provider implementing the TaskExecutor's LLMProvider protocol.
Supports Anthropic Claude, OpenAI GPT, and a local mock for testing.

Design:
    - Protocol-compatible: async def __call__(prompt, max_tokens) -> str
    - Retries with exponential backoff
    - Token tracking and cost calculation per call
    - Model selection based on task complexity
    - Rate limiting aware

Usage:
    # Auto-detect from environment
    provider = create_provider()

    # Explicit backend
    provider = create_provider(backend="openai", model="gpt-4o-mini")

    # In TaskExecutor
    executor = TaskExecutor(agent_name="kk-agent-3", llm_provider=provider)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

logger = logging.getLogger("kk.llm")


# ═══════════════════════════════════════════════════════════════════
# Cost & Pricing
# ═══════════════════════════════════════════════════════════════════

# Pricing per million tokens (input, output) in USD
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # Anthropic
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-haiku-4-5-20250514": (1.0, 5.0),
    "claude-opus-4-6": (15.0, 75.0),
    # OpenAI
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1": (2.0, 8.0),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "o3-mini": (1.10, 4.40),
}

# Default models per complexity tier
TIER_MODELS = {
    "cheap": {
        "anthropic": "claude-haiku-4-5-20250514",
        "openai": "gpt-4.1-nano",
    },
    "balanced": {
        "anthropic": "claude-sonnet-4-20250514",
        "openai": "gpt-4o-mini",
    },
    "powerful": {
        "anthropic": "claude-sonnet-4-20250514",
        "openai": "gpt-4o",
    },
}


class Backend(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    MOCK = "mock"


@dataclass
class LLMCallMetrics:
    """Metrics from a single LLM call."""
    model: str = ""
    backend: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    retries: int = 0
    cached_tokens: int = 0


@dataclass
class ProviderStats:
    """Aggregate stats for a provider instance."""
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    total_latency_ms: int = 0
    errors: int = 0
    calls: list[LLMCallMetrics] = field(default_factory=list)

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / max(self.total_calls, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "errors": self.errors,
        }


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate cost for a given model and token count."""
    pricing = MODEL_PRICING.get(model, (3.0, 15.0))  # default to sonnet pricing
    input_cost = (input_tokens / 1_000_000) * pricing[0]
    output_cost = (output_tokens / 1_000_000) * pricing[1]
    return input_cost + output_cost


# ═══════════════════════════════════════════════════════════════════
# Provider Protocol (matches TaskExecutor's LLMProvider)
# ═══════════════════════════════════════════════════════════════════


class LLMProvider(Protocol):
    """Protocol for LLM completion providers."""

    async def __call__(self, prompt: str, max_tokens: int = 4096) -> str: ...


# ═══════════════════════════════════════════════════════════════════
# Anthropic Provider
# ═══════════════════════════════════════════════════════════════════


class AnthropicProvider:
    """Anthropic Claude API provider.

    Uses the anthropic Python SDK for API calls.
    Supports retries, token tracking, and model selection.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
        max_retries: int = 3,
        system_prompt: str = "",
        temperature: float = 0.3,
    ):
        try:
            import anthropic
        except ImportError:
            raise ImportError("anthropic SDK required: pip install anthropic")

        self.model = model
        self.max_retries = max_retries
        self.system_prompt = system_prompt or (
            "You are a skilled task execution agent. Complete the given task "
            "thoroughly and accurately. Provide structured, actionable output."
        )
        self.temperature = temperature
        self.stats = ProviderStats()

        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise ValueError(
                "ANTHROPIC_API_KEY not set. Set env var or pass api_key parameter."
            )
        self._client = anthropic.AsyncAnthropic(api_key=key)

    async def __call__(self, prompt: str, max_tokens: int = 4096) -> str:
        """Execute a prompt and return the response text."""
        last_error = None

        for attempt in range(self.max_retries):
            start = time.monotonic()
            try:
                response = await self._client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=self.temperature,
                    system=self.system_prompt,
                    messages=[{"role": "user", "content": prompt}],
                )

                latency = int((time.monotonic() - start) * 1000)
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                cost = calculate_cost(self.model, input_tokens, output_tokens)

                metrics = LLMCallMetrics(
                    model=self.model,
                    backend="anthropic",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost,
                    latency_ms=latency,
                    retries=attempt,
                    cached_tokens=getattr(response.usage, "cache_read_input_tokens", 0),
                )
                self._record(metrics)

                # Extract text from response
                text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        text += block.text
                return text

            except Exception as e:
                last_error = e
                latency = int((time.monotonic() - start) * 1000)
                self.stats.errors += 1
                logger.warning(
                    f"Anthropic call failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # exponential backoff

        raise RuntimeError(f"Anthropic API failed after {self.max_retries} attempts: {last_error}")

    def _record(self, metrics: LLMCallMetrics) -> None:
        self.stats.total_calls += 1
        self.stats.total_input_tokens += metrics.input_tokens
        self.stats.total_output_tokens += metrics.output_tokens
        self.stats.total_cost_usd += metrics.cost_usd
        self.stats.total_latency_ms += metrics.latency_ms
        self.stats.calls.append(metrics)


# ═══════════════════════════════════════════════════════════════════
# OpenAI Provider
# ═══════════════════════════════════════════════════════════════════


class OpenAIProvider:
    """OpenAI API provider.

    Uses the openai Python SDK (or httpx for direct calls).
    Supports GPT-4o, GPT-4o-mini, GPT-4.1, o3-mini.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: str | None = None,
        max_retries: int = 3,
        system_prompt: str = "",
        temperature: float = 0.3,
    ):
        self.model = model
        self.max_retries = max_retries
        self.system_prompt = system_prompt or (
            "You are a skilled task execution agent. Complete the given task "
            "thoroughly and accurately. Provide structured, actionable output."
        )
        self.temperature = temperature
        self.stats = ProviderStats()

        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "OPENAI_API_KEY not set. Set env var or pass api_key parameter."
            )

        # Use httpx directly to avoid heavy openai SDK dependency
        import httpx
        self._http = httpx.AsyncClient(
            base_url="https://api.openai.com/v1",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=120.0,
        )

    async def __call__(self, prompt: str, max_tokens: int = 4096) -> str:
        """Execute a prompt and return the response text."""
        last_error = None

        for attempt in range(self.max_retries):
            start = time.monotonic()
            try:
                payload = {
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "temperature": self.temperature,
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                }

                resp = await self._http.post("/chat/completions", json=payload)
                resp.raise_for_status()
                data = resp.json()

                latency = int((time.monotonic() - start) * 1000)
                usage = data.get("usage", {})
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)
                cost = calculate_cost(self.model, input_tokens, output_tokens)

                metrics = LLMCallMetrics(
                    model=self.model,
                    backend="openai",
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost,
                    latency_ms=latency,
                    retries=attempt,
                )
                self._record(metrics)

                text = data["choices"][0]["message"]["content"]
                return text

            except Exception as e:
                last_error = e
                self.stats.errors += 1
                logger.warning(
                    f"OpenAI call failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)

        raise RuntimeError(f"OpenAI API failed after {self.max_retries} attempts: {last_error}")

    def _record(self, metrics: LLMCallMetrics) -> None:
        self.stats.total_calls += 1
        self.stats.total_input_tokens += metrics.input_tokens
        self.stats.total_output_tokens += metrics.output_tokens
        self.stats.total_cost_usd += metrics.cost_usd
        self.stats.total_latency_ms += metrics.latency_ms
        self.stats.calls.append(metrics)

    async def close(self):
        await self._http.aclose()


# ═══════════════════════════════════════════════════════════════════
# Mock Provider (Testing)
# ═══════════════════════════════════════════════════════════════════


class MockProvider:
    """Mock LLM provider for testing.

    Returns configurable responses without calling any external API.
    Tracks calls for assertion in tests.
    """

    def __init__(
        self,
        default_response: str = "",
        responses: list[str] | None = None,
        latency_ms: int = 10,
        fail_after: int | None = None,
    ):
        self.default_response = default_response or (
            "Based on the task analysis, here is my comprehensive response:\n\n"
            "1. The task has been thoroughly analyzed.\n"
            "2. Key findings are presented below.\n"
            "3. Recommendations follow.\n\n"
            "This response was generated by the KK V2 mock provider for testing."
        )
        self._responses = list(responses or [])
        self._call_index = 0
        self.latency_ms = latency_ms
        self.fail_after = fail_after
        self.stats = ProviderStats()
        self.call_log: list[dict[str, Any]] = []

    async def __call__(self, prompt: str, max_tokens: int = 4096) -> str:
        if self.fail_after is not None and self._call_index >= self.fail_after:
            self.stats.errors += 1
            raise RuntimeError(f"Mock provider: configured to fail after {self.fail_after} calls")

        # Simulate latency
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000)

        start = time.monotonic()

        # Pick response
        if self._call_index < len(self._responses):
            response = self._responses[self._call_index]
        else:
            response = self.default_response

        self._call_index += 1

        # Estimate tokens
        input_tokens = len(prompt.split()) * 4 // 3  # rough tokenizer
        output_tokens = len(response.split()) * 4 // 3
        latency = int((time.monotonic() - start) * 1000) + self.latency_ms

        metrics = LLMCallMetrics(
            model="mock",
            backend="mock",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=0.0,
            latency_ms=latency,
        )
        self._record(metrics)

        self.call_log.append({
            "index": self._call_index - 1,
            "prompt_length": len(prompt),
            "max_tokens": max_tokens,
            "response_length": len(response),
        })

        return response

    def _record(self, metrics: LLMCallMetrics) -> None:
        self.stats.total_calls += 1
        self.stats.total_input_tokens += metrics.input_tokens
        self.stats.total_output_tokens += metrics.output_tokens
        self.stats.total_latency_ms += metrics.latency_ms
        self.stats.calls.append(metrics)


# ═══════════════════════════════════════════════════════════════════
# Adaptive Provider (auto-selects model by complexity)
# ═══════════════════════════════════════════════════════════════════


class AdaptiveProvider:
    """Wraps a base provider and selects the model dynamically.

    For cheap tasks (short prompt, simple instructions) → use cheap model.
    For complex tasks (long prompt, multi-step) → use powerful model.
    This saves cost while maintaining quality where it matters.
    """

    def __init__(
        self,
        backend: Backend = Backend.OPENAI,
        api_key: str | None = None,
        cheap_threshold_tokens: int = 500,
        powerful_threshold_tokens: int = 3000,
        system_prompt: str = "",
    ):
        self.backend = backend
        self.cheap_threshold = cheap_threshold_tokens
        self.powerful_threshold = powerful_threshold_tokens
        self.stats = ProviderStats()

        # Create providers for each tier
        self._providers: dict[str, Any] = {}
        for tier in ("cheap", "balanced", "powerful"):
            model = TIER_MODELS[tier][backend.value]
            if backend == Backend.ANTHROPIC:
                self._providers[tier] = AnthropicProvider(
                    model=model, api_key=api_key, system_prompt=system_prompt
                )
            elif backend == Backend.OPENAI:
                self._providers[tier] = OpenAIProvider(
                    model=model, api_key=api_key, system_prompt=system_prompt
                )

    def _select_tier(self, prompt: str) -> str:
        """Select model tier based on prompt complexity."""
        est_tokens = len(prompt.split()) * 4 // 3

        if est_tokens < self.cheap_threshold:
            return "cheap"
        elif est_tokens > self.powerful_threshold:
            return "powerful"
        return "balanced"

    async def __call__(self, prompt: str, max_tokens: int = 4096) -> str:
        tier = self._select_tier(prompt)
        provider = self._providers[tier]
        logger.debug(f"Adaptive: selected {tier} tier for {len(prompt)} char prompt")

        result = await provider(prompt, max_tokens)

        # Aggregate stats
        if provider.stats.calls:
            latest = provider.stats.calls[-1]
            self.stats.total_calls += 1
            self.stats.total_input_tokens += latest.input_tokens
            self.stats.total_output_tokens += latest.output_tokens
            self.stats.total_cost_usd += latest.cost_usd
            self.stats.total_latency_ms += latest.latency_ms
            self.stats.calls.append(latest)

        return result


# ═══════════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════════


def create_provider(
    backend: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    adaptive: bool = False,
    system_prompt: str = "",
    **kwargs,
) -> Any:
    """Create an LLM provider from configuration.

    Auto-detects backend from available API keys if not specified.

    Args:
        backend: "anthropic", "openai", or "mock". Auto-detect if None.
        model: Specific model name. Uses tier defaults if None.
        api_key: API key override.
        adaptive: Use AdaptiveProvider for auto model selection.
        system_prompt: Custom system prompt.
        **kwargs: Passed to provider constructor.

    Returns:
        An LLM provider implementing the __call__ protocol.
    """
    # Auto-detect backend
    if backend is None:
        if os.environ.get("ANTHROPIC_API_KEY"):
            backend = "anthropic"
        elif os.environ.get("OPENAI_API_KEY"):
            backend = "openai"
        else:
            logger.warning("No API keys found, using mock provider")
            backend = "mock"

    backend_enum = Backend(backend)

    if adaptive and backend_enum != Backend.MOCK:
        return AdaptiveProvider(
            backend=backend_enum,
            api_key=api_key,
            system_prompt=system_prompt,
            **kwargs,
        )

    if backend_enum == Backend.ANTHROPIC:
        return AnthropicProvider(
            model=model or "claude-sonnet-4-20250514",
            api_key=api_key,
            system_prompt=system_prompt,
            **kwargs,
        )
    elif backend_enum == Backend.OPENAI:
        return OpenAIProvider(
            model=model or "gpt-4o-mini",
            api_key=api_key,
            system_prompt=system_prompt,
            **kwargs,
        )
    else:
        return MockProvider(**kwargs)
