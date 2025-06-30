#!/usr/bin/env python3
"""
Vista3D CLI - Command line interface for Vista3D MCP server
Simple wrapper around the MCP client for common tasks
"""

import json
import subprocess
import sys
import argparse
import time
from pathlib import Path

class Vista3DCLI:
    def __init__(self, tasks_path="/home/lbert/tasks-live", image_dirs="/home/lbert/claude-agent/sample_data"):
        self.server_command = [
            "python3", 
            "/home/lbert/claude-agent/vista3d_mcp_server.py",
            "--tasks-path", tasks_path,
            "--image-dirs", image_dirs
        ]
        self.process = None
        self.request_id = 0
        
    def start_server(self):
        """Start the Vista3D MCP server"""
        print(f"Starting Vista3D server...")
        self.process = subprocess.Popen(
            self.server_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0
        )
        
    def stop_server(self):
        """Stop the server"""
        if self.process:
            self.process.terminate()
            self.process.wait()
            
    def send_request(self, method, params=None):
        """Send MCP request"""
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "id": self.request_id
        }
        if params:
            request["params"] = params
            
        request_json = json.dumps(request)
        self.process.stdin.write(request_json + "\n")
        self.process.stdin.flush()
        
        response_line = self.process.stdout.readline()
        if not response_line:
            raise Exception("No response from server")
            
        response = json.loads(response_line.strip())
        
        if "error" in response:
            raise Exception(f"Server error: {response['error']}")
            
        return response
        
    def initialize(self):
        """Initialize connection"""
        return self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "vista3d-cli", "version": "1.0.0"}
        })
        
    def submit_task(self, input_file, output_dir, x, y, z, patient_id=None, series_uid=None):
        """Submit Vista3D segmentation task"""
        args = {
            "input_file": input_file,
            "output_directory": output_dir,
            "point_coordinates": [int(x), int(y), int(z)]
        }
        
        if patient_id:
            args["patient_id"] = patient_id
        if series_uid:
            args["series_uid"] = series_uid
            
        response = self.send_request("tools/call", {
            "name": "submit_vista3d_point_task",
            "arguments": args
        })
        
        return response["result"]["content"][0]["text"]
        
    def check_status(self, task_id):
        """Check task status"""
        response = self.send_request("tools/call", {
            "name": "check_vista3d_task_status", 
            "arguments": {"task_id": task_id}
        })
        
        return response["result"]["content"][0]["text"]
        
    def list_images(self):
        """List available images"""
        response = self.send_request("tools/call", {
            "name": "list_available_images",
            "arguments": {}
        })
        
        return response["result"]["content"][0]["text"]

def main():
    parser = argparse.ArgumentParser(description="Vista3D CLI - Medical image segmentation")
    parser.add_argument("--tasks-path", default="/home/lbert/tasks-live", help="Tasks directory path")
    parser.add_argument("--image-dirs", default="/home/lbert/claude-agent/sample_data", help="Image directories")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Submit command
    submit_parser = subparsers.add_parser("submit", help="Submit segmentation task")
    submit_parser.add_argument("input_file", help="Input NIfTI file path")
    submit_parser.add_argument("output_dir", help="Output directory path") 
    submit_parser.add_argument("x", type=int, help="Point X coordinate")
    submit_parser.add_argument("y", type=int, help="Point Y coordinate")
    submit_parser.add_argument("z", type=int, help="Point Z coordinate")
    submit_parser.add_argument("--patient-id", help="Patient ID")
    submit_parser.add_argument("--series-uid", help="Series UID")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check task status")
    status_parser.add_argument("task_id", help="Task ID to check")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List available images")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
        
    cli = Vista3DCLI(args.tasks_path, args.image_dirs)
    
    try:
        cli.start_server()
        cli.initialize()
        
        if args.command == "submit":
            result = cli.submit_task(
                args.input_file, args.output_dir, 
                args.x, args.y, args.z,
                args.patient_id, args.series_uid
            )
            print(result)
            
        elif args.command == "status":
            result = cli.check_status(args.task_id)
            print(result)
            
        elif args.command == "list":
            result = cli.list_images()
            print(result)
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        cli.stop_server()

if __name__ == "__main__":
    main()