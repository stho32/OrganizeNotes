#!/usr/bin/env python3

import os
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('find_duplicate_filenames.log'),
        logging.StreamHandler()
    ]
)

class DuplicateFileFinder:
    def __init__(self, config_path: str = "notes_organizer_config.json"):
        self.config = self._load_config(config_path)
        self.notes_path = Path(self.config['notes_path'])
        logging.info(f"Initialized DuplicateFileFinder with notes path: {self.notes_path}")

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            raise

    def find_duplicates(self) -> Dict[str, List[Path]]:
        """Find files with identical names in different folders."""
        duplicates = defaultdict(list)
        
        # Walk through all files in the notes directory
        for root, dirs, files in os.walk(self.notes_path):
            # Skip directories that start with a dot
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for filename in files:
                file_path = Path(root) / filename
                duplicates[filename].append(file_path)
        
        # Filter out files that don't have duplicates
        return {k: v for k, v in duplicates.items() if len(v) > 1}

    def handle_duplicates(self):
        """Interactive menu to handle duplicate files."""
        duplicates = self.find_duplicates()
        
        if not duplicates:
            print("No duplicate filenames found!")
            return

        print(f"\nFound {len(duplicates)} sets of duplicate filenames:")
        
        for filename, paths in duplicates.items():
            print(f"\nDuplicate filename: {filename}")
            print("Files found:")
            
            for idx, path in enumerate(paths, 1):
                print(f"{idx}. {path}")
                
            while True:
                print("\nOptions:")
                print("1-N: Delete corresponding file")
                print("s: Skip this set")
                print("q: Quit program")
                
                choice = input("\nWhat would you like to do? ").lower()
                
                if choice == 'q':
                    print("Exiting program...")
                    return
                elif choice == 's':
                    print("Skipping to next set...")
                    break
                else:
                    try:
                        idx = int(choice)
                        if 1 <= idx <= len(paths):
                            file_to_delete = paths[idx-1]
                            try:
                                os.remove(file_to_delete)
                                print(f"Deleted: {file_to_delete}")
                                break
                            except Exception as e:
                                logging.error(f"Error deleting file: {e}")
                                print(f"Error deleting file: {e}")
                        else:
                            print("Invalid number. Please try again.")
                    except ValueError:
                        print("Invalid input. Please enter a number, 's' to skip, or 'q' to quit.")

def main():
    try:
        finder = DuplicateFileFinder()
        finder.handle_duplicates()
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
