# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
Block Assembler for memory context management (ADR-003 Phase 2).

This module assembles context from multiple memory blocks to provide
structured context for LLM consumption within token budget constraints.

The 5-Block Layout:
1. System Block: Core instructions, persona
2. Project Block: Current project context, conventions
3. Task Block: Active task, goals, constraints
4. History Block: Compressed conversation history
5. Knowledge Block: Retrieved ADRs, incidents, code

Related GitHub Issues:
- #116: Phase 2: Memory Blocks Architecture

ADR Reference: ADR-003 Memory Architecture, Phase 2 (Context Engineering)
"""

from datetime import datetime, timezone
from typing import Any, Optional

from src.memory.blocks.compressor import HistoryCompressor
from src.memory.blocks.schemas import (
    DEFAULT_BLOCK_PRIORITIES,
    DEFAULT_TOKEN_BUDGETS,
    BlockType,
    MemoryBlock,
    Provenance,
)


class BlockAssembler:
    """
    Assembles context from multiple memory blocks within token budget.

    Provides structured context management by assembling content from
    five distinct block types, each with its own token budget and priority.
    """

    def __init__(
        self,
        token_budget: int = 5000,
        block_budgets: Optional[dict[BlockType, int]] = None,
    ) -> None:
        """
        Initialize the block assembler.

        Args:
            token_budget: Total token budget for all blocks
            block_budgets: Optional custom budgets per block type
        """
        self.token_budget = token_budget
        self.block_budgets = block_budgets or DEFAULT_TOKEN_BUDGETS.copy()
        self._compressor = HistoryCompressor()

    def _count_tokens(self, text: str) -> int:
        """
        Count tokens in text using the compressor's method.

        Args:
            text: Text to count tokens for

        Returns:
            Approximate token count
        """
        return self._compressor.count_tokens(text)

    async def build_system_block(self) -> MemoryBlock:
        """
        Build static system instructions block.

        Returns:
            MemoryBlock with system instructions
        """
        content = (
            "You are a helpful AI assistant with access to memory systems. "
            "Use the provided context to give relevant and personalized responses."
        )

        # Ensure content fits within budget, preserving formatting
        budget = self.block_budgets[BlockType.SYSTEM]
        token_count = self._count_tokens(content)

        if token_count > budget:
            content = self._truncate_preserving_format(content, budget)
            token_count = self._count_tokens(content)

        return MemoryBlock(
            block_type=BlockType.SYSTEM,
            content=content,
            token_count=token_count,
            priority=DEFAULT_BLOCK_PRIORITIES[BlockType.SYSTEM],
            metadata={},
        )

    async def build_project_block(self, user_id: str) -> MemoryBlock:
        """
        Build project context from metadata.

        Args:
            user_id: User ID for project context lookup

        Returns:
            MemoryBlock with project context
        """
        # In production, this would fetch project metadata
        # For now, create a placeholder
        content = f"Project context for user {user_id}."

        token_count = self._count_tokens(content)

        return MemoryBlock(
            block_type=BlockType.PROJECT,
            content=content,
            token_count=token_count,
            priority=DEFAULT_BLOCK_PRIORITIES[BlockType.PROJECT],
            metadata={"user_id": user_id},
        )

    async def build_task_block(self, task_context: str) -> MemoryBlock:
        """
        Build active task block.

        Args:
            task_context: Description of current task

        Returns:
            MemoryBlock with task context
        """
        content = task_context
        token_count = self._count_tokens(content)

        # Ensure content fits within budget, preserving formatting
        budget = self.block_budgets[BlockType.TASK]
        if token_count > budget:
            content = self._truncate_preserving_format(content, budget)
            token_count = self._count_tokens(content)

        return MemoryBlock(
            block_type=BlockType.TASK,
            content=content,
            token_count=token_count,
            priority=DEFAULT_BLOCK_PRIORITIES[BlockType.TASK],
            metadata={"original_length": len(task_context)},
        )

    async def build_history_block(
        self,
        conversation_history: list[Any],
    ) -> MemoryBlock:
        """
        Build compressed history block.

        Args:
            conversation_history: List of conversation messages

        Returns:
            MemoryBlock with compressed history
        """
        if not conversation_history:
            return MemoryBlock(
                block_type=BlockType.HISTORY,
                content="",
                token_count=0,
                priority=DEFAULT_BLOCK_PRIORITIES[BlockType.HISTORY],
                metadata={"message_count": 0},
            )

        budget = self.block_budgets[BlockType.HISTORY]
        compressor = HistoryCompressor(max_tokens=budget)
        content = compressor.compress(conversation_history)
        token_count = self._count_tokens(content)

        return MemoryBlock(
            block_type=BlockType.HISTORY,
            content=content,
            token_count=token_count,
            priority=DEFAULT_BLOCK_PRIORITIES[BlockType.HISTORY],
            metadata={"message_count": len(conversation_history)},
        )

    async def build_knowledge_block(
        self,
        user_id: str,
        query: str,
    ) -> MemoryBlock:
        """
        Build retrieved knowledge block with provenance.

        Args:
            user_id: User ID for memory retrieval
            query: Search query for relevant knowledge

        Returns:
            MemoryBlock with retrieved knowledge and provenance
        """
        if not query:
            return MemoryBlock(
                block_type=BlockType.KNOWLEDGE,
                content="",
                token_count=0,
                priority=DEFAULT_BLOCK_PRIORITIES[BlockType.KNOWLEDGE],
                metadata={"user_id": user_id, "query": query},
            )

        # In production, this would retrieve from memory system
        # For now, create a placeholder that tracks the query
        content = f"Retrieved knowledge for query: {query}"
        token_count = self._count_tokens(content)

        # Create provenance for the knowledge block (ADR-003 Phase 2 requirement)
        provenance = Provenance(
            source_id=f"knowledge:{user_id}:{query[:50]}",
            source_type="knowledge_retrieval",
            confidence=1.0,
            created_at=datetime.now(timezone.utc),
            retrieval_score=1.0,  # Placeholder score
        )

        return MemoryBlock(
            block_type=BlockType.KNOWLEDGE,
            content=content,
            token_count=token_count,
            priority=DEFAULT_BLOCK_PRIORITIES[BlockType.KNOWLEDGE],
            metadata={"user_id": user_id, "query": query, "retrieval_count": 0},
            provenance=provenance,
        )

    async def assemble(
        self,
        user_id: str,
        task_context: Optional[str] = None,
        conversation_history: Optional[list[Any]] = None,
        query: Optional[str] = None,
    ) -> list[MemoryBlock]:
        """
        Assemble context from all blocks within token budget.

        Args:
            user_id: User ID for personalized context
            task_context: Optional current task description
            conversation_history: Optional conversation messages
            query: Optional search query for knowledge retrieval

        Returns:
            List of MemoryBlocks sorted by priority
        """
        blocks = []

        # Build all blocks
        system_block = await self.build_system_block()
        blocks.append(system_block)

        project_block = await self.build_project_block(user_id)
        blocks.append(project_block)

        if task_context is not None:
            task_block = await self.build_task_block(task_context)
            blocks.append(task_block)
        else:
            # Empty task block
            blocks.append(
                MemoryBlock(
                    block_type=BlockType.TASK,
                    content="",
                    token_count=0,
                    priority=DEFAULT_BLOCK_PRIORITIES[BlockType.TASK],
                    metadata={},
                )
            )

        history_block = await self.build_history_block(conversation_history or [])
        blocks.append(history_block)

        knowledge_block = await self.build_knowledge_block(user_id, query or "")
        blocks.append(knowledge_block)

        # Sort by priority (lower number = higher priority)
        blocks.sort(key=lambda b: b.priority)

        # Ensure total is within budget
        total_tokens = sum(b.token_count for b in blocks)
        if total_tokens > self.token_budget:
            # Trim lower priority blocks first
            blocks = self._trim_to_budget(blocks)

        return blocks

    def _trim_to_budget(self, blocks: list[MemoryBlock]) -> list[MemoryBlock]:
        """
        Trim blocks to fit within total token budget.

        Trims lower priority blocks first. Preserves line structure
        by truncating at line boundaries when possible.

        Args:
            blocks: List of blocks sorted by priority

        Returns:
            List of blocks within budget
        """
        # Start from highest priority, accumulate until budget reached
        result = []
        remaining_budget = self.token_budget

        for block in blocks:
            if block.token_count <= remaining_budget:
                result.append(block)
                remaining_budget -= block.token_count
            elif remaining_budget > 0:
                # Partial inclusion - truncate by lines to preserve formatting
                truncated_content = self._truncate_preserving_format(
                    block.content, remaining_budget
                )
                truncated_tokens = self._count_tokens(truncated_content)

                result.append(
                    MemoryBlock(
                        block_type=block.block_type,
                        content=truncated_content,
                        token_count=truncated_tokens,
                        priority=block.priority,
                        metadata={**block.metadata, "truncated": True},
                        provenance=block.provenance,
                    )
                )
                remaining_budget = 0

        return result

    def _truncate_preserving_format(self, content: str, max_tokens: int) -> str:
        """
        Truncate content while preserving line structure and formatting.

        Truncates at line boundaries when possible to avoid breaking
        code blocks, lists, or structured text.

        Args:
            content: Content to truncate
            max_tokens: Maximum token budget

        Returns:
            Truncated content with formatting preserved
        """
        if not content:
            return ""

        # Try line-by-line truncation first
        lines = content.split("\n")
        result_lines = []
        current_tokens = 0

        for line in lines:
            line_tokens = self._count_tokens(line + "\n")
            if current_tokens + line_tokens <= max_tokens:
                result_lines.append(line)
                current_tokens += line_tokens
            else:
                # Add truncation marker
                if result_lines:
                    result_lines.append("... [truncated]")
                break

        if result_lines:
            return "\n".join(result_lines)

        # Fallback: word truncation if even first line is too long
        words = content.split()
        max_words = int(max_tokens / 1.3)
        return " ".join(words[:max_words]) + " ... [truncated]"

    def _escape_xml_content(self, content: str) -> str:
        """
        Escape content to prevent XML injection attacks.

        Escapes characters that could break XML structure or enable
        prompt injection attacks.

        Args:
            content: Raw content to escape

        Returns:
            Escaped content safe for XML embedding
        """
        if not content:
            return ""

        # Replace XML special characters
        escaped = content
        escaped = escaped.replace("&", "&amp;")
        escaped = escaped.replace("<", "&lt;")
        escaped = escaped.replace(">", "&gt;")

        return escaped

    def to_prompt(self, blocks: list[MemoryBlock]) -> str:
        """
        Convert blocks to a formatted prompt string with delimiters.

        Uses XML-style delimiters for clear block separation.
        Content is escaped to prevent prompt injection attacks.

        Args:
            blocks: List of MemoryBlocks to format

        Returns:
            Formatted prompt string with block delimiters
        """
        if not blocks:
            return ""

        sections = []
        for block in blocks:
            if block.content:
                # Escape content to prevent XML injection
                escaped_content = self._escape_xml_content(block.content)
                # Use XML-style delimiters for security and clarity
                block_name = block.block_type.value.upper()
                section = (
                    f"<{block_name}_CONTEXT>\n"
                    f"{escaped_content}\n"
                    f"</{block_name}_CONTEXT>"
                )
                sections.append(section)

        return "\n\n".join(sections)
