#!/usr/bin/env python3
"""
Robust MCP Client with OpenAI Integration
Handles large outputs and provides OpenAI-powered natural language interface
"""

import json
import subprocess
import sys
import time
import os
import signal
from typing import Dict, Any, Optional, List
from openai import OpenAI
import threading
import queue
from io import StringIO
from config import Config

class RobustMCPClient:
    def __init__(self, server_command: List[str], openai_api_key: Optional[str] = None):
        """Initialize robust MCP client with optional OpenAI integration"""
        self.server_command = server_command
        self.process = None
        self.request_id = 0
        self.openai_client = None
        self.output_queue = queue.Queue()
        self.error_queue = queue.Queue()
        
        # Initialize OpenAI - try provided key, then config, then environment
        if not openai_api_key:
            config = Config()
            openai_api_key = config.get_openai_key()
        else:
            config = Config()
        
        if openai_api_key:
            self.openai_client = OpenAI(api_key=openai_api_key)
            
        # Load base paths from config
        self.base_paths = config.get_base_paths()
        
    def start_server(self):
        """Start the MCP server process with robust error handling"""
        print(f"Starting MCP server: {' '.join(self.server_command)}")
        try:
            self.process = subprocess.Popen(
                self.server_command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                preexec_fn=os.setsid if os.name != 'nt' else None  # Process group for cleanup
            )
            
            # Start background threads to handle output
            self.stdout_thread = threading.Thread(target=self._read_stdout, daemon=True)
            self.stderr_thread = threading.Thread(target=self._read_stderr, daemon=True)
            self.stdout_thread.start()
            self.stderr_thread.start()
            
            time.sleep(1)  # Give server time to start
            
        except Exception as e:
            raise Exception(f"Failed to start server: {e}")
    
    def _read_stdout(self):
        """Background thread to read stdout without blocking"""
        try:
            while self.process and self.process.poll() is None:
                line = self.process.stdout.readline()
                if line:
                    self.output_queue.put(line.strip())
        except Exception as e:
            self.error_queue.put(f"Stdout reader error: {e}")
    
    def _read_stderr(self):
        """Background thread to read stderr without blocking"""
        try:
            while self.process and self.process.poll() is None:
                line = self.process.stderr.readline()
                if line:
                    self.error_queue.put(line.strip())
        except Exception as e:
            self.error_queue.put(f"Stderr reader error: {e}")
    
    def stop_server(self):
        """Stop the MCP server process gracefully"""
        if self.process:
            try:
                if os.name != 'nt':
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                else:
                    self.process.terminate()
                self.process.wait(timeout=5)
            except:
                if os.name != 'nt':
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                else:
                    self.process.kill()
    
    def send_request(self, method: str, params: Optional[Dict[str, Any]] = None, timeout: int = 30) -> Dict[str, Any]:
        """Send JSON-RPC request with timeout and error handling"""
        if not self.process or self.process.poll() is not None:
            raise Exception("Server process not running")
        
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self.request_id
        }
        if params:
            request["params"] = params
        
        # Send request
        try:
            request_json = json.dumps(request)
            print(f"→ Sending: {method}")
            self.process.stdin.write(request_json + "\n")
            self.process.stdin.flush()
        except Exception as e:
            raise Exception(f"Failed to send request: {e}")
        
        # Wait for response with timeout
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response_line = self.output_queue.get(timeout=1)
                if response_line.strip():
                    response = json.loads(response_line)
                    if response.get("id") == self.request_id:
                        print(f"← Received: {method} completed")
                        
                        if "error" in response:
                            raise Exception(f"Server error: {response['error']}")
                        
                        return response
            except queue.Empty:
                continue
            except json.JSONDecodeError:
                continue
        
        raise Exception(f"Request {method} timed out after {timeout}s")
    
    def initialize(self):
        """Initialize MCP connection"""
        return self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "robust-mcp-client",
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
    
    def natural_language_command(self, command: str) -> Dict[str, Any]:
        """Process natural language command using OpenAI"""
        if not self.openai_client:
            raise Exception("OpenAI client not initialized")
        
        # Get available tools
        tools_response = self.list_tools()
        tools = tools_response.get("result", {}).get("tools", [])
        
        # Create prompt for OpenAI
        tools_info = []
        for tool in tools:
            tools_info.append({
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool.get("inputSchema", {}).get("properties", {})
            })
        
        
        prompt = f"""You are a Vista3D medical imaging assistant with intelligent file discovery.

Available tools:
{json.dumps(tools_info, indent=2)}

User command: "{command}"

Base path for patients: {self.base_paths['dcm2nifti_base']}

WORKFLOW: For patient commands, start the discovery process:
1. If user mentions "patient XXXX", use list_available_images with search_directory: "{self.base_paths['dcm2nifti_base']}/XXXX/"
2. The workflow will continue automatically after discovery

Return JSON with:
- "tool_name": tool to call
- "arguments": arguments with actual base path
- "explanation": what will be done

Respond only with valid JSON."""

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.1
            )
            
            content = response.choices[0].message.content.strip()
            print(f"🔍 OpenAI response: {content}")
            
            # Try to extract JSON from the response
            if content.startswith("```json"):
                content = content.split("```json")[1].split("```")[0].strip()
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            
            if "error" in result:
                return {"error": result["error"], "suggestions": result.get("suggestions", [])}
            
            # Execute the tool call
            tool_name = result["tool_name"]
            arguments = result["arguments"]
            explanation = result.get("explanation", "")
            
            print(f"🤖 {explanation}")
            
            # Call the tool
            tool_result = self.call_tool(tool_name, arguments)
            
            # Check if OpenAI wants to continue with more tool calls
            return self._continue_workflow_if_needed(command, tool_result)
            
        except Exception as e:
            return {"error": f"Failed to process command: {str(e)}"}
    
    def _continue_workflow_if_needed(self, original_command: str, tool_result: Dict[str, Any]) -> Dict[str, Any]:
        """Continue workflow if OpenAI determines more steps are needed"""
        try:
            # Ask OpenAI if the workflow is complete or if more steps are needed
            result_content = tool_result.get("result", {}).get("content", [])
            result_text = result_content[0].get("text", "") if result_content else ""
            
            # Get available tools for the continuation prompt
            tools_response = self.list_tools()
            tools = tools_response.get("result", {}).get("tools", [])
            
            tools_info = []
            for tool in tools:
                tools_info.append({
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool.get("inputSchema", {}).get("properties", {})
                })
            
            continuation_prompt = f"""Original command: "{original_command}"

Available tools:
{json.dumps(tools_info, indent=2)}

Last tool result: {result_text}

IMPORTANT: Use the ACTUAL file paths from the result above. 
- Find the MR series image.nii.gz file from the list
- Convert Linux paths (/mnt/c/) to Windows paths (C:\\)
- Use the real discovered paths, not placeholders

Is the workflow complete? If not, what's the next tool to call with the actual discovered file paths?

If complete, return: {{"workflow_complete": true, "explanation": "Task completed"}}
If not complete, return: {{"tool_name": "actual_tool_name", "arguments": {{...with real paths...}}, "explanation": "Next step"}}

Respond only with valid JSON."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": continuation_prompt}],
                max_tokens=1000,
                temperature=0.1
            )
            
            content = response.choices[0].message.content.strip()
            print(f"🔍 OpenAI workflow check: {content}")
            
            # Parse the response
            if content.startswith("```json"):
                content = content.split("```json")[1].split("```")[0].strip()
            elif content.startswith("```"):
                content = content.split("```")[1].split("```")[0].strip()
            
            result = json.loads(content)
            
            # If workflow is complete, return the original result
            if result.get("workflow_complete"):
                return {
                    "success": True,
                    "explanation": result.get("explanation", "Workflow completed"),
                    "tool_result": tool_result
                }
            
            # If there's a next tool, execute it
            if "tool_name" in result:
                next_tool_name = result["tool_name"]
                next_arguments = result["arguments"]
                next_explanation = result.get("explanation", "")
                
                print(f"🤖 {next_explanation}")
                
                # Call the next tool
                next_result = self.call_tool(next_tool_name, next_arguments)
                
                return {
                    "success": True,
                    "explanation": next_explanation,
                    "tool_result": next_result
                }
            
            # Default: return original result
            return {
                "success": True,
                "explanation": "Workflow completed",
                "tool_result": tool_result
            }
            
        except Exception as e:
            # If continuation fails, return original result
            return {
                "success": True,
                "explanation": "Tool executed successfully",
                "tool_result": tool_result
            }
            
        except Exception as e:
            return {"error": f"Failed to process command: {str(e)}"}

def main():
    """Main CLI interface"""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 robust_mcp_client.py <server_command> [args...]")
        print("  OPENAI_API_KEY=your_key python3 robust_mcp_client.py python3 vista3d_mcp_server.py --tasks-path /home/lbert/tasks-live")
        sys.exit(1)
    
    server_command = sys.argv[1:]
    
    # Try to get OpenAI API key automatically
    config = Config()
    openai_api_key = config.get_openai_key()
    
    client = RobustMCPClient(server_command, openai_api_key)
    
    try:
        # Start server
        client.start_server()
        
        # Initialize connection
        print("🚀 Initializing MCP connection...")
        init_response = client.initialize()
        
        # List available tools
        print("📋 Loading available tools...")
        tools_response = client.list_tools()
        tools = tools_response.get("result", {}).get("tools", [])
        
        print(f"✅ Connected! {len(tools)} tools available.")
        
        if openai_api_key:
            print("🤖 OpenAI integration enabled - you can use natural language commands!")
        
        # Interactive mode
        print("\n=== Commands ===")
        print("  help - Show this help")
        print("  tools - List available tools")
        print("  call <tool_name> <json_args> - Call a tool directly")
        print("  Natural language: 'segment liver from test.nii.gz'")
        print("  quit - Exit")
        
        while True:
            try:
                command = input("\n> ").strip()
                
                if command == "quit":
                    break
                elif command == "help":
                    print("Available commands:")
                    print("  tools - List available tools")
                    print("  call <tool_name> <json_args> - Direct tool call")
                    if openai_api_key:
                        print("  Natural language commands (e.g., 'segment liver from test.nii.gz')")
                elif command == "tools":
                    for i, tool in enumerate(tools, 1):
                        print(f"{i}. {tool['name']}: {tool['description']}")
                elif command.startswith("call "):
                    parts = command.split(" ", 2)
                    if len(parts) < 3:
                        print("Usage: call <tool_name> <json_args>")
                        continue
                    tool_name = parts[1]
                    try:
                        args = json.loads(parts[2])
                        result = client.call_tool(tool_name, args)
                        print(f"✅ Tool completed: {result}")
                    except json.JSONDecodeError:
                        print("❌ Invalid JSON arguments")
                    except Exception as e:
                        print(f"❌ Tool failed: {e}")
                elif command and openai_api_key:
                    # Try natural language processing
                    result = client.natural_language_command(command)
                    if "error" in result:
                        print(f"❌ {result['error']}")
                        if "suggestions" in result:
                            print("💡 Suggestions:")
                            for suggestion in result["suggestions"]:
                                print(f"  - {suggestion}")
                    else:
                        print(f"✅ {result.get('explanation', 'Command completed')}")
                        if "tool_result" in result:
                            print(f"📊 Result: {result['tool_result']}")
                else:
                    print("❌ Unknown command or OpenAI not configured")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                
    except Exception as e:
        print(f"❌ Failed to start: {e}")
    finally:
        client.stop_server()
        print("🔌 MCP client stopped.")

if __name__ == "__main__":
    main()