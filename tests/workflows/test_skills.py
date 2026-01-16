# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""
TDD: Tests for Agent Skills (ADR-002 Phase 3).

These tests verify that the Agent Skills conform to the SKILL.md specification:
- Proper YAML frontmatter with required fields
- Markdown body with workflow instructions
- Correct directory structure

Related: ADR-002 Workflow Integration, Phase 3 (Skills)
Agent Skills Specification: https://agentskills.io/specification
"""

import re
from pathlib import Path

import pytest
import yaml


class TestSkillDirectoryStructure:
    """TDD: Tests for skill directory structure."""

    def test_claude_skills_directory_exists(self):
        """skills directory should exist in .claude.

        ADR Reference: ADR-002 Phase 3 (Skills)
        """
        skills_dir = Path(__file__).parent.parent.parent / ".claude" / "skills"
        assert skills_dir.exists(), f"Skills directory not found at {skills_dir}"

    def test_session_init_skill_directory_exists(self):
        """session-init skill directory should exist.

        ADR Reference: ADR-002 Phase 3 (Skills)
        """
        skill_dir = Path(__file__).parent.parent.parent / ".claude" / "skills" / "session-init"
        assert skill_dir.exists(), f"session-init directory not found at {skill_dir}"

    def test_session_save_skill_directory_exists(self):
        """session-save skill directory should exist.

        ADR Reference: ADR-002 Phase 3 (Skills)
        """
        skill_dir = Path(__file__).parent.parent.parent / ".claude" / "skills" / "session-save"
        assert skill_dir.exists(), f"session-save directory not found at {skill_dir}"

    def test_session_init_skill_md_exists(self):
        """session-init/SKILL.md should exist.

        ADR Reference: ADR-002 Phase 3 (Skills)
        """
        skill_md = Path(__file__).parent.parent.parent / ".claude" / "skills" / "session-init" / "SKILL.md"
        assert skill_md.exists(), f"SKILL.md not found at {skill_md}"

    def test_session_save_skill_md_exists(self):
        """session-save/SKILL.md should exist.

        ADR Reference: ADR-002 Phase 3 (Skills)
        """
        skill_md = Path(__file__).parent.parent.parent / ".claude" / "skills" / "session-save" / "SKILL.md"
        assert skill_md.exists(), f"SKILL.md not found at {skill_md}"


class TestSessionInitSkill:
    """TDD: Tests for session-init skill content."""

    @pytest.fixture
    def skill_content(self):
        """Load session-init SKILL.md content."""
        skill_md = Path(__file__).parent.parent.parent / ".claude" / "skills" / "session-init" / "SKILL.md"
        return skill_md.read_text()

    @pytest.fixture
    def skill_frontmatter(self, skill_content):
        """Parse YAML frontmatter from skill."""
        # Extract content between --- markers
        match = re.match(r'^---\n(.*?)\n---', skill_content, re.DOTALL)
        if match:
            return yaml.safe_load(match.group(1))
        return {}

    def test_has_yaml_frontmatter(self, skill_content):
        """session-init should have YAML frontmatter.

        ADR Reference: ADR-002 Phase 3 (Skills)
        Agent Skills Spec: Required
        """
        assert skill_content.startswith("---"), "SKILL.md should start with YAML frontmatter"

    def test_has_name_field(self, skill_frontmatter):
        """session-init frontmatter should have name field.

        ADR Reference: ADR-002 Phase 3 (Skills)
        Agent Skills Spec: Required
        """
        assert "name" in skill_frontmatter, "Frontmatter should have 'name' field"
        assert skill_frontmatter["name"] == "session-init", "Name should be 'session-init'"

    def test_has_description_field(self, skill_frontmatter):
        """session-init frontmatter should have description field.

        ADR Reference: ADR-002 Phase 3 (Skills)
        Agent Skills Spec: Required
        """
        assert "description" in skill_frontmatter, "Frontmatter should have 'description' field"
        assert len(skill_frontmatter["description"]) > 10, "Description should be meaningful"

    def test_has_version_field(self, skill_frontmatter):
        """session-init frontmatter should have version field.

        ADR Reference: ADR-002 Phase 3 (Skills)
        """
        assert "version" in skill_frontmatter, "Frontmatter should have 'version' field"

    def test_has_compatibility_field(self, skill_frontmatter):
        """session-init frontmatter should have compatibility field.

        ADR Reference: ADR-002 Phase 3 (Skills)
        """
        assert "compatibility" in skill_frontmatter, "Frontmatter should have 'compatibility' field"

    def test_requires_session_memory_mcp(self, skill_frontmatter):
        """session-init should require session-memory MCP.

        ADR Reference: ADR-002 Phase 3 (Skills)
        """
        compat = skill_frontmatter.get("compatibility", [])
        mcp_servers = [c.get("mcp") for c in compat if isinstance(c, dict)]
        assert "session-memory" in mcp_servers, "Should require session-memory MCP"

    def test_requires_pixeltable_memory_mcp(self, skill_frontmatter):
        """session-init should require pixeltable-memory MCP.

        ADR Reference: ADR-002 Phase 3 (Skills)
        """
        compat = skill_frontmatter.get("compatibility", [])
        mcp_servers = [c.get("mcp") for c in compat if isinstance(c, dict)]
        assert "pixeltable-memory" in mcp_servers, "Should require pixeltable-memory MCP"

    def test_has_workflow_instructions(self, skill_content):
        """session-init should have workflow instructions in body.

        ADR Reference: ADR-002 Phase 3 (Skills)
        """
        # Should have sections
        assert "## " in skill_content, "Should have markdown sections"

    def test_mentions_freshness_check(self, skill_content):
        """session-init should check KB freshness.

        ADR Reference: ADR-002 Phase 3 (Skills)
        """
        assert "last_ingest_sha" in skill_content, "Should check last_ingest_sha"

    def test_mentions_task_context(self, skill_content):
        """session-init should reference task context.

        ADR Reference: ADR-002 Phase 3 (Skills)
        """
        assert "get_task_context" in skill_content, "Should reference get_task_context"

    def test_has_output_format(self, skill_content):
        """session-init should define output format.

        ADR Reference: ADR-002 Phase 3 (Skills)
        """
        assert "Output Format" in skill_content, "Should define output format"


class TestSessionSaveSkill:
    """TDD: Tests for session-save skill content."""

    @pytest.fixture
    def skill_content(self):
        """Load session-save SKILL.md content."""
        skill_md = Path(__file__).parent.parent.parent / ".claude" / "skills" / "session-save" / "SKILL.md"
        return skill_md.read_text()

    @pytest.fixture
    def skill_frontmatter(self, skill_content):
        """Parse YAML frontmatter from skill."""
        match = re.match(r'^---\n(.*?)\n---', skill_content, re.DOTALL)
        if match:
            return yaml.safe_load(match.group(1))
        return {}

    def test_has_yaml_frontmatter(self, skill_content):
        """session-save should have YAML frontmatter.

        ADR Reference: ADR-002 Phase 3 (Skills)
        Agent Skills Spec: Required
        """
        assert skill_content.startswith("---"), "SKILL.md should start with YAML frontmatter"

    def test_has_name_field(self, skill_frontmatter):
        """session-save frontmatter should have name field.

        ADR Reference: ADR-002 Phase 3 (Skills)
        Agent Skills Spec: Required
        """
        assert "name" in skill_frontmatter, "Frontmatter should have 'name' field"
        assert skill_frontmatter["name"] == "session-save", "Name should be 'session-save'"

    def test_has_description_field(self, skill_frontmatter):
        """session-save frontmatter should have description field.

        ADR Reference: ADR-002 Phase 3 (Skills)
        Agent Skills Spec: Required
        """
        assert "description" in skill_frontmatter, "Frontmatter should have 'description' field"
        assert len(skill_frontmatter["description"]) > 10, "Description should be meaningful"

    def test_requires_session_memory_mcp(self, skill_frontmatter):
        """session-save should require session-memory MCP.

        ADR Reference: ADR-002 Phase 3 (Skills)
        """
        compat = skill_frontmatter.get("compatibility", [])
        mcp_servers = [c.get("mcp") for c in compat if isinstance(c, dict)]
        assert "session-memory" in mcp_servers, "Should require session-memory MCP"

    def test_mentions_set_task_context(self, skill_content):
        """session-save should reference set_task_context.

        ADR Reference: ADR-002 Phase 3 (Skills)
        """
        assert "set_task_context" in skill_content, "Should reference set_task_context"

    def test_mentions_git_status(self, skill_content):
        """session-save should check git status.

        ADR Reference: ADR-002 Phase 3 (Skills)
        """
        assert "git status" in skill_content, "Should check git status"

    def test_has_output_format(self, skill_content):
        """session-save should define output format.

        ADR Reference: ADR-002 Phase 3 (Skills)
        """
        assert "Output Format" in skill_content, "Should define output format"
