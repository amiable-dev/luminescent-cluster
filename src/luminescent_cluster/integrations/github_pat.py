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
GitHub Personal Access Token Integration (FREE Tier).

Provides read-only access to GitHub repositories using a Personal Access Token.
Per ADR-005, this is a FREE tier feature because it uses personal credentials
(user's own PAT) rather than organization-level OAuth Apps.

Features:
- Fetch repository metadata
- List repository contents (files/directories)
- Get file contents
- Get commit history
- Get pull request information

Limitations (FREE tier):
- Read-only access
- Personal repositories only (PAT scope determines access)
- Rate limited by GitHub (5000 requests/hour for authenticated)

Cloud Tier (luminescent-cloud) adds:
- Organization-level GitHub App integration
- Write access (PR agent)
- Webhook subscriptions
- Higher rate limits
"""

import os
import base64
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import json


@dataclass
class GitHubFile:
    """Represents a file from GitHub."""

    path: str
    name: str
    sha: str
    size: int
    content: Optional[str] = None
    encoding: Optional[str] = None
    type: str = "file"  # file, dir, submodule, symlink


@dataclass
class GitHubCommit:
    """Represents a commit from GitHub."""

    sha: str
    message: str
    author: str
    date: str
    files_changed: int = 0


@dataclass
class GitHubPullRequest:
    """Represents a pull request from GitHub."""

    number: int
    title: str
    state: str
    author: str
    created_at: str
    updated_at: str
    base_branch: str
    head_branch: str
    body: Optional[str] = None


class GitHubPATError(Exception):
    """Base exception for GitHub PAT errors."""

    pass


class GitHubAuthError(GitHubPATError):
    """Authentication failed (invalid or expired PAT)."""

    pass


class GitHubRateLimitError(GitHubPATError):
    """Rate limit exceeded."""

    pass


class GitHubNotFoundError(GitHubPATError):
    """Resource not found."""

    pass


class GitHubPATClient:
    """
    GitHub client using Personal Access Token for authentication.

    This is a FREE tier integration per ADR-005. Users provide their own
    PAT which determines their access scope and rate limits.

    Example:
        ```python
        # Initialize with PAT from environment
        client = GitHubPATClient()

        # Or provide PAT explicitly
        client = GitHubPATClient(token="ghp_xxxx")

        # Fetch repository contents
        files = client.list_contents("owner/repo", "src/")

        # Get file content
        content = client.get_file_content("owner/repo", "README.md")

        # Get recent commits
        commits = client.get_commits("owner/repo", limit=10)
        ```
    """

    API_BASE = "https://api.github.com"

    def __init__(self, token: Optional[str] = None):
        """
        Initialize GitHub client.

        Args:
            token: GitHub Personal Access Token. If not provided, reads from
                   GITHUB_TOKEN or GITHUB_PAT environment variable.

        Raises:
            GitHubAuthError: If no token is available.
        """
        self.token = token or os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_PAT")
        if not self.token:
            raise GitHubAuthError(
                "No GitHub token provided. Set GITHUB_TOKEN or GITHUB_PAT "
                "environment variable, or pass token to constructor."
            )

    def _request(self, endpoint: str, method: str = "GET") -> Dict[str, Any]:
        """
        Make authenticated request to GitHub API.

        Args:
            endpoint: API endpoint (without base URL)
            method: HTTP method

        Returns:
            Parsed JSON response

        Raises:
            GitHubAuthError: If authentication fails (401)
            GitHubRateLimitError: If rate limit exceeded (403)
            GitHubNotFoundError: If resource not found (404)
            GitHubPATError: For other errors
        """
        url = f"{self.API_BASE}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "LuminescentCluster/1.0",
        }

        request = Request(url, headers=headers, method=method)

        try:
            with urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as e:
            if e.code == 401:
                raise GitHubAuthError("Invalid or expired GitHub token")
            elif e.code == 403:
                # Check if rate limited
                if "rate limit" in str(e.read().decode()).lower():
                    raise GitHubRateLimitError("GitHub API rate limit exceeded")
                raise GitHubPATError(f"Access forbidden: {e}")
            elif e.code == 404:
                raise GitHubNotFoundError(f"Resource not found: {endpoint}")
            else:
                raise GitHubPATError(f"GitHub API error: {e}")
        except URLError as e:
            raise GitHubPATError(f"Network error: {e}")

    def get_repository(self, repo: str) -> Dict[str, Any]:
        """
        Get repository metadata.

        Args:
            repo: Repository in "owner/name" format

        Returns:
            Repository metadata dict
        """
        return self._request(f"/repos/{repo}")

    def list_contents(
        self, repo: str, path: str = "", ref: Optional[str] = None
    ) -> List[GitHubFile]:
        """
        List contents of a directory in a repository.

        Args:
            repo: Repository in "owner/name" format
            path: Path within repository (empty for root)
            ref: Git reference (branch, tag, or SHA). Default: default branch

        Returns:
            List of GitHubFile objects
        """
        endpoint = f"/repos/{repo}/contents/{path}"
        if ref:
            endpoint += f"?ref={ref}"

        data = self._request(endpoint)

        # Single file returns dict, directory returns list
        if isinstance(data, dict):
            data = [data]

        return [
            GitHubFile(
                path=item["path"],
                name=item["name"],
                sha=item["sha"],
                size=item.get("size", 0),
                type=item["type"],
            )
            for item in data
        ]

    def get_file_content(self, repo: str, path: str, ref: Optional[str] = None) -> str:
        """
        Get content of a specific file.

        Args:
            repo: Repository in "owner/name" format
            path: Path to file within repository
            ref: Git reference (branch, tag, or SHA). Default: default branch

        Returns:
            Decoded file content as string
        """
        endpoint = f"/repos/{repo}/contents/{path}"
        if ref:
            endpoint += f"?ref={ref}"

        data = self._request(endpoint)

        if data.get("type") != "file":
            raise GitHubPATError(f"Path is not a file: {path}")

        content = data.get("content", "")
        encoding = data.get("encoding", "base64")

        if encoding == "base64":
            # GitHub returns base64 with newlines, strip them
            content = content.replace("\n", "")
            return base64.b64decode(content).decode("utf-8")
        else:
            return content

    def get_commits(
        self, repo: str, path: Optional[str] = None, ref: Optional[str] = None, limit: int = 10
    ) -> List[GitHubCommit]:
        """
        Get commit history.

        Args:
            repo: Repository in "owner/name" format
            path: Filter to commits affecting this path
            ref: Git reference (branch, tag, or SHA)
            limit: Maximum number of commits to return

        Returns:
            List of GitHubCommit objects
        """
        endpoint = f"/repos/{repo}/commits?per_page={limit}"
        if path:
            endpoint += f"&path={path}"
        if ref:
            endpoint += f"&sha={ref}"

        data = self._request(endpoint)

        return [
            GitHubCommit(
                sha=commit["sha"][:7],
                message=commit["commit"]["message"].split("\n")[0],  # First line
                author=commit["commit"]["author"]["name"],
                date=commit["commit"]["author"]["date"],
            )
            for commit in data
        ]

    def get_pull_requests(
        self, repo: str, state: str = "open", limit: int = 10
    ) -> List[GitHubPullRequest]:
        """
        Get pull requests for a repository.

        Args:
            repo: Repository in "owner/name" format
            state: Filter by state ("open", "closed", "all")
            limit: Maximum number of PRs to return

        Returns:
            List of GitHubPullRequest objects
        """
        endpoint = f"/repos/{repo}/pulls?state={state}&per_page={limit}"
        data = self._request(endpoint)

        return [
            GitHubPullRequest(
                number=pr["number"],
                title=pr["title"],
                state=pr["state"],
                author=pr["user"]["login"],
                created_at=pr["created_at"],
                updated_at=pr["updated_at"],
                base_branch=pr["base"]["ref"],
                head_branch=pr["head"]["ref"],
                body=pr.get("body"),
            )
            for pr in data
        ]

    def get_rate_limit(self) -> Dict[str, Any]:
        """
        Get current rate limit status.

        Returns:
            Dict with rate limit info (limit, remaining, reset time)
        """
        return self._request("/rate_limit")

    def validate_token(self) -> bool:
        """
        Validate that the token is valid and has basic repo access.

        Returns:
            True if token is valid

        Raises:
            GitHubAuthError: If token is invalid
        """
        try:
            self._request("/user")
            return True
        except GitHubAuthError:
            return False

    def get_tree_recursive(
        self, repo: str, ref: str = "HEAD", extensions: Optional[set] = None
    ) -> List[GitHubFile]:
        """
        Get all files in repository recursively.

        This uses the Git Trees API which is more efficient for large repos
        than traversing contents directory by directory.

        Args:
            repo: Repository in "owner/name" format
            ref: Git reference (branch, tag, or SHA). Default: HEAD
            extensions: Optional set of file extensions to filter (e.g., {".py", ".md"})

        Returns:
            List of GitHubFile objects for all files (not directories)
        """
        # First get the SHA for the ref
        if ref == "HEAD":
            repo_data = self.get_repository(repo)
            ref = repo_data["default_branch"]

        endpoint = f"/repos/{repo}/git/trees/{ref}?recursive=1"
        data = self._request(endpoint)

        files = []
        for item in data.get("tree", []):
            if item["type"] != "blob":
                continue  # Skip directories

            path = item["path"]

            # Filter by extension if specified
            if extensions:
                ext = os.path.splitext(path)[1].lower()
                if ext not in extensions:
                    continue

            files.append(
                GitHubFile(
                    path=path,
                    name=os.path.basename(path),
                    sha=item["sha"],
                    size=item.get("size", 0),
                    type="file",
                )
            )

        return files
