#!/usr/bin/env python3
"""
Vista3D MCP Server

This MCP server provides tools for submitting and monitoring Vista3D segmentation tasks
in the ARTDaemon system. It uses stdio transport for communication with Claude Code.
"""

import json
import sys
import time
import os
from pathlib import Path
from typing import Dict, List, Any, Optional


class Vista3DMCPServer:
    """MCP Server for Vista3D task management."""
    
    def __init__(self):
        self.tasks_base_path = "/home/lbert/tasks-live"
        self.vista3d_tasks_path = Path(self.tasks_base_path) / "Vista3D" / "tasks"
        self.vista3d_processed_path = Path(self.tasks_base_path) / "Vista3D" / "processed"
        
        # Ensure directories exist
        self.vista3d_tasks_path.mkdir(parents=True, exist_ok=True)
        self.vista3d_processed_path.mkdir(parents=True, exist_ok=True)
    
    def generate_task_id(self, prefix: str = "vista3d_point") -> str:
        """Generate a unique task ID with timestamp."""
        timestamp = int(time.time() * 1000)
        return f"{prefix}_{timestamp}"
    
    def create_vista3d_task(
        self,
        point_coordinates: List[int],
        input_file: str = "C:/ARTDaemon/Segman/dcm2nifti/GGJJVZPCBPSSDVRV/MR.1.3.12.2.1107.5.2.43.66059.9420413823708647.0.0.0/image.nii.gz",
        output_directory: str = "C:/ARTDaemon/Segman/dcm2nifti/GGJJVZPCBPSSDVRV/MR.1.3.12.2.1107.5.2.43.66059.9420413823708647.0.0.0/Vista3D/",
        point_type: str = "positive",
        label: int = 1,
        additional_points: Optional[List[Dict]] = None,
        patient_id: str = "GGJJVZPCBPSSDVRV",
        modality: str = "MR",
        series_uid: str = "1.3.12.2.1107.5.2.43.66059.9420413823708647.0.0.0",
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a Vista3D point-based segmentation task."""
        
        if task_id is None:
            task_id = self.generate_task_id()
        
        task = {
            "task_id": task_id,
            "input_file": input_file,
            "output_directory": output_directory,
            "segmentation_type": "point",
            "point_coordinates": point_coordinates,
            "point_type": point_type,
            "label": label,
            "patientId": patient_id,
            "modality": modality,
            "seriesInstanceUID": series_uid
        }
        
        if additional_points:
            task["additional_points"] = additional_points
        else:
            task["additional_points"] = []
        
        return task
    
    def submit_task(self, task: Dict[str, Any]) -> str:
        """Submit a task by writing JSON file to Vista3D tasks folder."""
        task_id = task["task_id"]
        filename = f"{task_id}.json"
        task_file_path = self.vista3d_tasks_path / filename
        
        try:
            with open(task_file_path, 'w') as f:
                json.dump(task, f, indent=2)
            return str(task_file_path)
        except Exception as e:
            raise Exception(f"Failed to submit task: {str(e)}")
    
    def check_task_status(self, task_id: str) -> Dict[str, Any]:
        """Check the status of a submitted task."""
        
        # Check if task is still pending in tasks folder
        pending_file = self.vista3d_tasks_path / f"{task_id}.json"
        if pending_file.exists():
            return {
                "status": "pending",
                "task_id": task_id,
                "message": "Task is queued for processing"
            }
        
        # Check if task is processed
        processed_file = self.vista3d_processed_path / f"{task_id}.json"
        result_file = self.vista3d_processed_path / f"{task_id}_result.json"
        
        if processed_file.exists():
            status = {
                "status": "processed",
                "task_id": task_id,
                "processed_file": str(processed_file)
            }
            
            if result_file.exists():
                try:
                    with open(result_file, 'r') as f:
                        result_data = json.load(f)
                    status["result"] = result_data
                    if "output_mask" in result_data:
                        status["output_mask"] = result_data["output_mask"]
                except Exception as e:
                    status["result_error"] = str(e)
            
            return status
        
        # Check if task failed
        failed_folder = Path(self.tasks_base_path) / "Vista3D" / "failed"
        failed_file = failed_folder / f"{task_id}.json"
        
        if failed_file.exists():
            return {
                "status": "failed",
                "task_id": task_id,
                "failed_file": str(failed_file)
            }
        
        return {
            "status": "not_found",
            "task_id": task_id,
            "message": "Task not found in any location"
        }
    
    def list_available_images(self) -> List[str]:
        """List available input images in the system."""
        # This would scan the dcm2nifti folder structure
        # For now, return the known test image
        return [
            "C:/ARTDaemon/Segman/dcm2nifti/GGJJVZPCBPSSDVRV/MR.1.3.12.2.1107.5.2.43.66059.9420413823708647.0.0.0/image.nii.gz"
        ]
    
    def handle_mcp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP protocol requests."""
        method = request.get("method")
        
        if method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "tools": [
                        {
                            "name": "submit_vista3d_point_task",
                            "description": "Submit a point-based segmentation task to Vista3D",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "point_coordinates": {
                                        "type": "array",
                                        "items": {"type": "integer"},
                                        "minItems": 3,
                                        "maxItems": 3,
                                        "description": "3D coordinates [x, y, z] for the seed point"
                                    },
                                    "point_type": {
                                        "type": "string",
                                        "enum": ["positive", "negative"],
                                        "default": "positive",
                                        "description": "Type of point prompt"
                                    },
                                    "additional_points": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "coordinates": {
                                                    "type": "array",
                                                    "items": {"type": "integer"},
                                                    "minItems": 3,
                                                    "maxItems": 3
                                                },
                                                "type": {
                                                    "type": "string",
                                                    "enum": ["positive", "negative"]
                                                }
                                            },
                                            "required": ["coordinates", "type"]
                                        },
                                        "description": "Additional points for refinement"
                                    },
                                    "input_file": {
                                        "type": "string",
                                        "description": "Path to input NIfTI file (optional, uses default)"
                                    }
                                },
                                "required": ["point_coordinates"]
                            }
                        },
                        {
                            "name": "check_vista3d_task_status",
                            "description": "Check the status of a Vista3D task",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "task_id": {
                                        "type": "string",
                                        "description": "Task ID to check"
                                    }
                                },
                                "required": ["task_id"]
                            }
                        },
                        {
                            "name": "list_available_images",
                            "description": "List available input images for processing",
                            "inputSchema": {
                                "type": "object",
                                "properties": {}
                            }
                        }
                    ]
                }
            }
        
        elif method == "tools/call":
            tool_name = request.get("params", {}).get("name")
            arguments = request.get("params", {}).get("arguments", {})
            
            try:
                if tool_name == "submit_vista3d_point_task":
                    # Extract parameters
                    point_coordinates = arguments.get("point_coordinates")
                    point_type = arguments.get("point_type", "positive")
                    additional_points = arguments.get("additional_points", [])
                    input_file = arguments.get("input_file")
                    
                    # Create task
                    task_params = {
                        "point_coordinates": point_coordinates,
                        "point_type": point_type,
                        "additional_points": additional_points
                    }
                    if input_file:
                        task_params["input_file"] = input_file
                    
                    task = self.create_vista3d_task(**task_params)
                    task_file_path = self.submit_task(task)
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Successfully submitted Vista3D task!\n\nTask ID: {task['task_id']}\nTask file: {task_file_path}\nPoint coordinates: {point_coordinates}\nPoint type: {point_type}\n\nTask is now queued for processing by ARTDaemon."
                                }
                            ]
                        }
                    }
                
                elif tool_name == "check_vista3d_task_status":
                    task_id = arguments.get("task_id")
                    status = self.check_task_status(task_id)
                    
                    status_text = f"Task ID: {task_id}\nStatus: {status['status']}\n"
                    
                    if status['status'] == "processed":
                        if "output_mask" in status:
                            status_text += f"Output mask: {status['output_mask']}\n"
                        if "result" in status:
                            status_text += f"Result details: {json.dumps(status['result'], indent=2)}\n"
                    elif status['status'] == "pending":
                        status_text += "Task is still being processed...\n"
                    elif status['status'] == "failed":
                        status_text += f"Task failed. Check file: {status.get('failed_file', 'N/A')}\n"
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": status_text
                                }
                            ]
                        }
                    }
                
                elif tool_name == "list_available_images":
                    images = self.list_available_images()
                    images_text = "Available input images:\n" + "\n".join(f"- {img}" for img in images)
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": images_text
                                }
                            ]
                        }
                    }
                
                else:
                    return {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "error": {
                            "code": -32601,
                            "message": f"Unknown tool: {tool_name}"
                        }
                    }
            
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    }
                }
        
        elif method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "vista3d-mcp-server",
                        "version": "1.0.0"
                    }
                }
            }
        
        else:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32601,
                    "message": f"Unknown method: {method}"
                }
            }
    
    def run(self):
        """Run the MCP server using stdio transport."""
        try:
            for line in sys.stdin:
                try:
                    request = json.loads(line.strip())
                    response = self.handle_mcp_request(request)
                    print(json.dumps(response), flush=True)
                except json.JSONDecodeError:
                    # Invalid JSON input
                    continue
                except Exception as e:
                    # Log error to stderr (won't interfere with MCP protocol)
                    print(f"Error processing request: {e}", file=sys.stderr)
                    continue
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f"Server error: {e}", file=sys.stderr)


if __name__ == "__main__":
    server = Vista3DMCPServer()
    server.run()