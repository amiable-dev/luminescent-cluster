# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
History Compressor for token efficiency (ADR-003 Phase 2).

This module provides conversation history compression to achieve the
30% token efficiency improvement target.

Compression strategies:
1. Preserve recent N messages verbatim
2. Summarize older messages
3. Respect token budget limits

Related GitHub Issues:
- #116: Phase 2: Memory Blocks Architecture

ADR Reference: ADR-003 Memory Architecture, Phase 2 (Context Engineering)
"""

from typing import Any, Protocol


class Message(Protocol):
    """Protocol for message objects."""

    role: str
    content: str


class HistoryCompressor:
    """
    Compresses conversation history to fit within token budget.

    Preserves recent messages verbatim while summarizing older messages
    to achieve token efficiency without losing important context.
    """

    def __init__(self, max_tokens: int = 1000) -> None:
        """
        Initialize the history compressor.

        Args:
            max_tokens: Maximum tokens for compressed history
        """
        self.max_tokens = max_tokens

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.

        Uses a simple word-based approximation. For production,
        use tiktoken with the actual model's tokenizer.

        Args:
            text: Text to count tokens for

        Returns:
            Approximate token count
        """
        if not text:
            return 0

        # Simple approximation: ~1.3 tokens per word on average
        words = text.split()
        return int(len(words) * 1.3)

    def compress(
        self,
        messages: list[Any],
        preserve_recent: int = 3,
    ) -> str:
        """
        Compress conversation history to fit token budget.

        Args:
            messages: List of message objects with role and content
            preserve_recent: Number of recent messages to preserve verbatim

        Returns:
            Compressed conversation history as string
        """
        if not messages:
            return ""

        # Split into old and recent messages
        if len(messages) <= preserve_recent:
            # All messages fit in "recent" - format and truncate if needed
            formatted = self._format_messages(messages)
            if self.count_tokens(formatted) <= self.max_tokens:
                return formatted
            return self._truncate_to_tokens(formatted, self.max_tokens)

        old_messages = messages[:-preserve_recent]
        recent_messages = messages[-preserve_recent:]

        # Format recent messages first
        recent_text = self._format_messages(recent_messages)
        recent_tokens = self.count_tokens(recent_text)

        # If recent alone exceeds budget, truncate recent and skip summary
        if recent_tokens >= self.max_tokens:
            return self._truncate_to_tokens(recent_text, self.max_tokens)

        # Calculate remaining budget for summary
        summary_budget = self.max_tokens - recent_tokens - 10  # 10 token overhead

        if summary_budget <= 10:
            # No room for summary
            return recent_text

        # Summarize old messages
        summary = self.summarize(old_messages)

        # Truncate summary to fit budget
        summary = self._truncate_to_tokens(summary, summary_budget)

        if summary:
            return f"[Summary: {summary}]\n\n{recent_text}"
        return recent_text

    def summarize(self, messages: list[Any]) -> str:
        """
        Generate a summary of messages.

        For production, this could use an LLM for better summaries.
        This implementation uses a simple extraction approach.

        Args:
            messages: Messages to summarize

        Returns:
            Summary string
        """
        if not messages:
            return ""

        # Simple summarization: extract key points
        points = []
        for msg in messages:
            content = getattr(msg, "content", str(msg))
            role = getattr(msg, "role", "unknown")

            # Extract first sentence or first 50 chars
            first_sentence = content.split(".")[0]
            if len(first_sentence) > 50:
                first_sentence = first_sentence[:50]

            points.append(f"{role}: {first_sentence}")

        return "; ".join(points)

    def _format_messages(self, messages: list[Any]) -> str:
        """Format messages as readable text."""
        lines = []
        for msg in messages:
            content = getattr(msg, "content", str(msg))
            role = getattr(msg, "role", "unknown")
            lines.append(f"{role}: {content}")
        return "\n".join(lines)

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within token budget."""
        words = text.split()
        max_words = int(max_tokens / 1.3)  # Reverse the token approximation

        if len(words) <= max_words:
            return text

        return " ".join(words[:max_words])
