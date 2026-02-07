"""
Tests for skills module: progressive disclosure loader, bundled skills, and CLI.

Progressive disclosure levels:
1. Metadata only (~100-200 tokens) - YAML frontmatter
2. Full SKILL.md content (~500-1000 tokens)
3. Resources on demand - files from references/ directory
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from luminescent_cluster.skills.loader import (
    SkillLoader,
    SkillMetadata,
    SkillNotFoundError,
    SkillParseError,
    load_skill_full,
    load_skill_metadata,
    load_skill_resource,
)


# Test fixtures
SAMPLE_SKILL_MD = """---
name: test-skill
description: |
  A test skill for unit testing.
  Keywords: test, example, demo

license: MIT
compatibility: "luminescent-cluster >= 0.4.0"
metadata:
  category: testing
  domain: development
  author: test-author

allowed-tools: "Read Grep Glob mcp:session-memory/test"
---

# Test Skill

This is the full content of the test skill.

## Usage

Use this skill for testing purposes.

## Example

```bash
test-skill --verbose
```
"""

SAMPLE_SKILL_MINIMAL = """---
name: minimal-skill
description: Minimal skill with required fields only.
---

# Minimal Skill

Basic content.
"""


class TestSkillMetadata:
    """Tests for SkillMetadata dataclass."""

    def test_metadata_has_required_fields(self):
        metadata = SkillMetadata(
            name="test",
            description="Test description",
        )
        assert metadata.name == "test"
        assert metadata.description == "Test description"

    def test_metadata_has_optional_fields(self):
        metadata = SkillMetadata(
            name="test",
            description="Test description",
            license="MIT",
            compatibility="luminescent-cluster >= 0.4.0",
            allowed_tools=["Read", "Grep"],
            category="testing",
            domain="development",
            author="test-author",
        )
        assert metadata.license == "MIT"
        assert metadata.compatibility == "luminescent-cluster >= 0.4.0"
        assert metadata.allowed_tools == ["Read", "Grep"]
        assert metadata.category == "testing"

    def test_metadata_token_estimate(self):
        metadata = SkillMetadata(
            name="test-skill",
            description="A test skill for unit testing.\nKeywords: test, example",
        )
        assert 10 <= metadata.estimated_tokens <= 50


class TestLoadSkillMetadata:
    """Tests for Level 1: Metadata extraction."""

    def test_load_metadata_from_string(self):
        metadata = load_skill_metadata(SAMPLE_SKILL_MD)
        assert metadata.name == "test-skill"
        assert "test skill" in metadata.description.lower()
        assert metadata.license == "MIT"

    def test_load_metadata_extracts_allowed_tools(self):
        metadata = load_skill_metadata(SAMPLE_SKILL_MD)
        assert "Read" in metadata.allowed_tools
        assert "Grep" in metadata.allowed_tools
        assert "mcp:session-memory/test" in metadata.allowed_tools

    def test_load_metadata_extracts_nested_metadata(self):
        metadata = load_skill_metadata(SAMPLE_SKILL_MD)
        assert metadata.category == "testing"
        assert metadata.domain == "development"
        assert metadata.author == "test-author"

    def test_load_metadata_handles_minimal_skill(self):
        metadata = load_skill_metadata(SAMPLE_SKILL_MINIMAL)
        assert metadata.name == "minimal-skill"
        assert "Minimal skill" in metadata.description
        assert metadata.license is None
        assert metadata.allowed_tools == []

    def test_load_metadata_raises_on_missing_frontmatter(self):
        with pytest.raises(SkillParseError) as exc_info:
            load_skill_metadata("# No frontmatter\n\nJust content.")
        assert "frontmatter" in str(exc_info.value).lower()

    def test_load_metadata_raises_on_missing_name(self):
        invalid_skill = """---
description: Missing name field.
---
# Content
"""
        with pytest.raises(SkillParseError) as exc_info:
            load_skill_metadata(invalid_skill)
        assert "name" in str(exc_info.value).lower()

    def test_load_metadata_raises_on_missing_description(self):
        invalid_skill = """---
name: no-desc
---
# Content
"""
        with pytest.raises(SkillParseError) as exc_info:
            load_skill_metadata(invalid_skill)
        assert "description" in str(exc_info.value).lower()


class TestLoadSkillFull:
    """Tests for Level 2: Full SKILL.md loading."""

    def test_load_full_returns_complete_content(self):
        result = load_skill_full(SAMPLE_SKILL_MD)
        assert result.metadata.name == "test-skill"
        assert "# Test Skill" in result.body
        assert "## Usage" in result.body
        assert "## Example" in result.body

    def test_load_full_separates_metadata_and_body(self):
        result = load_skill_full(SAMPLE_SKILL_MD)
        assert "---" not in result.body.strip()[:10]
        assert "name:" not in result.body

    def test_load_full_preserves_code_blocks(self):
        result = load_skill_full(SAMPLE_SKILL_MD)
        assert "```bash" in result.body
        assert "test-skill --verbose" in result.body

    def test_load_full_estimates_body_tokens(self):
        result = load_skill_full(SAMPLE_SKILL_MD)
        assert result.estimated_tokens > result.metadata.estimated_tokens
        assert result.estimated_tokens < 2000


class TestSkillLoader:
    """Tests for SkillLoader class."""

    @pytest.fixture
    def skill_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_path = Path(tmpdir) / ".claude" / "skills"

            # Create test-skill
            test_skill_dir = skills_path / "test-skill"
            test_skill_dir.mkdir(parents=True)
            (test_skill_dir / "SKILL.md").write_text(SAMPLE_SKILL_MD)

            # Create references
            refs_dir = test_skill_dir / "references"
            refs_dir.mkdir()
            (refs_dir / "rubrics.md").write_text("# Rubrics\n\nTest rubric content.")
            (refs_dir / "examples.md").write_text("# Examples\n\nTest examples.")

            # Create minimal-skill
            minimal_dir = skills_path / "minimal-skill"
            minimal_dir.mkdir(parents=True)
            (minimal_dir / "SKILL.md").write_text(SAMPLE_SKILL_MINIMAL)

            yield skills_path

    def test_loader_discovers_skills(self, skill_dir: Path):
        loader = SkillLoader(skill_dir)
        skills = loader.list_skills()
        assert "test-skill" in skills
        assert "minimal-skill" in skills

    def test_loader_loads_metadata_level1(self, skill_dir: Path):
        loader = SkillLoader(skill_dir)
        metadata = loader.load_metadata("test-skill")
        assert metadata.name == "test-skill"
        assert metadata.category == "testing"

    def test_loader_loads_full_level2(self, skill_dir: Path):
        loader = SkillLoader(skill_dir)
        full = loader.load_full("test-skill")
        assert full.metadata.name == "test-skill"
        assert "# Test Skill" in full.body

    def test_loader_loads_resource_level3(self, skill_dir: Path):
        loader = SkillLoader(skill_dir)
        rubrics = loader.load_resource("test-skill", "rubrics.md")
        assert "# Rubrics" in rubrics
        assert "Test rubric content" in rubrics

    def test_loader_lists_resources(self, skill_dir: Path):
        loader = SkillLoader(skill_dir)
        resources = loader.list_resources("test-skill")
        assert "rubrics.md" in resources
        assert "examples.md" in resources

    def test_loader_raises_skill_not_found(self, skill_dir: Path):
        loader = SkillLoader(skill_dir)
        with pytest.raises(SkillNotFoundError):
            loader.load_metadata("nonexistent-skill")

    def test_loader_raises_resource_not_found(self, skill_dir: Path):
        loader = SkillLoader(skill_dir)
        with pytest.raises(SkillNotFoundError):
            loader.load_resource("test-skill", "nonexistent.md")

    def test_loader_handles_skill_without_resources(self, skill_dir: Path):
        loader = SkillLoader(skill_dir)
        resources = loader.list_resources("minimal-skill")
        assert resources == []

    def test_loader_handles_nonexistent_directory(self):
        loader = SkillLoader(Path("/nonexistent/path"))
        assert loader.list_skills() == []


class TestSkillLoaderSecurity:
    """Tests for path traversal protection."""

    @pytest.fixture
    def skill_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_path = Path(tmpdir) / "skills"
            test_dir = skills_path / "test-skill"
            test_dir.mkdir(parents=True)
            (test_dir / "SKILL.md").write_text(SAMPLE_SKILL_MINIMAL)
            yield skills_path

    def test_rejects_path_traversal_dots(self, skill_dir: Path):
        loader = SkillLoader(skill_dir)
        with pytest.raises(ValueError, match="Path traversal"):
            loader.load_metadata("../etc/passwd")

    def test_rejects_path_traversal_slash(self, skill_dir: Path):
        loader = SkillLoader(skill_dir)
        with pytest.raises(ValueError, match="Path traversal"):
            loader.load_metadata("foo/bar")

    def test_rejects_path_traversal_backslash(self, skill_dir: Path):
        loader = SkillLoader(skill_dir)
        with pytest.raises(ValueError, match="Path traversal"):
            loader.load_metadata("foo\\bar")

    def test_rejects_empty_name(self, skill_dir: Path):
        loader = SkillLoader(skill_dir)
        with pytest.raises(ValueError, match="empty"):
            loader.load_metadata("")

    def test_rejects_invalid_characters(self, skill_dir: Path):
        loader = SkillLoader(skill_dir)
        with pytest.raises(ValueError, match="Invalid skill name"):
            loader.load_metadata("UPPER_CASE")


class TestSkillLoaderCaching:
    """Tests for thread-safe caching."""

    @pytest.fixture
    def skill_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_path = Path(tmpdir) / "skills"
            test_dir = skills_path / "test-skill"
            test_dir.mkdir(parents=True)
            (test_dir / "SKILL.md").write_text(SAMPLE_SKILL_MD)
            yield skills_path

    def test_caches_metadata(self, skill_dir: Path):
        loader = SkillLoader(skill_dir)
        meta1 = loader.load_metadata("test-skill")
        meta2 = loader.load_metadata("test-skill")
        assert meta1 is meta2

    def test_invalidate_single_skill(self, skill_dir: Path):
        loader = SkillLoader(skill_dir)
        meta1 = loader.load_metadata("test-skill")
        loader.invalidate_cache("test-skill")
        meta2 = loader.load_metadata("test-skill")
        assert meta1 is not meta2
        assert meta1.name == meta2.name

    def test_invalidate_all(self, skill_dir: Path):
        loader = SkillLoader(skill_dir)
        loader.load_metadata("test-skill")
        loader.invalidate_cache()
        # Cache should be empty now
        assert loader._metadata_cache == {}


class TestLoadSkillResource:
    """Tests for Level 3: Resource loading."""

    def test_load_resource_from_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            resource_path = Path(tmpdir) / "test.md"
            resource_path.write_text("# Test Resource\n\nContent here.")
            content = load_skill_resource(resource_path)
            assert "# Test Resource" in content
            assert "Content here" in content

    def test_load_resource_raises_on_missing(self):
        with pytest.raises(SkillNotFoundError):
            load_skill_resource(Path("/nonexistent/path.md"))


class TestBundledSkillFormat:
    """Verify bundled SKILL.md files parse correctly."""

    @pytest.fixture
    def bundled_dir(self) -> Path:
        return Path(__file__).parent.parent / "src" / "luminescent_cluster" / "skills" / "bundled"

    def test_session_init_parses(self, bundled_dir: Path):
        content = (bundled_dir / "session-init" / "SKILL.md").read_text()
        metadata = load_skill_metadata(content)
        assert metadata.name == "session-init"
        assert metadata.category == "session-management"

    def test_session_save_parses(self, bundled_dir: Path):
        content = (bundled_dir / "session-save" / "SKILL.md").read_text()
        metadata = load_skill_metadata(content)
        assert metadata.name == "session-save"
        assert metadata.category == "session-management"

    def test_session_init_full_content(self, bundled_dir: Path):
        content = (bundled_dir / "session-init" / "SKILL.md").read_text()
        full = load_skill_full(content)
        assert "Environment Verification" in full.body
        assert "Context Loading" in full.body

    def test_session_save_full_content(self, bundled_dir: Path):
        content = (bundled_dir / "session-save" / "SKILL.md").read_text()
        full = load_skill_full(content)
        assert "Summarize Session" in full.body
        assert "Update Task Context" in full.body

    def test_bundled_loader_discovers_skills(self, bundled_dir: Path):
        loader = SkillLoader(bundled_dir)
        skills = loader.list_skills()
        assert "session-init" in skills
        assert "session-save" in skills

    def test_marketplace_json_exists(self, bundled_dir: Path):
        import json

        marketplace = bundled_dir / "marketplace.json"
        assert marketplace.exists()
        data = json.loads(marketplace.read_text())
        assert data["name"] == "luminescent-cluster-skills"
        skill_names = [s["name"] for s in data["skills"]]
        assert "session-init" in skill_names
        assert "session-save" in skill_names


class TestInstallSkillsCLI:
    """Tests for install-skills CLI command."""

    def test_install_skills_list(self, capsys):
        from luminescent_cluster.cli import install_skills

        install_skills(list_only=True)
        captured = capsys.readouterr()
        assert "session-init" in captured.out
        assert "session-save" in captured.out

    def test_install_skills_to_directory(self):
        from luminescent_cluster.cli import install_skills

        with tempfile.TemporaryDirectory() as tmpdir:
            target = str(Path(tmpdir) / "skills")
            install_skills(target=target)
            target_path = Path(target)
            assert (target_path / "session-init" / "SKILL.md").exists()
            assert (target_path / "session-save" / "SKILL.md").exists()
            assert (target_path / "marketplace.json").exists()

    def test_install_skills_skip_existing(self, capsys):
        from luminescent_cluster.cli import install_skills

        with tempfile.TemporaryDirectory() as tmpdir:
            target = str(Path(tmpdir) / "skills")
            # Install once
            install_skills(target=target)
            # Install again without force
            install_skills(target=target)
            captured = capsys.readouterr()
            assert "Skipped" in captured.out

    def test_install_skills_force_overwrite(self, capsys):
        from luminescent_cluster.cli import install_skills

        with tempfile.TemporaryDirectory() as tmpdir:
            target = str(Path(tmpdir) / "skills")
            # Install once
            install_skills(target=target)
            # Install again with force
            install_skills(target=target, force=True)
            captured = capsys.readouterr()
            assert "Installed" in captured.out
            assert "Skipped" not in captured.out


class TestProgressiveDisclosureIntegration:
    """Integration tests for progressive disclosure workflow."""

    @pytest.fixture
    def skill_dir(self) -> Path:
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_path = Path(tmpdir) / "skills"
            test_skill_dir = skills_path / "test-skill"
            test_skill_dir.mkdir(parents=True)
            (test_skill_dir / "SKILL.md").write_text(SAMPLE_SKILL_MD)

            refs_dir = test_skill_dir / "references"
            refs_dir.mkdir()
            (refs_dir / "detailed.md").write_text("# Detailed\n\n" + "x" * 1000)

            yield skills_path

    def test_progressive_loading_token_efficiency(self, skill_dir: Path):
        loader = SkillLoader(skill_dir)

        meta = loader.load_metadata("test-skill")
        level1_tokens = meta.estimated_tokens

        full = loader.load_full("test-skill")
        level2_tokens = full.estimated_tokens

        resource = loader.load_resource("test-skill", "detailed.md")
        level3_tokens = level2_tokens + len(resource) // 4

        assert level1_tokens < level2_tokens
        assert level2_tokens < level3_tokens
        assert level1_tokens < 300

    def test_load_all_levels_successively(self, skill_dir: Path):
        loader = SkillLoader(skill_dir)

        skills = loader.list_skills()
        assert len(skills) > 0

        skill_name = skills[0]
        meta = loader.load_metadata(skill_name)
        assert meta.name == skill_name

        full = loader.load_full(skill_name)
        assert full.body is not None

        resources = loader.list_resources(skill_name)
        if resources:
            content = loader.load_resource(skill_name, resources[0])
            assert len(content) > 0
