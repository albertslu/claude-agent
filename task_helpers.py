#!/usr/bin/env python3
"""
ARTDaemon Task Submission Helpers

Helper functions for creating and submitting tasks to the ARTDaemon system.
These functions can be used with MCP tools to automate task creation.
"""

import json
import time
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Base path for tasks - can be overridden
def get_tasks_base_path() -> str:
    """Get the base path for tasks from environment or default."""
    return os.getenv("VISTA3D_TASKS_BASE_PATH", os.path.expanduser("~/tasks-live"))

def generate_task_id(prefix: str = "task") -> str:
    """Generate a unique task ID with timestamp."""
    timestamp = int(time.time() * 1000)  # milliseconds
    return f"{prefix}_{timestamp}"

def create_vista3d_point_task(
    input_file: str,
    output_directory: str,
    point_coordinates: List[int],
    point_type: str = "positive",
    label: int = 1,
    additional_points: Optional[List[Dict]] = None,
    task_id: Optional[str] = None
) -> Dict:
    """
    Create a Vista3D point-based segmentation task.
    
    Args:
        input_file: Path to input NIfTI file
        output_directory: Path to output directory
        point_coordinates: [x, y, z] coordinates for the seed point
        point_type: "positive" or "negative"
        label: Integer label for the segmentation
        additional_points: List of additional points with coordinates and type
        task_id: Custom task ID (auto-generated if None)
    
    Returns:
        Dictionary with task parameters
    """
    if task_id is None:
        task_id = generate_task_id("vista3d_point")
    
    task = {
        "task_id": task_id,
        "input_file": input_file,
        "output_directory": output_directory,
        "segmentation_type": "point",
        "point_coordinates": point_coordinates,
        "point_type": point_type,
        "label": label
    }
    
    if additional_points:
        task["additional_points"] = additional_points
    
    return task

def create_sam_task(
    input_file: str,
    output_file: str,
    output_folder: str,
    image_series_uid: str,
    modality: str = "MR",
    box: Optional[List[int]] = None,
    roi_index: Optional[List[int]] = None,
    roi_name: str = "sam1",
    sam_mode: int = 0,
    current_slice: int = 96,
    value: int = 1
) -> Dict:
    """
    Create a SAM (Segment Anything Model) task.
    
    Args:
        input_file: Path to input NIfTI file
        output_file: Path to output segmentation file
        output_folder: Path to output folder
        image_series_uid: DICOM series UID
        modality: Image modality (MR, CT, etc.)
        box: Bounding box [x1, y1, x2, y2]
        roi_index: ROI center point [x, y]
        roi_name: Name for the ROI
        sam_mode: SAM processing mode
        current_slice: Current slice index
        value: Segmentation value
    
    Returns:
        Dictionary with task parameters
    """
    task = {
        "InputImageFile": input_file,
        "OutputImageFile": output_file,
        "OutputFileFolder": output_folder,
        "imageSeriesUID": image_series_uid,
        "modality": modality,
        "ROIName": roi_name,
        "sam_mode": sam_mode,
        "current_slice": current_slice,
        "value": value
    }
    
    if box:
        task["Box"] = box
    if roi_index:
        task["ROIIndex"] = roi_index
    
    return task

def create_segman_task(
    short_name: str,
    db_table_name: str,
    template_task_file: str,
    task_id: str,
    user: str = "test",
    user_group: str = "User",
    confirmation: Optional[str] = None
) -> Dict:
    """
    Create a Segman template task.
    
    Args:
        short_name: Short name for the task
        db_table_name: Database table name (MR, CT, etc.)
        template_task_file: Path to template task file
        task_id: Unique task identifier
        user: Username
        user_group: User group
        confirmation: Confirmation prompt
    
    Returns:
        Dictionary with task parameters
    """
    task = {
        "ShortName": short_name,
        "DBTableName": db_table_name,
        "TemplateTaskFile": template_task_file,
        "UserGroup": user_group,
        "TaskID": task_id,
        "user": user
    }
    
    if confirmation:
        task["Confirmation"] = confirmation
    
    return task

def submit_task(task: Dict, task_folder: str, filename: Optional[str] = None, tasks_base_path: Optional[str] = None) -> str:
    """
    Submit a task by writing JSON file to the appropriate folder.
    
    Args:
        task: Task dictionary
        task_folder: Folder name under tasks base path
        filename: Custom filename (auto-generated if None)
        tasks_base_path: Base path for tasks (uses default if None)
    
    Returns:
        Path to the created task file
    """
    if filename is None:
        if "task_id" in task:
            filename = f"{task['task_id']}.json"
        else:
            filename = f"{generate_task_id()}.json"
    
    # Ensure filename ends with .json
    if not filename.endswith('.json'):
        filename += '.json'
    
    base_path = tasks_base_path or get_tasks_base_path()
    folder_path = Path(base_path) / task_folder
    folder_path.mkdir(parents=True, exist_ok=True)
    
    task_file_path = folder_path / filename
    
    with open(task_file_path, 'w') as f:
        json.dump(task, f, indent=2)
    
    return str(task_file_path)

def submit_vista3d_task(
    input_file: str,
    output_directory: str,
    point_coordinates: List[int],
    point_type: str = "positive",
    label: int = 1,
    additional_points: Optional[List[Dict]] = None,
    tasks_base_path: Optional[str] = None
) -> str:
    """
    Create and submit a Vista3D point task.
    
    Returns:
        Path to the created task file
    """
    task = create_vista3d_point_task(
        input_file=input_file,
        output_directory=output_directory,
        point_coordinates=point_coordinates,
        point_type=point_type,
        label=label,
        additional_points=additional_points
    )
    
    return submit_task(task, "Vista3D", tasks_base_path=tasks_base_path)

def submit_sam_task(
    input_file: str,
    output_file: str,
    output_folder: str,
    image_series_uid: str,
    modality: str = "MR",
    box: Optional[List[int]] = None,
    roi_index: Optional[List[int]] = None,
    tasks_base_path: Optional[str] = None
) -> str:
    """
    Create and submit a SAM task.
    
    Returns:
        Path to the created task file
    """
    task = create_sam_task(
        input_file=input_file,
        output_file=output_file,
        output_folder=output_folder,
        image_series_uid=image_series_uid,
        modality=modality,
        box=box,
        roi_index=roi_index
    )
    
    return submit_task(task, "SAM", tasks_base_path=tasks_base_path)

def check_task_status(task_id: str, task_folder: str, tasks_base_path: Optional[str] = None) -> Dict:
    """
    Check the status of a submitted task.
    
    Args:
        task_id: Task ID to check
        task_folder: Folder where task was submitted
        tasks_base_path: Base path for tasks (uses default if None)
    
    Returns:
        Dictionary with status information
    """
    base_path = tasks_base_path or get_tasks_base_path()
    folder_path = Path(base_path) / task_folder
    
    # Check if task is still in queue
    pending_file = folder_path / f"{task_id}.json"
    if pending_file.exists():
        return {"status": "pending", "file": str(pending_file)}
    
    # Check if task is processed
    processed_folder = folder_path / "processed"
    processed_file = processed_folder / f"{task_id}.json"
    result_file = processed_folder / f"{task_id}_result.json"
    
    if processed_file.exists():
        status = {"status": "processed", "file": str(processed_file)}
        if result_file.exists():
            with open(result_file, 'r') as f:
                status["result"] = json.load(f)
        return status
    
    # Check if task failed
    failed_folder = folder_path / "failed"
    failed_file = failed_folder / f"{task_id}.json"
    
    if failed_file.exists():
        return {"status": "failed", "file": str(failed_file)}
    
    return {"status": "not_found"}

# Example usage functions for few-shot learning
def example_brain_metastases_segmentation(
    input_file: str = "/path/to/image.nii.gz",
    output_dir: str = "/path/to/output/Vista3D/",
    tasks_base_path: Optional[str] = None
):
    """Example: Submit a brain metastases segmentation task."""
    # Point coordinates for a suspected metastasis
    point_coords = [113, 203, 96]
    
    task_file = submit_vista3d_task(
        input_file=input_file,
        output_directory=output_dir,
        point_coordinates=point_coords,
        point_type="positive",
        label=1,
        tasks_base_path=tasks_base_path
    )
    
    print(f"Submitted brain metastases segmentation task: {task_file}")
    return task_file

def example_interactive_sam_segmentation(
    input_file: str = "/path/to/image.nii.gz",
    output_file: str = "/path/to/output/SAM/SAM_raw.nii.gz",
    output_folder: str = "/path/to/output/SAM/",
    series_uid: str = "1.3.12.2.1107.5.2.43.66059.9420413823708647.0.0.0",
    tasks_base_path: Optional[str] = None
):
    """Example: Submit an interactive SAM segmentation task."""
    # Bounding box around region of interest
    bounding_box = [194, 104, 211, 121]
    roi_center = [202, 112]
    
    task_file = submit_sam_task(
        input_file=input_file,
        output_file=output_file,
        output_folder=output_folder,
        image_series_uid=series_uid,
        modality="MR",
        box=bounding_box,
        roi_index=roi_center,
        tasks_base_path=tasks_base_path
    )
    
    print(f"Submitted SAM segmentation task: {task_file}")
    return task_file

if __name__ == "__main__":
    print("ARTDaemon Task Helpers")
    print("Available functions:")
    print("- submit_vista3d_task(): Point-based 3D segmentation")
    print("- submit_sam_task(): Interactive segmentation with SAM")
    print("- check_task_status(): Check task processing status")
    print("- example_brain_metastases_segmentation(): Example brain mets task")
    print("- example_interactive_sam_segmentation(): Example SAM task")