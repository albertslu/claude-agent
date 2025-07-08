#!/usr/bin/env python3
"""
Test script for the MCP client without interactive input
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from robust_mcp_client import RobustMCPClient
from config import Config

def test_mcp_client():
    """Test the MCP client functionality"""
    server_command = ["python3", "vista3d_mcp_server.py", "--tasks-path", "/tmp/vista3d_tasks"]
    
    # Use config system to get API key
    config = Config()
    openai_api_key = config.get_openai_key()
    
    client = RobustMCPClient(server_command, openai_api_key)
    
    try:
        print("🚀 Starting MCP server...")
        client.start_server()
        
        print("🔌 Initializing connection...")
        init_response = client.initialize()
        print(f"✅ Initialized: {init_response['result']['serverInfo']['name']}")
        
        print("📋 Listing tools...")
        tools_response = client.list_tools()
        tools = tools_response.get("result", {}).get("tools", [])
        print(f"✅ Found {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool['name']}: {tool['description']}")
        
        print("\n🔍 Testing list_available_images...")
        try:
            result = client.call_tool("list_available_images", {})
            print(f"✅ Images listed: {result}")
        except Exception as e:
            print(f"❌ Failed to list images: {e}")
        
        print("\n🧠 Testing natural language command...")
        if openai_api_key:
            try:
                result = client.natural_language_command("list available images in sample_data folder")
                print(f"✅ Natural language result: {result}")
            except Exception as e:
                print(f"❌ Natural language failed: {e}")
        else:
            print("⚠️  No OpenAI API key - skipping natural language test")
        
        print("\n📤 Testing task submission...")
        try:
            test_args = {
                "input_file": "sample_data/test_volume.nii.gz",
                "output_directory": "/tmp/vista3d_output",
                "point_coordinates": [100, 100, 50]
            }
            result = client.call_tool("submit_vista3d_point_task", test_args)
            print(f"✅ Task submitted: {result}")
            
            # Check task status if we got a task ID
            if "result" in result and "task_id" in result["result"]:
                task_id = result["result"]["task_id"]
                print(f"\n📊 Checking status of task {task_id}...")
                status_result = client.call_tool("check_vista3d_task_status", {"task_id": task_id})
                print(f"✅ Task status: {status_result}")
            
        except Exception as e:
            print(f"❌ Task submission failed: {e}")
        
        print("\n✅ All tests completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("🔌 Stopping server...")
        client.stop_server()

if __name__ == "__main__":
    test_mcp_client()