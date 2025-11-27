"""
Pixeltable MCP Server

Exposes long-term organizational memory to Claude via MCP protocol.
Provides semantic search over code, decisions, incidents, and meetings.
"""

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
import pixeltable as pxt
import json
from typing import Optional, List, Dict, Any


class PixeltableMemoryServer:
    """MCP server for Pixeltable long-term memory"""
    
    def __init__(self):
        """Initialize connection to Pixeltable knowledge base"""
        try:
            self.kb = pxt.get_table('org_knowledge')
            print("✓ Connected to org_knowledge table")
        except Exception as e:
            print(f"Warning: Could not connect to org_knowledge: {e}")
            self.kb = None
        
        try:
            self.meetings = pxt.get_table('meetings')
            print("✓ Connected to meetings table")
        except Exception:
            self.meetings = None
    
    async def search_knowledge(
        self,
        query: str,
        type_filter: Optional[str] = None,
        service_filter: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search organizational knowledge base"""
        
        if not self.kb:
            return []
        
        results = self.kb
        
        # Apply filters
        if type_filter:
            results = results.where(self.kb.type == type_filter)
        
        if service_filter:
            results = results.where(
                self.kb.metadata['service'] == service_filter
            )
        
        # Semantic similarity search
        sim = self.kb.content.similarity(query)
        
        matches = (
            results.order_by(sim, asc=False)
            .select(
                self.kb.type,
                self.kb.path,
                self.kb.title,
                self.kb.summary,
                self.kb.metadata,
                self.kb.is_adr,
                score=sim
            )
            .limit(limit)
        )
        
        return [dict(row) for row in matches.collect()]
    
    async def get_adrs(
        self,
        topic: Optional[str] = None,
        service: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get Architectural Decision Records"""
        
        if not self.kb:
            return []
        
        adrs = self.kb.where(self.kb.is_adr == True)
        
        # Filter by service if specified
        if service:
            adrs = adrs.where(self.kb.metadata['service'] == service)
        
        if topic:
            sim = adrs.content.similarity(topic)
            adrs = adrs.order_by(sim, asc=False)
        else:
            adrs = adrs.order_by(self.kb.created_at, asc=False)
        
        results = adrs.select(
            self.kb.path,
            self.kb.title,
            self.kb.summary,
            self.kb.created_at,
            self.kb.metadata
        ).limit(limit)
        
        return [dict(row) for row in results.collect()]
    
    async def get_incidents(
        self,
        service: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get production incident history"""
        
        if not self.kb:
            return []
        
        incidents = self.kb.where(self.kb.type == 'incident')
        
        if service:
            incidents = incidents.where(
                self.kb.metadata['service'] == service
            )
        
        results = incidents.order_by(
            self.kb.created_at, asc=False
        ).select(
            self.kb.title,
            self.kb.summary,
            self.kb.created_at,
            self.kb.metadata
        ).limit(limit)
        
        return [dict(row) for row in results.collect()]
    
    async def get_full_content(self, path: str) -> Optional[str]:
        """Get full content for a specific item by path"""
        
        if not self.kb:
            return None
        
        result = self.kb.where(self.kb.path == path).select(
            self.kb.content
        ).limit(1)
        
        items = list(result.collect())
        return items[0]['content'] if items else None
    
    async def search_meetings(
        self,
        query: str,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """Search meeting transcripts"""
        
        if not self.meetings:
            return []
        
        sim = self.meetings.transcript.similarity(query)
        
        results = self.meetings.order_by(
            sim, asc=False
        ).select(
            self.meetings.title,
            self.meetings.date,
            self.meetings.attendees,
            self.meetings.topics,
            score=sim
        ).limit(limit)
        
        return [dict(row) for row in results.collect()]
    
    async def get_service_context(self, service: str) -> Dict[str, Any]:
        """Get comprehensive context for a specific service"""
        
        if not self.kb:
            return {}
        
        # Get counts by type
        code_count = self.kb.where(
            (self.kb.metadata['service'] == service) & (self.kb.type == 'code')
        ).count()
        
        decision_count = self.kb.where(
            (self.kb.metadata['service'] == service) & (self.kb.type == 'decision')
        ).count()
        
        incident_count = self.kb.where(
            (self.kb.metadata['service'] == service) & (self.kb.type == 'incident')
        ).count()
        
        # Get recent incidents
        recent_incidents = list(
            self.kb.where(
                (self.kb.metadata['service'] == service) & (self.kb.type == 'incident')
            )
            .order_by(self.kb.created_at, asc=False)
            .select(self.kb.title, self.kb.created_at)
            .limit(3)
            .collect()
        )
        
        return {
            'service': service,
            'code_files': code_count,
            'decisions': decision_count,
            'incidents': incident_count,
            'recent_incidents': [dict(i) for i in recent_incidents]
        }
    
    # Write Operations
    async def ingest_codebase_data(
        self,
        repo_path: str,
        service_name: str
    ) -> Dict[str, Any]:
        """Ingest code files from a repository"""
        if not self.kb:
            return {'error': 'Knowledge base not initialized'}
        
        from pixeltable_setup import ingest_codebase
        try:
            count = ingest_codebase(self.kb, repo_path, service_name)
            return {
                'success': True,
                'files_ingested': count,
                'service': service_name,
                'repo_path': repo_path
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def ingest_adr_data(
        self,
        adr_path: str,
        title: str
    ) -> Dict[str, Any]:
        """Ingest an Architectural Decision Record"""
        if not self.kb:
            return {'error': 'Knowledge base not initialized'}
        
        from pixeltable_setup import ingest_adr
        try:
            ingest_adr(self.kb, adr_path, title)
            return {'success': True, 'adr': title, 'path': adr_path}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def ingest_incident_data(
        self,
        incident_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Ingest a production incident"""
        if not self.kb:
            return {'error': 'Knowledge base not initialized'}
        
        from pixeltable_setup import ingest_incident
        from datetime import datetime
        
        # Ensure date is datetime object
        if 'date' in incident_data and isinstance(incident_data['date'], str):
            incident_data['date'] = datetime.fromisoformat(incident_data['date'])
        elif 'date' not in incident_data:
            incident_data['date'] = datetime.now()
        
        try:
            ingest_incident(self.kb, incident_data)
            return {'success': True, 'incident': incident_data['title']}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    # Stats & Info Operations
    async def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics"""
        if not self.kb:
            return {'error': 'Knowledge base not initialized'}
        
        from pixeltable_setup import get_knowledge_stats
        try:
            return get_knowledge_stats(self.kb)
        except Exception as e:
            return {'error': str(e)}
    
    async def list_all_services(self) -> List[str]:
        """List all services in the knowledge base"""
        if not self.kb:
            return []
        
        from pixeltable_setup import list_services
        try:
            return list_services(self.kb)
        except Exception as e:
            return [f"Error listing services: {str(e)}"]
    
    # Snapshot Operations
    async def create_knowledge_snapshot(
        self,
        name: str,
        description: str = "",
        tags: List[str] = None
    ) -> Dict[str, Any]:
        """Create a snapshot of the knowledge base"""
        from pixeltable_setup import snapshot_knowledge_base
        
        try:
            snapshot_knowledge_base(name, tags or [])
            return {
                'success': True,
                'snapshot': name,
                'description': description,
                'tags': tags or []
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def list_all_snapshots(self) -> List[Dict[str, Any]]:
        """List all knowledge base snapshots"""
        from pixeltable_setup import list_snapshots
        
        try:
            return list_snapshots()
        except Exception as e:
            return []
    
    # Data Management Operations    
    async def delete_service(
        self,
        service_name: str,
        confirm: bool = False
    ) -> Dict[str, Any]:
        """Delete all data for a service"""
        if not self.kb:
            return {'error': 'Knowledge base not initialized'}
        
        if not confirm:
            return {
                'error': 'Confirmation required',
                'message': f'Set confirm=True to delete all data for {service_name}'
            }
        
        from pixeltable_setup import delete_service_data
        try:
            result = delete_service_data(self.kb, service_name)
            return {**result, 'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    async def prune_old(
        self,
        days_old: int,
        confirm: bool = False
    ) -> Dict[str, Any]:
        """Delete data older than specified days"""
        if not self.kb:
            return {'error': 'Knowledge base not initialized'}
        
        if not confirm:
            return {
                'error': 'Confirmation required',
                'message': f'Set confirm=True to delete data older than {days_old} days'
            }
        
        from pixeltable_setup import prune_old_data
        try:
            result = prune_old_data(self.kb, days_old)
            return {**result, 'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}


async def serve():
    """Main server entry point"""
    
    server = Server("pixeltable-memory")
    memory = PixeltableMemoryServer()
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available long-term memory tools"""
        return [
            Tool(
                name="search_organizational_memory",
                description=(
                    "Search the organization's long-term knowledge base. "
                    "This includes code, architectural decisions, incidents, and documentation. "
                    "Use for: understanding past decisions, finding incident history, "
                    "discovering relevant code patterns."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query - can be natural language"
                        },
                        "type_filter": {
                            "type": "string",
                            "description": "Filter by type: 'code', 'decision', 'incident', 'documentation'",
                            "enum": ["code", "decision", "incident", "documentation"]
                        },
                        "service_filter": {
                            "type": "string",
                            "description": "Filter by service name"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results (default: 5)",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="get_architectural_decisions",
                description=(
                    "Retrieve Architectural Decision Records (ADRs). "
                    "These document why specific technical decisions were made. "
                    "Critical for understanding the reasoning behind current architecture."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "Optional topic to filter ADRs (e.g., 'authentication', 'database')"
                        },
                        "service": {
                            "type": "string",
                            "description": "Optional service/project name to filter ADRs (e.g., 'auth-service')"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results (default: 5)",
                            "default": 5
                        }
                    }
                }
            ),
            Tool(
                name="get_incident_history",
                description=(
                    "Get production incident history. "
                    "Learn from past failures to avoid repeating mistakes. "
                    "Includes root causes and resolutions."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "service": {
                            "type": "string",
                            "description": "Filter by service name"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results (default: 5)",
                            "default": 5
                        }
                    }
                }
            ),
            Tool(
                name="get_full_document",
                description=(
                    "Retrieve full content of a specific document by path. "
                    "Use after finding relevant items via search to get complete details."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the document"
                        }
                    },
                    "required": ["path"]
                }
            ),
            Tool(
                name="search_meeting_transcripts",
                description=(
                    "Search meeting transcripts and discussions. "
                    "Find decisions and context from team meetings."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results (default: 3)",
                            "default": 3
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="get_service_overview",
                description=(
                    "Get comprehensive overview of a specific service including "
                    "code files, decisions, and incident history."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "service": {
                            "type": "string",
                            "description": "Service name"
                        }
                    },
                    "required": ["service"]
                }
            ),
            # Write Operations
            Tool(
                name="ingest_codebase",
                description=(
                    "Ingest code files from a repository into the knowledge base. "
                    "Use this to add a new service/project to organizational memory."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "repo_path": {
                            "type": "string",
                            "description": "Path to the repository (use current directory with '.' or absolute path)"
                        },
                        "service_name": {
                            "type": "string",
                            "description": "Service identifier (e.g., 'auth-service', 'payment-api')"
                        }
                    },
                    "required": ["repo_path", "service_name"]
                }
            ),
            Tool(
                name="ingest_architectural_decision",
                description=(
                    "Add an Architectural Decision Record (ADR) to the knowledge base. "
                    "ADRs document important technical decisions."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "adr_path": {
                            "type": "string",
                            "description": "Path to the ADR markdown file"
                        },
                        "title": {
                            "type": "string",
                            "description": "ADR title (e.g., 'ADR 001: Database Choice')"
                        }
                    },
                    "required": ["adr_path", "title"]
                }
            ),
            Tool(
                name="ingest_incident",
                description=(
                    "Record a production incident in the knowledge base. "
                    "Helps learn from past failures."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Incident title"
                        },
                        "description": {
                            "type": "string",
                            "description": "Detailed incident description and resolution"
                        },
                        "date": {
                            "type": "string",
                            "description": "Incident date (ISO 8601 format, e.g., '2024-11-27T10:00:00')"
                        },
                        "service": {
                            "type": "string",
                            "description": "Optional: Affected service name"
                        },
                        "severity": {
                            "type": "string",
                            "description": "Optional: Severity level (critical, high, medium, low)"
                        },
                        "root_cause": {
                            "type": "string",
                            "description": "Optional: Root cause analysis"
                        }
                    },
                    "required": ["title", "description"]
                }
            ),
            # Info Operations
            Tool(
                name="get_knowledge_base_stats",
                description=(
                    "Get statistics about the knowledge base including total items, "
                    "breakdown by type, and list of services."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            Tool(
                name="list_services",
                description="List all unique service names currently in the knowledge base.",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            # Snapshot Operations
            Tool(
                name="create_snapshot",
                description="Create a named snapshot of the knowledge base for backup/recovery purposes.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Snapshot name (e.g., 'before-refactor', 'q4-2024')"
                        },
                        "description": {
                            "type": "string",
                            "description": "Optional description of what this snapshot represents"
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional tags for categorization"
                        }
                    },
                    "required": ["name"]
                }
            ),
            Tool(
                name="list_snapshots",
                description="List all knowledge base snapshots with their names, creation dates, and tags.",
                inputSchema={
                    "type": "object",
                    "properties": {}
                }
            ),
            # Data Management
            Tool(
                name="delete_service_data",
                description="Delete all data for a specific service. DANGEROUS - requires confirmation.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "service_name": {
                            "type": "string",
                            "description": "Service name to delete (e.g., 'deprecated-auth')"
                        },
                        "confirm": {
                            "type": "boolean",
                            "description": "MUST be true to actually delete. Safety check."
                        }
                    },
                    "required": ["service_name", "confirm"]
                }
            ),
            Tool(
                name="prune_old_data",
                description="Delete data older than specified number of days. DANGEROUS - requires confirmation.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "days_old": {
                            "type": "integer",
                            "description": "Delete data older than this many days"
                        },
                        "confirm": {
                            "type": "boolean",
                            "description": "MUST be true to actually delete. Safety check."
                        }
                    },
                    "required": ["days_old", "confirm"]
                }
            )
        ]
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Handle tool calls"""
        
        try:
            if name == "search_organizational_memory":
                result = await memory.search_knowledge(
                    query=arguments["query"],
                    type_filter=arguments.get("type_filter"),
                    service_filter=arguments.get("service_filter"),
                    limit=arguments.get("limit", 5)
                )
            
            elif name == "get_architectural_decisions":
                result = await memory.get_adrs(
                    topic=arguments.get("topic"),
                    limit=arguments.get("limit", 5)
                )
            
            elif name == "get_incident_history":
                result = await memory.get_incidents(
                    service=arguments.get("service"),
                    limit=arguments.get("limit", 5)
                )
            
            elif name == "get_full_document":
                result = await memory.get_full_content(
                    path=arguments["path"]
                )
            
            elif name == "search_meeting_transcripts":
                result = await memory.search_meetings(
                    query=arguments["query"],
                    limit=arguments.get("limit", 3)
                )
            
            elif name == "get_service_overview":
                result = await memory.get_service_context(
                    service=arguments["service"]
                )
            
            # Write Operations
            elif name == "ingest_codebase":
                result = await memory.ingest_codebase_data(
                    repo_path=arguments["repo_path"],
                    service_name=arguments["service_name"]
                )
            
            elif name == "ingest_architectural_decision":
                result = await memory.ingest_adr_data(
                    adr_path=arguments["adr_path"],
                    title=arguments["title"]
                )
            
            elif name == "ingest_incident":
                result = await memory.ingest_incident_data(
                    incident_data=arguments
                )
            
            # Info Operations
            elif name == "get_knowledge_base_stats":
                result = await memory.get_stats()
            
            elif name == "list_services":
                result = await memory.list_all_services()
            
            # Snapshot Operations
            elif name == "create_snapshot":
                result = await memory.create_knowledge_snapshot(
                    name=arguments["name"],
                    description=arguments.get("description", ""),
                    tags=arguments.get("tags")
                )
            
            elif name == "list_snapshots":
                result = await memory.list_all_snapshots()
            
            # Data Management
            elif name == "delete_service_data":
                result = await memory.delete_service(
                    service_name=arguments["service_name"],
                    confirm=arguments.get("confirm", False)
                )
            
            elif name == "prune_old_data":
                result = await memory.prune_old(
                    days_old=arguments["days_old"],
                    confirm=arguments.get("confirm", False)
                )
            
            else:
                raise ValueError(f"Unknown tool: {name}")
            
            # Format result
            if isinstance(result, (dict, list)):
                result_str = json.dumps(result, indent=2, default=str)
            else:
                result_str = str(result) if result else "No results found"
            
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
