#!/usr/bin/env python3
# This is the modified Python script to be run by Electron.
# It takes inputs as command-line arguments and prints logs as JSON.

import os
import json
import subprocess
import sys
import platform
import shutil
from datetime import datetime, timezone, timedelta

# --- New Logging Function ---
# This prints JSON to stdout, which python-shell captures
def log_message(message, tag=None):
    """Prints a JSON object to stdout for Electron to capture."""
    log_entry = {"text": message, "tag": tag if tag else "default"}
    print(json.dumps(log_entry))
    sys.stdout.flush() # Ensure it's sent immediately

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

# --- All Helper Functions (from the original class) ---

def find_json_files(root_dir):
    """Finds all supplemental metadata JSON files recursively."""
    patterns = [
        '.supplemental-metadata.json',
        '.supplemental-metada.json', # Handle potential typos from Google
        '.supplemental-met.json',
        '.supplemental-m.json',
        '.supplemental.json',
        '.supplement.json'
    ]
    json_files = []
    # Ignore specific folders during scan
    ignore_folders = {'NO_METADATA_FOUND', 'JSON_METADATA'}

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Modify dirnames in-place to prevent descending into ignored folders
        dirnames[:] = [d for d in dirnames if d not in ignore_folders]

        for filename in filenames:
            # Check for JSON patterns, including case variations if needed
            if any(filename.lower().endswith(pattern.lower()) for pattern in patterns):
                json_path = os.path.join(dirpath, filename)
                json_files.append(json_path)
    return json_files

def find_media_file(json_path):
    """Finds the corresponding media file for a given JSON path.
       Returns the media file path and the specific JSON suffix found."""
    json_dir = os.path.dirname(json_path)
    json_filename = os.path.basename(json_path)

    base_name = json_filename
    json_patterns = [
        '.supplemental-metadata.json',
        '.supplemental-metada.json',
        '.supplemental-met.json',
        '.supplemental-m.json',
        '.supplemental.json',
        '.supplement.json'
    ]

    # Remove the JSON suffix to get the base media filename
    current_json_suffix = ""
    for pattern in json_patterns:
        # Use lower() for case-insensitive matching
        if base_name.lower().endswith(pattern.lower()):
            base_name = base_name[:-len(pattern)]
            # Store the suffix including the leading dot, preserving case from pattern
            current_json_suffix = pattern
            break

    # List of common media extensions to check (case-insensitive)
    media_extensions = [
        '.jpg', '.jpeg', '.heic', '.png', '.gif', '.webp', '.tiff', '.tif',
        '.mp4', '.m4v', '.mov', '.avi', '.mpg', '.mpeg'
    ]

    # Check for files with matching base name and common extensions in the same directory
    for ext in media_extensions:
        # Check both exact case and lower/upper case variations more robustly
        potential_file_exact = os.path.join(json_dir, base_name + ext)
        potential_file_lower = os.path.join(json_dir, base_name + ext.lower())
        potential_file_upper = os.path.join(json_dir, base_name + ext.upper())

        if os.path.exists(potential_file_exact):
            return potential_file_exact, current_json_suffix # Return json suffix too
        if os.path.exists(potential_file_lower):
            return potential_file_lower, current_json_suffix
        if os.path.exists(potential_file_upper):
            return potential_file_upper, current_json_suffix

    # Fallback: Check slightly modified names Google sometimes uses (e.g., "(1)")
    for suffix in ["(1)", "(2)"]: # Add more if needed
         for ext in media_extensions:
            potential_file_suffix = os.path.join(json_dir, base_name + suffix + ext)
            if os.path.exists(potential_file_suffix):
                 # Try to determine json suffix even for complex names if possible
                 guessed_suffix = ""
                 # Check if the original json filename might correspond (heuristic)
                 if json_filename.lower().startswith( (base_name + suffix).lower() ):
                     for pattern in json_patterns:
                         if json_filename.lower().endswith(pattern.lower()):
                             guessed_suffix = pattern
                             break
                 return potential_file_suffix, guessed_suffix

    # Fallback: Check parent directory (sometimes Takeout structure is odd)
    parent_dir = os.path.dirname(json_dir)
    if parent_dir and parent_dir != json_dir:
        for ext in media_extensions:
            potential_file_parent = os.path.join(parent_dir, base_name + ext)
            if os.path.exists(potential_file_parent):
                return potential_file_parent, current_json_suffix

    return None, None # Return None for both if not found

def is_pdt(timestamp):
    """Checks if a given UTC timestamp falls within Pacific Daylight Time (PDT)."""
    try:
        dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
        year = dt.year
        # DST typically starts on the second Sunday in March and ends on the first Sunday in November (US rules post-2007)
        # Find the start date (second Sunday in March at 2 AM UTC)
        dst_start = datetime(year, 3, 8, 2, tzinfo=timezone.utc) # Start checking from March 8th
        day_offset = (6 - dst_start.weekday()) % 7 # Days until Sunday
        dst_start += timedelta(days=day_offset) # First Sunday
        dst_start += timedelta(days=7) # Second Sunday

        # Find the end date (first Sunday in November at 2 AM UTC, but DST ends at 2 AM local which is later UTC)
        std_start = datetime(year, 11, 1, 2, tzinfo=timezone.utc) # Check from Nov 1st
        day_offset = (6 - std_start.weekday()) % 7 # Days until Sunday
        std_start += timedelta(days=day_offset) # First Sunday in November
        # The transition *happens* at 2 AM local time, which is 9 AM UTC on that day (during DST).
        std_start = std_start.replace(hour=9)

        # Check if the timestamp is within the DST period
        return dst_start <= dt < std_start
    except ValueError:
        return False # Assume standard time if calculation fails

def get_pacific_datetime(utc_timestamp_str):
    """Converts a UTC timestamp string to Pacific Time (PDT/PST) string."""
    try:
        utc_ts = int(utc_timestamp_str)
        dt_utc = datetime.fromtimestamp(utc_ts, tz=timezone.utc)
        if is_pdt(utc_ts):
            offset_hours = -7
        else:
            offset_hours = -8
        pacific_tz = timezone(timedelta(hours=offset_hours))
        dt_pacific = dt_utc.astimezone(pacific_tz)
        return dt_pacific.strftime('%Y:%m:%d %H:%M:%S')
    except (ValueError, TypeError):
        log_message(f"Error converting timestamp: {utc_timestamp_str}", "error")
        return None

def get_utc_datetime(utc_timestamp_str):
    """Converts a UTC timestamp string to a formatted UTC datetime string."""
    try:
        utc_ts = int(utc_timestamp_str)
        dt = datetime.fromtimestamp(utc_ts, tz=timezone.utc)
        return dt.strftime('%Y:%m:%d %H:%M:%S')
    except (ValueError, TypeError):
        log_message(f"Error converting timestamp: {utc_timestamp_str}", "error")
        return None

def run_exiftool_command(exiftool_cmd_array, cmd_args):
    """Runs an exiftool command using subprocess."""
    if isinstance(exiftool_cmd_array, list):
        command = exiftool_cmd_array + cmd_args
    else:
        command = [exiftool_cmd_array] + cmd_args

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False, encoding='utf-8', errors='replace')
        return result
    except FileNotFoundError:
        log_message(f"ExifTool not found or command error: {' '.join(command)}", "error")
        return None
    except Exception as e:
        log_message(f"Error running ExifTool: {e}", "error")
        return None

# --- Main Processing Logic ---

def process_photos(source_folder, timezone_mode, exiftool_cmd_array_or_path):
    """Processes photos in the source folder based on JSON metadata."""
    log_message("🚀 Starting metadata application...", "success")
    log_message("=" * 60)

    json_files = find_json_files(source_folder)

    if not json_files:
        log_message("❌ No JSON metadata files found!", "error")
        return 0, 0, 0, 0

    log_message(f"✓ Found {len(json_files)} JSON files", "success")
    log_message(f"✓ Timezone mode: {timezone_mode.upper()}", "success")
    log_message("Processing files...\n")

    total_files_scanned = len(json_files)
    updated_photos = 0
    error_photos = 0
    skipped_no_media = 0

    processed_json_paths = set() # Track JSONs handled (including renames)

    # Use a copy for iteration as renaming might affect the original list indirectly
    json_files_to_process = list(json_files)

    for current_json_path in json_files_to_process:

        # Skip if already handled (e.g., renamed and processed under new name)
        if current_json_path in processed_json_paths:
            continue
        # Skip if it no longer exists (was renamed)
        if not os.path.exists(current_json_path):
            continue

        media_file = None
        json_suffix = None
        original_media_file_for_error = None # Store original path for logging errors

        try:
            with open(current_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if 'photoTakenTime' not in data or 'timestamp' not in data['photoTakenTime']:
                log_message(f"⚠️ Missing 'photoTakenTime' in {os.path.basename(current_json_path)}", "warning")
                processed_json_paths.add(current_json_path)
                continue

            utc_timestamp = data['photoTakenTime']['timestamp']
            gps_data = data.get('geoData', {})
            latitude = gps_data.get('latitude')
            longitude = gps_data.get('longitude')
            description = data.get('description', '')

            if timezone_mode == 'pacific':
                datetime_str = get_pacific_datetime(utc_timestamp)
                timezone_label = "PDT/PST"
            else:
                datetime_str = get_utc_datetime(utc_timestamp)
                timezone_label = "UTC"

            if not datetime_str:
                error_photos +=1
                processed_json_paths.add(current_json_path)
                continue

            media_file, json_suffix = find_media_file(current_json_path)
            original_media_file_for_error = media_file # Store before potential rename

            if not media_file:
                log_message(f"⚠️ No media file found for: {os.path.basename(current_json_path)}", "warning")
                skipped_no_media += 1
                processed_json_paths.add(current_json_path)
                continue

            # Check for potential rename scenario BEFORE building command
            needs_rename = False
            new_jpg_media_file = None
            new_jpg_json_file = None

            if media_file.lower().endswith('.heic'):
                # Preliminary check: Run exiftool with just the file to see if it throws the error
                check_result = run_exiftool_command(exiftool_cmd_array_or_path, [media_file])
                if check_result and check_result.returncode != 0 and "looks more like a JPEG" in (check_result.stderr or ""):
                    needs_rename = True
                    log_message(f"⚠️ {os.path.basename(media_file)} needs rename (is JPEG).", "warning")

                    # Ensure json_suffix was found
                    if not json_suffix:
                         log_message(f"  ✗ Cannot rename: Failed to determine JSON suffix for {os.path.basename(current_json_path)}. Skipping.", "error")
                         error_photos += 1
                         processed_json_paths.add(current_json_path)
                         continue # Skip this file

                    base_name_no_ext = os.path.splitext(media_file)[0]
                    new_jpg_media_file = base_name_no_ext + '.jpg'

                    # Construct new JSON name robustly
                    json_original_base = os.path.basename(current_json_path)
                    for pattern in [ # Use same patterns as find_json_files
                        '.supplemental-metadata.json', '.supplemental-metada.json',
                        '.supplemental-met.json', '.supplemental-m.json',
                        '.supplemental.json', '.supplement.json']:
                        if json_original_base.lower().endswith(pattern.lower()):
                            json_original_base = json_original_base[:-len(pattern)]
                            break
                    # Verify base name consistency before proceeding
                    if os.path.splitext(os.path.basename(media_file))[0].lower() != json_original_base.lower():
                         log_message(f"  ✗ JSON base name mismatch: '{json_original_base}' vs '{os.path.splitext(os.path.basename(media_file))[0]}'. Cannot rename JSON safely. Skipping.", "error")
                         error_photos += 1
                         processed_json_paths.add(current_json_path)
                         continue

                    new_jpg_json_file = base_name_no_ext + '.jpg' + json_suffix

                    # --- Perform Renames ---
                    try:
                        # Check for existing target files BEFORE renaming
                        if os.path.exists(new_jpg_media_file):
                            log_message(f"  ✗ Cannot rename: Target file {os.path.basename(new_jpg_media_file)} already exists. Skipping.", "error")
                            raise FileExistsError() # Raise error to skip
                        if os.path.exists(new_jpg_json_file):
                            log_message(f"  ✗ Cannot rename: Target JSON file {os.path.basename(new_jpg_json_file)} already exists. Skipping.", "error")
                            raise FileExistsError()

                        shutil.move(media_file, new_jpg_media_file)
                        log_message(f"  ✓ Renamed {os.path.basename(media_file)} to {os.path.basename(new_jpg_media_file)}", "info")
                        media_file = new_jpg_media_file # Update media_file to the new path

                        if os.path.exists(current_json_path):
                            shutil.move(current_json_path, new_jpg_json_file)
                            log_message(f"  ✓ Renamed {os.path.basename(current_json_path)} to {os.path.basename(new_jpg_json_file)}", "info")
                            processed_json_paths.add(new_jpg_json_file) # Mark new JSON path as handled
                            current_json_path = new_jpg_json_file # Update current path
                        else:
                            log_message(f"  ⚠️ Could not find original JSON {os.path.basename(current_json_path)} to rename (maybe already moved?).", "warning")
                            processed_json_paths.add(current_json_path) # Mark original as handled

                    except Exception as rename_error:
                         log_message(f"  ✗ Failed to rename files for {os.path.basename(original_media_file_for_error)}: {rename_error}", "error")
                         error_photos += 1
                         processed_json_paths.add(current_json_path) # Mark original json path as handled (error)
                         continue # Skip processing this file further

            # --- Build and Run ExifTool command ---
            cmd_args = ['-overwrite_original_in_place', '-q']
            cmd_args.append(f'-DateTimeOriginal={datetime_str}')
            cmd_args.append(f'-FileCreateDate={datetime_str}')
            cmd_args.append(f'-FileModifyDate={datetime_str}')

            if latitude is not None and longitude is not None and (latitude != 0.0 or longitude != 0.0):
                if -90 <= latitude <= 90 and -180 <= longitude <= 180:
                    cmd_args.append(f'-GPSLatitude={latitude}')
                    cmd_args.append(f'-GPSLongitude={longitude}')
                    altitude = gps_data.get('altitude')
                    if altitude is not None and altitude != 0.0:
                         cmd_args.append(f'-GPSAltitude={altitude}')
                else:
                    log_message(f"⚠️ Invalid GPS coordinates ({latitude}, {longitude}) skipped for {os.path.basename(media_file)}", "warning")

            if description:
                cmd_args.append(f'-Description={description}')

            cmd_args.append(media_file) # Target file (potentially renamed)

            result = run_exiftool_command(exiftool_cmd_array_or_path, cmd_args)

            if result and result.returncode == 0:
                log_tag = "[Renamed from HEIC]" if needs_rename else ""
                log_message(f"✓ {os.path.basename(media_file)} → {datetime_str} ({timezone_label}) {log_tag}", "success")
                updated_photos += 1
                processed_json_paths.add(current_json_path) # Mark current (possibly new) json path
            elif result:
                error_msg = result.stderr.strip() if result.stderr else "Unknown ExifTool error"
                log_message(f"✗ Error processing {os.path.basename(media_file)}: {error_msg}", "error")
                error_photos += 1
                processed_json_paths.add(current_json_path)
            else:
                 log_message(f"✗ Failed to execute ExifTool for {os.path.basename(media_file)}", "error")
                 error_photos += 1
                 processed_json_paths.add(current_json_path)

        except json.JSONDecodeError:
            log_message(f"✗ Invalid JSON: {os.path.basename(current_json_path)}", "error")
            error_photos += 1
            processed_json_paths.add(current_json_path)
        except Exception as e:
            media_name = os.path.basename(original_media_file_for_error) if original_media_file_for_error else "unknown media file"
            log_message(f"✗ Unexpected error processing {os.path.basename(current_json_path)} for {media_name}: {e}", "error")
            error_photos += 1
            processed_json_paths.add(current_json_path)


    return updated_photos, error_photos, skipped_no_media, total_files_scanned

# --- Post-Processing Functions ---

def move_files_without_matching_json(source_folder):
    """Moves media files without corresponding JSON to a separate folder."""
    log_message("\n" + "=" * 60)
    log_message("🔄 Separating files without metadata...", "warning")
    no_metadata_folder = os.path.join(source_folder, "NO_METADATA_FOUND")
    os.makedirs(no_metadata_folder, exist_ok=True)

    media_extensions_lower = {
        '.jpg', '.jpeg', '.heic', '.png', '.gif', '.webp', '.tiff', '.tif',
        '.mp4', '.m4v', '.mov', '.avi', '.mpg', '.mpeg'
    }
    json_patterns_lower = {
        '.supplemental-metadata.json', '.supplemental-metada.json',
        '.supplemental-met.json', '.supplemental-m.json',
        '.supplemental.json', '.supplement.json'
    }

    moved_count = 0
    moved_files = []
    # Store tuples of (base_name_lower, dirpath) for json files *that still exist*
    json_bases_existing = set()

    # First pass: find all base names that *currently* have a JSON file
    # This runs AFTER processing, so it includes renamed JSONs (.jpg.json)
    for dirpath, dirnames, filenames in os.walk(source_folder):
        dirnames[:] = [d for d in dirnames if d not in {'NO_METADATA_FOUND', 'JSON_METADATA'}]
        for filename in filenames:
            name_lower = filename.lower()
            if any(name_lower.endswith(pattern) for pattern in json_patterns_lower):
                base_name = filename
                # Find the base name by removing the known JSON pattern
                for pattern in json_patterns_lower:
                     if name_lower.endswith(pattern):
                          base_name = filename[:-len(pattern)]
                          break
                json_bases_existing.add((base_name.lower(), dirpath)) # Store lowercase base and dir


    # Second pass: move media files if their base name has no corresponding entry in the existing json set
    for dirpath, dirnames, filenames in os.walk(source_folder):
        dirnames[:] = [d for d in dirnames if d not in {'NO_METADATA_FOUND', 'JSON_METADATA'}]
        for filename in filenames:
            file_lower = filename.lower()
            # Only consider media files
            if file_lower.endswith(tuple(media_extensions_lower)):
                base_name, _ = os.path.splitext(filename)
                source_file = os.path.normpath(os.path.join(dirpath, filename))

                # Check if this base name (lower case) and directory exists in our *current* json set
                if (base_name.lower(), dirpath) not in json_bases_existing:
                    # Make sure the file itself still exists (it might have been moved already)
                    if not os.path.exists(source_file):
                        continue

                    dest_path_base = os.path.join(no_metadata_folder, filename)
                    dest_path = dest_path_base
                    counter = 1
                    while os.path.exists(dest_path):
                        name, ext = os.path.splitext(filename)
                        dest_path = os.path.join(no_metadata_folder, f"{name}({counter}){ext}")
                        counter += 1
                    try:
                        shutil.move(source_file, dest_path)
                        log_message(f"  ✓ Moved (no JSON): {filename}", "success") # Clarified log
                        moved_count += 1
                        moved_files.append(filename)
                    except Exception as e:
                        log_message(f"  ✗ Error moving {filename}: {e}", "error")

    # Create README (same as before)
    if moved_count > 0:
        readme_path = os.path.join(no_metadata_folder, "README.txt")
        try:
            with open(readme_path, 'w', encoding='utf-8') as f:
                 f.write("FILES WITHOUT METADATA\n" + "=" * 50 + "\n\n" +
                         "This folder contains media files from your Takeout\n" +
                         "that did NOT have a corresponding JSON metadata file\n" +
                         "at the end of the processing.\n\n" + # Clarified timing
                         f"Total files moved here: {moved_count}\n\n" +
                         "Files in this folder:\n" + "-" * 50 + "\n")
                 for fname in sorted(moved_files):
                     f.write(f"  • {fname}\n")
                 f.write("\n" + "-" * 50 + "\n\n" +
                         "These files could not be processed automatically because:\n" +
                         "- No matching .json file was found in the Takeout export (or it was moved/renamed unexpectedly).\n" + # Added context
                         "- They might be duplicates or files Google couldn't associate metadata with.\n\n" +
                         "You can:\n" +
                         "- Manually add metadata if desired.\n" +
                         "- Delete them if they are not needed.\n" +
                         "- Move them elsewhere for archival.\n")
            log_message(f"✓ Created/updated README.txt in NO_METADATA_FOUND", "success")
        except Exception as e:
            log_message(f"✗ Error writing README.txt: {e}", "error")

    log_message(f"✓ Finished separating files. Moved {moved_count} file(s).", "success")
    log_message("=" * 60 + "\n")


def organize_json_files(source_folder):
    """Moves all remaining JSON files to a dedicated folder."""
    log_message("\n" + "=" * 60)
    log_message("📋 Organizing JSON files...", "warning")
    json_folder = os.path.join(source_folder, "JSON_METADATA")
    os.makedirs(json_folder, exist_ok=True)

    json_patterns_lower = {
        '.supplemental-metadata.json', '.supplemental-metada.json',
        '.supplemental-met.json', '.supplemental-m.json',
        '.supplemental.json', '.supplement.json'
    }

    moved_count = 0

    # This runs last, so just find any remaining JSONs
    for dirpath, dirnames, filenames in os.walk(source_folder):
        dirnames[:] = [d for d in dirnames if d not in {'JSON_METADATA', 'NO_METADATA_FOUND'}]

        for filename in filenames:
            if any(filename.lower().endswith(pattern) for pattern in json_patterns_lower):
                source_file = os.path.join(dirpath, filename)
                # Check if the file still exists
                if not os.path.exists(source_file):
                    continue

                dest_path_base = os.path.join(json_folder, filename)
                dest_path = dest_path_base
                counter = 1
                while os.path.exists(dest_path):
                    name, ext = os.path.splitext(filename)
                    dest_path = os.path.join(json_folder, f"{name}_dup{counter}{ext}")
                    counter += 1
                try:
                    shutil.move(source_file, dest_path)
                    moved_count += 1
                except Exception as e:
                    log_message(f"  ✗ Error moving JSON {filename}: {e}", "error")

    # Create README (same as before)
    if moved_count > 0:
        readme_path = os.path.join(json_folder, "README.txt")
        try:
            with open(readme_path, 'w', encoding='utf-8') as f:
                 f.write("GOOGLE PHOTOS METADATA FILES\n" + "=" * 50 + "\n\n" +
                         "This folder contains all the JSON metadata files\n" +
                         "from your Google Photos Takeout export that were\n" +
                         "successfully processed, attempted, or renamed.\n\n" +
                         f"Total JSON files moved here: {moved_count}\n\n" +
                         "These files have been organized here after processing.\n" +
                         "They contain the original metadata exported by Google,\n" +
                         "such as timestamps, GPS (if available), and descriptions.\n\n" +
                         "It is generally safe to keep these as a backup reference,\n" +
                         "but the metadata should now be embedded in your media files\n" +
                         "(which may have been renamed from .heic to .jpg in some cases).\n")
            log_message(f"✓ Created/updated README.txt in JSON_METADATA", "success")
        except Exception as e:
            log_message(f"✗ Error writing README.txt for JSON files: {e}", "error")

    log_message(f"✓ Finished organizing JSON files. Moved {moved_count} file(s).", "success")
    log_message("=" * 60 + "\n")


# --- Entry Point ---

if __name__ == "__main__":
    if len(sys.argv) != 4:
        log_message("Usage: python batch_fixer_cli.py <source_folder> <timezone_mode> <exiftool_path>", "error")
        sys.exit(1)

    source_folder_arg = sys.argv[1]
    timezone_mode_arg = sys.argv[2]
    exiftool_path_arg = sys.argv[3]

    exiftool_command = get_exiftool_command(exiftool_path_arg)

    if not os.path.isdir(source_folder_arg):
         log_message(f"Error: Source folder not found: {source_folder_arg}", "error")
         sys.exit(1)

    if timezone_mode_arg not in ['pacific', 'utc']:
        log_message(f"Error: Invalid timezone mode '{timezone_mode_arg}'. Use 'pacific' or 'utc'.", "error")
        sys.exit(1)

    test_run_args = ['-ver']
    test_result = run_exiftool_command(exiftool_command, test_run_args)
    if not test_result or test_result.returncode != 0:
         log_message(f"Error: ExifTool failed initial check. Path: {exiftool_path_arg}. Error: {test_result.stderr if test_result else 'Execution failed'}", "error")
         sys.exit(1)
    else:
        log_message(f"✓ ExifTool check successful (Version: {test_result.stdout.strip()})", "success")


    updated_count, error_count, skipped_count, total_scanned = process_photos(source_folder_arg, timezone_mode_arg, exiftool_command)

    # Run post-processing AFTER the main loop finishes
    move_files_without_matching_json(source_folder_arg)
    organize_json_files(source_folder_arg)

    log_message("\n" + "=" * 60)
    log_message("🎉 Metadata Application Complete!", "success")
    log_message("=" * 60)
    log_message(f"Total JSON files initially found: {total_scanned}") # Clarified
    log_message(f"Successfully updated files: {updated_count}", "success")
    log_message(f"Skipped (no media found):   {skipped_count}", "warning" if skipped_count > 0 else "default")
    log_message(f"Errors during processing:   {error_count}", "error" if error_count > 0 else "default")
    log_message("\n✅ Metadata embedding finished.", "success")
    log_message("PROCESSING_COMPLETE", "final_marker")

