#!/usr/bin/env python3
"""
Natural Language MCP Client
Process single commands like Claude Code
"""

import sys
import os
from robust_mcp_client import RobustMCPClient
from config import Config

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print('  python3 nlp_client.py "segment liver from test.nii.gz"')
        print('  python3 nlp_client.py "check status of task123"')
        print('  python3 nlp_client.py "list available images"')
        print('  python3 nlp_client.py "submit full body segmentation for test.nii.gz"')
        sys.exit(1)
    
    # Get the natural language command
    command = " ".join(sys.argv[1:])
    
    # Server configuration
    server_command = ["python3", "vista3d_mcp_server.py", "--tasks-path", "/home/lbert/tasks-live"]
    
    # Get API key from config
    config = Config()
    openai_api_key = config.get_openai_key()
    
    if not openai_api_key:
        print("❌ No OpenAI API key found. Run: python3 config.py set-key 'your_key'")
        sys.exit(1)
    
    # Create client
    client = RobustMCPClient(server_command, openai_api_key)
    
    try:
        print(f"🤖 Processing: '{command}'")
        
        # Start server
        client.start_server()
        
        # Initialize
        client.initialize()
        
        # Process natural language command
        result = client.natural_language_command(command)
        
        if "error" in result:
            print(f"❌ {result['error']}")
            if "suggestions" in result:
                print("💡 Suggestions:")
                for suggestion in result["suggestions"]:
                    print(f"  - {suggestion}")
        else:
            print(f"✅ {result.get('explanation', 'Command completed')}")
            
            # Show the actual result
            if "tool_result" in result:
                tool_result = result["tool_result"]
                if "result" in tool_result and "content" in tool_result["result"]:
                    content = tool_result["result"]["content"]
                    if isinstance(content, list) and len(content) > 0:
                        print(f"📊 Result: {content[0].get('text', 'No details')}")
                else:
                    print(f"📊 Result: {tool_result}")
    
    except Exception as e:
        print(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.stop_server()

if __name__ == "__main__":
    main()