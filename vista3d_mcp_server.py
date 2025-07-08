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
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional


class Vista3DMCPServer:
    """MCP Server for Vista3D task management."""
    
    def __init__(self, tasks_base_path: Optional[str] = None):
        # Use provided path, environment variable, or default
        self.tasks_base_path = (
            tasks_base_path or 
            os.getenv("VISTA3D_TASKS_BASE_PATH") or 
            os.path.expanduser("~/tasks-live")
        )
        
        self.vista3d_tasks_path = Path(self.tasks_base_path) / "Vista3D"
        self.vista3d_processed_path = Path(self.tasks_base_path.replace("tasks-live", "tasks-history")) / "Vista3d"
        
        # Validate and create directories
        self._validate_and_create_directories()
    
    def _validate_and_create_directories(self):
        """Validate base path exists and create required directories."""
        base_path = Path(self.tasks_base_path)
        if not base_path.parent.exists():
            raise ValueError(f"Parent directory does not exist: {base_path.parent}")
        
        try:
            self.vista3d_tasks_path.mkdir(parents=True, exist_ok=True)
            # Don't create processed path - service handles TasksHistory automatically
        except PermissionError:
            raise ValueError(f"Permission denied creating directories in: {self.tasks_base_path}")
    
    def generate_task_id(self, prefix: str = "vista3d_point") -> str:
        """Generate a unique task ID with timestamp."""
        timestamp = int(time.time() * 1000)
        return f"{prefix}_{timestamp}"
    
    def create_vista3d_task(
        self,
        point_coordinates: List[int],
        input_file: str,
        output_directory: str,
        point_type: str = "positive",
        label: int = 1,
        additional_points: Optional[List[Dict]] = None,
        patient_id: Optional[str] = None,
        modality: str = "MR",
        series_uid: Optional[str] = None,
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
            "segmentation_prompts": [
                {
                    "target_output_label": label,
                    "positive_points": [point_coordinates] if point_type == "positive" else [],
                    "negative_points": [point_coordinates] if point_type == "negative" else []
                }
            ],
            "modality": modality
        }
        
        # Only include optional fields if provided
        if patient_id:
            task["patientId"] = patient_id
        if series_uid:
            task["seriesInstanceUID"] = series_uid
        
        if additional_points:
            # Add additional points to segmentation_prompts
            for point in additional_points:
                if point["type"] == "positive":
                    task["segmentation_prompts"][0]["positive_points"].append(point["coordinates"])
                elif point["type"] == "negative":
                    task["segmentation_prompts"][0]["negative_points"].append(point["coordinates"])
        
        return task
    
    def create_full_body_task(
        self,
        input_file: str,
        output_directory: str,
        description: str = None,
        patient_id: Optional[str] = None,
        series_uid: Optional[str] = None,
        task_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a full body segmentation task."""
        
        if task_id is None:
            task_id = self.generate_task_id(prefix="full_body")
        
        task = {
            "task_id": task_id,
            "input_file": input_file,
            "output_directory": output_directory,
            "segmentation_type": "full"
        }
        
        # Only include optional fields if provided
        if description:
            task["description"] = description
        if patient_id:
            task["patientId"] = patient_id
        if series_uid:
            task["seriesInstanceUID"] = series_uid
        
        return task
    
    def submit_task(self, task: Dict[str, Any]) -> str:
        """Submit a task by writing TSK file to Vista3D tasks folder."""
        task_id = task["task_id"]
        filename = f"{task_id}.tsk"
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
        pending_file = self.vista3d_tasks_path / f"{task_id}.tsk"
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
        
        
        return {
            "status": "not_found",
            "task_id": task_id,
            "message": "Task not found in any location"
        }
    
    def list_available_images(self, search_directory: str = None) -> List[str]:
        """List available input images in the system."""
        image_paths = []
        
        if search_directory:
            # Use provided directory
            if Path(search_directory).exists():
                for img_file in Path(search_directory).rglob("*.nii.gz"):
                    image_paths.append(str(img_file))
        else:
            # Check environment variable for image directories
            env_dirs = os.getenv("VISTA3D_IMAGE_DIRS", "")
            if env_dirs:
                image_dirs = [d.strip() for d in env_dirs.split(":") if d.strip()]
                for dir_path in image_dirs:
                    if dir_path and Path(dir_path).exists():
                        for img_file in Path(dir_path).rglob("*.nii.gz"):
                            image_paths.append(str(img_file))
        
        return image_paths
    
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
                                        "description": "Path to input NIfTI file (required)"
                                    },
                                    "output_directory": {
                                        "type": "string",
                                        "description": "Path to output directory (required)"
                                    },
                                    "patient_id": {
                                        "type": "string",
                                        "description": "Patient ID (optional)"
                                    },
                                    "series_uid": {
                                        "type": "string",
                                        "description": "Series instance UID (optional)"
                                    }
                                },
                                "required": ["point_coordinates", "input_file", "output_directory"]
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
                            "name": "submit_full_body_task",
                            "description": "Submit a full body segmentation task",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "input_file": {
                                        "type": "string",
                                        "description": "Path to input NIfTI file (required)"
                                    },
                                    "output_directory": {
                                        "type": "string",
                                        "description": "Path to output directory (required)"
                                    },
                                    "description": {
                                        "type": "string",
                                        "description": "Description of the segmentation task (optional)"
                                    },
                                    "patient_id": {
                                        "type": "string",
                                        "description": "Patient ID (optional)"
                                    },
                                    "series_uid": {
                                        "type": "string",
                                        "description": "Series instance UID (optional)"
                                    }
                                },
                                "required": ["input_file", "output_directory"]
                            }
                        },
                        {
                            "name": "list_available_images",
                            "description": "List available input images for processing",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "search_directory": {
                                        "type": "string",
                                        "description": "Directory path to search for .nii.gz images (optional)"
                                    }
                                }
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
                    # Extract required parameters
                    point_coordinates = arguments.get("point_coordinates")
                    input_file = arguments.get("input_file")
                    output_directory = arguments.get("output_directory")
                    
                    # Validate required parameters
                    if not point_coordinates:
                        raise ValueError("point_coordinates is required")
                    if not input_file:
                        raise ValueError("input_file is required")
                    if not output_directory:
                        raise ValueError("output_directory is required")
                    
                    # Extract optional parameters
                    point_type = arguments.get("point_type", "positive")
                    additional_points = arguments.get("additional_points", [])
                    patient_id = arguments.get("patient_id")
                    series_uid = arguments.get("series_uid")
                    
                    # Create task
                    task_params = {
                        "point_coordinates": point_coordinates,
                        "input_file": input_file,
                        "output_directory": output_directory,
                        "point_type": point_type,
                        "additional_points": additional_points,
                        "patient_id": patient_id,
                        "series_uid": series_uid
                    }
                    
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
                
                elif tool_name == "submit_full_body_task":
                    # Extract required parameters
                    input_file = arguments.get("input_file")
                    output_directory = arguments.get("output_directory")
                    
                    # Validate required parameters
                    if not input_file:
                        raise ValueError("input_file is required")
                    if not output_directory:
                        raise ValueError("output_directory is required")
                    
                    # Extract optional parameters
                    description = arguments.get("description")
                    patient_id = arguments.get("patient_id")
                    series_uid = arguments.get("series_uid")
                    
                    # Create task
                    task_params = {
                        "input_file": input_file,
                        "output_directory": output_directory,
                        "description": description,
                        "patient_id": patient_id,
                        "series_uid": series_uid
                    }
                    
                    task = self.create_full_body_task(**task_params)
                    task_file_path = self.submit_task(task)
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Successfully submitted full body segmentation task!\n\nTask ID: {task['task_id']}\nTask file: {task_file_path}\nInput file: {input_file}\nOutput directory: {output_directory}\n\nTask is now queued for processing by ARTDaemon."
                                }
                            ]
                        }
                    }
                
                elif tool_name == "list_available_images":
                    search_directory = arguments.get("search_directory")
                    images = self.list_available_images(search_directory)
                    if search_directory:
                        images_text = f"Available input images in {search_directory}:\n" + "\n".join(f"- {img}" for img in images)
                    else:
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
                    # Send proper error response
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": request.get("id") if 'request' in locals() else None,
                        "error": {
                            "code": -32603,
                            "message": f"Internal error: {str(e)}"
                        }
                    }
                    print(json.dumps(error_response), flush=True)
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f"Server error: {e}", file=sys.stderr)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Vista3D MCP Server for medical image segmentation tasks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default tasks directory (~/.tasks-live)
  python vista3d_mcp_server.py
  
  # Specify custom tasks directory
  python vista3d_mcp_server.py --tasks-path /path/to/tasks
  
  # Specify image directories for discovery
  python vista3d_mcp_server.py --tasks-path /data/tasks --image-dirs /data/images:/data/scans
  
Environment Variables:
  VISTA3D_TASKS_BASE_PATH    Default tasks directory (overridden by --tasks-path)
  VISTA3D_IMAGE_DIRS         Colon-separated image directories for discovery
        """
    )
    
    parser.add_argument(
        "--tasks-path",
        type=str,
        help="Base directory for task processing (default: ~/tasks-live or VISTA3D_TASKS_BASE_PATH)"
    )
    
    parser.add_argument(
        "--image-dirs",
        type=str,
        help="Colon-separated directories to search for input images (also sets VISTA3D_IMAGE_DIRS)"
    )
    
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    
    # Set environment variables from command line args
    if args.image_dirs:
        os.environ["VISTA3D_IMAGE_DIRS"] = args.image_dirs
    
    try:
        server = Vista3DMCPServer(tasks_base_path=args.tasks_path)
        server.run()
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("Server stopped by user", file=sys.stderr)
        sys.exit(0)
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        sys.exit(1)