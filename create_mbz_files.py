import os
import shutil
import zipfile

def create_mbz_backup(folder_path, output_mbz_path):
    """Create a valid Moodle .mbz file from a backup folder."""
    with zipfile.ZipFile(output_mbz_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path)
                zipf.write(file_path, arcname)

# Create output directory for .mbz files
OUTPUT_DIR = "moodle_mbz_backups"
GENERATED_DIR = "generated_backups"

if not os.path.exists(GENERATED_DIR):
    print(f"Error: {GENERATED_DIR} folder not found!")
    exit(1)

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)
    print(f"Created output directory: {OUTPUT_DIR}")

# Get list of all backup folders
backup_folders = [d for d in os.listdir(GENERATED_DIR) 
                  if os.path.isdir(os.path.join(GENERATED_DIR, d))]

print(f"Found {len(backup_folders)} backup folders to convert to .mbz")

for i, folder_name in enumerate(backup_folders, 1):
    folder_path = os.path.join(GENERATED_DIR, folder_name)
    mbz_path = os.path.join(OUTPUT_DIR, f"{folder_name}.mbz")
    
    try:
        create_mbz_backup(folder_path, mbz_path)
        print(f"[{i}/{len(backup_folders)}] Created: {folder_name}.mbz")
    except Exception as e:
        print(f"[{i}/{len(backup_folders)}] Error creating {folder_name}.mbz: {e}")

print(f"\nSuccessfully created {len(backup_folders)} .mbz files in '{OUTPUT_DIR}'")
print("You can now upload these .mbz files to Moodle!")
