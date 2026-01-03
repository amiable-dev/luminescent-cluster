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
Session Memory MCP Server

Provides fast access to hot context for AI coding assistants:
- Recent git commits and changes
- Active files being edited
- Open pull requests
- Current task context
- Persistent user memory (ADR-003)

This is Tier 1 memory - ephemeral, fast, session-scoped.
Integrates with ADR-003 Memory Architecture for persistent context.
"""

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import git
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
from datetime import datetime, timedelta

# Import memory module tools (ADR-003)
from src.memory.mcp import (
    create_memory,
    get_memories,
    get_memory_by_id,
    search_memories,
    delete_memory,
    update_memory,
    invalidate_memory,
    get_memory_provenance,
)

# Import extraction pipeline (ADR-003 Phase 1b)
from src.memory.extraction import ExtractionPipeline

# Shared extraction pipeline instance
_extraction_pipeline = None


def _get_extraction_pipeline() -> ExtractionPipeline:
    """Get the shared extraction pipeline instance."""
    global _extraction_pipeline
    if _extraction_pipeline is None:
        _extraction_pipeline = ExtractionPipeline()
    return _extraction_pipeline


class SessionMemoryServer:
    """MCP server for session-level context memory"""
    
    def __init__(self, repo_path: Optional[str] = None):
        """Initialize with repository path"""
        if repo_path is None:
            repo_path = os.environ.get("REPO_PATH", os.getcwd())
        
        self.repo_path = Path(repo_path)
        try:
            self.repo = git.Repo(repo_path, search_parent_directories=True)
        except git.InvalidGitRepositoryError:
            self.repo = None
            print(f"Warning: {repo_path} is not a git repository")
        
        self.active_files = set()
        self.task_context = {}
    
    async def get_recent_commits(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent commits with messages and metadata"""
        if not self.repo:
            return []
        
        commits = []
        for commit in list(self.repo.iter_commits(max_count=limit)):
            commits.append({
                'hash': commit.hexsha[:8],
                'message': commit.message.strip(),
                'author': str(commit.author),
                'date': commit.committed_datetime.isoformat(),
                'stats': {
                    'files_changed': len(commit.stats.files),
                    'insertions': commit.stats.total['insertions'],
                    'deletions': commit.stats.total['deletions']
                }
            })
        
        return commits
    
    async def get_changed_files(self, since_hours: int = 24) -> List[Dict[str, Any]]:
        """Get files changed in the last N hours"""
        if not self.repo:
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=since_hours)
        changed = []
        
        for commit in self.repo.iter_commits(since=cutoff_time):
            for file_path in commit.stats.files:
                if file_path not in [c['path'] for c in changed]:
                    changed.append({
                        'path': file_path,
                        'last_modified': commit.committed_datetime.isoformat(),
                        'last_author': str(commit.author)
                    })
        
        return changed
    
    async def get_current_diff(self) -> str:
        """Get unstaged changes in the repository"""
        if not self.repo:
            return "No git repository"
        
        # Get unstaged changes
        diff = self.repo.git.diff()
        
        # Also get staged changes
        staged = self.repo.git.diff('--cached')
        
        result = ""
        if diff:
            result += "## Unstaged Changes\n\n" + diff
        if staged:
            result += "\n\n## Staged Changes\n\n" + staged
        
        return result if result else "No changes"
    
    async def get_current_branch(self) -> Dict[str, Any]:
        """Get current branch information"""
        if not self.repo:
            return {}
        
        branch = self.repo.active_branch
        
        # Get ahead/behind info relative to remote
        try:
            tracking_branch = branch.tracking_branch()
            if tracking_branch:
                ahead, behind = self.repo.git.rev_list(
                    '--left-right', 
                    '--count', 
                    f'{tracking_branch}...{branch}'
                ).split('\t')
            else:
                ahead, behind = '0', '0'
        except Exception:
            ahead, behind = '0', '0'
        
        return {
            'name': branch.name,
            'commit': branch.commit.hexsha[:8],
            'ahead': int(ahead),
            'behind': int(behind)
        }
    
    async def search_commits(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search commit messages"""
        if not self.repo:
            return []
        
        results = []
        for commit in self.repo.iter_commits(max_count=200):
            if query.lower() in commit.message.lower():
                results.append({
                    'hash': commit.hexsha[:8],
                    'message': commit.message.strip(),
                    'author': str(commit.author),
                    'date': commit.committed_datetime.isoformat()
                })
                
                if len(results) >= limit:
                    break
        
        return results
    
    async def get_file_history(self, file_path: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get commit history for a specific file"""
        if not self.repo:
            return []
        
        history = []
        try:
            for commit in self.repo.iter_commits(paths=file_path, max_count=limit):
                history.append({
                    'hash': commit.hexsha[:8],
                    'message': commit.message.strip(),
                    'author': str(commit.author),
                    'date': commit.committed_datetime.isoformat()
                })
        except Exception as e:
            print(f"Error getting history for {file_path}: {e}")
        
        return history
    
    async def set_task_context(self, task: str, details: Dict[str, Any]) -> str:
        """Set current task context"""
        self.task_context = {
            'task': task,
            'details': details,
            'set_at': datetime.now().isoformat()
        }
        return f"Task context set: {task}"
    
    async def get_task_context(self) -> Dict[str, Any]:
        """Get current task context"""
        return self.task_context


async def serve():
    """Main server entry point"""
    
    # Initialize server
    server = Server("session-memory")
    session_memory = SessionMemoryServer()
    
    # Register tools
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available session memory tools"""
        return [
            Tool(
                name="get_recent_commits",
                description=(
                    "Get recent git commits from the current repository. "
                    "Use this to understand recent changes and development context. "
                    "Returns commit hash, message, author, date, and statistics."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Number of commits to retrieve (default: 10)",
                            "default": 10
                        }
                    }
                }
            ),
            Tool(
                name="get_changed_files",
                description=(
                    "Get files that have been modified in the last N hours. "
                    "Useful for understanding what's actively being worked on."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "since_hours": {
                            "type": "integer",
                            "description": "Look back this many hours (default: 24)",
                            "default": 24
                        }
                    }
                }
            ),
            Tool(
                name="get_current_diff",
                description=(
                    "Get current unstaged and staged changes in the repository. "
                    "Use this to see what's currently being modified."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="get_current_branch",
                description=(
                    "Get information about the current git branch including "
                    "name, commit, and tracking status."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="search_commits",
                description=(
                    "Search commit messages for specific terms. "
                    "Useful for finding when specific changes were made."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search term to find in commit messages"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results to return (default: 5)",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="get_file_history",
                description=(
                    "Get commit history for a specific file. "
                    "Shows who changed it and when."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to the file"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of commits to retrieve (default: 5)",
                            "default": 5
                        }
                    },
                    "required": ["file_path"]
                }
            ),
            Tool(
                name="set_task_context",
                description=(
                    "Set the current task context for this session. "
                    "Use this to remember what you're working on."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "Brief description of current task"
                        },
                        "details": {
                            "type": "object",
                            "description": "Additional task details",
                            "default": {}
                        }
                    },
                    "required": ["task"]
                }
            ),
            Tool(
                name="get_task_context",
                description=(
                    "Get the current task context if one has been set. "
                    "Returns what you're currently working on."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            # ADR-003 Memory Tools
            Tool(
                name="create_user_memory",
                description=(
                    "Create a new persistent memory for the user. "
                    "Stores preferences, facts, or decisions that persist across sessions."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "user_id": {
                            "type": "string",
                            "description": "User who owns this memory"
                        },
                        "content": {
                            "type": "string",
                            "description": "The memory content"
                        },
                        "memory_type": {
                            "type": "string",
                            "enum": ["preference", "fact", "decision"],
                            "description": "Type of memory"
                        },
                        "source": {
                            "type": "string",
                            "description": "Where this memory came from",
                            "default": "conversation"
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Confidence score (0.0-1.0)",
                            "default": 1.0
                        }
                    },
                    "required": ["user_id", "content", "memory_type"]
                }
            ),
            Tool(
                name="get_user_memories",
                description=(
                    "Retrieve memories matching a query for a user. "
                    "Uses semantic search to find relevant memories."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "user_id": {
                            "type": "string",
                            "description": "User ID to filter memories"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results (default: 5)",
                            "default": 5
                        }
                    },
                    "required": ["query", "user_id"]
                }
            ),
            Tool(
                name="search_user_memories",
                description=(
                    "Search memories with filters. "
                    "Filter by memory type, source, or confidence threshold."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "user_id": {
                            "type": "string",
                            "description": "User ID to filter memories"
                        },
                        "memory_type": {
                            "type": "string",
                            "enum": ["preference", "fact", "decision"],
                            "description": "Filter by memory type"
                        },
                        "source": {
                            "type": "string",
                            "description": "Filter by source"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results (default: 10)",
                            "default": 10
                        }
                    },
                    "required": ["user_id"]
                }
            ),
            Tool(
                name="update_user_memory",
                description=(
                    "Update an existing memory's content. "
                    "Tracks update history for provenance."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "memory_id": {
                            "type": "string",
                            "description": "Memory ID to update"
                        },
                        "content": {
                            "type": "string",
                            "description": "New memory content"
                        },
                        "source": {
                            "type": "string",
                            "description": "Source of this update"
                        }
                    },
                    "required": ["memory_id", "content", "source"]
                }
            ),
            Tool(
                name="invalidate_user_memory",
                description=(
                    "Mark a memory as invalid with a reason. "
                    "Invalidated memories are excluded from retrieval."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "memory_id": {
                            "type": "string",
                            "description": "Memory ID to invalidate"
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for invalidation"
                        }
                    },
                    "required": ["memory_id", "reason"]
                }
            ),
            Tool(
                name="get_memory_provenance",
                description=(
                    "Get the full provenance (history) of a memory. "
                    "Shows creation, updates, and invalidation events."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "memory_id": {
                            "type": "string",
                            "description": "Memory ID to get provenance for"
                        }
                    },
                    "required": ["memory_id"]
                }
            ),
            Tool(
                name="delete_user_memory",
                description=(
                    "Permanently delete a memory. "
                    "Use invalidate_user_memory for soft delete."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "memory_id": {
                            "type": "string",
                            "description": "Memory ID to delete"
                        }
                    },
                    "required": ["memory_id"]
                }
            ),
            Tool(
                name="extract_memories_from_conversation",
                description=(
                    "Extract memories from a conversation text. "
                    "Runs async extraction pipeline to find preferences, facts, and decisions. "
                    "Use after response is sent for non-blocking extraction."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "conversation": {
                            "type": "string",
                            "description": "The conversation text to extract memories from"
                        },
                        "user_id": {
                            "type": "string",
                            "description": "User ID for the extracted memories"
                        },
                        "source": {
                            "type": "string",
                            "description": "Source of the conversation",
                            "default": "conversation"
                        }
                    },
                    "required": ["conversation", "user_id"]
                }
            )
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Handle tool calls"""
        
        try:
            if name == "get_recent_commits":
                result = await session_memory.get_recent_commits(
                    limit=arguments.get("limit", 10)
                )
            elif name == "get_changed_files":
                result = await session_memory.get_changed_files(
                    since_hours=arguments.get("since_hours", 24)
                )
            elif name == "get_current_diff":
                result = await session_memory.get_current_diff()
            elif name == "get_current_branch":
                result = await session_memory.get_current_branch()
            elif name == "search_commits":
                result = await session_memory.search_commits(
                    query=arguments["query"],
                    limit=arguments.get("limit", 5)
                )
            elif name == "get_file_history":
                result = await session_memory.get_file_history(
                    file_path=arguments["file_path"],
                    limit=arguments.get("limit", 5)
                )
            elif name == "set_task_context":
                result = await session_memory.set_task_context(
                    task=arguments["task"],
                    details=arguments.get("details", {})
                )
            elif name == "get_task_context":
                result = await session_memory.get_task_context()
            # ADR-003 Memory Tools
            elif name == "create_user_memory":
                result = await create_memory(
                    user_id=arguments["user_id"],
                    content=arguments["content"],
                    memory_type=arguments["memory_type"],
                    source=arguments.get("source", "conversation"),
                    confidence=arguments.get("confidence", 1.0),
                )
            elif name == "get_user_memories":
                result = await get_memories(
                    query=arguments["query"],
                    user_id=arguments["user_id"],
                    limit=arguments.get("limit", 5),
                )
            elif name == "search_user_memories":
                result = await search_memories(
                    user_id=arguments["user_id"],
                    memory_type=arguments.get("memory_type"),
                    source=arguments.get("source"),
                    limit=arguments.get("limit", 10),
                )
            elif name == "update_user_memory":
                result = await update_memory(
                    memory_id=arguments["memory_id"],
                    content=arguments["content"],
                    source=arguments["source"],
                )
            elif name == "invalidate_user_memory":
                result = await invalidate_memory(
                    memory_id=arguments["memory_id"],
                    reason=arguments["reason"],
                )
            elif name == "get_memory_provenance":
                result = await get_memory_provenance(
                    memory_id=arguments["memory_id"],
                )
            elif name == "delete_user_memory":
                result = await delete_memory(
                    memory_id=arguments["memory_id"],
                )
            elif name == "extract_memories_from_conversation":
                pipeline = _get_extraction_pipeline()
                extractions = await pipeline.process(
                    conversation=arguments["conversation"],
                    user_id=arguments["user_id"],
                    source=arguments.get("source", "conversation"),
                )
                result = {
                    "extracted_count": len(extractions),
                    "memories": [
                        {
                            "content": e.content,
                            "memory_type": e.memory_type,
                            "confidence": e.confidence,
                        }
                        for e in extractions
                    ],
                }
            else:
                raise ValueError(f"Unknown tool: {name}")
            
            # Format result as JSON for consistent parsing
            if isinstance(result, (dict, list)):
                result_str = json.dumps(result, indent=2)
            else:
                result_str = str(result)
            
            return [TextContent(type="text", text=result_str)]
            
        except Exception as e:
            error_msg = f"Error executing {name}: {str(e)}"
            return [TextContent(type="text", text=error_msg)]
    
    # Run server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    import asyncio
    asyncio.run(serve())
