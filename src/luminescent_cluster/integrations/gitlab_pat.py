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
GitLab Personal Access Token Integration (FREE Tier).

Provides read-only access to GitLab repositories using a Personal Access Token.
Per ADR-005, this is a FREE tier feature because it uses personal credentials
(user's own PAT) rather than organization-level OAuth Apps.

Features:
- Fetch project metadata
- List repository tree (files/directories)
- Get file contents
- Get commit history
- Get merge request information

Supports:
- GitLab.com (default)
- Self-hosted GitLab instances (via base_url parameter)

Limitations (FREE tier):
- Read-only access
- Personal projects only (PAT scope determines access)
- Rate limited by GitLab instance

Cloud Tier (luminescent-cloud) adds:
- Organization-level GitLab App integration
- Write access (MR agent)
- Webhook subscriptions
"""

import os
import base64
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import quote
import json


@dataclass
class GitLabFile:
    """Represents a file from GitLab."""

    path: str
    name: str
    id: str  # GitLab uses 'id' for blob SHA
    type: str  # "blob" or "tree"
    mode: Optional[str] = None


@dataclass
class GitLabCommit:
    """Represents a commit from GitLab."""

    id: str
    short_id: str
    title: str
    message: str
    author: str
    created_at: str


@dataclass
class GitLabMergeRequest:
    """Represents a merge request from GitLab."""

    iid: int  # GitLab uses iid for project-scoped ID
    title: str
    state: str
    author: str
    created_at: str
    updated_at: str
    target_branch: str
    source_branch: str
    description: Optional[str] = None


class GitLabPATError(Exception):
    """Base exception for GitLab PAT errors."""

    pass


class GitLabAuthError(GitLabPATError):
    """Authentication failed (invalid or expired PAT)."""

    pass


class GitLabRateLimitError(GitLabPATError):
    """Rate limit exceeded."""

    pass


class GitLabNotFoundError(GitLabPATError):
    """Resource not found."""

    pass


class GitLabPATClient:
    """
    GitLab client using Personal Access Token for authentication.

    This is a FREE tier integration per ADR-005. Users provide their own
    PAT which determines their access scope and rate limits.

    Supports both GitLab.com and self-hosted GitLab instances.

    Example:
        ```python
        # Initialize with PAT from environment (GitLab.com)
        client = GitLabPATClient()

        # Or for self-hosted GitLab
        client = GitLabPATClient(
            token="glpat-xxxx",
            base_url="https://gitlab.company.com"
        )

        # Fetch project contents
        files = client.list_repository_tree("owner/repo", path="src/")

        # Get file content
        content = client.get_file_content("owner/repo", "README.md")

        # Get recent commits
        commits = client.get_commits("owner/repo", limit=10)
        ```
    """

    DEFAULT_BASE_URL = "https://gitlab.com"

    def __init__(self, token: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize GitLab client.

        Args:
            token: GitLab Personal Access Token. If not provided, reads from
                   GITLAB_TOKEN or GITLAB_PAT environment variable.
            base_url: GitLab instance URL (default: https://gitlab.com).
                      For self-hosted, e.g., "https://gitlab.company.com"

        Raises:
            GitLabAuthError: If no token is available.
        """
        self.token = token or os.getenv("GITLAB_TOKEN") or os.getenv("GITLAB_PAT")
        if not self.token:
            raise GitLabAuthError(
                "No GitLab token provided. Set GITLAB_TOKEN or GITLAB_PAT "
                "environment variable, or pass token to constructor."
            )

        base = base_url or self.DEFAULT_BASE_URL
        # Ensure we have the API path
        self.base_url = f"{base.rstrip('/')}/api/v4"

    def _encode_project_path(self, project: str) -> str:
        """URL-encode project path for API requests."""
        return quote(project, safe="")

    def _encode_file_path(self, path: str) -> str:
        """URL-encode file path for API requests."""
        return quote(path, safe="")

    def _request(self, endpoint: str, method: str = "GET") -> Any:
        """
        Make authenticated request to GitLab API.

        Args:
            endpoint: API endpoint (without base URL)
            method: HTTP method

        Returns:
            Parsed JSON response

        Raises:
            GitLabAuthError: If authentication fails (401)
            GitLabRateLimitError: If rate limit exceeded (429)
            GitLabNotFoundError: If resource not found (404)
            GitLabPATError: For other errors
        """
        url = f"{self.base_url}{endpoint}"
        headers = {
            "PRIVATE-TOKEN": self.token,
            "Accept": "application/json",
            "User-Agent": "LuminescentCluster/1.0",
        }

        request = Request(url, headers=headers, method=method)

        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as e:
            if e.code == 401:
                raise GitLabAuthError("Invalid or expired GitLab token")
            elif e.code == 403:
                raise GitLabPATError(f"Access forbidden: {e}")
            elif e.code == 404:
                raise GitLabNotFoundError(f"Resource not found: {endpoint}")
            elif e.code == 429:
                raise GitLabRateLimitError("GitLab API rate limit exceeded")
            else:
                raise GitLabPATError(f"GitLab API error: {e}")
        except URLError as e:
            raise GitLabPATError(f"Network error: {e}")

    def get_project(self, project: str) -> Dict[str, Any]:
        """
        Get project metadata.

        Args:
            project: Project path in "namespace/project" format

        Returns:
            Project metadata dict
        """
        encoded = self._encode_project_path(project)
        return self._request(f"/projects/{encoded}")

    def list_repository_tree(
        self, project: str, path: str = "", ref: Optional[str] = None, recursive: bool = False
    ) -> List[GitLabFile]:
        """
        List contents of repository tree.

        Args:
            project: Project path in "namespace/project" format
            path: Path within repository (empty for root)
            ref: Git reference (branch, tag, or SHA). Default: default branch
            recursive: If True, list all files recursively

        Returns:
            List of GitLabFile objects
        """
        encoded_project = self._encode_project_path(project)
        endpoint = f"/projects/{encoded_project}/repository/tree?"

        params = []
        if path:
            params.append(f"path={path}")
        if ref:
            params.append(f"ref={ref}")
        if recursive:
            params.append("recursive=true")

        endpoint += "&".join(params)
        data = self._request(endpoint)

        return [
            GitLabFile(
                path=item["path"],
                name=item["name"],
                id=item["id"],
                type=item["type"],
                mode=item.get("mode"),
            )
            for item in data
        ]

    def get_file_content(self, project: str, path: str, ref: Optional[str] = None) -> str:
        """
        Get content of a specific file.

        Args:
            project: Project path in "namespace/project" format
            path: Path to file within repository
            ref: Git reference (branch, tag, or SHA). Default: default branch

        Returns:
            Decoded file content as string
        """
        encoded_project = self._encode_project_path(project)
        encoded_path = self._encode_file_path(path)
        endpoint = f"/projects/{encoded_project}/repository/files/{encoded_path}"

        if ref:
            endpoint += f"?ref={ref}"
        else:
            endpoint += "?ref=HEAD"

        data = self._request(endpoint)

        content = data.get("content", "")
        encoding = data.get("encoding", "base64")

        if encoding == "base64":
            return base64.b64decode(content).decode("utf-8")
        else:
            return content

    def get_commits(
        self, project: str, path: Optional[str] = None, ref: Optional[str] = None, limit: int = 10
    ) -> List[GitLabCommit]:
        """
        Get commit history.

        Args:
            project: Project path in "namespace/project" format
            path: Filter to commits affecting this path
            ref: Git reference (branch, tag, or SHA)
            limit: Maximum number of commits to return

        Returns:
            List of GitLabCommit objects
        """
        encoded_project = self._encode_project_path(project)
        endpoint = f"/projects/{encoded_project}/repository/commits?per_page={limit}"

        if path:
            endpoint += f"&path={path}"
        if ref:
            endpoint += f"&ref_name={ref}"

        data = self._request(endpoint)

        return [
            GitLabCommit(
                id=commit["id"],
                short_id=commit["short_id"],
                title=commit["title"],
                message=commit["message"],
                author=commit["author_name"],
                created_at=commit["created_at"],
            )
            for commit in data
        ]

    def get_merge_requests(
        self, project: str, state: str = "opened", limit: int = 10
    ) -> List[GitLabMergeRequest]:
        """
        Get merge requests for a project.

        Args:
            project: Project path in "namespace/project" format
            state: Filter by state ("opened", "closed", "merged", "all")
            limit: Maximum number of MRs to return

        Returns:
            List of GitLabMergeRequest objects
        """
        encoded_project = self._encode_project_path(project)
        endpoint = f"/projects/{encoded_project}/merge_requests?state={state}&per_page={limit}"

        data = self._request(endpoint)

        return [
            GitLabMergeRequest(
                iid=mr["iid"],
                title=mr["title"],
                state=mr["state"],
                author=mr["author"]["username"],
                created_at=mr["created_at"],
                updated_at=mr["updated_at"],
                target_branch=mr["target_branch"],
                source_branch=mr["source_branch"],
                description=mr.get("description"),
            )
            for mr in data
        ]

    def validate_token(self) -> bool:
        """
        Validate that the token is valid.

        Returns:
            True if token is valid

        Raises:
            GitLabAuthError: If token is invalid
        """
        try:
            self._request("/user")
            return True
        except GitLabAuthError:
            return False

    def get_all_files(
        self, project: str, ref: Optional[str] = None, extensions: Optional[Set[str]] = None
    ) -> List[GitLabFile]:
        """
        Get all files in repository recursively.

        Args:
            project: Project path in "namespace/project" format
            ref: Git reference (branch, tag, or SHA). Default: default branch
            extensions: Optional set of file extensions to filter (e.g., {".py", ".md"})

        Returns:
            List of GitLabFile objects for all files (not directories)
        """
        all_items = self.list_repository_tree(project, ref=ref, recursive=True)

        files = []
        for item in all_items:
            if item.type != "blob":
                continue

            # Filter by extension if specified
            if extensions:
                ext = os.path.splitext(item.path)[1].lower()
                if ext not in extensions:
                    continue

            files.append(item)

        return files
