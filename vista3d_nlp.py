#!/usr/bin/env python3
"""
Vista3D Natural Language Interface
Converts natural language commands to Vista3D MCP calls
"""

import json
import re
import os
import glob
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from vista3d_cli import Vista3DCLI

class Vista3DNLPClient:
    def __init__(self, tasks_path="/home/lbert/tasks-live", image_dirs="/home/lbert/claude-agent/sample_data"):
        self.cli = Vista3DCLI(tasks_path, image_dirs)
        self.tasks_path = tasks_path
        self.image_dirs = image_dirs.split(":")
        
    def parse_coordinates(self, text: str) -> Optional[Tuple[int, int, int]]:
        """Extract coordinates from text like 'point 120 180 100' or 'coordinates [120, 180, 100]'"""
        # Pattern: three numbers separated by spaces, commas, or in brackets
        patterns = [
            r'(\d+)\s*,?\s*(\d+)\s*,?\s*(\d+)',  # 120 180 100 or 120,180,100
            r'\[(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\]',  # [120, 180, 100]
            r'point\s+(\d+)\s+(\d+)\s+(\d+)',  # point 120 180 100
            r'coordinates?\s+(\d+)\s+(\d+)\s+(\d+)',  # coordinate 120 180 100
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return (int(match.group(1)), int(match.group(2)), int(match.group(3)))
        return None
        
    def find_image_files(self, query: str) -> List[str]:
        """Find image files based on natural language query"""
        found_files = []
        
        # Search in image directories
        for img_dir in self.image_dirs:
            if os.path.exists(img_dir):
                # Find NIfTI files
                nii_files = glob.glob(os.path.join(img_dir, "**/*.nii*"), recursive=True)
                found_files.extend(nii_files)
                
        # If query contains specific terms, filter files
        query_lower = query.lower()
        if any(term in query_lower for term in ['brain', 'head', 'skull']):
            found_files = [f for f in found_files if any(term in f.lower() for term in ['brain', 'head', 'skull'])]
        elif any(term in query_lower for term in ['chest', 'lung', 'thorax']):
            found_files = [f for f in found_files if any(term in f.lower() for term in ['chest', 'lung', 'thorax'])]
        elif any(term in query_lower for term in ['abdomen', 'liver', 'kidney']):
            found_files = [f for f in found_files if any(term in f.lower() for term in ['abdomen', 'liver', 'kidney'])]
            
        # If specific file path mentioned, try to find it
        if "/" in query or "\\" in query:
            # Extract potential file paths
            path_matches = re.findall(r'["\']?([^"\']+\.(nii|nii\.gz))["\']?', query, re.IGNORECASE)
            for match in path_matches:
                path = match[0]
                if os.path.exists(path):
                    found_files.append(path)
                    
        return list(set(found_files))  # Remove duplicates
        
    def parse_output_directory(self, text: str) -> Optional[str]:
        """Extract output directory from text"""
        # Look for common patterns
        patterns = [
            r'output\s+(?:to\s+)?["\']?([^"\']+)["\']?',
            r'save\s+(?:to\s+)?["\']?([^"\']+)["\']?',
            r'directory\s+["\']?([^"\']+)["\']?',
            r'folder\s+["\']?([^"\']+)["\']?',
            r'["\']([^"\']+)["\']',  # Any quoted path
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                path = match.group(1).strip()
                # Ensure it's a directory path
                if not path.endswith(('/', '\\')):
                    path += '/'
                return path
                
        return None
        
    def parse_patient_info(self, text: str) -> Dict[str, str]:
        """Extract patient ID and series UID from text"""
        info = {}
        
        # Patient ID patterns
        patient_patterns = [
            r'patient\s+(?:id\s+)?["\']?([A-Z0-9]+)["\']?',
            r'patient[:\s]+["\']?([A-Z0-9]+)["\']?',
            r'id\s+["\']?([A-Z0-9]+)["\']?',
        ]
        
        for pattern in patient_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                info['patient_id'] = match.group(1)
                break
                
        # Series UID patterns
        series_patterns = [
            r'series\s+(?:uid\s+)?["\']?([0-9.]+)["\']?',
            r'uid\s+["\']?([0-9.]+)["\']?',
        ]
        
        for pattern in series_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                info['series_uid'] = match.group(1)
                break
                
        return info
        
    def parse_natural_language(self, text: str) -> Dict:
        """Parse natural language command into structured data"""
        text = text.strip()
        command_type = None
        
        # Determine command type
        if any(word in text.lower() for word in ['submit', 'create', 'start', 'run', 'segment']):
            command_type = 'submit'
        elif any(word in text.lower() for word in ['status', 'check', 'progress', 'state']):
            command_type = 'status'
        elif any(word in text.lower() for word in ['list', 'show', 'find', 'images']):
            command_type = 'list'
        else:
            # Try to infer from context
            if re.search(r'\d+\s+\d+\s+\d+', text):  # Has coordinates
                command_type = 'submit'
            elif re.search(r'vista3d_point_\d+', text):  # Has task ID
                command_type = 'status'
            else:
                command_type = 'list'
                
        result = {'command': command_type}
        
        if command_type == 'submit':
            # Extract coordinates
            coords = self.parse_coordinates(text)
            if coords:
                result['coordinates'] = coords
                
            # Find image files
            image_files = self.find_image_files(text)
            if image_files:
                result['input_file'] = image_files[0]  # Use first match
                
            # Extract output directory
            output_dir = self.parse_output_directory(text)
            if output_dir:
                result['output_directory'] = output_dir
                
            # Extract patient info
            patient_info = self.parse_patient_info(text)
            result.update(patient_info)
            
        elif command_type == 'status':
            # Extract task ID
            task_id_match = re.search(r'(vista3d_point_\d+)', text)
            if task_id_match:
                result['task_id'] = task_id_match.group(1)
                
        return result
        
    def execute_command(self, parsed_cmd: Dict) -> str:
        """Execute the parsed command"""
        try:
            self.cli.start_server()
            self.cli.initialize()
            
            if parsed_cmd['command'] == 'submit':
                # Validate required fields
                if 'coordinates' not in parsed_cmd:
                    return "❌ Error: Could not find coordinates in your request. Please specify point coordinates like '120 180 100'"
                    
                if 'input_file' not in parsed_cmd:
                    return "❌ Error: Could not find input file. Please specify the image file path."
                    
                if 'output_directory' not in parsed_cmd:
                    return "❌ Error: Could not find output directory. Please specify where to save results."
                    
                x, y, z = parsed_cmd['coordinates']
                result = self.cli.submit_task(
                    parsed_cmd['input_file'],
                    parsed_cmd['output_directory'],
                    x, y, z,
                    parsed_cmd.get('patient_id'),
                    parsed_cmd.get('series_uid')
                )
                return f"✅ {result}"
                
            elif parsed_cmd['command'] == 'status':
                if 'task_id' not in parsed_cmd:
                    return "❌ Error: Could not find task ID in your request."
                    
                result = self.cli.check_status(parsed_cmd['task_id'])
                return f"📊 {result}"
                
            elif parsed_cmd['command'] == 'list':
                result = self.cli.list_images()
                return f"📁 {result}"
                
        except Exception as e:
            return f"❌ Error: {str(e)}"
        finally:
            self.cli.stop_server()
            
    def process_natural_language(self, text: str) -> str:
        """Main method to process natural language input"""
        print(f"🤖 Understanding: '{text}'")
        
        parsed = self.parse_natural_language(text)
        print(f"🔍 Parsed as: {json.dumps(parsed, indent=2)}")
        
        return self.execute_command(parsed)

def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Vista3D Natural Language Interface")
        print("Usage: python3 vista3d_nlp.py \"<natural language command>\"")
        print("\nExamples:")
        print('  "Submit a task with coordinates 120 180 100 using image.nii.gz to output folder"')
        print('  "Check status of task vista3d_point_1751302930147"')
        print('  "List available images"')
        print('  "Segment the brain image at point 150 200 110 and save to /tmp/results"')
        return
        
    command = " ".join(sys.argv[1:])
    
    nlp_client = Vista3DNLPClient()
    result = nlp_client.process_natural_language(command)
    print(f"\n{result}")

if __name__ == "__main__":
    main()