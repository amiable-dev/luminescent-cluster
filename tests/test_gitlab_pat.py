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
Tests for GitLab PAT integration (ADR-005 FREE tier).

These tests verify the GitLab Personal Access Token integration
works correctly for read-only repository access.
"""

import pytest
import os
import json
import base64
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError

from integrations.gitlab_pat import (
    GitLabPATClient,
    GitLabFile,
    GitLabCommit,
    GitLabMergeRequest,
    GitLabAuthError,
    GitLabRateLimitError,
    GitLabNotFoundError,
    GitLabPATError,
)


class TestGitLabPATClientInit:
    """Tests for GitLabPATClient initialization."""

    def test_init_with_explicit_token(self):
        """Client should accept token via constructor."""
        client = GitLabPATClient(token="test_token")
        assert client.token == "test_token"

    def test_init_with_custom_base_url(self):
        """Client should accept custom GitLab instance URL."""
        client = GitLabPATClient(token="test_token", base_url="https://gitlab.company.com")
        assert client.base_url == "https://gitlab.company.com/api/v4"

    def test_init_from_gitlab_token_env(self):
        """Client should read from GITLAB_TOKEN env var."""
        with patch.dict(os.environ, {"GITLAB_TOKEN": "env_token"}):
            client = GitLabPATClient()
            assert client.token == "env_token"

    def test_init_from_gitlab_pat_env(self):
        """Client should read from GITLAB_PAT env var as fallback."""
        with patch.dict(os.environ, {"GITLAB_PAT": "pat_token"}, clear=True):
            os.environ.pop("GITLAB_TOKEN", None)
            client = GitLabPATClient()
            assert client.token == "pat_token"

    def test_init_raises_without_token(self):
        """Client should raise GitLabAuthError if no token available."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GITLAB_TOKEN", None)
            os.environ.pop("GITLAB_PAT", None)
            with pytest.raises(GitLabAuthError) as exc_info:
                GitLabPATClient()
            assert "No GitLab token provided" in str(exc_info.value)


class TestGitLabPATClientRequests:
    """Tests for GitLab API request handling."""

    @pytest.fixture
    def client(self):
        """Create a client with test token."""
        return GitLabPATClient(token="test_token")

    @pytest.fixture
    def mock_response(self):
        """Create mock response helper."""
        def _mock_response(data, status=200):
            mock = MagicMock()
            mock.read.return_value = json.dumps(data).encode("utf-8")
            mock.__enter__ = MagicMock(return_value=mock)
            mock.__exit__ = MagicMock(return_value=False)
            return mock
        return _mock_response

    def test_request_includes_private_token_header(self, client, mock_response):
        """Request should include PRIVATE-TOKEN header."""
        with patch("integrations.gitlab_pat.urlopen") as mock_urlopen:
            mock_urlopen.return_value = mock_response({"test": "data"})

            client._request("/test")

            call_args = mock_urlopen.call_args
            request = call_args[0][0]
            assert request.get_header("Private-token") == "test_token"

    def test_request_includes_user_agent(self, client, mock_response):
        """Request should include User-Agent header."""
        with patch("integrations.gitlab_pat.urlopen") as mock_urlopen:
            mock_urlopen.return_value = mock_response({"test": "data"})

            client._request("/test")

            request = mock_urlopen.call_args[0][0]
            assert "LuminescentCluster" in request.get_header("User-agent")

    def test_request_handles_401_as_auth_error(self, client):
        """401 response should raise GitLabAuthError."""
        with patch("integrations.gitlab_pat.urlopen") as mock_urlopen:
            mock_error = HTTPError(
                url="https://gitlab.com/api/v4/test",
                code=401,
                msg="Unauthorized",
                hdrs={},
                fp=MagicMock()
            )
            mock_urlopen.side_effect = mock_error

            with pytest.raises(GitLabAuthError):
                client._request("/test")

    def test_request_handles_404_as_not_found(self, client):
        """404 response should raise GitLabNotFoundError."""
        with patch("integrations.gitlab_pat.urlopen") as mock_urlopen:
            mock_error = HTTPError(
                url="https://gitlab.com/api/v4/test",
                code=404,
                msg="Not Found",
                hdrs={},
                fp=MagicMock()
            )
            mock_urlopen.side_effect = mock_error

            with pytest.raises(GitLabNotFoundError):
                client._request("/test")

    def test_request_handles_rate_limit(self, client):
        """429 response should raise GitLabRateLimitError."""
        with patch("integrations.gitlab_pat.urlopen") as mock_urlopen:
            mock_error = HTTPError(
                url="https://gitlab.com/api/v4/test",
                code=429,
                msg="Too Many Requests",
                hdrs={},
                fp=MagicMock()
            )
            mock_urlopen.side_effect = mock_error

            with pytest.raises(GitLabRateLimitError):
                client._request("/test")


class TestGitLabPATClientProjectOperations:
    """Tests for project-level operations."""

    @pytest.fixture
    def client(self):
        """Create a client with test token."""
        return GitLabPATClient(token="test_token")

    def test_get_project(self, client):
        """get_project should return project metadata."""
        mock_data = {
            "id": 123,
            "name": "test-repo",
            "path_with_namespace": "owner/test-repo",
            "default_branch": "main",
        }

        with patch.object(client, "_request", return_value=mock_data):
            result = client.get_project("owner/test-repo")

            assert result["name"] == "test-repo"
            assert result["path_with_namespace"] == "owner/test-repo"

    def test_get_project_encodes_path(self, client):
        """get_project should URL-encode the project path."""
        with patch.object(client, "_request", return_value={}) as mock_request:
            client.get_project("owner/test-repo")

            call_arg = mock_request.call_args[0][0]
            assert "owner%2Ftest-repo" in call_arg

    def test_list_repository_tree(self, client):
        """list_repository_tree should return list of GitLabFile objects."""
        mock_data = [
            {"path": "README.md", "name": "README.md", "id": "abc123", "type": "blob"},
            {"path": "src", "name": "src", "id": "def456", "type": "tree"},
        ]

        with patch.object(client, "_request", return_value=mock_data):
            result = client.list_repository_tree("owner/repo")

            assert len(result) == 2
            assert isinstance(result[0], GitLabFile)
            assert result[0].path == "README.md"
            assert result[0].type == "blob"
            assert result[1].type == "tree"

    def test_list_repository_tree_with_path(self, client):
        """list_repository_tree should filter by path."""
        with patch.object(client, "_request", return_value=[]) as mock_request:
            client.list_repository_tree("owner/repo", path="src")

            call_arg = mock_request.call_args[0][0]
            assert "path=src" in call_arg

    def test_list_repository_tree_recursive(self, client):
        """list_repository_tree should support recursive listing."""
        with patch.object(client, "_request", return_value=[]) as mock_request:
            client.list_repository_tree("owner/repo", recursive=True)

            call_arg = mock_request.call_args[0][0]
            assert "recursive=true" in call_arg


class TestGitLabPATClientFileOperations:
    """Tests for file content operations."""

    @pytest.fixture
    def client(self):
        """Create a client with test token."""
        return GitLabPATClient(token="test_token")

    def test_get_file_content_decodes_base64(self, client):
        """get_file_content should decode base64 content."""
        content = "Hello, World!"
        encoded = base64.b64encode(content.encode()).decode()
        mock_data = {
            "content": encoded,
            "encoding": "base64",
        }

        with patch.object(client, "_request", return_value=mock_data):
            result = client.get_file_content("owner/repo", "test.txt")

            assert result == "Hello, World!"

    def test_get_file_content_with_ref(self, client):
        """get_file_content should pass ref parameter."""
        mock_data = {"content": base64.b64encode(b"test").decode(), "encoding": "base64"}

        with patch.object(client, "_request", return_value=mock_data) as mock_request:
            client.get_file_content("owner/repo", "test.txt", ref="develop")

            call_arg = mock_request.call_args[0][0]
            assert "ref=develop" in call_arg

    def test_get_file_content_encodes_path(self, client):
        """get_file_content should URL-encode the file path."""
        mock_data = {"content": base64.b64encode(b"test").decode(), "encoding": "base64"}

        with patch.object(client, "_request", return_value=mock_data) as mock_request:
            client.get_file_content("owner/repo", "src/main.py")

            call_arg = mock_request.call_args[0][0]
            assert "src%2Fmain.py" in call_arg


class TestGitLabPATClientCommitOperations:
    """Tests for commit history operations."""

    @pytest.fixture
    def client(self):
        """Create a client with test token."""
        return GitLabPATClient(token="test_token")

    def test_get_commits_returns_commit_list(self, client):
        """get_commits should return list of GitLabCommit objects."""
        mock_data = [
            {
                "id": "abc1234567890",
                "short_id": "abc1234",
                "title": "Initial commit",
                "message": "Initial commit\n\nDetailed description",
                "author_name": "Test User",
                "created_at": "2024-01-01T00:00:00Z",
            },
        ]

        with patch.object(client, "_request", return_value=mock_data):
            result = client.get_commits("owner/repo")

            assert len(result) == 1
            assert isinstance(result[0], GitLabCommit)
            assert result[0].short_id == "abc1234"
            assert result[0].title == "Initial commit"
            assert result[0].author == "Test User"

    def test_get_commits_respects_limit(self, client):
        """get_commits should pass per_page parameter."""
        with patch.object(client, "_request", return_value=[]) as mock_request:
            client.get_commits("owner/repo", limit=5)

            call_arg = mock_request.call_args[0][0]
            assert "per_page=5" in call_arg

    def test_get_commits_with_path(self, client):
        """get_commits should filter by path."""
        with patch.object(client, "_request", return_value=[]) as mock_request:
            client.get_commits("owner/repo", path="src/main.py")

            call_arg = mock_request.call_args[0][0]
            assert "path=src" in call_arg


class TestGitLabPATClientMergeRequestOperations:
    """Tests for merge request operations."""

    @pytest.fixture
    def client(self):
        """Create a client with test token."""
        return GitLabPATClient(token="test_token")

    def test_get_merge_requests_returns_mr_list(self, client):
        """get_merge_requests should return list of GitLabMergeRequest objects."""
        mock_data = [
            {
                "iid": 42,
                "title": "Add feature",
                "state": "opened",
                "author": {"username": "contributor"},
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-02T00:00:00Z",
                "target_branch": "main",
                "source_branch": "feature-branch",
                "description": "Description",
            },
        ]

        with patch.object(client, "_request", return_value=mock_data):
            result = client.get_merge_requests("owner/repo")

            assert len(result) == 1
            assert isinstance(result[0], GitLabMergeRequest)
            assert result[0].iid == 42
            assert result[0].title == "Add feature"
            assert result[0].author == "contributor"

    def test_get_merge_requests_filters_by_state(self, client):
        """get_merge_requests should filter by state parameter."""
        with patch.object(client, "_request", return_value=[]) as mock_request:
            client.get_merge_requests("owner/repo", state="merged")

            call_arg = mock_request.call_args[0][0]
            assert "state=merged" in call_arg


class TestGitLabPATClientValidation:
    """Tests for token validation."""

    @pytest.fixture
    def client(self):
        """Create a client with test token."""
        return GitLabPATClient(token="test_token")

    def test_validate_token_returns_true_for_valid(self, client):
        """validate_token should return True for valid token."""
        with patch.object(client, "_request", return_value={"username": "user"}):
            assert client.validate_token() is True

    def test_validate_token_returns_false_for_invalid(self, client):
        """validate_token should return False for invalid token."""
        with patch.object(client, "_request", side_effect=GitLabAuthError("Invalid")):
            assert client.validate_token() is False


class TestGitLabPATClientTreeOperations:
    """Tests for recursive tree operations with filtering."""

    @pytest.fixture
    def client(self):
        """Create a client with test token."""
        return GitLabPATClient(token="test_token")

    def test_get_all_files_returns_blobs_only(self, client):
        """get_all_files should return only blobs, not trees."""
        mock_data = [
            {"path": "src", "name": "src", "id": "dir1", "type": "tree"},
            {"path": "src/main.py", "name": "main.py", "id": "file1", "type": "blob"},
            {"path": "README.md", "name": "README.md", "id": "file2", "type": "blob"},
        ]

        with patch.object(client, "_request", return_value=mock_data):
            result = client.get_all_files("owner/repo")

            assert len(result) == 2
            assert all(f.type == "blob" for f in result)
            paths = [f.path for f in result]
            assert "src/main.py" in paths
            assert "README.md" in paths
            assert "src" not in paths

    def test_get_all_files_filters_by_extension(self, client):
        """get_all_files should filter by file extension."""
        mock_data = [
            {"path": "main.py", "name": "main.py", "id": "file1", "type": "blob"},
            {"path": "README.md", "name": "README.md", "id": "file2", "type": "blob"},
            {"path": "test.js", "name": "test.js", "id": "file3", "type": "blob"},
        ]

        with patch.object(client, "_request", return_value=mock_data):
            result = client.get_all_files("owner/repo", extensions={".py", ".md"})

            assert len(result) == 2
            paths = [f.path for f in result]
            assert "main.py" in paths
            assert "README.md" in paths
            assert "test.js" not in paths
