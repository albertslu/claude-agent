#!/usr/bin/env python3
"""
Vista3D Smart Interface - Advanced natural language processing with LLM
Uses local LLM for better command interpretation
"""

import json
import re
import os
import sys
import subprocess
import openai
from typing import Dict, Any
from vista3d_cli import Vista3DCLI

class Vista3DSmartClient:
    def __init__(self, tasks_path="/home/lbert/tasks-live", image_dirs="/home/lbert/claude-agent/sample_data"):
        self.cli = Vista3DCLI(tasks_path, image_dirs)
        self.tasks_path = tasks_path
        self.image_dirs = image_dirs
        
        # Initialize OpenAI client
        self.openai_client = openai.OpenAI(
            api_key=os.getenv('OPENAI_API_KEY')
        )
        
    def llm_parse_command(self, user_input: str) -> Dict[str, Any]:
        """Use LLM to parse natural language command"""
        
        # System prompt for the LLM
        system_prompt = """You are a medical imaging command parser. Convert natural language requests into structured JSON commands for Vista3D segmentation.

Available commands:
1. submit - Submit segmentation task (requires: input_file, output_directory, coordinates [x,y,z])
2. status - Check task status (requires: task_id)  
3. list - List available images (no parameters)

Extract these fields when present:
- command: "submit", "status", or "list"
- input_file: Path to NIfTI image file
- output_directory: Where to save results
- coordinates: [x, y, z] point coordinates as integers
- patient_id: Patient identifier (optional)
- series_uid: Series UID (optional)
- task_id: Task ID for status checks

Respond ONLY with valid JSON. If information is missing, set field to null.

Examples:
Input: "Submit task with coordinates 120 180 100 using brain.nii.gz to /output/"
Output: {"command": "submit", "input_file": "brain.nii.gz", "output_directory": "/output/", "coordinates": [120, 180, 100], "patient_id": null, "series_uid": null}

Input: "Check status of vista3d_point_1751302930147"
Output: {"command": "status", "task_id": "vista3d_point_1751302930147"}"""

        user_prompt = f"Parse this request: {user_input}"
        
        # Use OpenAI GPT-4o mini
        if not self.openai_client.api_key:
            raise ValueError("OpenAI API key not found. Please set OPENAI_API_KEY environment variable.")
            
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=200,
            temperature=0
        )
        
        response_text = response.choices[0].message.content.strip()
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        else:
            raise ValueError(f"Could not parse JSON from response: {response_text}")
        
        
    def smart_file_finder(self, query: str) -> str:
        """Intelligently find image files based on context"""
        # If full path provided, use it
        if os.path.exists(query):
            return query
            
        # Search in common locations
        search_paths = [
            "/mnt/c/ARTDaemon/Segman/dcm2nifti/",
            self.image_dirs,
            "."
        ]
        
        for search_path in search_paths:
            if os.path.exists(search_path):
                # Find NIfTI files
                for root, dirs, files in os.walk(search_path):
                    for file in files:
                        if file.endswith(('.nii', '.nii.gz')):
                            full_path = os.path.join(root, file)
                            if query.lower() in file.lower() or query in full_path:
                                return full_path
                                
        # Return original query if no file found
        return query
        
    def execute_smart_command(self, parsed_cmd: Dict[str, Any]) -> str:
        """Execute command with smart defaults and validation"""
        try:
            self.cli.start_server()
            self.cli.initialize()
            
            if parsed_cmd['command'] == 'submit':
                # Smart validation and defaults
                if not parsed_cmd.get('coordinates'):
                    return "❌ Error: Please specify point coordinates (e.g., '120 180 100')"
                    
                # Smart file finding
                input_file = parsed_cmd.get('input_file')
                if not input_file:
                    input_file = self.smart_file_finder("image")
                    print(f"🔍 Using image: {input_file}")
                else:
                    input_file = self.smart_file_finder(input_file)
                    
                # Smart output directory
                output_dir = parsed_cmd.get('output_directory')
                if not output_dir:
                    # Create output directory based on input
                    if "ARTDaemon" in input_file:
                        base_dir = os.path.dirname(input_file)
                        output_dir = os.path.join(base_dir, "Vista3D/")
                    else:
                        output_dir = "/tmp/vista3d_output/"
                    print(f"📁 Using output directory: {output_dir}")
                    
                x, y, z = parsed_cmd['coordinates']
                result = self.cli.submit_task(
                    input_file, output_dir, x, y, z,
                    parsed_cmd.get('patient_id'),
                    parsed_cmd.get('series_uid')
                )
                return f"✅ {result}"
                
            elif parsed_cmd['command'] == 'status':
                if not parsed_cmd.get('task_id'):
                    return "❌ Error: Please specify a task ID (e.g., 'vista3d_point_1751302930147')"
                    
                result = self.cli.check_status(parsed_cmd['task_id'])
                return f"📊 {result}"
                
            elif parsed_cmd['command'] == 'list':
                result = self.cli.list_images()
                # Limit list output to avoid crashes
                if len(str(result)) > 200:
                    result = str(result)[:200] + "... [truncated - too many files]"
                return f"📁 {result}"
                
        except Exception as e:
            return f"❌ Error: {str(e)}"
        finally:
            self.cli.stop_server()
            
    def chat_mode(self):
        """Interactive chat mode for natural language commands"""
        print("🧠 Vista3D Smart Interface - Natural Language Mode")
        print("Type your requests in plain English. Examples:")
        print("  'Submit a segmentation task at coordinates 120 180 100'")
        print("  'Check the status of my last task'") 
        print("  'List available brain images'")
        print("  'Process the MRI scan at point 150 200 110'")
        print("Type 'quit' to exit.\n")
        
        while True:
            try:
                user_input = input("👤 You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    print("👋 Goodbye!")
                    break
                    
                if not user_input:
                    continue
                    
                print(f"🤖 Processing: '{user_input}'")
                
                # Parse with LLM
                parsed = self.llm_parse_command(user_input)
                # Limit parsed output to avoid crashes
                parsed_str = json.dumps(parsed, indent=2)
                if len(parsed_str) > 50:
                    parsed_str = parsed_str[:50] + "... [truncated]"
                print(f"🔍 Understood: {parsed_str}")
                
                # Execute command
                result = self.execute_smart_command(parsed)
                # Limit result output to avoid crashes
                if len(result) > 100:
                    result = result[:100] + "... [truncated]"
                print(f"🎯 Result: {result}\n")
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                error_msg = str(e)
                if len(error_msg) > 50:
                    error_msg = error_msg[:50] + "... [truncated]"
                print(f"❌ Error: {error_msg}\n")

def main():
    if len(sys.argv) > 1:
        # Single command mode
        command = " ".join(sys.argv[1:])
        client = Vista3DSmartClient()
        
        print(f"🤖 Processing: '{command}'")
        parsed = client.llm_parse_command(command)
        # Limit parsed output to avoid crashes
        parsed_str = json.dumps(parsed, indent=2)
        if len(parsed_str) > 50:
            parsed_str = parsed_str[:50] + "... [truncated]"
        print(f"🔍 Parsed: {parsed_str}")
        
        result = client.execute_smart_command(parsed)
        # Limit result output to avoid crashes
        if len(result) > 100:
            result = result[:100] + "... [truncated]"
        print(f"\n{result}")
    else:
        # Interactive chat mode
        client = Vista3DSmartClient()
        client.chat_mode()

if __name__ == "__main__":
    main()