#!/usr/bin/env python3

import os
import json
import logging
from pathlib import Path
from typing import List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('delete_empty_folders.log'),
        logging.StreamHandler()
    ]
)

class EmptyFolderCleaner:
    def __init__(self, config_path: str = "notes_organizer_config.json"):
        self.config = self._load_config(config_path)
        self.notes_path = Path(self.config['notes_path'])
        logging.info(f"Initialized EmptyFolderCleaner with notes path: {self.notes_path}")

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            raise

    def is_empty(self, path: Path) -> bool:
        """Check if a directory is empty, ignoring hidden files."""
        try:
            # List all items in the directory
            items = list(path.iterdir())
            
            # Filter out hidden files/folders
            visible_items = [item for item in items if not item.name.startswith('.')]
            
            return len(visible_items) == 0
        except Exception as e:
            logging.error(f"Error checking if directory is empty: {e}")
            return False

    def find_empty_folders(self) -> List[Path]:
        """Find all empty folders in the notes directory."""
        empty_folders = []
        
        # Walk bottom-up so we can identify nested empty folders
        for root, dirs, files in os.walk(self.notes_path, topdown=False):
            # Skip directories that start with a dot
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            current_path = Path(root)
            
            # Skip if the current directory starts with a dot
            if current_path.name.startswith('.'):
                continue
                
            if self.is_empty(current_path):
                empty_folders.append(current_path)
                
        return empty_folders

    def clean_empty_folders(self):
        """Remove all empty folders."""
        empty_folders = self.find_empty_folders()
        
        if not empty_folders:
            print("No empty folders found!")
            return
            
        print(f"\nFound {len(empty_folders)} empty folders:")
        for folder in empty_folders:
            print(f"Removing: {folder}")
            try:
                os.rmdir(folder)
                logging.info(f"Removed empty folder: {folder}")
            except Exception as e:
                logging.error(f"Error removing folder {folder}: {e}")
                print(f"Error removing folder {folder}: {e}")

def main():
    try:
        cleaner = EmptyFolderCleaner()
        cleaner.clean_empty_folders()
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
