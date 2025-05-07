import json
import os
import time
import pathlib
import logging
import threading
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union

# Create an independent logger for hunting operations that doesn't rely on Flask
def create_independent_logger():
    """Create a logger that works regardless of Flask context"""
    log_handler = logging.StreamHandler(sys.stdout)
    log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
                                      datefmt='%Y-%m-%d %H:%M:%S')
    log_handler.setFormatter(log_formatter)
    
    independent_logger = logging.getLogger("hunting_manager_independent")
    independent_logger.setLevel(logging.INFO)
    independent_logger.addHandler(log_handler)
    independent_logger.propagate = False  # Don't propagate to parent loggers
    
    return independent_logger

# Standard logger (may fail in background threads)
logger = logging.getLogger("hunting_manager")
# Independent logger (will work in any context)
independent_logger = create_independent_logger()

# Path will be /config/history in production
HISTORY_BASE_PATH = pathlib.Path("/config/history")

# Lock to prevent race conditions during file operations
history_locks = {
    "sonarr": threading.Lock(),
    "radarr": threading.Lock(),
    "lidarr": threading.Lock(),
    "readarr": threading.Lock(),
    "whisparr": threading.Lock(),
    "eros": threading.Lock(),
    "swaparr": threading.Lock()
}

class HuntingManager:
    """Unified HuntingManager that combines hunting and history functionality.
    
    This class handles all aspects of hunting and history tracking:
    1. Management of history files with app-specific metadata
    2. Tracking hunt status and processed items
    3. Providing statistics and recent activity information
    4. Integration with the stateful_manager for processed IDs
    
    The field_mapper.py handles the actual data processing and structure.
    """
    def __init__(self, config_dir: str):
        """Initialize the HuntingManager with minimal configuration.
        
        Args:
            config_dir: Base configuration directory (mostly for compatibility)
        """
        self.config_dir = config_dir
        self.history_dir = os.path.join(config_dir, "history")
        logger.info(f"HuntingManager initialized using history data from {self.history_dir}")
        # Ensure history directories exist
        self.ensure_history_dir()
        
    def ensure_history_dir(self):
        """Ensure the history directory exists with app-specific subdirectories"""
        try:
            # Create base directory
            HISTORY_BASE_PATH.mkdir(exist_ok=True, parents=True)
            
            # Create app-specific directories
            for app in history_locks.keys():
                app_dir = HISTORY_BASE_PATH / app
                app_dir.mkdir(exist_ok=True, parents=True)
                        
            return True
        except Exception as e:
            logger.error(f"Failed to create history directory: {str(e)}")
            return False
    
    def get_history_file_path(self, app_type: str, instance_name: Optional[str] = None) -> pathlib.Path:
        """Get the appropriate history file path based on app type and instance name
        
        Args:
            app_type: Type of application (radarr, sonarr, etc.)
            instance_name: Name of the instance, defaults to "Default"
            
        Returns:
            Path to the history file
        """
        # If no instance name is provided, use "Default"
        if instance_name is None:
            instance_name = "Default"
        
        # Create safe filename from instance name
        safe_instance_name = "".join([c if c.isalnum() else "_" for c in instance_name])
        return HISTORY_BASE_PATH / app_type / f"{safe_instance_name}.json"

    def add_history_entry(self, app_type: str, entry_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Add a history entry to the history file."""
        # Validate app type
        if app_type not in history_locks:
            independent_logger.error(f"Invalid app type: {app_type}")
            return None
        
        # Check required fields
        required_fields = ["name", "instance_name", "id"]
        for field in required_fields:
            if field not in entry_data:
                independent_logger.error(f"Missing required field: {field}")
                return None
        
        # Log the instance name for debugging
        instance_name = entry_data["instance_name"]
        independent_logger.info(f"Adding history entry for {app_type} with instance_name: '{instance_name}'")
        
        # Create the entry with timestamp
        timestamp = int(time.time())
        
        # Base fields common to all app types
        entry = {
            "date_time": timestamp,
            "date_time_readable": datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S'),
            "processed_info": entry_data["name"],
            "id": entry_data["id"],
            "instance_name": instance_name,
            "operation_type": entry_data.get("operation_type", "missing"),
            "app_type": app_type,
            "hunt_status": entry_data.get("hunt_status", "Not Tracked"),
            "monitored": entry_data.get("monitored", None)
        }
        
        # Add app-specific fields based on the app_type
        if app_type == "radarr" or app_type == "whisparr" or app_type == "eros":
            # Movie-specific fields
            entry.update({
                "quality": entry_data.get("quality", None),
                "size_mb": entry_data.get("size_mb", None),
                "protocol": entry_data.get("protocol", None), 
                "year": entry_data.get("year", None)
            })
            # Only add IDs if they exist
            if "imdb_id" in entry_data:
                entry["imdb_id"] = entry_data["imdb_id"]
            if "tmdb_id" in entry_data:
                entry["tmdb_id"] = entry_data["tmdb_id"]
                
        elif app_type == "sonarr":
            # Series-specific fields
            entry.update({
                "quality": entry_data.get("quality", None),
                "size_mb": entry_data.get("size_mb", None),
                "protocol": entry_data.get("protocol", None),
                "season": entry_data.get("season", None),
                "episode": entry_data.get("episode", None)
            })
            # Only add IDs if they exist
            if "tvdb_id" in entry_data:
                entry["tvdb_id"] = entry_data["tvdb_id"]
                
        elif app_type == "lidarr":
            # Music-specific fields
            entry.update({
                "quality": entry_data.get("quality", None),
                "size_mb": entry_data.get("size_mb", None),
                "artist": entry_data.get("artist", None),
                "album": entry_data.get("album", None)
            })
            
        elif app_type == "readarr":
            # Book-specific fields
            entry.update({
                "quality": entry_data.get("quality", None),
                "size_mb": entry_data.get("size_mb", None),
                "author": entry_data.get("author", None),
                "book": entry_data.get("book", None)
            })
            
        # Add indexer if provided (useful for all types)
        if "indexer" in entry_data:
            entry["indexer"] = entry_data["indexer"]
        
        history_file = self.get_history_file_path(app_type, instance_name)
        independent_logger.debug(f"Writing to history file: {history_file}")
        
        # Make sure the parent directory exists
        history_file.parent.mkdir(exist_ok=True, parents=True)
        
        # Thread-safe file operation
        with history_locks[app_type]:
            try:
                if history_file.exists():
                    with open(history_file, 'r') as f:
                        history_data = json.load(f)
                else:
                    history_data = []
                    
                # Check for duplicates based on ID and operation_type
                # Only allow one entry per ID per operation type
                for existing_entry in history_data:
                    if (str(existing_entry.get("id")) == str(entry["id"]) and 
                        existing_entry.get("operation_type") == entry["operation_type"]):
                        independent_logger.debug(f"Duplicate entry found for {app_type}-{instance_name} ID {entry['id']} with operation {entry['operation_type']}")
                        return None
                
                # Add new entry at the beginning for most recent first
                history_data.insert(0, entry)
                
                # Write back to file
                with open(history_file, 'w') as f:
                    json.dump(history_data, f, indent=2)
                
                independent_logger.info(f"Added history entry for {app_type}-{instance_name}: {entry_data['name']}")
                return entry
                
            except Exception as e:
                independent_logger.error(f"Error adding history entry: {str(e)}")
                return None
                
    def update_history_entry_status(self, app_type: str, instance_name: str, item_id: str, 
                                     new_status: str, additional_fields: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update the status of an existing history entry
        
        Parameters:
        - app_type: str - The app type (sonarr, radarr, etc)
        - instance_name: str - Name of the instance
        - item_id: str - ID of the history entry to update
        - new_status: str - New status value
        - additional_fields: dict - Additional fields to update in the entry
        
        Returns:
            True if the update was successful, False otherwise
        """
        if not self.ensure_history_dir():
            logger.error("Could not ensure history directory exists")
            return False
            
        history_file = self.get_history_file_path(app_type, instance_name)
        
        if not history_file.exists():
            logger.error(f"History file does not exist: {history_file}")
            return False
        
        # Use a lock to prevent race conditions
        with history_locks[app_type]:
            try:
                # Read existing entries
                with open(history_file, 'r') as f:
                    entries = json.load(f)
                
                # Find the entry to update
                updated = False
                for entry in entries:
                    if str(entry.get("id")) == str(item_id):
                        # Update the status
                        entry["hunt_status"] = new_status
                        
                        # Update additional fields if provided
                        if additional_fields:
                            entry.update(additional_fields)
                            
                        updated = True
                        break
                
                if updated:
                    # Write back to file
                    with open(history_file, 'w') as f:
                        json.dump(entries, f, indent=2)
                    logger.info(f"Updated hunt status for {app_type}-{instance_name} ID {item_id} to '{new_status}'")
                    return True
                else:
                    logger.warning(f"Could not find history entry for {app_type}-{instance_name} ID {item_id}")
                    return False
            except Exception as e:
                independent_logger.error(f"Error updating history entry: {str(e)}")
                return False
                
    def track_item(self, app_type: str, instance_name: str, item_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Track an item and create a history entry for it
        
        This is a convenience method that maps to add_history_entry
        
        Args:
            app_type: Type of app (radarr, sonarr, etc.)
            instance_name: Name of the app instance
            item_data: Dictionary of item information
            
        Returns:
            The created entry or None if there was an error
        """
        # Structure the data for add_history_entry
        entry_data = {
            "name": item_data.get("title", item_data.get("name", "Unknown")),
            "instance_name": instance_name,
            "id": item_data.get("id"),
            # Include other fields from item_data
            **item_data
        }
        
        return self.add_history_entry(app_type, entry_data)
        
    def update_item_status(self, app_type: str, instance_name: str, item_id: str, 
                           new_status: str, additional_fields: Optional[Dict[str, Any]] = None):
        """Update the status of a tracked item
        
        This now maps directly to update_history_entry_status
        
        Args:
            app_type: Type of app
            instance_name: Name of the app instance
            item_id: ID of the item
            new_status: New status value
            additional_fields: Optional additional fields to update
            
        Returns:
            True if successful, False otherwise
        """
        return self.update_history_entry_status(app_type, instance_name, item_id, new_status, additional_fields)
    
    def get_history(self, app_type: str, instance_name: Optional[str] = None, 
                   page: int = 1, page_size: int = 50) -> Dict[str, Any]:
        """Get history entries with pagination."""
        # Validate app type
        if app_type not in history_locks and app_type != "all":
            independent_logger.error(f"Invalid app type: {app_type}")
            return {"error": "Invalid app type"}
            
        # Calculate pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        all_entries = []
        
        try:
            # List all history files for the app type
            app_dir = HISTORY_BASE_PATH / app_type
            if not app_dir.exists():
                return {"total": 0, "page": page, "page_size": page_size, "total_pages": 0, "items": []}
                
            if instance_name is not None:
                # Only look at specified instance
                history_file = self.get_history_file_path(app_type, instance_name)
                if history_file.exists():
                    with open(history_file, 'r') as f:
                        entries = json.load(f)
                        all_entries.extend(entries)
            else:
                # Look at all instances
                for file in app_dir.glob("*.json"):
                    if file.is_file():
                        try:
                            with open(file, 'r') as f:
                                entries = json.load(f)
                                all_entries.extend(entries)
                        except Exception as e:
                            logger.error(f"Error reading history file {file}: {str(e)}")
            
            # Sort by timestamp (most recent first)
            all_entries.sort(key=lambda x: x.get("date_time", 0), reverse=True)
            
            # Calculate total number of entries and pages
            total = len(all_entries)
            total_pages = (total + page_size - 1) // page_size
            
            # Get the entries for the current page
            page_entries = all_entries[start_idx:end_idx]
            
            # Calculate how_long_ago for each entry
            current_time = int(time.time())
            for entry in page_entries:
                entry_time = entry.get("date_time", 0)
                seconds_elapsed = current_time - entry_time
                
                if seconds_elapsed < 1:
                    entry["how_long_ago"] = "Just now"
                elif seconds_elapsed < 60:
                    entry["how_long_ago"] = f"{seconds_elapsed} {'second' if seconds_elapsed == 1 else 'seconds'} ago"
                elif seconds_elapsed < 3600:  # Less than an hour
                    minutes = int(seconds_elapsed / 60)
                    entry["how_long_ago"] = f"{minutes} {'minute' if minutes == 1 else 'minutes'} ago"
                elif seconds_elapsed < 86400:  # Less than a day
                    hours = int(seconds_elapsed / 3600)
                    entry["how_long_ago"] = f"{hours} {'hour' if hours == 1 else 'hours'} ago"
                elif seconds_elapsed < 604800:  # Less than a week
                    days = int(seconds_elapsed / 86400)
                    entry["how_long_ago"] = f"{days} {'day' if days == 1 else 'days'} ago"
                else:
                    # More than a week, show the actual date
                    entry["how_long_ago"] = datetime.fromtimestamp(entry_time).strftime('%Y-%m-%d')
            
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "items": page_entries
            }
        except Exception as e:
            independent_logger.error(f"Error getting history: {str(e)}")
            return {"total": 0, "page": page, "page_size": page_size, "total_pages": 0, "items": []}
            
    def clear_history(self, app_type: Optional[str] = None, instance_name: Optional[str] = None) -> bool:
        """
        Clear history entries
        
        Parameters:
        - app_type: str - Optional app type to clear history for, if None will clear all app types
        - instance_name: str - Optional instance name to clear history for, if None will clear all instances
        
        Returns:
            True if successful, False otherwise
        """
        if not self.ensure_history_dir():
            logger.error("Could not ensure history directory exists")
            return False
            
        try:
            if app_type is not None:
                # Clear history for specific app type
                if app_type not in history_locks:
                    independent_logger.error("Invalid app type: {}".format(app_type))
                    return False
                    
                app_dir = HISTORY_BASE_PATH / app_type
                if not app_dir.exists():
                    return True  # Nothing to clear
                    
                with history_locks[app_type]:
                    if instance_name is not None:
                        # Clear history for specific instance
                        history_file = self.get_history_file_path(app_type, instance_name)
                        if history_file.exists():
                            # Write empty array to file
                            with open(history_file, 'w') as f:
                                json.dump([], f)
                            logger.info(f"Cleared history for {app_type}-{instance_name}")
                    else:
                        # Clear history for all instances of this app type
                        for file in app_dir.glob("*.json"):
                            if file.is_file():
                                # Write empty array to file
                                with open(file, 'w') as f:
                                    json.dump([], f)
                        logger.info(f"Cleared history for all instances of {app_type}")
            else:
                # Clear history for all app types
                for app_type in history_locks.keys():
                    app_dir = HISTORY_BASE_PATH / app_type
                    if app_dir.exists():
                        with history_locks[app_type]:
                            for file in app_dir.glob("*.json"):
                                if file.is_file():
                                    # Write empty array to file
                                    with open(file, 'w') as f:
                                        json.dump([], f)
                logger.info("Cleared all history")
                
            return True
        except Exception as e:
            independent_logger.error(f"Error clearing history: {str(e)}")
            return False
    
    def get_latest_statuses(self, limit: int = 5) -> List[Dict]:
        """Get the latest hunt statuses directly from history files.
        
        This now uses the get_history method of this class to get the latest statuses.
        
        Args:
            limit: Maximum number of items to return
            
        Returns:
            List of dictionaries with status information
        """
        # Get history entries for all app types
        app_types = ['radarr', 'sonarr', 'lidarr', 'readarr', 'whisparr', 'eros']
        all_history = []
        
        for app_type in app_types:
            try:
                # Get most recent entries for this app type
                history = self.get_history(app_type, page=1, page_size=limit)
                if history and 'items' in history:
                    all_history.extend(history['items'])
            except Exception as e:
                logger.error(f"Error getting history for {app_type}: {e}")
        
        # Sort by timestamp, most recent first
        all_history.sort(key=lambda x: x.get("date_time", 0), reverse=True)
        
        # Format for the expected output format
        result = []
        for entry in all_history[:limit]:
            result.append({
                "app_type": entry.get("app_type", "unknown"),
                "instance": entry.get("instance_name", "unknown"),
                "id": entry.get("id", "unknown"),
                "name": entry.get("processed_info", "Unknown"),
                "timestamp": entry.get("date_time", 0),
                "action": entry.get("operation_type", "unknown"),
                "status": entry.get("hunt_status", "Not Tracked")
            })
            
        return result
            
    def cleanup_old_records(self):
        """Cleanup is no longer needed as the history_manager handles record retention.
        
        This is maintained as a no-op method for compatibility.
        """
        # No longer needed - history retention is handled internally
        pass