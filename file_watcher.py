import os
import time
import re
import shutil
import logging
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class MarkdownHandler(FileSystemEventHandler):
    def __init__(self, output_dir, vault_sync_dir):
        self.output_dir = output_dir
        self.vault_sync_dir = vault_sync_dir

    def on_created(self, event):
        if event.is_directory:
            return

        filename = os.path.basename(event.src_path)
        if not filename.endswith('.md'):
            return

        # Wait a brief moment to ensure file write is complete
        time.sleep(0.5)
        
        try:
            self.process_file(event.src_path, filename)
        except Exception as e:
            logging.error(f"Error processing file {filename}: {e}")

    def sanitize_filename(self, filename):
        # Remove extension for sanitization
        name, ext = os.path.splitext(filename)
        # Remove illegal characters (keep alphanumeric, spaces, hyphens, underscores)
        sanitized_name = re.sub(r'[^\w\s-]', '', name)
        # Strip whitespace and replace multiple spaces with single space
        sanitized_name = re.sub(r'\s+', ' ', sanitized_name).strip()
        return f"{sanitized_name}{ext}"

    def process_file(self, file_path, original_filename):
        logging.info(f"Detected new file: {original_filename}")

        # 1. Sanitize filename
        sanitized_filename = self.sanitize_filename(original_filename)
        
        # 2. Read content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 3. Prepend YAML frontmatter
        timestamp = datetime.now().isoformat()
        frontmatter = f"""---
created: {timestamp}
type: "WorldSmith Entry"
status: "AI Generated"
---

"""
        new_content = frontmatter + content

        # 4. Move to vault_sync
        # We write to the new location directly to handle the move + edit in one logical step for the destination
        # But the requirement says "Move the processed file". 
        # So we can overwrite the current file then move, or write new and delete old.
        # Writing new and deleting old is safer.
        
        dest_path = os.path.join(self.vault_sync_dir, sanitized_filename)
        
        # Ensure destination directory exists (script attempts to create it if possible)
        os.makedirs(self.vault_sync_dir, exist_ok=True)

        with open(dest_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        logging.info(f"Processed and moved to: {dest_path}")

        # Remove original file
        try:
            os.remove(file_path)
        except OSError as e:
            logging.warning(f"Could not remove original file {file_path}: {e}")

if __name__ == "__main__":
    # Define paths relative to this script
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # "../database/output" relative to script. 
    # If script is in .../database, then .. is .../ and ../database/output is .../database/output
    # Effectively ./output
    OUTPUT_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "../database/output"))
    
    # "../vault_sync" relative to script
    VAULT_SYNC_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "../vault_sync"))

    # Ensure output directory exists to watch it
    if not os.path.exists(OUTPUT_DIR):
        try:
            os.makedirs(OUTPUT_DIR)
            logging.info(f"Created output directory: {OUTPUT_DIR}")
        except OSError as e:
            logging.error(f"Failed to create output directory {OUTPUT_DIR}: {e}")
            exit(1)

    event_handler = MarkdownHandler(OUTPUT_DIR, VAULT_SYNC_DIR)
    observer = Observer()
    observer.schedule(event_handler, OUTPUT_DIR, recursive=False)
    
    logging.info(f"Monitoring {OUTPUT_DIR}")
    logging.info(f"Target sync folder: {VAULT_SYNC_DIR}")
    
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
