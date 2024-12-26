import os
import json
import shutil
import zlib
from pathlib import Path
import logging
from typing import Dict, List, Optional
from anthropic import Anthropic

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('notes_organizer.log')
    ]
)

class NotesOrganizer:
    def __init__(self, config_path: str = "notes_organizer_config.json", sort_mode: str = "sorted"):
        logging.info("Initializing NotesOrganizer")
        self.config = self._load_config(config_path)
        self.api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not self.api_key:
            logging.error("ANTHROPIC_API_KEY environment variable is not set")
            raise ValueError("ANTHROPIC_API_KEY environment variable is not set")
        self.client = Anthropic(api_key=self.api_key)
        self.memory_file = "gedaechtnis.json"
        self.memory = self._load_memory()
        self.sort_mode = sort_mode.lower()
        if self.sort_mode not in ["sorted", "random"]:
            logging.warning(f"Invalid sort_mode '{sort_mode}', defaulting to 'sorted'")
            self.sort_mode = "sorted"
        logging.info(f"Loaded configuration from {config_path}")
        logging.info(f"Notes path: {self.config['notes_path']}")
        logging.info(f"Memory file: {self.memory_file}")
        logging.info(f"Sort mode: {self.sort_mode}")
        
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config
        except Exception as e:
            logging.error(f"Error loading config: {e}")
            raise
    
    def _load_memory(self) -> dict:
        """Load or initialize memory file."""
        logging.info(f"Loading memory from {self.memory_file}")
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r', encoding='utf-8') as f:
                    memory = json.load(f)
                    logging.info(f"Loaded existing memory with {len(memory['files'])} files and {len(memory['themes'])} themes")
                    return memory
            except Exception as e:
                logging.error(f"Error loading memory file: {e}")
                logging.info("Deleting corrupted memory file and creating new one")
                try:
                    os.remove(self.memory_file)
                except Exception as del_err:
                    logging.error(f"Error deleting corrupted memory file: {del_err}")
        
        logging.info("Creating new memory file with existing folder names")
        # Get existing folder names from the target directory
        themes = []
        try:
            for item in os.listdir(self.config["notes_path"]):
                full_path = os.path.join(self.config["notes_path"], item)
                if os.path.isdir(full_path) and not item.startswith('.'):
                    themes.append(item)
            logging.info(f"Found {len(themes)} existing themes in target directory")
        except Exception as e:
            logging.error(f"Error reading target directory: {e}")
            themes = []
            
        memory = {"files": {}, "themes": themes}
        self.memory = memory  # Assign to self.memory before saving
        self._save_memory()  # Save the initialized memory
        return memory
    
    def _save_memory(self):
        """Save current memory state to file."""
        logging.info("Saving memory to file")
        try:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.memory, f, indent=4)
            logging.info(f"Memory saved successfully with {len(self.memory['files'])} files and {len(self.memory['themes'])} themes")
        except Exception as e:
            logging.error(f"Error saving memory: {e}")
            raise
    
    def calculate_crc(self, file_path: str) -> str:
        """Calculate CRC32 hash of a file."""
        logging.info(f"Calculating CRC for {file_path}")
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
                crc = format(zlib.crc32(content) & 0xFFFFFFFF, '08x')
                return crc
        except Exception as e:
            logging.error(f"Error calculating CRC for {file_path}: {e}")
            raise
    
    def get_file_content(self, file_path: str) -> Optional[str]:
        """Get file content if it's a markdown file."""
        if file_path.lower().endswith('.md'):
            logging.info(f"Reading markdown file: {file_path}")
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Check if file is empty or contains only whitespace
                    if not content.strip():
                        logging.info(f"Found empty markdown file: {file_path}")
                        try:
                            os.remove(file_path)
                            logging.info(f"Deleted empty markdown file: {file_path}")
                            return None
                        except Exception as e:
                            logging.error(f"Error deleting empty file {file_path}: {e}")
                            raise
                    return content
            except Exception as e:
                logging.error(f"Error reading file {file_path}: {e}")
                raise
        logging.info(f"Skipping non-markdown file: {file_path}")
        return None
    
    def get_theme_from_llm(self, filename: str, content: Optional[str]) -> List[str]:
        """Query LLM to determine three possible themes for the file."""
        logging.info(f"Getting themes for {filename}")
        
        existing_themes = ", ".join(self.memory["themes"]) if self.memory["themes"] else "No existing themes yet"
        logging.info(f"Existing themes: {existing_themes}")
        
        system_prompt = "You are a helpful assistant that categorizes files into themes. Return exactly three theme suggestions, one per line, no additional text. If any themes match existing ones, use those exact names. For new themes, make them concise (1-3 words) and descriptive."
        
        user_prompt = f"""Analyze this file and suggest three possible themes. If it contains 'MOC' in the filename or the content, make 'MOCs' the first theme.
Filename: {filename}
Existing themes: {existing_themes}

Content: {content if content else 'Non-markdown file, using filename only'}

Return exactly three themes, one per line."""

        try:
            logging.info(f"Sending request to Anthropic API for {filename}")
            message = self.client.messages.create(
                model=self.config["model"],
                system=system_prompt,
                max_tokens=100,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            # Get all non-empty lines from the response
            themes = [t.strip() for t in message.content[0].text.strip().split('\n') if t.strip()]
            
            # Validate themes
            valid_themes = []
            for theme in themes[:3]:  # Take at most 3 themes
                # Basic validation: ensure theme is a reasonable length and contains valid characters
                if 1 <= len(theme) <= 50 and any(c.isalnum() for c in theme):
                    valid_themes.append(theme)
            
            # If we got no valid themes from AI, use fallback
            if not valid_themes:
                logging.warning("No valid themes received from AI, using fallback themes")
                valid_themes = ["Unsorted", "General", "Misc"]
            
            # If we got fewer than 3 themes, add some sensible defaults
            while len(valid_themes) < 3:
                fallback_options = ["Unsorted", "General", "Misc", "Documents", "Notes"]
                for fallback in fallback_options:
                    if fallback not in valid_themes:
                        valid_themes.append(fallback)
                        break
                if len(valid_themes) < 3:  # If we still don't have enough, add numbered misc
                    valid_themes.append(f"Misc_{len(valid_themes) + 1}")
            
            logging.info(f"Final themes after validation: {valid_themes[:3]}")
            return valid_themes[:3]
            
        except Exception as e:
            logging.error(f"Error getting themes from LLM: {e}")
            logging.warning(f"Using fallback themes for {filename}")
            return ["Unsorted", "General", "Misc"]

    def sanitize_theme_name(self, theme: str) -> str:
        """Convert theme name to directory-friendly format."""
        logging.info(f"Sanitizing theme name: {theme}")
        sanitized = "".join(c if c.isalnum() or c in "_ -" else "_" for c in theme)
        result = sanitized.strip("_")
        return result
    
    def should_process_path(self, path: str) -> bool:
        """Check if a path should be processed."""
        # Check each part of the path
        path_parts = Path(path).parts
        for part in path_parts:
            # Skip if any directory in the path starts with a dot
            if part.startswith('.'):
                return False
        return True

    def remove_empty_directories(self):
        """Remove empty directories recursively in the target directory."""
        logging.info("Starting removal of empty directories")
        
        def is_directory_empty(path: str) -> bool:
            """Check if directory is empty, ignoring .git and dot files/directories."""
            for item in os.listdir(path):
                # Skip .git and dot files/directories
                if item.startswith('.'):
                    continue
                item_path = os.path.join(path, item)
                if os.path.isfile(item_path) or os.path.isdir(item_path):
                    return False
            return True

        # Walk bottom-up so we process deepest directories first
        for root, dirs, files in os.walk(self.config["notes_path"], topdown=False):
            # Skip directories we shouldn't process
            if not self.should_process_path(root):
                logging.info(f"Skipping excluded directory: {root}")
                continue

            logging.info(f"Scanning directory: {root}")
            for file in files:
                if file != self.memory_file:
                    file_path = os.path.normpath(os.path.join(root, file))
                    self.process_file(file_path)
            
            # After processing all files, remove empty directories
            if is_directory_empty(root) and root != self.config["notes_path"]:
                try:
                    os.rmdir(root)
                    logging.info(f"Removed empty directory: {root}")
                except Exception as e:
                    logging.error(f"Error removing directory {root}: {e}")

    def process_file(self, file_path: str):
        """Process a single file."""
        # Skip files we shouldn't process
        if not self.should_process_path(file_path):
            logging.info(f"Skipping excluded path: {file_path}")
            return

        # Skip processing if file doesn't exist (might have been deleted as empty)
        if not os.path.exists(file_path):
            logging.info(f"File no longer exists, skipping: {file_path}")
            return
            
        logging.info(f"Processing file: {file_path}")
        filename = os.path.basename(file_path)
        
        while True:  # Loop to allow retries
            current_crc = self.calculate_crc(file_path)
            
            # Check if file needs processing
            if (filename in self.memory["files"] and 
                self.memory["files"][filename]["crc"] == current_crc):
                logging.info(f"File {filename} already processed and unchanged, skipping")
                return
            
            logging.info(f"File {filename} needs processing (new or modified)")
            # Get content and themes
            content = self.get_file_content(file_path)
            
            # Display file content
            print("\n" + "="*80)
            print(f"Dateiinhalt von '{filename}':")
            print("="*80)
            if content:
                # If it's a markdown file, show the content
                print(content)
            else:
                # If it's not a markdown file or content is None
                print("(Keine Vorschau verfügbar - keine Markdown-Datei)")
            print("="*80 + "\n")
            
            try:
                themes = self.get_theme_from_llm(filename, content)
                if not themes or len(themes) != 3:
                    logging.error("Unexpected number of themes received")
                    themes = ["Unsorted", "General", "Misc"]
            except Exception as e:
                logging.error(f"Error during theme generation: {e}")
                themes = ["Unsorted", "General", "Misc"]
            
            # Print suggestions and get user choice
            print(f"\nVorgeschlagene Aktionen für '{filename}':")
            print(f"Aktueller Pfad: {file_path}")
            print("\nVorgeschlagene Themen:")
            for i, theme in enumerate(themes, 1):
                sanitized_theme = self.sanitize_theme_name(theme)
                new_path = os.path.join(self.config["notes_path"], sanitized_theme, filename)
                print(f"{i} - {theme}      -> {new_path}")
            
            print("\nOptionen:")
            print("1-3 - Thema auswählen")
            print("n   - Abbrechen")
            print("d   - löschen")
            print("r   - noch einmal versuchen")
            print("Alternativer Name - Geben Sie einen anderen Ordnernamen ein")
            confirmation = input("\nIhre Wahl: ").strip()

            if confirmation.lower() == 'n':
                logging.info(f"User skipped moving {filename}")
                return
            elif confirmation.lower() == 'd':
                try:
                    os.remove(file_path)
                    logging.info(f"Deleted file: {filename}")
                    return
                except Exception as e:
                    logging.error(f"Error deleting file {filename}: {e}")
                    raise
            elif confirmation.lower() == 'r':
                logging.info(f"User requested retry for {filename}")
                continue  # Start the process again
            
            # Handle theme selection (1-3) or custom theme
            selected_theme = None
            if confirmation in ['1', '2', '3']:
                selected_theme = themes[int(confirmation) - 1]
            else:
                selected_theme = confirmation
            
            sanitized_theme = self.sanitize_theme_name(selected_theme)
            theme_dir = os.path.join(self.config["notes_path"], sanitized_theme)
            new_path = os.path.join(theme_dir, filename)
            os.makedirs(theme_dir, exist_ok=True)
            
            try:
                shutil.move(file_path, new_path)
                logging.info(f"File moved successfully")
            except Exception as e:
                logging.error(f"Error moving file: {e}")
                raise
            
            # Update memory
            if selected_theme not in self.memory["themes"]:
                logging.info(f"Adding new theme: {selected_theme}")
                self.memory["themes"].append(selected_theme)
            
            self.memory["files"][filename] = {
                "crc": current_crc,
                "theme": selected_theme
            }
            
            self._save_memory()
            logging.info(f"Successfully processed {filename} -> {selected_theme}")
            return  # Exit the loop after successful processing
    
    def organize_notes(self):
        """Main function to organize all notes."""
        logging.info("Starting notes organization")
        logging.info(f"Processing directory: {self.config['notes_path']} in {self.sort_mode} order")
        
        try:
            # Collect all files first
            files_to_process = []
            print("\nScanning for files...")
            for root, _, files in os.walk(self.config["notes_path"]):
                # Skip directories we shouldn't process
                if not self.should_process_path(root):
                    logging.info(f"Skipping excluded directory: {root}")
                    continue

                logging.info(f"Scanning directory: {root}")
                for file in files:
                    if file != self.memory_file:
                        file_path = os.path.normpath(os.path.join(root, file))
                        files_to_process.append((file_path, len(os.path.dirname(file_path).split(os.sep))))

            total_files = len(files_to_process)
            print(f"\nGefunden: {total_files} Dateien zum Verarbeiten")

            # Sort files based on sort_mode
            if self.sort_mode == "sorted":
                # Sort by depth (files without folders first), then alphabetically
                files_to_process.sort(key=lambda x: (x[1], x[0]))
                logging.info("Processing files in sorted order")
            else:  # random mode
                import random
                random.shuffle(files_to_process)
                logging.info("Processing files in random order")

            # Process files in the determined order
            for index, (file_path, _) in enumerate(files_to_process, 1):
                print(f"\nVerarbeite Datei {index} von {total_files} ({(index/total_files)*100:.1f}%)")
                print(f"Aktuelle Datei: {os.path.basename(file_path)}")
                self.process_file(file_path)
            
            # After processing all files, remove empty directories
            print("\nEntferne leere Verzeichnisse...")
            self.remove_empty_directories()
            
            print("\nVerarbeitung abgeschlossen!")
            logging.info("Notes organization completed successfully")
        except Exception as e:
            logging.error(f"Error during notes organization: {e}")
            raise

if __name__ == "__main__":
    try:
        logging.info("Starting NotesOrganizer")
        # Ask for sort mode
        print("\nHow would you like to process the files?")
        print("1. Sorted (alphabetically, files without folders first)")
        print("2. Random order")
        choice = input("\nEnter your choice (1/2): ").strip()
        
        sort_mode = "sorted" if choice == "1" else "random"
        organizer = NotesOrganizer(sort_mode=sort_mode)
        organizer.organize_notes()
        logging.info("NotesOrganizer completed successfully")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        raise
