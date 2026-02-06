# Copyright 2024-2025 Amiable Development
# SPDX-License-Identifier: Apache-2.0

"""Query rewriting for improved recall.

Expands search terms to include synonyms and related terms.

Related GitHub Issues:
- #98: Query Rewriting

ADR Reference: ADR-003 Memory Architecture, Phase 1c (Retrieval & Ranking)
"""

from typing import List, Set


# Common programming synonyms for term expansion
DEFAULT_SYNONYMS: dict[str, List[str]] = {
    # Authentication
    "auth": ["authentication", "login", "signin", "authorization"],
    "authentication": ["auth", "login", "signin"],
    "login": ["auth", "authentication", "signin"],
    "oauth": ["auth", "authentication", "oauth2"],
    # Database
    "db": ["database", "storage", "datastore"],
    "database": ["db", "storage", "datastore"],
    "sql": ["database", "query", "relational"],
    "postgres": ["postgresql", "database", "sql"],
    "postgresql": ["postgres", "database", "sql"],
    "mysql": ["database", "sql", "relational"],
    "redis": ["cache", "database", "keyvalue"],
    "mongo": ["mongodb", "database", "nosql"],
    "mongodb": ["mongo", "database", "nosql"],
    # API
    "api": ["endpoint", "service", "interface"],
    "rest": ["api", "http", "restful"],
    "graphql": ["api", "query", "schema"],
    "grpc": ["api", "rpc", "protobuf"],
    # Languages
    "python": ["py", "python3"],
    "py": ["python", "python3"],
    "javascript": ["js", "node", "nodejs"],
    "js": ["javascript", "node", "nodejs"],
    "typescript": ["ts", "javascript"],
    "ts": ["typescript", "javascript"],
    # Frameworks
    "fastapi": ["python", "api", "async"],
    "django": ["python", "web", "framework"],
    "flask": ["python", "web", "framework"],
    "react": ["javascript", "frontend", "ui"],
    "vue": ["javascript", "frontend", "ui"],
    "express": ["node", "api", "backend"],
    # Infrastructure
    "docker": ["container", "containerization"],
    "kubernetes": ["k8s", "container", "orchestration"],
    "k8s": ["kubernetes", "container", "orchestration"],
    "aws": ["cloud", "amazon"],
    "gcp": ["cloud", "google"],
    "azure": ["cloud", "microsoft"],
    # Testing
    "test": ["testing", "unittest", "spec"],
    "pytest": ["test", "testing", "python"],
    "jest": ["test", "testing", "javascript"],
    # Version control
    "git": ["version", "vcs", "repo"],
    "github": ["git", "repo", "repository"],
    # General
    "config": ["configuration", "settings", "setup"],
    "env": ["environment", "config"],
    "async": ["asynchronous", "await", "concurrent"],
    "cache": ["caching", "redis", "memory"],
}


class QueryRewriter:
    """Rewrites queries for improved recall.

    Expands search terms to include synonyms and related terms
    to improve the chances of finding relevant memories.

    Attributes:
        synonyms: Dictionary mapping terms to their synonyms.

    Example:
        >>> rewriter = QueryRewriter()
        >>> expanded = rewriter.expand("auth")
        >>> print(expanded)
        ['auth', 'authentication', 'login', 'signin', 'authorization']
    """

    def __init__(self, synonyms: dict[str, List[str]] | None = None):
        """Initialize the query rewriter.

        Args:
            synonyms: Custom synonym mappings. Uses defaults if not provided.
        """
        self.synonyms = synonyms or DEFAULT_SYNONYMS

    def expand(self, term: str) -> List[str]:
        """Expand a single term to include synonyms.

        Args:
            term: Term to expand.

        Returns:
            List of terms including original and synonyms.
        """
        term_lower = term.lower()
        expanded: Set[str] = {term_lower}

        if term_lower in self.synonyms:
            expanded.update(self.synonyms[term_lower])

        return list(expanded)

    def expand_query(self, query: str) -> List[str]:
        """Expand all terms in a query.

        Args:
            query: Multi-word query string.

        Returns:
            List of all expanded terms.
        """
        if not query:
            return []

        terms = query.lower().split()
        expanded: Set[str] = set()

        for term in terms:
            expanded.update(self.expand(term))

        return list(expanded)

    def rewrite(self, query: str) -> str:
        """Rewrite query to include expanded terms.

        Args:
            query: Original query string.

        Returns:
            Rewritten query with expanded terms.
        """
        if not query:
            return ""

        expanded = self.expand_query(query)

        # Return space-separated expanded terms
        return " ".join(expanded)
