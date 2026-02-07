"""
Skills module for agent skills integration.

Provides progressive disclosure loading for agent skills:
- Level 1: Metadata only (~100-200 tokens)
- Level 2: Full SKILL.md content
- Level 3: Resources on demand
"""

from luminescent_cluster.skills.loader import (
    DEFAULT_SEARCH_PATHS,
    REFERENCES_DIR,
    SKILL_FILENAME,
    SkillError,
    SkillFull,
    SkillLoader,
    SkillMetadata,
    SkillNotFoundError,
    SkillParseError,
    load_skill_full,
    load_skill_metadata,
    load_skill_resource,
)

__all__ = [
    # Constants
    "SKILL_FILENAME",
    "REFERENCES_DIR",
    "DEFAULT_SEARCH_PATHS",
    # Exceptions
    "SkillError",
    "SkillNotFoundError",
    "SkillParseError",
    # Data classes
    "SkillMetadata",
    "SkillFull",
    # Functions
    "load_skill_metadata",
    "load_skill_full",
    "load_skill_resource",
    # Loader class
    "SkillLoader",
]
