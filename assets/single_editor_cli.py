#!/usr/bin/env python3

import os
import json
import subprocess
import sys
import platform
from datetime import datetime

# --- Logging Function ---
def log_message(message, tag=None):
    """Prints log messages as JSON for Electron to capture."""
    log_entry = {"text": message, "tag": tag if tag else "default"}
    print(json.dumps(log_entry))
    sys.stdout.flush()

# --- Helper: Get ExifTool Command ---
def get_exiftool_command(exiftool_path):
    """Determines the correct command to run exiftool based on OS."""
    exiftool_command = []
    if platform.system() == "Windows":
         exiftool_command = [exiftool_path]
    else:
        # For Mac/Linux, check if the corresponding 'lib' exists
        script_dir = os.path.dirname(exiftool_path)
        lib_path = os.path.join(script_dir, 'lib')
        if os.path.isdir(lib_path):
             exiftool_command = ['perl', f'-I{lib_path}', exiftool_path]
        else:
             exiftool_command = [exiftool_path] # Assume standalone
    return exiftool_command

# --- Helper: Validate Date/Time ---
def validate_datetime(date_str, time_str):
    """Validate date and time format from strings."""
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        datetime.strptime(time_str, '%H:%M:%S')
        return True
    except ValueError as e:
        log_message(f"Invalid date/time format: {e}. Use YYYY-MM-DD and HH:MM:SS", "error")
        return False

# --- Core Logic ---
def apply_metadata(file_path, date_str, time_str, exiftool_cmd):
    """Applies the new date and time to the selected file."""
    try:
        log_message("=" * 60)
        log_message("🚀 Updating metadata...", "success")
        log_message("=" * 60 + "\n")
        
        log_message(f"File: {os.path.basename(file_path)}")
        log_message(f"New Date: {date_str}")
        log_message(f"New Time: {time_str}\n")
        
        datetime_str = f"{date_str} {time_str}"
        
        # Format for exiftool: YYYY:MM:DD HH:MM:SS
        exiftool_datetime = datetime_str.replace('-', ':')
        
        cmd_args = ['-overwrite_original_in_place', '-q']
        # Apply to all relevant tags
        cmd_args.append(f'-AllDates={exiftool_datetime}')
        cmd_args.append(f'-FileCreateDate={exiftool_datetime}')
        cmd_args.append(f'-FileModifyDate={exiftool_datetime}')
        
        # Specific tags for videos that AllDates might miss
        cmd_args.append(f'-TrackCreateDate={exiftool_datetime}')
        cmd_args.append(f'-TrackModifyDate={exiftool_datetime}')
        cmd_args.append(f'-MediaCreateDate={exiftool_datetime}')
        cmd_args.append(f'-MediaModifyDate={exiftool_datetime}')
        
        cmd_args.append(file_path)
        
        full_cmd = exiftool_cmd + cmd_args
        
        result = subprocess.run(full_cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        
        if result.returncode == 0:
            log_message("=" * 60)
            log_message(f"✓ All Dates Set To: {exiftool_datetime}", "success")
            # The final "success" message is sent by the renderer.js
        else:
            error_msg = result.stderr.strip() if result.stderr else "Unknown error"
            log_message(f"❌ Error: {error_msg}", "error")
    
    except Exception as e:
        log_message(f"❌ Fatal error: {e}", "error")
    
    finally:
        # Signal to Electron that processing is done
        log_message("PROCESSING_COMPLETE", "final_marker")

# --- Entry Point ---
if __name__ == "__main__":
    if len(sys.argv) != 5:
        log_message(f"Error: Incorrect number of arguments. Expected 4, got {len(sys.argv) - 1}", "error")
        log_message("Usage: python ... <file_path> <date_str> <time_str> <exiftool_path>", "error")
        sys.exit(1)

    file_path_arg = sys.argv[1]
    date_str_arg = sys.argv[2]
    time_str_arg = sys.argv[3]
    exiftool_path_arg = sys.argv[4]

    # --- Initial Checks ---
    if not os.path.exists(file_path_arg):
         log_message(f"Error: File not found: {file_path_arg}", "error")
         sys.exit(1)
         
    if not os.path.exists(exiftool_path_arg):
         log_message(f"Error: ExifTool path not found: {exiftool_path_arg}", "error")
         sys.exit(1)

    if not validate_datetime(date_str_arg, time_str_arg):
        sys.exit(1)
        
    exiftool_command = get_exiftool_command(exiftool_path_arg)
    
    # --- Run ExifTool Check ---
    test_result = subprocess.run(exiftool_command + ['-ver'], capture_output=True, text=True)
    if test_result.returncode != 0:
        log_message(f"Error: ExifTool failed initial check. {test_result.stderr}", "error")
        sys.exit(1)
    else:
        log_message(f"✓ ExifTool check successful (Version: {test_result.stdout.strip()})", "success")

    # --- Run Main Process ---
    try:
        apply_metadata(file_path_arg, date_str_arg, time_str_arg, exiftool_command)
    except Exception as e:
        log_message(f"A critical error occurred: {e}", "error")
        sys.exit(1)

    sys.exit(0)
