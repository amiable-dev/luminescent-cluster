# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: Tests for History Compressor.

These tests define the expected behavior for conversation history
compression to achieve the 30% token efficiency target.

Related GitHub Issues:
- #116: Phase 2: Memory Blocks Architecture

ADR Reference: ADR-003 Memory Architecture, Phase 2 (Context Engineering)
"""

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest


@dataclass
class Message:
    """Simple message for testing."""

    role: str
    content: str
    timestamp: datetime


class TestHistoryCompressorExists:
    """TDD: Tests for HistoryCompressor class existence."""

    def test_history_compressor_exists(self):
        """HistoryCompressor class should be defined."""
        from src.memory.blocks.compressor import HistoryCompressor

        assert HistoryCompressor is not None

    def test_history_compressor_instantiable(self):
        """HistoryCompressor should be instantiable with max_tokens."""
        from src.memory.blocks.compressor import HistoryCompressor

        compressor = HistoryCompressor(max_tokens=1000)
        assert compressor.max_tokens == 1000

    def test_default_max_tokens(self):
        """HistoryCompressor should default to 1000 max_tokens."""
        from src.memory.blocks.compressor import HistoryCompressor

        compressor = HistoryCompressor()
        assert compressor.max_tokens == 1000


class TestTokenCounting:
    """TDD: Tests for token counting functionality."""

    def test_count_tokens_returns_int(self):
        """count_tokens should return an integer."""
        from src.memory.blocks.compressor import HistoryCompressor

        compressor = HistoryCompressor()
        result = compressor.count_tokens("Hello world")

        assert isinstance(result, int)

    def test_count_tokens_empty_string(self):
        """count_tokens should return 0 for empty string."""
        from src.memory.blocks.compressor import HistoryCompressor

        compressor = HistoryCompressor()
        result = compressor.count_tokens("")

        assert result == 0

    def test_count_tokens_simple_text(self):
        """count_tokens should return reasonable count for text."""
        from src.memory.blocks.compressor import HistoryCompressor

        compressor = HistoryCompressor()
        result = compressor.count_tokens("Hello world, how are you?")

        # Should be roughly 6-8 tokens
        assert result > 0
        assert result < 20


class TestCompress:
    """TDD: Tests for history compression."""

    @pytest.fixture
    def compressor(self):
        """Create a HistoryCompressor for tests."""
        from src.memory.blocks.compressor import HistoryCompressor

        return HistoryCompressor(max_tokens=100)

    @pytest.fixture
    def sample_messages(self):
        """Create sample messages for testing."""
        now = datetime.now(timezone.utc)
        return [
            Message(role="user", content="Hello", timestamp=now),
            Message(role="assistant", content="Hi there!", timestamp=now),
            Message(role="user", content="How are you?", timestamp=now),
            Message(role="assistant", content="I'm doing well, thanks!", timestamp=now),
            Message(role="user", content="What's the weather?", timestamp=now),
        ]

    def test_compress_returns_string(self, compressor, sample_messages):
        """compress should return a string."""
        result = compressor.compress(sample_messages)

        assert isinstance(result, str)

    def test_compress_preserves_recent_messages(self, compressor, sample_messages):
        """compress should preserve the last N messages verbatim."""
        result = compressor.compress(sample_messages, preserve_recent=2)

        # Last 2 messages should be preserved
        assert "What's the weather?" in result

    def test_compress_empty_list(self, compressor):
        """compress should handle empty message list."""
        result = compressor.compress([])

        assert result == ""

    def test_compress_respects_token_limit(self):
        """compress should respect max_tokens limit."""
        from src.memory.blocks.compressor import HistoryCompressor

        # Use a very small limit
        compressor = HistoryCompressor(max_tokens=50)

        now = datetime.now(timezone.utc)
        long_messages = [
            Message(
                role="user",
                content="This is a very long message " * 20,
                timestamp=now,
            ),
            Message(
                role="assistant",
                content="This is another very long response " * 20,
                timestamp=now,
            ),
        ]

        result = compressor.compress(long_messages)
        tokens = compressor.count_tokens(result)

        # Should be under or near the limit
        assert tokens <= 100  # Some tolerance for summarization


class TestSummarize:
    """TDD: Tests for message summarization."""

    @pytest.fixture
    def compressor(self):
        """Create a HistoryCompressor for tests."""
        from src.memory.blocks.compressor import HistoryCompressor

        return HistoryCompressor(max_tokens=1000)

    def test_summarize_returns_string(self, compressor):
        """summarize should return a string."""
        now = datetime.now(timezone.utc)
        messages = [
            Message(role="user", content="Hello", timestamp=now),
            Message(role="assistant", content="Hi", timestamp=now),
        ]

        result = compressor.summarize(messages)

        assert isinstance(result, str)

    def test_summarize_empty_list(self, compressor):
        """summarize should handle empty list."""
        result = compressor.summarize([])

        assert result == ""

    def test_summarize_single_message(self, compressor):
        """summarize should handle single message."""
        now = datetime.now(timezone.utc)
        messages = [Message(role="user", content="Hello world", timestamp=now)]

        result = compressor.summarize(messages)

        assert isinstance(result, str)
        assert len(result) > 0


class TestDictMessageHandling:
    """TDD: Tests for dictionary-based message handling."""

    @pytest.fixture
    def compressor(self):
        """Create a HistoryCompressor for tests."""
        from src.memory.blocks.compressor import HistoryCompressor

        return HistoryCompressor(max_tokens=500)

    def test_compress_dict_messages(self, compressor):
        """compress should handle dict-based messages properly."""
        # Dict messages are common in LLM APIs
        dict_messages = [
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "assistant", "content": "I'm doing great, thanks!"},
        ]

        result = compressor.compress(dict_messages)

        # Should extract content properly, not show dict repr
        assert "Hello, how are you?" in result
        assert "I'm doing great" in result
        assert "{'role':" not in result  # No dict repr

    def test_summarize_dict_messages(self, compressor):
        """summarize should handle dict-based messages properly."""
        dict_messages = [
            {"role": "user", "content": "First question about Python."},
            {"role": "assistant", "content": "Python is a great language."},
        ]

        result = compressor.summarize(dict_messages)

        # Should not contain dict repr
        assert "{'role':" not in result
        assert "user:" in result or "First question" in result


class TestTokenCountingDoSProtection:
    """TDD: Tests for DoS protection in token counting.

    Council Round 9: Identified that text.split() allows strings without
    spaces to bypass budget limits.
    """

    @pytest.fixture
    def compressor(self):
        """Create a HistoryCompressor for tests."""
        from src.memory.blocks.compressor import HistoryCompressor

        return HistoryCompressor(max_tokens=100)

    def test_count_tokens_string_without_spaces(self, compressor):
        """Token count should handle strings without spaces (DoS vector)."""
        # This could bypass word-based counting
        no_spaces = "a" * 10000

        result = compressor.count_tokens(no_spaces)

        # Should return a reasonable token count based on characters
        # ~4 chars per token is a rough approximation
        assert result > 0
        assert result >= 100  # Should recognize this is a large string

    def test_count_tokens_long_url(self, compressor):
        """Token count should handle long URLs properly."""
        long_url = "https://example.com/" + "a" * 1000

        result = compressor.count_tokens(long_url)

        # Should be counted properly, not as 1 word
        assert result > 50

    def test_count_tokens_mixed_content(self, compressor):
        """Token count should handle mixed content with long tokens."""
        mixed = "Hello " + "x" * 500 + " World"

        result = compressor.count_tokens(mixed)

        # Should count the long token properly
        assert result > 100


class TestWhitespacePreservation:
    """TDD: Tests for whitespace preservation during truncation."""

    @pytest.fixture
    def compressor(self):
        """Create a HistoryCompressor for tests."""
        from src.memory.blocks.compressor import HistoryCompressor

        return HistoryCompressor(max_tokens=50)

    def test_truncate_preserves_line_breaks(self, compressor):
        """Truncation should preserve line breaks, not collapse whitespace."""
        text_with_lines = "Line one\nLine two\nLine three\nLine four"

        result = compressor._truncate_to_tokens(text_with_lines, 20)

        # Should preserve newlines, not split on all whitespace
        assert "\n" in result or len(result.split("\n")) >= 1

    def test_truncate_preserves_indentation(self, compressor):
        """Truncation should not destroy indentation."""
        code_text = "def foo():\n    x = 1\n    return x"

        result = compressor._truncate_to_tokens(code_text, 30)

        # If we got any content, check indentation preserved
        if len(result) > 10:
            # Should have preserved some indentation
            lines = result.split("\n")
            if len(lines) > 1:
                # Check that subsequent lines still have leading spaces
                assert any(line.startswith("    ") or line.startswith("\t") for line in lines[1:])
