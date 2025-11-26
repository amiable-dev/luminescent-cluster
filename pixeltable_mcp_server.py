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
        sim = results.content.similarity(query)
        
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
        
        return [dict(row) for row in matches]
    
    async def get_adrs(self, topic: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Get Architectural Decision Records"""
        
        if not self.kb:
            return []
        
        adrs = self.kb.where(self.kb.is_adr == True)
        
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
        
        return [dict(row) for row in results]
    
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
        
        return [dict(row) for row in results]
    
    async def get_full_content(self, path: str) -> Optional[str]:
        """Get full content for a specific item by path"""
        
        if not self.kb:
            return None
        
        result = self.kb.where(self.kb.path == path).select(
            self.kb.content
        ).limit(1)
        
        items = list(result)
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
        
        return [dict(row) for row in results]
    
    async def get_service_context(self, service: str) -> Dict[str, Any]:
        """Get comprehensive context for a specific service"""
        
        if not self.kb:
            return {}
        
        service_data = self.kb.where(
            self.kb.metadata['service'] == service
        )
        
        # Get counts by type
        code_count = len(list(service_data.where(self.kb.type == 'code')))
        decision_count = len(list(service_data.where(self.kb.type == 'decision')))
        incident_count = len(list(service_data.where(self.kb.type == 'incident')))
        
        # Get recent incidents
        recent_incidents = list(
            service_data.where(self.kb.type == 'incident')
            .order_by(self.kb.created_at, asc=False)
            .select(self.kb.title, self.kb.created_at)
            .limit(3)
        )
        
        return {
            'service': service,
            'code_files': code_count,
            'decisions': decision_count,
            'incidents': incident_count,
            'recent_incidents': [dict(i) for i in recent_incidents]
        }


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
