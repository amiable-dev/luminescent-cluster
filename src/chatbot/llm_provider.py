# Copyright 2024-2025 Amiable Development
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
LLM Provider abstraction for Luminescent Cluster chatbot.

This module provides a unified interface for interacting with various LLM
providers (OpenAI, Ollama, and other OpenAI-compatible APIs) with built-in
resilience patterns.

Design Principles (from ADR-006):
1. LLM Agnostic - OpenAI-compatible API for provider flexibility
2. Local-first - Support for Ollama/local models
3. Resilient - Circuit breaker pattern for fault tolerance

Version: 1.0.0
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional, Any
import time
import asyncio
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# Circuit Breaker Implementation
# =============================================================================


class CircuitState(Enum):
    """State of the circuit breaker."""

    CLOSED = auto()  # Normal operation, requests allowed
    OPEN = auto()  # Failures exceeded threshold, requests blocked
    HALF_OPEN = auto()  # Testing if service recovered


@dataclass
class CircuitBreaker:
    """
    Circuit breaker pattern implementation for fault tolerance.

    The circuit breaker prevents cascading failures by stopping requests
    to a failing service and allowing it time to recover.

    States:
        CLOSED: Normal operation, all requests pass through
        OPEN: Service failing, all requests rejected immediately
        HALF_OPEN: Testing recovery, one request allowed through

    Attributes:
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before testing recovery
        failure_count: Current consecutive failure count
        state: Current circuit state
        last_failure_time: Timestamp of last failure
    """

    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    failure_count: int = field(default=0, init=False)
    state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    last_failure_time: Optional[float] = field(default=None, init=False)

    def allow_request(self) -> bool:
        """
        Check if a request should be allowed.

        Returns:
            True if request should proceed, False if circuit is open.
        """
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self.last_failure_time is not None:
                elapsed = time.time() - self.last_failure_time
                if elapsed >= self.recovery_timeout:
                    # Transition to HALF_OPEN
                    self.state = CircuitState.HALF_OPEN
                    return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            # Allow one request to test recovery
            return True

        return False

    def record_success(self) -> None:
        """Record a successful request."""
        if self.state == CircuitState.HALF_OPEN:
            # Recovery successful, close circuit
            self.state = CircuitState.CLOSED

        # Reset failure count
        self.failure_count = 0

    def record_failure(self) -> None:
        """Record a failed request."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            # Recovery failed, reopen circuit
            self.state = CircuitState.OPEN

        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker opened after {self.failure_count} failures"
                )


# =============================================================================
# LLM Configuration and Response Models
# =============================================================================


@dataclass
class LLMConfig:
    """
    Configuration for LLM provider.

    Attributes:
        provider: Provider name (openai, ollama, anthropic, etc.)
        api_key: API key for authentication (optional for local providers)
        base_url: Base URL for API requests
        model: Model name to use
        temperature: Sampling temperature (0.0 to 2.0)
        max_tokens: Maximum tokens in response
        timeout: Request timeout in seconds
        circuit_breaker_enabled: Enable circuit breaker pattern
        circuit_breaker_threshold: Failures before opening circuit
        circuit_breaker_timeout: Recovery timeout in seconds
    """

    provider: str
    api_key: Optional[str] = None
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    timeout: float = 60.0
    circuit_breaker_enabled: bool = True
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout: float = 30.0

    def __post_init__(self):
        """Set provider-specific defaults."""
        if self.provider == "ollama" and self.base_url == "https://api.openai.com/v1":
            self.base_url = "http://localhost:11434"


@dataclass
class LLMResponse:
    """
    Normalized response from LLM provider.

    Attributes:
        content: Response text content
        model: Model that generated the response
        tokens_used: Total tokens used (prompt + completion)
        finish_reason: Why generation stopped (stop, length, etc.)
        prompt_tokens: Tokens used for prompt (optional)
        completion_tokens: Tokens used for completion (optional)
        latency_ms: Request latency in milliseconds (optional)
        metadata: Additional provider-specific metadata (optional)
    """

    content: str
    model: str
    tokens_used: int
    finish_reason: str
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    latency_ms: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMCapabilities:
    """
    Capabilities of an LLM model.

    Attributes:
        supports_vision: Can process images
        supports_function_calling: Can call functions/tools
        supports_streaming: Supports streaming responses
        max_context_tokens: Maximum context window size
        max_output_tokens: Maximum output tokens
    """

    supports_vision: bool = False
    supports_function_calling: bool = False
    supports_streaming: bool = True
    max_context_tokens: int = 4096
    max_output_tokens: int = 4096


# =============================================================================
# Model Capability Database
# =============================================================================

# Known model capabilities (OpenAI models)
MODEL_CAPABILITIES = {
    # GPT-4o family
    "gpt-4o": LLMCapabilities(
        supports_vision=True,
        supports_function_calling=True,
        supports_streaming=True,
        max_context_tokens=128000,
        max_output_tokens=16384,
    ),
    "gpt-4o-mini": LLMCapabilities(
        supports_vision=True,
        supports_function_calling=True,
        supports_streaming=True,
        max_context_tokens=128000,
        max_output_tokens=16384,
    ),
    # GPT-4 family
    "gpt-4-turbo": LLMCapabilities(
        supports_vision=True,
        supports_function_calling=True,
        supports_streaming=True,
        max_context_tokens=128000,
        max_output_tokens=4096,
    ),
    "gpt-4": LLMCapabilities(
        supports_vision=False,
        supports_function_calling=True,
        supports_streaming=True,
        max_context_tokens=8192,
        max_output_tokens=4096,
    ),
    # GPT-3.5 family
    "gpt-3.5-turbo": LLMCapabilities(
        supports_vision=False,
        supports_function_calling=True,
        supports_streaming=True,
        max_context_tokens=16385,
        max_output_tokens=4096,
    ),
    # Claude models (via OpenAI-compatible API)
    "claude-3-opus": LLMCapabilities(
        supports_vision=True,
        supports_function_calling=True,
        supports_streaming=True,
        max_context_tokens=200000,
        max_output_tokens=4096,
    ),
    "claude-3-sonnet": LLMCapabilities(
        supports_vision=True,
        supports_function_calling=True,
        supports_streaming=True,
        max_context_tokens=200000,
        max_output_tokens=4096,
    ),
}

# Default capabilities for unknown models
DEFAULT_CAPABILITIES = LLMCapabilities(
    supports_vision=False,
    supports_function_calling=False,
    supports_streaming=True,
    max_context_tokens=4096,
    max_output_tokens=4096,
)


# =============================================================================
# LLM Provider Implementation
# =============================================================================


class LLMProvider:
    """
    Unified LLM provider with support for multiple backends.

    Supports:
        - OpenAI API (and compatible APIs)
        - Ollama (local models)
        - Any OpenAI-compatible endpoint

    Features:
        - Automatic capability detection
        - Circuit breaker for fault tolerance
        - Request/response normalization

    Example:
        config = LLMConfig(
            provider="openai",
            api_key="sk-...",
            model="gpt-4o-mini",
        )
        provider = LLMProvider(config)

        response = await provider.chat(
            messages=[{"role": "user", "content": "Hello!"}]
        )
        print(response.content)
    """

    def __init__(self, config: LLMConfig):
        """
        Initialize LLM provider.

        Args:
            config: LLM configuration
        """
        self.config = config
        self._capabilities_cache: Optional[LLMCapabilities] = None

        # Initialize circuit breaker if enabled
        if config.circuit_breaker_enabled:
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=config.circuit_breaker_threshold,
                recovery_timeout=config.circuit_breaker_timeout,
            )
        else:
            self.circuit_breaker = None

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs,
    ) -> LLMResponse:
        """
        Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Override config temperature
            max_tokens: Override config max_tokens
            **kwargs: Additional provider-specific parameters

        Returns:
            LLMResponse with generated content

        Raises:
            Exception: If circuit breaker is open or request fails
        """
        # Check circuit breaker
        if self.circuit_breaker and not self.circuit_breaker.allow_request():
            raise Exception("Circuit breaker open: LLM service unavailable")

        start_time = time.time()

        try:
            # Build request parameters
            request_params = {
                "messages": messages,
                "model": self.config.model,
                "temperature": temperature or self.config.temperature,
            }

            if max_tokens or self.config.max_tokens:
                request_params["max_tokens"] = max_tokens or self.config.max_tokens

            request_params.update(kwargs)

            # Make the request
            raw_response = await self._make_request(**request_params)

            # Parse response
            choice = raw_response["choices"][0]
            usage = raw_response.get("usage", {})

            response = LLMResponse(
                content=choice["message"]["content"],
                model=raw_response.get("model", self.config.model),
                tokens_used=usage.get("total_tokens", 0),
                finish_reason=choice.get("finish_reason", "stop"),
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                latency_ms=(time.time() - start_time) * 1000,
            )

            # Record success
            if self.circuit_breaker:
                self.circuit_breaker.record_success()

            return response

        except Exception as e:
            # Record failure
            if self.circuit_breaker:
                self.circuit_breaker.record_failure()
            raise

    async def _make_request(self, **kwargs) -> dict:
        """
        Make HTTP request to LLM API.

        This method should be overridden or mocked in tests.

        Args:
            **kwargs: Request parameters

        Returns:
            Raw API response dict
        """
        # In production, this would use httpx or aiohttp
        # For now, this is a placeholder that tests can mock
        import httpx

        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        url = f"{self.config.base_url}/chat/completions"

        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.post(url, json=kwargs, headers=headers)
            response.raise_for_status()
            return response.json()

    async def get_capabilities(self) -> LLMCapabilities:
        """
        Get capabilities of the configured model.

        Capabilities are cached after first detection.

        Returns:
            LLMCapabilities for the model
        """
        if self._capabilities_cache is not None:
            return self._capabilities_cache

        self._capabilities_cache = await self._detect_capabilities()
        return self._capabilities_cache

    async def _detect_capabilities(self) -> LLMCapabilities:
        """
        Detect model capabilities.

        Returns:
            LLMCapabilities for the model
        """
        model = self.config.model

        # Check known models first
        if model in MODEL_CAPABILITIES:
            return MODEL_CAPABILITIES[model]

        # Check for model family prefixes
        for known_model, caps in MODEL_CAPABILITIES.items():
            if model.startswith(known_model):
                return caps

        # For Ollama, try to fetch model info
        if self.config.provider == "ollama":
            try:
                info = await self._fetch_model_info()
                return LLMCapabilities(
                    supports_vision=False,
                    supports_function_calling=False,
                    supports_streaming=True,
                    max_context_tokens=info.get("context_length", 4096),
                    max_output_tokens=4096,
                )
            except Exception:
                pass

        return DEFAULT_CAPABILITIES

    async def _fetch_model_info(self) -> dict:
        """
        Fetch model info from Ollama.

        Returns:
            Model info dict
        """
        import httpx

        url = f"{self.config.base_url}/api/show"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json={"name": self.config.model})
            response.raise_for_status()
            return response.json()

    async def list_models(self) -> list[str]:
        """
        List available models (Ollama only).

        Returns:
            List of model names
        """
        return await self._list_models()

    async def _list_models(self) -> list[str]:
        """
        List available models from provider.

        Returns:
            List of model names
        """
        if self.config.provider != "ollama":
            raise NotImplementedError("list_models only supported for Ollama")

        import httpx

        url = f"{self.config.base_url}/api/tags"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            return [m["name"] for m in data.get("models", [])]
