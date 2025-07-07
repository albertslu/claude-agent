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
from typing import Dict, Any
from vista3d_cli import Vista3DCLI

class Vista3DSmartClient:
    def __init__(self, tasks_path="/home/lbert/tasks-live", image_dirs="/home/lbert/claude-agent/sample_data"):
        self.cli = Vista3DCLI(tasks_path, image_dirs)
        self.tasks_path = tasks_path
        self.image_dirs = image_dirs
        
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
        
        # Try to use local LLM (ollama) if available
        try:
            result = subprocess.run([
                "ollama", "run", "llama3.2:1b", 
                f"{system_prompt}\n\nUser: {user_prompt}\nAssistant:"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and result.stdout.strip():
                # Extract JSON from response
                response = result.stdout.strip()
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                    
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
            pass
            
        # Fallback to rule-based parsing
        return self.fallback_parse(user_input)
        
    def fallback_parse(self, text: str) -> Dict[str, Any]:
        """Fallback rule-based parsing when LLM is not available"""
        result = {}
        text_lower = text.lower()
        
        # Determine command
        if any(word in text_lower for word in ['submit', 'create', 'start', 'run', 'segment']):
            result['command'] = 'submit'
        elif any(word in text_lower for word in ['status', 'check', 'progress']):
            result['command'] = 'status'
        elif any(word in text_lower for word in ['list', 'show', 'images']):
            result['command'] = 'list'
        else:
            result['command'] = 'submit'  # Default
            
        # Extract coordinates
        coord_match = re.search(r'(\d+)\s*,?\s*(\d+)\s*,?\s*(\d+)', text)
        if coord_match:
            result['coordinates'] = [int(coord_match.group(1)), int(coord_match.group(2)), int(coord_match.group(3))]
        else:
            result['coordinates'] = None
            
        # Extract file paths
        file_match = re.search(r'["\']?([^"\']+\.nii(?:\.gz)?)["\']?', text)
        if file_match:
            result['input_file'] = file_match.group(1)
        else:
            result['input_file'] = None
            
        # Extract output directory
        output_match = re.search(r'(?:output|save|to)\s+["\']?([^"\']+/?)["\']?', text, re.IGNORECASE)
        if output_match:
            result['output_directory'] = output_match.group(1)
        else:
            result['output_directory'] = None
            
        # Extract task ID
        task_match = re.search(r'(vista3d_point_\d+)', text)
        if task_match:
            result['task_id'] = task_match.group(1)
        else:
            result['task_id'] = None
            
        # Extract patient info
        patient_match = re.search(r'patient\s+(?:id\s+)?([A-Z0-9]+)', text, re.IGNORECASE)
        result['patient_id'] = patient_match.group(1) if patient_match else None
        
        series_match = re.search(r'series\s+(?:uid\s+)?([0-9.]+)', text, re.IGNORECASE)
        result['series_uid'] = series_match.group(1) if series_match else None
        
        return result
        
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
                                
        # No fallback - return original query if no file found
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
                    # Create default output directory based on input
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