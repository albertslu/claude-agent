# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Codebase Overview

This repository tracks Claude's interactions with the ARTDaemon task processing system. The ARTDaemon system processes medical imaging tasks through a folder-based queue system.

## Task System Architecture

### Task Folder Structure
The ARTDaemon system monitors folders under `/home/lbert/tasks-live/` (linked to `C:\ARTDaemon\Segman\Tasks\`) for:

- **MetsSeg/**: Medical image segmentation tasks
  - `Segman_MR_BMs/`: Brain metastases segmentation on MR images
  - Various other anatomical segmentation modules
- **Vista3D/**: 3D segmentation with point prompts
- **SAM/**: Segment Anything Model tasks
- **Admin/**: Administrative and maintenance tasks
- **DcmConverter/**: DICOM conversion tasks
- **Atlas/**: Atlas-based processing

### Task File Formats

#### .tsk Files (Template Tasks)
JSON format with basic task parameters:
```json
{
  "ShortName": "SegBMs",
  "DBTableName": "MR", 
  "TemplateTaskFile": "MetsSeg/Segman_MR_BMs/MR.xxx.tsk",
  "UserGroup": "User",
  "Confirmation": "Segman_MR_BMs?",
  "TaskID": "1.3.12.2.1107.5.2.43.66059.xxx",
  "user": "test"
}
```

#### Vista3D Tasks
Point-based segmentation tasks:
```json
{
  "task_id": "vista3d_point_timestamp",
  "input_file": "C:/ARTDaemon/Segman/dcm2nifti/.../image.nii.gz",
  "output_directory": "C:/ARTDaemon/Segman/dcm2nifti/.../Vista3D/",
  "segmentation_type": "point",
  "point_coordinates": [x, y, z],
  "point_type": "positive",
  "label": 1,
  "additional_points": [{"coordinates": [x,y,z], "type": "negative"}]
}
```

#### SAM Tasks
Segment Anything Model tasks with bounding boxes or points:
```json
{
  "InputImageFile": "C:/ARTDaemon/Segman/dcm2nifti/.../image.nii.gz",
  "OutputImageFile": "dcm2nifti/.../SAM/SAM_raw.nii.gz", 
  "OutputFileFolder": "dcm2nifti/.../SAM/",
  "Box": [x1, y1, x2, y2],
  "ROIIndex": [x, y],
  "imageSeriesUID": "1.3.12.2.1107.5.2.43.66059.xxx",
  "modality": "MR",
  "ROIName": "sam1",
  "sam_mode": 0,
  "current_slice": 96
}
```

### Task Processing Workflow

1. **Task Creation**: JSON files are created in appropriate task folders
2. **Processing**: ARTDaemon monitors folders and processes tasks
3. **Results**: Processed tasks move to `processed/` subfolders with `_result.json` files
4. **Failed Tasks**: Failed tasks move to `failed/` subfolders

### Key File Paths
- Input images: `C:/ARTDaemon/Segman/dcm2nifti/[HASH]/[UID]/image.nii.gz`
- Output folders: Task-specific subfolders (Vista3D/, SAM/, etc.)
- Task files: Timestamped JSON files in task type folders

## Development Commands

No specific build commands - this is a monitoring/task creation system.

## Task Submission Helpers

When creating MCP tools for task submission:

1. **Generate unique task IDs**: Use timestamp-based IDs like `vista3d_point_[timestamp]`
2. **Validate file paths**: Ensure input files exist before task creation
3. **Use proper JSON formatting**: Tasks must be valid JSON
4. **Handle coordinate systems**: Vista3D uses image coordinate system (x,y,z)
5. **Monitor processing**: Check `processed/` and `failed/` folders for results

## Common Task Types for MCP Integration

- **Brain metastases segmentation**: Use Segman_MR_BMs folder
- **Point-based segmentation**: Use Vista3D with point coordinates  
- **Interactive segmentation**: Use SAM with bounding boxes or points
- **Batch processing**: Create multiple tasks with unique IDs

The system expects tasks to be submitted as JSON files in the appropriate folders, where they will be automatically picked up and processed by the ARTDaemon service.