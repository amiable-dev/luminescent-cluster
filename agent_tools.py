#!/usr/bin/env python3
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
Agent Tools Wrapper

This script allows you to invoke the Context-Aware AI System tools directly from the command line.
It wraps the Docker execution commands for both Session Memory and Pixeltable Memory.

Usage:
    python agent_tools.py session <tool_name> [args...]
    python agent_tools.py pixeltable <tool_name> [args...]

Examples:
    python agent_tools.py session get_recent_commits --limit 5
    python agent_tools.py pixeltable search_knowledge --query "deployment"
"""

import argparse
import subprocess
import json
import sys
import shlex

def run_docker_tool(container, script, tool_name, args_dict):
    """Run a tool inside the docker container"""
    
    # Construct the python code to run inside the container
    # We import the server class, instantiate it, and call the method
    
    if container == "session-memory-mcp":
        server_class = "SessionMemoryServer"
        import_line = "from session_memory_server import SessionMemoryServer"
    else:
        server_class = "PixeltableMemoryServer"
        import_line = "from pixeltable_mcp_server import PixeltableMemoryServer"
        
    # Convert args_dict to python kwargs string
    kwargs = ", ".join([f"{k}={repr(v)}" for k, v in args_dict.items()])
    
    python_code = f"""
import asyncio
import json
import sys
{import_line}

async def run():
    try:
        server = {server_class}()
        # Some tools might be async, some sync. The servers we built have async methods.
        if hasattr(server, '{tool_name}'):
            method = getattr(server, '{tool_name}')
            if asyncio.iscoroutinefunction(method):
                result = await method({kwargs})
            else:
                result = method({kwargs})
            
            # Print result as JSON for easy parsing
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"Error: Tool '{tool_name}' not found", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Error: {{e}}", file=sys.stderr)
        sys.exit(1)

asyncio.run(run())
"""
    
    cmd = [
        "docker-compose", "exec", "-T", 
        container.replace("-mcp", ""), # docker-compose service name
        "python", "-c", python_code
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Error executing command: {result.stderr}", file=sys.stderr)
            sys.exit(result.returncode)
        
        print(result.stdout)
        
    except Exception as e:
        print(f"Failed to run docker command: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Context-Aware AI Tools Wrapper")
    subparsers = parser.add_subparsers(dest="command_group", required=True)
    
    # Session Memory
    session_parser = subparsers.add_parser("session", help="Session Memory Tools")
    session_parser.add_argument("tool", help="Tool name (e.g., get_recent_commits)")
    session_parser.add_argument("--limit", type=int, help="Limit results")
    session_parser.add_argument("--query", type=str, help="Search query")
    session_parser.add_argument("--path", type=str, help="File path")
    
    # Pixeltable Memory
    pixel_parser = subparsers.add_parser("pixeltable", help="Pixeltable Memory Tools")
    pixel_parser.add_argument("tool", help="Tool name (e.g., search_knowledge)")
    pixel_parser.add_argument("--query", type=str, help="Search query")
    pixel_parser.add_argument("--limit", type=int, help="Limit results")
    pixel_parser.add_argument("--type_filter", type=str, help="Filter by type")
    pixel_parser.add_argument("--service", type=str, help="Service name")
    pixel_parser.add_argument("--path", type=str, help="Document path")
    pixel_parser.add_argument("--topic", type=str, help="ADR topic")
    
    args = parser.parse_args()
    
    # Build arguments dictionary for the tool
    tool_args = {}
    if hasattr(args, 'limit') and args.limit is not None:
        tool_args['limit'] = args.limit
    if hasattr(args, 'query') and args.query is not None:
        tool_args['query'] = args.query
    if hasattr(args, 'path') and args.path is not None:
        tool_args['path'] = args.path
    if hasattr(args, 'type_filter') and args.type_filter is not None:
        tool_args['type_filter'] = args.type_filter
    if hasattr(args, 'service') and args.service is not None:
        tool_args['service'] = args.service
    if hasattr(args, 'topic') and args.topic is not None:
        tool_args['topic'] = args.topic
        
    container = "session-memory-mcp" if args.command_group == "session" else "pixeltable-memory-mcp"
    
    run_docker_tool(container, None, args.tool, tool_args)

if __name__ == "__main__":
    main()
