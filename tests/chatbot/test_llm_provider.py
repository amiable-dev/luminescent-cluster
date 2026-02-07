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
TDD: RED Phase - Tests for LLM Provider abstraction.

These tests define the expected behavior for the LLM provider before
implementation. They should FAIL until the provider is implemented.

Related GitHub Issues:
- #19: Test LLM provider with OpenAI-compatible API
- #20: Test LLM provider with Ollama local models
- #21: Implement LLMProvider class
- #22: Test LLM capability detection
- #23: Implement capability detection
- #24: Test circuit breaker for LLM failures
- #25: Implement circuit breaker pattern

ADR Reference: ADR-006 Chatbot Platform Integrations
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from typing import Optional, AsyncIterator

# Import the LLM provider - this will fail until implemented (RED phase)
from luminescent_cluster.chatbot.llm_provider import (
    LLMProvider,
    LLMConfig,
    LLMResponse,
    LLMCapabilities,
    CircuitBreaker,
    CircuitState,
)


class TestLLMConfig:
    """TDD: Tests for LLMConfig data model."""

    def test_config_with_openai_defaults(self):
        """LLMConfig should work with OpenAI defaults."""
        config = LLMConfig(
            provider="openai",
            api_key="sk-test-key",
        )

        assert config.provider == "openai"
        assert config.api_key == "sk-test-key"
        assert config.base_url == "https://api.openai.com/v1"
        assert config.model == "gpt-4o-mini"

    def test_config_with_custom_base_url(self):
        """LLMConfig should support custom base URLs for compatible APIs."""
        config = LLMConfig(
            provider="openai",
            api_key="key",
            base_url="https://api.custom-llm.com/v1",
            model="custom-model",
        )

        assert config.base_url == "https://api.custom-llm.com/v1"
        assert config.model == "custom-model"

    def test_config_for_ollama(self):
        """LLMConfig should work for Ollama local models."""
        config = LLMConfig(
            provider="ollama",
            base_url="http://localhost:11434",
            model="llama3.2",
        )

        assert config.provider == "ollama"
        assert config.base_url == "http://localhost:11434"
        assert config.model == "llama3.2"
        assert config.api_key is None  # Ollama doesn't need API key

    def test_config_optional_parameters(self):
        """LLMConfig should support optional parameters."""
        config = LLMConfig(
            provider="openai",
            api_key="key",
            temperature=0.7,
            max_tokens=1000,
            timeout=30.0,
        )

        assert config.temperature == 0.7
        assert config.max_tokens == 1000
        assert config.timeout == 30.0


class TestLLMResponse:
    """TDD: Tests for LLMResponse data model."""

    def test_response_has_required_fields(self):
        """LLMResponse should have all required fields."""
        response = LLMResponse(
            content="Hello, how can I help?",
            model="gpt-4o-mini",
            tokens_used=25,
            finish_reason="stop",
        )

        assert response.content == "Hello, how can I help?"
        assert response.model == "gpt-4o-mini"
        assert response.tokens_used == 25
        assert response.finish_reason == "stop"

    def test_response_optional_fields(self):
        """LLMResponse should support optional fields."""
        response = LLMResponse(
            content="Response",
            model="gpt-4",
            tokens_used=100,
            finish_reason="stop",
            prompt_tokens=50,
            completion_tokens=50,
            latency_ms=245.5,
            metadata={"request_id": "req-123"},
        )

        assert response.prompt_tokens == 50
        assert response.completion_tokens == 50
        assert response.latency_ms == 245.5
        assert response.metadata["request_id"] == "req-123"


class TestLLMProviderOpenAI:
    """TDD: Tests for LLM provider with OpenAI-compatible API (Issue #19)."""

    @pytest.fixture
    def openai_config(self):
        """Create OpenAI config for testing."""
        return LLMConfig(
            provider="openai",
            api_key="sk-test-key",
            model="gpt-4o-mini",
        )

    @pytest.mark.asyncio
    async def test_create_provider_with_openai_config(self, openai_config):
        """Should create provider with OpenAI configuration."""
        provider = LLMProvider(openai_config)

        assert provider.config.provider == "openai"
        assert provider.config.model == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_chat_completion_basic(self, openai_config):
        """Should make basic chat completion request."""
        provider = LLMProvider(openai_config)

        with patch.object(provider, "_make_request") as mock_request:
            mock_request.return_value = {
                "choices": [{"message": {"content": "Hello!"}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 20, "prompt_tokens": 10, "completion_tokens": 10},
                "model": "gpt-4o-mini",
            }

            response = await provider.chat(messages=[{"role": "user", "content": "Hi"}])

            assert response.content == "Hello!"
            assert response.tokens_used == 20

    @pytest.mark.asyncio
    async def test_chat_with_system_message(self, openai_config):
        """Should support system messages."""
        provider = LLMProvider(openai_config)

        with patch.object(provider, "_make_request") as mock_request:
            mock_request.return_value = {
                "choices": [{"message": {"content": "I am helpful"}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 30},
                "model": "gpt-4o-mini",
            }

            response = await provider.chat(
                messages=[
                    {"role": "system", "content": "You are helpful"},
                    {"role": "user", "content": "Who are you?"},
                ]
            )

            assert response.content == "I am helpful"
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert len(call_args[1]["messages"]) == 2

    @pytest.mark.asyncio
    async def test_chat_with_temperature(self, openai_config):
        """Should pass temperature parameter."""
        provider = LLMProvider(openai_config)

        with patch.object(provider, "_make_request") as mock_request:
            mock_request.return_value = {
                "choices": [{"message": {"content": "Response"}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 10},
                "model": "gpt-4o-mini",
            }

            await provider.chat(
                messages=[{"role": "user", "content": "Hi"}],
                temperature=0.5,
            )

            call_args = mock_request.call_args
            assert call_args[1]["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_chat_handles_api_error(self, openai_config):
        """Should handle API errors gracefully."""
        provider = LLMProvider(openai_config)

        with patch.object(provider, "_make_request") as mock_request:
            mock_request.side_effect = Exception("API Error: Rate limited")

            with pytest.raises(Exception, match="API Error"):
                await provider.chat(messages=[{"role": "user", "content": "Hi"}])


class TestLLMProviderOllama:
    """TDD: Tests for LLM provider with Ollama local models (Issue #20)."""

    @pytest.fixture
    def ollama_config(self):
        """Create Ollama config for testing."""
        return LLMConfig(
            provider="ollama",
            base_url="http://localhost:11434",
            model="llama3.2",
        )

    @pytest.mark.asyncio
    async def test_create_provider_with_ollama_config(self, ollama_config):
        """Should create provider with Ollama configuration."""
        provider = LLMProvider(ollama_config)

        assert provider.config.provider == "ollama"
        assert provider.config.model == "llama3.2"
        assert "localhost:11434" in provider.config.base_url

    @pytest.mark.asyncio
    async def test_ollama_chat_completion(self, ollama_config):
        """Should make chat completion request to Ollama."""
        provider = LLMProvider(ollama_config)

        with patch.object(provider, "_make_request") as mock_request:
            # Ollama uses slightly different response format
            mock_request.return_value = {
                "choices": [{"message": {"content": "Hello from Llama!"}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 15},
                "model": "llama3.2",
            }

            response = await provider.chat(messages=[{"role": "user", "content": "Hi"}])

            assert response.content == "Hello from Llama!"
            assert response.model == "llama3.2"

    @pytest.mark.asyncio
    async def test_ollama_no_api_key_required(self, ollama_config):
        """Ollama should not require API key."""
        provider = LLMProvider(ollama_config)

        # Should not raise even without API key
        assert provider.config.api_key is None

    @pytest.mark.asyncio
    async def test_ollama_connection_error(self, ollama_config):
        """Should handle Ollama connection errors."""
        provider = LLMProvider(ollama_config)

        with patch.object(provider, "_make_request") as mock_request:
            mock_request.side_effect = ConnectionError("Connection refused")

            with pytest.raises(ConnectionError):
                await provider.chat(messages=[{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_list_ollama_models(self, ollama_config):
        """Should list available Ollama models."""
        provider = LLMProvider(ollama_config)

        with patch.object(provider, "_list_models") as mock_list:
            mock_list.return_value = ["llama3.2", "codellama", "mistral"]

            models = await provider.list_models()

            assert "llama3.2" in models
            assert len(models) == 3


class TestLLMCapabilities:
    """TDD: Tests for LLM capability detection (Issue #22)."""

    def test_capabilities_data_model(self):
        """LLMCapabilities should have expected fields."""
        caps = LLMCapabilities(
            supports_vision=True,
            supports_function_calling=True,
            supports_streaming=True,
            max_context_tokens=128000,
            max_output_tokens=4096,
        )

        assert caps.supports_vision is True
        assert caps.supports_function_calling is True
        assert caps.max_context_tokens == 128000

    @pytest.mark.asyncio
    async def test_detect_gpt4_capabilities(self):
        """Should detect GPT-4 capabilities."""
        config = LLMConfig(provider="openai", api_key="key", model="gpt-4o")
        provider = LLMProvider(config)

        caps = await provider.get_capabilities()

        assert caps.supports_vision is True
        assert caps.supports_function_calling is True
        assert caps.max_context_tokens >= 128000

    @pytest.mark.asyncio
    async def test_detect_gpt35_capabilities(self):
        """Should detect GPT-3.5 capabilities."""
        config = LLMConfig(provider="openai", api_key="key", model="gpt-3.5-turbo")
        provider = LLMProvider(config)

        caps = await provider.get_capabilities()

        assert caps.supports_vision is False
        assert caps.supports_function_calling is True

    @pytest.mark.asyncio
    async def test_detect_ollama_capabilities(self):
        """Should detect Ollama model capabilities."""
        config = LLMConfig(provider="ollama", base_url="http://localhost:11434", model="llama3.2")
        provider = LLMProvider(config)

        with patch.object(provider, "_fetch_model_info") as mock_info:
            mock_info.return_value = {
                "parameters": "8B",
                "context_length": 8192,
            }

            caps = await provider.get_capabilities()

            assert caps.max_context_tokens == 8192

    @pytest.mark.asyncio
    async def test_capabilities_cached(self):
        """Capabilities should be cached after first fetch."""
        config = LLMConfig(provider="openai", api_key="key", model="gpt-4o")
        provider = LLMProvider(config)

        with patch.object(provider, "_detect_capabilities") as mock_detect:
            mock_detect.return_value = LLMCapabilities(
                supports_vision=True,
                supports_function_calling=True,
                supports_streaming=True,
                max_context_tokens=128000,
                max_output_tokens=4096,
            )

            # First call
            await provider.get_capabilities()
            # Second call should use cache
            await provider.get_capabilities()

            # Should only detect once
            assert mock_detect.call_count == 1


class TestCircuitBreaker:
    """TDD: Tests for circuit breaker pattern (Issue #24)."""

    def test_circuit_starts_closed(self):
        """Circuit breaker should start in CLOSED state."""
        breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=30.0,
        )

        assert breaker.state == CircuitState.CLOSED

    def test_circuit_opens_after_failures(self):
        """Circuit should open after reaching failure threshold."""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)

        # Record failures
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED

        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

    def test_circuit_rejects_when_open(self):
        """Circuit should reject calls when OPEN."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=30.0)

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Should reject
        assert breaker.allow_request() is False

    def test_circuit_allows_when_closed(self):
        """Circuit should allow calls when CLOSED."""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)

        assert breaker.allow_request() is True

    def test_circuit_half_open_after_timeout(self):
        """Circuit should become HALF_OPEN after recovery timeout."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        import time

        time.sleep(0.15)

        # Should transition to HALF_OPEN on next check
        assert breaker.allow_request() is True
        assert breaker.state == CircuitState.HALF_OPEN

    def test_circuit_closes_on_success_in_half_open(self):
        """Circuit should close on success in HALF_OPEN state."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        breaker.record_failure()
        import time

        time.sleep(0.15)

        # Transition to HALF_OPEN
        breaker.allow_request()
        assert breaker.state == CircuitState.HALF_OPEN

        # Record success
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED

    def test_circuit_reopens_on_failure_in_half_open(self):
        """Circuit should reopen on failure in HALF_OPEN state."""
        breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)

        breaker.record_failure()
        import time

        time.sleep(0.15)

        # Transition to HALF_OPEN
        breaker.allow_request()
        assert breaker.state == CircuitState.HALF_OPEN

        # Another failure
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

    def test_success_resets_failure_count(self):
        """Success should reset failure count in CLOSED state."""
        breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)

        breaker.record_failure()
        breaker.record_failure()
        assert breaker.failure_count == 2

        breaker.record_success()
        assert breaker.failure_count == 0


class TestLLMProviderWithCircuitBreaker:
    """TDD: Tests for LLM provider with circuit breaker integration (Issue #25)."""

    @pytest.fixture
    def config_with_breaker(self):
        """Create config with circuit breaker enabled."""
        return LLMConfig(
            provider="openai",
            api_key="key",
            model="gpt-4o-mini",
            circuit_breaker_enabled=True,
            circuit_breaker_threshold=3,
            circuit_breaker_timeout=30.0,
        )

    @pytest.mark.asyncio
    async def test_provider_has_circuit_breaker(self, config_with_breaker):
        """Provider should have circuit breaker when enabled."""
        provider = LLMProvider(config_with_breaker)

        assert provider.circuit_breaker is not None
        assert provider.circuit_breaker.failure_threshold == 3

    @pytest.mark.asyncio
    async def test_provider_opens_circuit_on_failures(self, config_with_breaker):
        """Provider should open circuit after failures."""
        provider = LLMProvider(config_with_breaker)

        with patch.object(provider, "_make_request") as mock_request:
            mock_request.side_effect = Exception("API Error")

            # Fail 3 times
            for _ in range(3):
                try:
                    await provider.chat(messages=[{"role": "user", "content": "Hi"}])
                except Exception:
                    pass

            assert provider.circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_provider_rejects_when_circuit_open(self, config_with_breaker):
        """Provider should reject requests when circuit is open."""
        provider = LLMProvider(config_with_breaker)

        # Manually open circuit
        for _ in range(3):
            provider.circuit_breaker.record_failure()

        with pytest.raises(Exception, match="Circuit breaker open"):
            await provider.chat(messages=[{"role": "user", "content": "Hi"}])

    @pytest.mark.asyncio
    async def test_provider_resets_circuit_on_success(self, config_with_breaker):
        """Provider should reset circuit on successful request."""
        provider = LLMProvider(config_with_breaker)

        # Record some failures (not enough to open)
        provider.circuit_breaker.record_failure()
        provider.circuit_breaker.record_failure()

        with patch.object(provider, "_make_request") as mock_request:
            mock_request.return_value = {
                "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 10},
                "model": "gpt-4o-mini",
            }

            await provider.chat(messages=[{"role": "user", "content": "Hi"}])

            assert provider.circuit_breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_provider_without_circuit_breaker(self):
        """Provider should work without circuit breaker."""
        config = LLMConfig(
            provider="openai",
            api_key="key",
            model="gpt-4o-mini",
            circuit_breaker_enabled=False,
        )
        provider = LLMProvider(config)

        assert provider.circuit_breaker is None

        with patch.object(provider, "_make_request") as mock_request:
            mock_request.return_value = {
                "choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
                "usage": {"total_tokens": 10},
                "model": "gpt-4o-mini",
            }

            response = await provider.chat(messages=[{"role": "user", "content": "Hi"}])
            assert response.content == "OK"


class TestLLMProviderStreaming:
    """TDD: Tests for batched/pseudo-streaming (V1 per ADR-006)."""

    @pytest.fixture
    def streaming_config(self):
        """Create config for streaming tests."""
        return LLMConfig(
            provider="openai",
            api_key="key",
            model="gpt-4o-mini",
        )

    @pytest.mark.asyncio
    async def test_chat_with_batched_response(self, streaming_config):
        """V1: Should support batched responses (pseudo-streaming)."""
        provider = LLMProvider(streaming_config)

        with patch.object(provider, "_make_request") as mock_request:
            # Full response (batched, not true streaming)
            mock_request.return_value = {
                "choices": [
                    {
                        "message": {"content": "This is a complete response."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"total_tokens": 20},
                "model": "gpt-4o-mini",
            }

            response = await provider.chat(
                messages=[{"role": "user", "content": "Tell me something"}],
            )

            # V1: Returns complete response
            assert "complete response" in response.content

    @pytest.mark.asyncio
    async def test_chat_respects_max_tokens(self, streaming_config):
        """Should respect max_tokens limit."""
        provider = LLMProvider(streaming_config)

        with patch.object(provider, "_make_request") as mock_request:
            mock_request.return_value = {
                "choices": [{"message": {"content": "Short"}, "finish_reason": "length"}],
                "usage": {"total_tokens": 50},
                "model": "gpt-4o-mini",
            }

            response = await provider.chat(
                messages=[{"role": "user", "content": "Write a long essay"}],
                max_tokens=50,
            )

            assert response.finish_reason == "length"
            call_args = mock_request.call_args
            assert call_args[1]["max_tokens"] == 50
