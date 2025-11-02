# This is the modified Python script to be run by Electron.
# It takes inputs as command-line arguments and prints logs as JSON.

import os
import json
import subprocess
import sys
import platform
import shutil
from datetime import datetime, timezone

# --- New Logging Function ---
# This prints JSON to stdout, which python-shell captures
def log(message, tag=None):
    """Prints a JSON object to stdout for Electron to capture."""
    log_entry = {"text": message, "tag": tag}
    print(json.dumps(log_entry))
    sys.stdout.flush() # Ensure it's sent immediately

# --- All Helper Functions (from the original class) ---

def find_json_files(root_dir):
    patterns = [
        '.supplemental-metadata.json', '.supplemental-metada.json',
        '.supplemental-met.json', '.supplemental-m.json',
        '.supplemental.json', '.supplement.json'
    ]
    json_files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip special folders
        if 'NO_METADATA_FOUND' in dirpath or 'JSON_METADATA' in dirpath:
            continue
        
        for filename in filenames:
            if any(filename.endswith(pattern) for pattern in patterns):
                json_path = os.path.join(dirpath, filename)
                json_files.append(json_path)
    return json_files

def find_media_file(json_path):
    json_dir = os.path.dirname(json_path)
    json_filename = os.path.basename(json_path)
    base_name = json_filename
    json_patterns = [
        '.supplemental-metadata.json', '.supplemental-metada.json',
        '.supplemental-met.json', '.supplemental-m.json',
        '.supplemental.json', '.supplement.json'
    ]
    for pattern in json_patterns:
        if base_name.endswith(pattern):
            base_name = base_name[:-len(pattern)]
            break
    
    media_extensions = [
        '.jpg', '.jpeg', '.heic', '.png', '.gif', '.webp', '.mp4', '.m4v', 
        '.mov', '.MP.jpg', '.HEIC', '.JPG', '.PNG', '.MP4', '.MOV'
    ]
    
    for ext in media_extensions:
        potential_file = os.path.join(json_dir, base_name + ext)
        if os.path.exists(potential_file):
            return potential_file

    # Case-insensitive check in the same directory
    if os.path.exists(json_dir):
        files_in_dir = os.listdir(json_dir)
        for filename in files_in_dir:
            # Skip JSON files when checking for media files
            if any(filename.endswith(pattern) for pattern in json_patterns):
                continue
            
            if filename.lower().startswith(base_name.lower()):
                for ext in media_extensions:
                    if filename.lower().endswith(ext.lower()):
                        return os.path.join(json_dir, filename)

    parent_dir = os.path.dirname(json_dir)
    if parent_dir and parent_dir != json_dir:
        for ext in media_extensions:
            potential_file = os.path.join(parent_dir, base_name + ext)
            if os.path.exists(potential_file):
                return potential_file
    return None

def is_pdt(timestamp):
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    year = dt.year
    month = dt.month
    day = dt.day
    # Simplified logic, good enough for recent/future years
    if month < 3 or month > 11: return False
    if month > 3 and month < 11: return True
    # Handle March (starts 2nd Sunday)
    if month == 3:
        first_day_of_month = datetime(year, 3, 1).weekday() # 0=Mon, 6=Sun
        second_sunday = 14 - (first_day_of_month + 1) % 7
        return day >= second_sunday
    # Handle November (ends 1st Sunday)
    if month == 11:
        first_day_of_month = datetime(year, 11, 1).weekday()
        first_sunday = 7 - (first_day_of_month + 1) % 7
        return day <= first_sunday
    return False

def get_pacific_datetime(utc_timestamp):
    # Attempt conversion, log error if timestamp is invalid
    try:
        utc_ts = int(utc_timestamp)
    except (ValueError, TypeError):
        log(f"Invalid timestamp for Pacific conversion: {utc_timestamp}", "error")
        return None # Indicate failure
        
    offset_seconds = -8 * 3600  # PST
    if is_pdt(utc_ts):
        offset_seconds = -7 * 3600  # PDT
    
    pacific_timestamp = utc_ts + offset_seconds
    dt = datetime.fromtimestamp(pacific_timestamp, tz=timezone.utc)
    return dt.strftime('%Y:%m:%d %H:%M:%S')

def get_utc_datetime(utc_timestamp):
    # Attempt conversion, log error if timestamp is invalid
    try:
        utc_ts = int(utc_timestamp)
    except (ValueError, TypeError):
        log(f"Invalid timestamp for UTC conversion: {utc_timestamp}", "error")
        return None # Indicate failure
        
    dt = datetime.fromtimestamp(utc_ts, tz=timezone.utc)
    return dt.strftime('%Y:%m:%d %H:%M:%S')

def move_files_without_matching_json(source_folder):
    try:
        no_metadata_folder = os.path.join(source_folder, "NO_METADATA_FOUND")
        os.makedirs(no_metadata_folder, exist_ok=True)
        media_extensions = [
            '.jpg', '.jpeg', '.heic', '.png', '.gif', '.webp', '.mp4', '.m4v',
            '.mov', '.MP.jpg', '.HEIC', '.JPG', '.PNG', '.MP4', '.MOV'
        ]
        json_patterns = [
            '.supplemental-metadata.json', '.supplemental-metada.json',
            '.supplemental-met.json', '.supplemental-m.json',
            '.supplemental.json', '.supplement.json'
        ]
        moved_count = 0
        
        for dirpath, dirnames, filenames in os.walk(source_folder):
            # Prune search: Don't descend into already processed/created folders
            dirnames[:] = [d for d in dirnames if d not in ('NO_METADATA_FOUND', 'JSON_METADATA')]
            
            for filename in filenames:
                is_media = any(filename.lower().endswith(ext.lower()) for ext in media_extensions)
                if not is_media:
                    continue

                has_matching_json = False
                # Efficiently check for corresponding JSON
                base, _ = os.path.splitext(filename)
                for pattern in json_patterns:
                    # Check if a JSON file exists that starts with the base name and ends with a pattern
                    # This handles cases like IMG_1234.JPG.json matching IMG_1234.JPG
                    potential_json = filename + pattern
                    if os.path.exists(os.path.join(dirpath, potential_json)):
                         has_matching_json = True
                         break
                    # Handle cases like edited photos IMG_1234(1).jpg having IMG_1234.jpg(1).json
                    if '(' in base and base.endswith(')'):
                         parts = base.rsplit('(', 1)
                         alt_json_base = parts[0]
                         alt_json_suffix = '(' + parts[1]
                         potential_alt_json = alt_json_base + pattern + alt_json_suffix
                         if os.path.exists(os.path.join(dirpath, potential_alt_json)):
                              has_matching_json = True
                              break

                if not has_matching_json:
                    source_file = os.path.join(dirpath, filename)
                    dest_path = os.path.join(no_metadata_folder, filename)
                    # Handle potential duplicate filenames in the destination
                    counter = 1
                    base_dest_path = dest_path
                    while os.path.exists(dest_path):
                         name, ext = os.path.splitext(base_dest_path)
                         dest_path = f"{name}_{counter}{ext}"
                         counter += 1

                    try:
                        shutil.move(source_file, dest_path)
                        log(f"  ✓ Moved (no JSON): {filename}", "warning")
                        moved_count += 1
                    except Exception as e:
                        log(f"  ✗ Failed to move {filename} to NO_METADATA: {e}", "error")
        
        if moved_count > 0:
            log(f"✓ Separated {moved_count} files into NO_METADATA_FOUND", "success")
            # Consider adding a README here if desired
            
    except Exception as e:
        log(f"✗ Error during file separation: {str(e)}", "error")


def organize_json_files(source_folder):
    try:
        json_folder = os.path.join(source_folder, "JSON_METADATA")
        os.makedirs(json_folder, exist_ok=True)
        json_patterns = [
            '.supplemental-metadata.json', '.supplemental-metada.json',
            '.supplemental-met.json', '.supplemental-m.json',
            '.supplemental.json', '.supplement.json'
        ]
        moved_count = 0
        
        for dirpath, dirnames, filenames in os.walk(source_folder):
             # Prune search: Don't descend into the destination folder
            dirnames[:] = [d for d in dirnames if d != 'JSON_METADATA']

            for filename in filenames:
                if any(filename.endswith(pattern) for pattern in json_patterns):
                    source_file = os.path.join(dirpath, filename)
                    dest_path = os.path.join(json_folder, filename)
                     # Handle potential duplicate filenames in the destination
                    counter = 1
                    base_dest_path = dest_path
                    while os.path.exists(dest_path):
                         name, ext = os.path.splitext(base_dest_path)
                         dest_path = f"{name}_{counter}{ext}"
                         counter += 1
                         
                    try:
                        shutil.move(source_file, dest_path)
                        moved_count += 1
                    except Exception as e:
                        log(f"  ✗ Failed to move {filename} to JSON_METADATA: {e}", "error")
        
        if moved_count > 0:
            log(f"✓ Organized {moved_count} JSON files into JSON_METADATA", "success")
             # Consider adding a README here if desired
            
    except Exception as e:
        log(f"✗ Error organizing JSON files: {str(e)}\n", "error")


# --- Main Processing Function ---
def process_photos(source_folder, timezone_mode, exiftool_path):
    try:
        log("=" * 60)
        
        json_files = find_json_files(source_folder)
        
        if not json_files:
            log("❌ No JSON metadata files found!", "error")
            return
            
        log(f"✓ Found {len(json_files)} JSON files", "success")
        log(f"✓ Timezone mode: {timezone_mode.upper()}", "success")
        log("Processing files...\n")
        
        total_photos = 0
        updated_photos = 0
        error_photos = 0
        
        # --- Determine how to call exiftool based on OS ---
        is_windows = platform.system() == "Windows"
        perl_cmd = []
        lib_dir = None

        if not is_windows:
            # On macOS/Linux, exiftool is likely a Perl script needing its lib path
            exiftool_dir = os.path.dirname(exiftool_path)
            potential_lib_dir = os.path.join(exiftool_dir, 'lib')
            if os.path.isdir(potential_lib_dir):
                 lib_dir = potential_lib_dir
                 # Command will be: perl -I /path/to/lib /path/to/exiftool ...
                 perl_cmd = ['perl', '-I', lib_dir, exiftool_path]
            else:
                 # Assume exiftool is executable directly (standalone or in PATH)
                 perl_cmd = [exiftool_path]
        else:
             # On Windows, expect exiftool_path to be the .exe
             perl_cmd = [exiftool_path]


        log(f"Using ExifTool command: {' '.join(perl_cmd)}", "info")
        if lib_dir:
             log(f"Using ExifTool lib path: {lib_dir}", "info")


        for json_path in json_files:
            try:
                # Check if the JSON file still exists (it might have been moved)
                if not os.path.exists(json_path):
                     log(f"Skipping already moved JSON: {os.path.basename(json_path)}", "info")
                     continue

                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Check for essential time data
                photo_taken_time = data.get('photoTakenTime')
                if not photo_taken_time or 'timestamp' not in photo_taken_time:
                    log(f"⚠️ Missing timestamp in: {os.path.basename(json_path)}", "warning")
                    continue
                
                utc_timestamp = photo_taken_time['timestamp']
                gps_data = data.get('geoData', {})
                latitude = gps_data.get('latitude')
                longitude = gps_data.get('longitude')
                description = data.get('description', '') # Handle potentially missing description
                
                # Get formatted datetime string, handling potential conversion errors
                datetime_str = None
                timezone_label = "UTC" # Default
                if timezone_mode == 'pacific':
                    datetime_str = get_pacific_datetime(utc_timestamp)
                    timezone_label = "PDT/PST"
                else:
                    datetime_str = get_utc_datetime(utc_timestamp)
                
                if datetime_str is None: # Skip if timestamp conversion failed
                    error_photos +=1
                    continue

                media_file = find_media_file(json_path)
                
                if not media_file:
                    log(f"⚠️  No media file found for: {os.path.basename(json_path)}", "warning")
                    continue
                
                 # Check if the media file still exists (it might have been moved)
                if not os.path.exists(media_file):
                    log(f"Skipping already moved media file: {os.path.basename(media_file)} referenced by {os.path.basename(json_path)}", "info")
                    continue

                total_photos += 1
                
                # Construct exiftool command arguments
                cmd_args = ['-overwrite_original', '-q']
                cmd_args.append(f'-DateTimeOriginal={datetime_str}')
                cmd_args.append(f'-FileCreateDate={datetime_str}')
                cmd_args.append(f'-FileModifyDate={datetime_str}')
                
                # Add GPS tags only if latitude and longitude are valid and non-zero
                if latitude is not None and longitude is not None and latitude != 0.0 and longitude != 0.0:
                    cmd_args.append(f'-GPSLatitude={latitude}')
                    cmd_args.append(f'-GPSLongitude={longitude}')
                    # Optional: Add altitude if needed and available, checking validity
                    # altitude = gps_data.get('altitude')
                    # if altitude is not None:
                    #     cmd_args.append(f'-GPSAltitude={altitude}')
                    # Consider adding Ref tags if needed by target applications
                    cmd_args.append(f'-GPSLatitudeRef={"N" if latitude >= 0 else "S"}')
                    cmd_args.append(f'-GPSLongitudeRef={"E" if longitude >= 0 else "W"}')

                
                if description: # Add description only if it's not empty
                    # Ensure description is properly handled for command line (basic escaping)
                    # For more robust handling consider base64 or temporary files if descriptions are complex
                    # Simple approach: Replace potential problematic chars if needed, though exiftool handles many cases
                    cmd_args.append(f'-Description={description}') 
                
                cmd_args.append(media_file)

                # Combine base command (perl or exe) with arguments
                full_cmd = perl_cmd + cmd_args

                try:
                     # Use utf-8 for stderr decoding
                    result = subprocess.run(full_cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
                
                    if result.returncode == 0:
                        log(f"✓ {os.path.basename(media_file)} → {datetime_str} ({timezone_label})", "success")
                        updated_photos += 1
                    else:
                        # Log stderr if available, otherwise just note the error code
                        error_detail = result.stderr.strip() if result.stderr else f"ExifTool exited with code {result.returncode}"
                        log(f"✗ Error processing {os.path.basename(media_file)}: {error_detail}", "error")
                        error_photos += 1
                except FileNotFoundError:
                     log(f"✗ Error: ExifTool (or Perl) not found at the specified path: {perl_cmd[0]}", "error")
                     # Stop processing further files if ExifTool isn't found
                     return 
                except Exception as sub_e:
                     log(f"✗ Subprocess error running ExifTool for {os.path.basename(media_file)}: {sub_e}", "error")
                     error_photos +=1

            except json.JSONDecodeError as json_e:
                log(f"✗ JSON decode error in: {os.path.basename(json_path)} | {json_e}", "error")
                error_photos += 1
            except FileNotFoundError:
                 # Catch if JSON file disappears between listing and processing
                 log(f"✗ File not found (moved?): {os.path.basename(json_path)}", "error")
                 error_photos += 1
            except Exception as e:
                log(f"✗ Unexpected file error: {os.path.basename(json_path)} | {e}", "error")
                error_photos += 1
        
        log("\n" + "=" * 60)
        log("🔄 Separating files without metadata...", "warning")
        move_files_without_matching_json(source_folder)
        
        log("\n" + "=" * 60)
        log("📋 Organizing JSON files...", "warning")
        organize_json_files(source_folder)
        
        # --- THIS LINE WAS FIXED ---
        log("\n" + "=" * 60)
        log("🎉 Metadata Application Complete!", "success")
        log("=" * 60)
        log(f"Total photos processed:  {total_photos}")
        log(f"Successfully updated:    {updated_photos}", "success")
        log(f"Errors encountered:      {error_photos}", "error" if error_photos > 0 else None)
        log("\n✅ Processing finished.", "success")
        
    except Exception as e:
        log(f"\n❌ Fatal error during processing: {e}", "error")
    finally:
        # Final log to signal completion regardless of success/failure,
        # helps Electron know the script finished.
        log("Script execution finished.", "info")


# --- Main execution ---
if __name__ == "__main__":
    if len(sys.argv) != 4:
        log("Usage: python batch_fixer_cli.py <source_folder> <timezone_mode> <exiftool_path>", "error")
        sys.exit(1)

    source_folder_arg = sys.argv[1]
    timezone_mode_arg = sys.argv[2]
    exiftool_path_arg = sys.argv[3] # Path to the bundled exiftool (script or exe)

    if not os.path.isdir(source_folder_arg):
         log(f"Error: Source folder not found or is not a directory: {source_folder_arg}", "error")
         sys.exit(1)

    if timezone_mode_arg not in ['pacific', 'utc']:
         log(f"Error: Invalid timezone mode '{timezone_mode_arg}'. Use 'pacific' or 'utc'.", "error")
         sys.exit(1)

    # Basic check if exiftool path exists (more robust check happens in process_photos)
    if not os.path.exists(exiftool_path_arg):
         log(f"Error: ExifTool path not found: {exiftool_path_arg}", "error")
         sys.exit(1)


    try:
        process_photos(source_folder_arg, timezone_mode_arg, exiftool_path_arg)
        
    except Exception as e:
        log(f"A critical error occurred: {e}", "error")
        sys.exit(1)

    # Exit with 0 if the script reached the end, even if there were processing errors logged.
    # Electron checks the exit code primarily for script crashes, not processing success.
    sys.exit(0)

