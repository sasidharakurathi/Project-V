import os
import shutil
from pathlib import Path
from typing import List, Dict, Union
import fnmatch
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import time


class AutoSortEventHandler(FileSystemEventHandler):
    """Watches a directory and automatically sorts new files based on extensions."""

    def __init__(self, watch_dir: str):
        self.watch_dir = watch_dir
        # Define basic sorting rules
        self.rules = {
            "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
            "Documents": [
                ".pdf",
                ".doc",
                ".docx",
                ".txt",
                ".xls",
                ".xlsx",
                ".ppt",
                ".pptx",
                ".md",
            ],
            "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
            "Executables": [".exe", ".msi"],
            "Audio": [".mp3", ".wav", ".ogg", ".flac"],
            "Video": [".mp4", ".mkv", ".avi", ".mov"],
        }

    def _execute_sort(self, event_path):
        """Actually performs the file move after a delay."""
        # Ensure the file still exists at the path (user might have renamed or deleted it during the delay)
        if not os.path.exists(event_path) or os.path.isdir(event_path):
            return

        path = Path(event_path)
        ext = path.suffix.lower()
        if not ext:
            return

        # Explicitly ignore common temporary browser download extensions
        if ext in [".crdownload", ".part", ".tmp", ".download"]:
            return

        # Find which category this extension belongs to
        dest_folder_name = None
        for category, extensions in self.rules.items():
            if ext in extensions:
                dest_folder_name = category
                break

        # If it doesn't match any known rule, do not aggressively sort it.
        # This prevents breaking unknown application files.
        if not dest_folder_name:
            return

        dest_dir = os.path.join(self.watch_dir, dest_folder_name)

        # Ensure destination directory exists
        if not os.path.exists(dest_dir):
            try:
                os.makedirs(dest_dir)
            except Exception:
                pass

        # Move the file
        dest_path = os.path.join(dest_dir, path.name)

        # Avoid overwriting existing files
        if os.path.exists(dest_path):
            base_name = path.stem
            dest_path = os.path.join(dest_dir, f"{base_name}_{int(time.time())}{ext}")

        try:
            shutil.move(event_path, dest_path)
            print(
                f"[Watchdog] Successfully auto-sorted: {path.name} -> {dest_folder_name}/"
            )
        except Exception as e:
            print(f"[Watchdog] Failed to auto-sort {path.name}: {e}")

    def _schedule_sort(self, event_path):
        """Schedules a file to be sorted after a 5 second delay to ensure the user isn't interacting with it."""
        timer = threading.Timer(5.0, self._execute_sort, args=[event_path])
        timer.daemon = True
        timer.start()

    def on_created(self, event):
        # We only care about new files created in the monitored directory
        # specifically ignoring files created inside subdirectories to prevent infinite loops
        if not event.is_directory and os.path.dirname(event.src_path) == self.watch_dir:
            self._schedule_sort(event.src_path)

    def on_moved(self, event):
        # Handle files moved into the directory or renamed within
        if (
            not event.is_directory
            and os.path.dirname(event.dest_path) == self.watch_dir
        ):
            self._schedule_sort(event.dest_path)


# Global observer reference so we can stop it if needed
_active_observer = None


def watch_folder(directory_path: str) -> str:
    """Starts a background watchdog observer to monitor a folder and automatically organize incoming files by extension type. Provide the absolute directory path."""
    global _active_observer

    if not os.path.isdir(directory_path):
        return f"Error: '{directory_path}' is not a valid directory."

    try:
        if _active_observer and _active_observer.is_alive():
            _active_observer.stop()
            _active_observer.join()

        event_handler = AutoSortEventHandler(directory_path)
        _active_observer = Observer()
        _active_observer.schedule(event_handler, directory_path, recursive=False)
        _active_observer.start()

        return f"Successfully started watching '{directory_path}'. New files will be automatically sorted into subtype folders."
    except Exception as e:
        return f"Failed to start folder watcher: {e}"


def rename_files(directory_path: str, pattern: str, replacement: str) -> str:
    """Batch renames files in a directory by replacing a specific string pattern with a new string. Case-sensitive."""
    if not os.path.isdir(directory_path):
        return f"Error: '{directory_path}' is not a valid directory."

    renamed_count = 0
    try:
        for filename in os.listdir(directory_path):
            if pattern in filename:
                new_name = filename.replace(pattern, replacement)
                old_path = os.path.join(directory_path, filename)
                new_path = os.path.join(directory_path, new_name)
                os.rename(old_path, new_path)
                renamed_count += 1

        return f"Successfully renamed {renamed_count} files in '{directory_path}' matching pattern '{pattern}'."
    except Exception as e:
        return f"Error during batch rename: {e}"


def move_files(
    source_dir: str, destination_dir: str, extension_filter: str = "*"
) -> str:
    """Moves all files (optionally filtered by extension like '.jpg') from a source to a destination directory."""
    if not os.path.isdir(source_dir):
        return f"Error: Source '{source_dir}' is not a valid directory."

    if not os.path.exists(destination_dir):
        try:
            os.makedirs(destination_dir)
        except Exception as e:
            return f"Error: Could not create destination directory '{destination_dir}': {e}"

    moved_count = 0
    try:
        for filename in os.listdir(source_dir):
            if extension_filter == "*" or filename.endswith(extension_filter):
                src_path = os.path.join(source_dir, filename)
                if os.path.isfile(src_path):
                    shutil.move(src_path, os.path.join(destination_dir, filename))
                    moved_count += 1

        return f"Successfully moved {moved_count} files matching '{extension_filter}' from '{source_dir}' to '{destination_dir}'."
    except Exception as e:
        return f"Error during file move: {e}"


def search_files(directory_path: str, query: str) -> str:
    """Performs a basic file search within a directory (recursive) looking for exact filename matches or wildcard globs like '*.txt'."""
    if not os.path.isdir(directory_path):
        return f"Error: '{directory_path}' is not a valid directory."

    results = []
    try:
        for root, _, files in os.walk(directory_path):
            for file in files:
                if (
                    fnmatch.fnmatch(file.lower(), query.lower())
                    or query.lower() in file.lower()
                ):
                    results.append(os.path.join(root, file))
                    if (
                        len(results) >= 20
                    ):  # Cap output to prevent massive LLM context overload
                        break
            if len(results) >= 20:
                break

        if not results:
            return f"No files found matching '{query}' in '{directory_path}'."

        found_str = "\\n".join(results)
        return f"Found {len(results)} matches for '{query}':\\n{found_str}"

    except Exception as e:
        return f"Error searching files: {e}"


def create_folder_structure(base_path: str, folders: str) -> str:
    """Creates multiple subfolders at a base path. Provide a comma-separated list of folder names (e.g. 'src,assets,docs')."""
    if not os.path.isdir(base_path):
        return f"Error: Base path '{base_path}' does not exist."

    folder_list = [f.strip() for f in folders.split(",") if f.strip()]
    created_count = 0

    try:
        for folder in folder_list:
            target_path = os.path.join(base_path, folder)
            os.makedirs(target_path, exist_ok=True)
            created_count += 1

        return f"Successfully created {created_count} folders at '{base_path}'."
    except Exception as e:
        return f"Error creating folder structure: {e}"
