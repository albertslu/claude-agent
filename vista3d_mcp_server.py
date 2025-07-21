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
import sqlite3
import re
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional


class Vista3DMCPServer:
    """MCP Server for Vista3D task management."""
    
    def __init__(self, tasks_base_path: Optional[str] = None, db_path: Optional[str] = None):
        # Set up logging
        self._setup_logging()
        
        # Use provided path, environment variable, or default
        self.tasks_base_path = (
            tasks_base_path or 
            os.getenv("VISTA3D_TASKS_BASE_PATH") or 
            os.path.expanduser("~/tasks-live")
        )
        
        # Database path configuration - get from config
        if db_path:
            self.db_path = db_path
        elif os.getenv("VISTA3D_DB_PATH"):
            self.db_path = os.getenv("VISTA3D_DB_PATH")
        else:
            # Get from config file
            from config import Config
            config = Config()
            self.db_path = config.get_database_path()
        
        self.vista3d_tasks_path = Path(self.tasks_base_path) / "Vista3D"
        self.vista3d_processed_path = Path(self.tasks_base_path.replace("tasks-live", "tasks-history")) / "Vista3d"
        
        # Validate and create directories
        self._validate_and_create_directories()
        
        self.logger.info(f"Vista3D MCP Server initialized:")
        self.logger.info(f"  Tasks base path: {self.tasks_base_path}")
        self.logger.info(f"  Database path: {self.db_path}")
    
    def _setup_logging(self):
        """Set up logging for debugging MCP server operations."""
        # Create logger
        self.logger = logging.getLogger('Vista3DMCPServer')
        self.logger.setLevel(logging.DEBUG)
        
        # Create console handler that writes to stderr (so it doesn't interfere with stdout MCP communication)
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.DEBUG)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        
        # Add handler to logger
        if not self.logger.handlers:
            self.logger.addHandler(handler)
    
    def _classify_mr_sequence(self, series_description: str) -> List[str]:
        """
        Classify MR sequence using sophisticated regex patterns from SegmanRepo.
        Returns list of sequence types that match (e.g., ['T1', 'T1NC'])
        """
        if not series_description:
            return []
        
        matches = []
        desc = series_description.strip()
        
        # T1 general filter (includes both contrast and non-contrast)
        t1_pattern = r"(^|[_\-\s])(?!.*FLAIR)[a-zA-Z0-9]*?(T1(W|WI)?|T1[-_ ]?weighted|T1W|MP[_\-\s]?RAGE|SPGR|FSPGR|FLASH|GRE|FFE|TFE|MP2RAGE|BRAVO|VIBE|LAVA|THRIVE|T1C|T1CE|mASTAR)([_\-\s]|$)"
        if re.search(t1_pattern, desc, re.IGNORECASE):
            matches.append("T1")
        
        # T1C (T1 with contrast)
        t1c_pattern = r"(^|[\s_\-]).*?((POST|GAD|CONTRAST|CE|\+C).*?(T1W|T1(W|WI)?|T1[-_ ]?WEIGHTED|MP[\s_\-]?RAGE|SPGR|FSPGR|FLASH|GRE|FFE|TFE|MP2RAGE|BRAVO)|(T1W|T1(W|WI)?|T1[-_ ]?WEIGHTED|MP[\s_\-]?RAGE|SPGR|FSPGR|FLASH|GRE|FFE|TFE|MP2RAGE|BRAVO).*?(POST|GAD|CONTRAST|CE|\+C)|VIBE|LAVA|THRIVE|T1C|T1CE|MASTAR)([\s_\-]|$)"
        if re.search(t1c_pattern, desc, re.IGNORECASE):
            matches.append("T1C")
        
        # T1NC (T1 without contrast) - only if T1 matches but T1C doesn't
        if "T1" in matches and "T1C" not in matches:
            t1nc_pattern = r"^(?!.*(POST|GAD|CONTRAST|CE|\+C|VIBE|LAVA|THRIVE|T1C|T1CE|MASTAR)).*?([_\-\s]|^)[A-Z0-9]*?(T1(W|WI)?|T1[-_ ]?WEIGHTED|T1W|MP[\s_\-]?RAGE|SPGR|FSPGR|FLASH|GRE|FFE|TFE|MP2RAGE|BRAVO)([_\-\s]|$)"
            if re.search(t1nc_pattern, desc, re.IGNORECASE):
                matches.append("T1NC")
        
        # T2 filter
        t2_pattern = r"^(?!.*(FLAIR|T1W|T1WI|T1[-_ ]?WEIGHTED|T1)).*?([_\-\s]|^)(T2(W|WI)?|T2[-_ ]?WEIGHTED|STIR|FSE|TSE|CISS|SPACE|VISTA|CUBE|PROP(?:ELLER)?|BLADE|FIESTA|TRUEFISP|BSSFP|DRIVE)([_\-\s]|$)"
        if re.search(t2_pattern, desc, re.IGNORECASE):
            matches.append("T2")
        
        # FLAIR filter
        flair_pattern = r"^(?!.*(T1W|T1WI|T1[-_ ]?WEIGHTED|T1)).*?(FLAIR|T2[\s_\-]?FLAIR|FLAIR[\s_\-]?T2|IR[\s_\-]?(T2|FSE|TSE)?[\s_\-]?FLAIR|FLAIRV\d*|FLUID[\s_\-]?ATTENUATED)([\s_\-]|$)"
        if re.search(flair_pattern, desc, re.IGNORECASE):
            matches.append("FLAIR")
        
        # DWI filter
        dwi_pattern = r"(^|[_\-\s])[a-zA-Z0-9]*?(DWI(_?EPI)?|EPI[_\- ]?DWI|Diffusion(_?Weighted)?|DTI(_\d+dir)?|ADC)([_\-\s]|$)"
        if re.search(dwi_pattern, desc, re.IGNORECASE):
            matches.append("DWI")
        
        return matches
    
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
    

    def query_patient_images(self, modality: Optional[str] = None, 
                           filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Query SQLite database to find patient images based on actual database schema
        
        Args:
            modality: Imaging modality (MR, CT, PT) - determines which table to query
            filters: Dictionary of column_name: value pairs for filtering
        """
        
        if not Path(self.db_path).exists():
            return [{"error": f"Database not found at {self.db_path}"}]
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.cursor()
            
            # Determine which table to query based on modality
            if modality == "MR":
                table = "MR"
            elif modality == "CT":
                table = "CT" 
            elif modality == "PT":
                table = "PT"
            else:
                # Default to MR if no modality specified
                table = "MR"
            
            # Load schema from JSON file
            schema_path = Path(__file__).parent / "rtplandb_schema.json"
            try:
                with open(schema_path, 'r') as f:
                    schema = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                return [{"error": f"Could not load schema: {e}"}]
            
            # Get columns from schema for the specific table
            if table not in schema.get("tables", {}):
                return [{"error": f"Table {table} not found in schema"}]
            
            table_columns = list(schema["tables"][table]["columns"].keys())
            self.logger.info(f"📋 Using table {table} with {len(table_columns)} columns from schema")
            
            # Build column list for SELECT statement - use all columns from schema
            select_columns = []
            for col in table_columns:
                # Use snake_case alias for all columns
                alias = col.lower().replace(' ', '_')
                select_columns.append(f"{col} as {alias}")
            
            self.logger.debug(f"🔍 Selected {len(select_columns)} columns with proper aliases")
            
            # Build dynamic query based on provided filters
            query_parts = []
            params = []
            requested_sequence_type = None
            
            base_query = f"""
            SELECT DISTINCT 
                {', '.join(select_columns)}
            FROM {table} 
            WHERE 1=1
            """
            
            # Apply filters based on actual schema columns
            if filters:
                for filter_key, value in filters.items():
                    if filter_key == 'sequence_type':
                        # Special handling for sequence type filtering (post-processing)
                        requested_sequence_type = value
                        continue
                    
                    # Find matching column in schema (case-insensitive, flexible matching)
                    matched_column = None
                    for schema_column in table_columns:
                        # Direct match
                        if filter_key == schema_column:
                            matched_column = schema_column
                            break
                        # Case-insensitive match
                        elif filter_key.lower() == schema_column.lower():
                            matched_column = schema_column
                            break
                        # Snake_case to CamelCase match
                        elif filter_key.lower().replace('_', '') == schema_column.lower().replace('_', ''):
                            matched_column = schema_column
                            break
                    
                    if matched_column:
                        # Use LIKE for text fields that might contain partial matches
                        text_search_fields = ['PatientID', 'PatientName', 'SeriesDescription', 'ProtocolName']
                        if matched_column in text_search_fields:
                            query_parts.append(f"AND {matched_column} LIKE ?")
                            params.append(f"%{value}%")
                        else:
                            # Use exact match for other fields
                            query_parts.append(f"AND {matched_column} = ?")
                            params.append(value)
                        self.logger.debug(f"🔍 Mapped filter '{filter_key}' -> '{matched_column}' = '{value}'")
                    else:
                        self.logger.warning(f"⚠️  Filter column '{filter_key}' not found in {table} table schema (available: {table_columns})")
            
            final_query = base_query + " ".join(query_parts) + " ORDER BY StudyDate DESC, SeriesDate DESC"
            
            self.logger.debug(f"🗃️ SQL Query: {final_query}")
            self.logger.debug(f"🗃️ SQL Parameters: {params}")
            
            cursor.execute(final_query, params)
            rows = cursor.fetchall()
            
            self.logger.info(f"📋 Raw SQL Results: {len(rows)} rows from database")
            
            results = []
            for row in rows:
                # Initialize classification info
                classified_sequences = []
                
                # Apply sophisticated sequence filtering for MR images
                if requested_sequence_type and table == "MR":
                    # Get series description safely from row
                    series_desc = ""
                    for key in row.keys():
                        if key.lower() == "series_description":
                            series_desc = row[key] or ""
                            break
                    
                    classified_sequences = self._classify_mr_sequence(series_desc)
                    
                    # Check if the requested sequence type matches any classified types
                    requested_type = requested_sequence_type.upper()
                    
                    # Log the classification for debugging
                    self.logger.debug(f"🧬 Sequence Classification: '{series_desc}' -> {classified_sequences}")
                    
                    if requested_type not in classified_sequences:
                        # Special case handling for common aliases
                        if requested_type == "T1_CONTRAST" and "T1C" not in classified_sequences:
                            self.logger.debug(f"❌ Filtered out: {requested_type} not in {classified_sequences}")
                            continue
                        elif requested_type == "T1_NO_CONTRAST" and "T1NC" not in classified_sequences:
                            self.logger.debug(f"❌ Filtered out: {requested_type} not in {classified_sequences}")
                            continue
                        elif requested_type not in classified_sequences:
                            self.logger.debug(f"❌ Filtered out: {requested_type} not in {classified_sequences}")
                            continue
                    
                    self.logger.debug(f"✅ Matched: {requested_type} in {classified_sequences}")
                
                # Build result dictionary using snake_case aliases from SELECT
                result = {}
                
                # Add all available columns - row.keys() should have the snake_case aliases
                for key in row.keys():
                    result[key] = row[key]
                
                # Add computed fields if we have the necessary columns
                patient_id_val = ""
                series_instance_uid_val = ""
                
                # Find patient_id and series_instance_uid safely from row keys
                for key in row.keys():
                    if key.lower() in ["patientid", "patient_id"]:
                        patient_id_val = row[key] or ""
                    elif key.lower() in ["seriesinstanceuid", "series_instance_uid"]:
                        series_instance_uid_val = row[key] or ""
                
                # Add constructed paths if we have the necessary data
                if patient_id_val and series_instance_uid_val:
                    result["input_file"] = f"C:\\ARTDaemon\\Segman\\dcm2nifti\\{patient_id_val}\\{series_instance_uid_val}\\image.nii.gz"
                    result["output_directory"] = f"C:\\ARTDaemon\\Segman\\dcm2nifti\\{patient_id_val}\\{series_instance_uid_val}\\Vista3D\\"
                
                # Add classification info for MR sequences
                if table == "MR":
                    result["classified_sequences"] = classified_sequences
                
                results.append(result)
            
            conn.close()
            
            if requested_sequence_type and table == "MR":
                self.logger.info(f"🎯 Sequence Filtering Summary:")
                self.logger.info(f"  Requested sequence type: {requested_sequence_type}")
                self.logger.info(f"  Raw database results: {len(rows)} rows")
                self.logger.info(f"  After sophisticated filtering: {len(results)} results")
            
            return results
            
        except sqlite3.Error as e:
            return [{"error": f"Database query failed: {str(e)}"}]
        except Exception as e:
            return [{"error": f"Unexpected error: {str(e)}"}]
    
    def handle_mcp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP protocol requests."""
        method = request.get("method")
        request_id = request.get("id")
        
        self.logger.debug(f"🔵 MCP Request: {method} (ID: {request_id})")
        
        if method == "tools/list":
            self.logger.debug("📋 Returning list of available tools")
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
                            "name": "query_patient_images",
                            "description": "Query SQLite database to find patient images using dynamic schema-based filtering",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "modality": {
                                        "type": "string",
                                        "description": "Imaging modality (MR, CT, PT) - determines which table to query"
                                    },
                                    "filters": {
                                        "type": "object",
                                        "description": "Dictionary of column_name: value pairs for filtering. Column names should match database schema. Use 'sequence_type' for MR sequence filtering (T1, T1C, T1NC, T2, FLAIR, DWI, etc.)",
                                        "additionalProperties": {
                                            "type": "string"
                                        }
                                    }
                                },
                                "required": []
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
            
            self.logger.info(f"🔧 Tool Call: {tool_name}")
            self.logger.info(f"📝 Arguments: {json.dumps(arguments, indent=2)}")
            
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
                
                elif tool_name == "query_patient_images":
                    # Extract query parameters
                    modality = arguments.get("modality")
                    filters = arguments.get("filters", {})
                    
                    self.logger.info(f"🔍 Database Query Parameters:")
                    self.logger.info(f"  modality: {modality}")
                    self.logger.info(f"  filters: {filters}")
                    
                    # Query the database
                    results = self.query_patient_images(
                        modality=modality,
                        filters=filters
                    )
                    
                    self.logger.info(f"📊 Query Results: Found {len(results)} images")
                    
                    # Format results for display
                    if results and "error" not in results[0]:
                        results_text = f"Found {len(results)} patient image(s):\n"
                        for i, result in enumerate(results, 1):
                            # Find patient info using flexible key matching
                            patient_id = result.get('patientid') or result.get('patient_id', 'N/A')
                            patient_name = result.get('patientname') or result.get('patient_name', 'N/A')
                            modality = result.get('modality', 'N/A')
                            study_date = result.get('studydate') or result.get('study_date', 'N/A')
                            
                            results_text += f"\n{i}. Patient: {patient_id} ({patient_name})\n"
                            results_text += f"   Modality: {modality}\n"
                            results_text += f"   Study Date: {study_date}\n"
                            results_text += f"   Input File: {result.get('input_file', 'N/A')}\n"
                            results_text += f"   Output Directory: {result.get('output_directory', 'N/A')}\n"
                            if result.get('sequence_name'):
                                results_text += f"   Sequence: {result.get('sequence_name')}\n"
                            if result.get('contrast_agent'):
                                results_text += f"   Contrast: {result.get('contrast_agent')}\n"
                    else:
                        if results and "error" in results[0]:
                            results_text = f"Database query error: {results[0]['error']}"
                        else:
                            results_text = "No patient images found matching the criteria."
                    
                    return {
                        "jsonrpc": "2.0",
                        "id": request.get("id"),
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": results_text
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
                self.logger.error(f"❌ Tool Call Error: {tool_name} failed with: {str(e)}")
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    }
                }
        
        elif method == "initialize":
            self.logger.info("🚀 MCP Server Initialize")
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