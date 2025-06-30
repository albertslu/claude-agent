#!/usr/bin/env python3
"""
Simple MCP (Model Context Protocol) Client
Communicates with MCP servers via JSON-RPC over stdio
"""

import json
import subprocess
import sys
import time
from typing import Dict, Any, Optional, List

class MCPClient:
    def __init__(self, server_command: List[str]):
        """Initialize MCP client with server command"""
        self.server_command = server_command
        self.process = None
        self.request_id = 0
        
    def start_server(self):
        """Start the MCP server process"""
        print(f"Starting MCP server: {' '.join(self.server_command)}")
        self.process = subprocess.Popen(
            self.server_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0
        )
        
    def stop_server(self):
        """Stop the MCP server process"""
        if self.process:
            self.process.terminate()
            self.process.wait()
            
    def send_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send JSON-RPC request to server"""
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self.request_id
        }
        if params:
            request["params"] = params
            
        # Send request
        request_json = json.dumps(request)
        print(f"→ Sending: {request_json}")
        self.process.stdin.write(request_json + "\n")
        self.process.stdin.flush()
        
        # Read response
        response_line = self.process.stdout.readline()
        if not response_line:
            raise Exception("No response from server")
            
        response = json.loads(response_line.strip())
        print(f"← Received: {json.dumps(response, indent=2)}")
        
        if "error" in response:
            raise Exception(f"Server error: {response['error']}")
            
        return response
        
    def initialize(self):
        """Initialize MCP connection"""
        return self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "simple-mcp-client",
                "version": "1.0.0"
            }
        })
        
    def list_tools(self):
        """List available tools"""
        return self.send_request("tools/list")
        
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]):
        """Call a specific tool"""
        return self.send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })

def main():
    """Main CLI interface"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 mcp_client.py <server_command> [args...]")
        print("  python3 mcp_client.py python3 vista3d_mcp_server.py --tasks-path /path/to/tasks")
        sys.exit(1)
        
    server_command = sys.argv[1:]
    client = MCPClient(server_command)
    
    try:
        # Start server
        client.start_server()
        
        # Initialize connection
        print("\n=== Initializing MCP Connection ===")
        init_response = client.initialize()
        
        # List available tools
        print("\n=== Available Tools ===")
        tools_response = client.list_tools()
        tools = tools_response.get("result", {}).get("tools", [])
        
        for i, tool in enumerate(tools, 1):
            print(f"{i}. {tool['name']}: {tool['description']}")
            
        # Interactive mode
        print("\n=== Interactive Mode ===")
        print("Commands:")
        print("  list - List available tools")
        print("  call <tool_name> <json_args> - Call a tool")
        print("  submit <input_file> <output_dir> <x> <y> <z> - Submit Vista3D task")
        print("  status <task_id> - Check task status")
        print("  quit - Exit")
        
        while True:
            try:
                command = input("\n> ").strip()
                
                if command == "quit":
                    break
                elif command == "list":
                    client.list_tools()
                elif command.startswith("call "):
                    parts = command.split(" ", 2)
                    if len(parts) < 3:
                        print("Usage: call <tool_name> <json_args>")
                        continue
                    tool_name = parts[1]
                    try:
                        args = json.loads(parts[2])
                        client.call_tool(tool_name, args)
                    except json.JSONDecodeError:
                        print("Invalid JSON arguments")
                elif command.startswith("submit "):
                    parts = command.split()
                    if len(parts) < 6:
                        print("Usage: submit <input_file> <output_dir> <x> <y> <z>")
                        continue
                    args = {
                        "input_file": parts[1],
                        "output_directory": parts[2],
                        "point_coordinates": [int(parts[3]), int(parts[4]), int(parts[5])]
                    }
                    client.call_tool("submit_vista3d_point_task", args)
                elif command.startswith("status "):
                    task_id = command.split(" ", 1)[1]
                    client.call_tool("check_vista3d_task_status", {"task_id": task_id})
                else:
                    print("Unknown command")
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
                
    finally:
        client.stop_server()
        print("\nMCP client stopped.")

if __name__ == "__main__":
    main()