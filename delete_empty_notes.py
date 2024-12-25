#!/usr/bin/env python3

import os
import json

def load_config():
    """Load the configuration from notes_organizer_config.json"""
    with open('notes_organizer_config.json', 'r') as f:
        return json.load(f)

def is_file_empty(filepath):
    """Check if a file is empty or contains only whitespace"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read().strip()
        return len(content) == 0

def find_and_delete_empty_markdown_files(notes_path):
    """Recursively find and delete empty markdown files"""
    deleted_files = []
    skipped_files = []
    auto_accept = False
    
    print("\nStarting search for empty markdown files...")
    
    for root, _, files in os.walk(notes_path):
        for file in files:
            if file.lower().endswith(('.md', '.markdown')):
                filepath = os.path.join(root, file)
                print(f"\nChecking file: {filepath}")
                
                try:
                    if is_file_empty(filepath):
                        print(f"Found empty file: {filepath}")
                        
                        if not auto_accept:
                            response = input("Do you want to delete this file? (y/n/a - 'a' to accept all): ").lower().strip()
                            if response == 'a':
                                auto_accept = True
                                response = 'y'
                        else:
                            response = 'y'
                            print("Auto-accepting deletion...")
                        
                        if response == 'y':
                            os.remove(filepath)
                            deleted_files.append(filepath)
                            print(f"Deleted: {filepath}")
                        else:
                            skipped_files.append(filepath)
                            print(f"Skipped: {filepath}")
                    else:
                        print(f"File is not empty, skipping.")
                except (IOError, OSError) as e:
                    print(f"Error processing {filepath}: {e}")
    
    return deleted_files, skipped_files

def main():
    try:
        config = load_config()
        notes_path = config['notes_path']
        
        if not os.path.exists(notes_path):
            print(f"Error: Notes path '{notes_path}' does not exist!")
            return
        
        print(f"Starting search in: {notes_path}")
        deleted_files, skipped_files = find_and_delete_empty_markdown_files(notes_path)
        
        print("\n=== Summary ===")
        if deleted_files:
            print("\nDeleted files:")
            for file in deleted_files:
                print(f"- {file}")
            print(f"\nTotal files deleted: {len(deleted_files)}")
        else:
            print("\nNo files were deleted.")
            
        if skipped_files:
            print("\nSkipped files:")
            for file in skipped_files:
                print(f"- {file}")
            print(f"\nTotal files skipped: {len(skipped_files)}")
            
    except FileNotFoundError:
        print("Error: Could not find notes_organizer_config.json")
    except json.JSONDecodeError:
        print("Error: Invalid JSON in configuration file")
    except KeyError:
        print("Error: Missing required 'notes_path' in configuration")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
