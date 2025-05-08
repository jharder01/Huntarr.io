"""
Queue tracker for monitoring download progress in different applications.

This module provides functionality to track download queue status and update
history entries with progress information.
"""
import logging
import time
import traceback
import os
from typing import Dict, List, Optional, Any
from src.primary.utils.logger import get_logger
import json

class QueueTracker:
    """Handles queue tracking across different applications"""
    
    def __init__(self):
        """Initialize the queue tracker"""
        self.logger = get_logger("queue_tracker")
        self.logger.setLevel(logging.DEBUG)
        self.logger.info("[QueueTracker __init__] Initializing QueueTracker with get_logger.")

        # Dedicated debug logger for queue_tracker_debug.log
        try:
            self.logger.info("[QueueTracker __init__] Setting up debug_logger.")
            self.debug_logger = logging.getLogger("queue_tracker_debug")
            self.debug_logger.setLevel(logging.DEBUG)
            debug_log_file_path = "/config/logs/queue_tracker_debug.log"
            self.logger.info(f"[QueueTracker __init__] Attempting to create FileHandler for: {debug_log_file_path}")
            
            debug_file_handler = logging.FileHandler(debug_log_file_path)
            self.logger.info(f"[QueueTracker __init__] FileHandler created for: {debug_log_file_path}")
            
            debug_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            debug_file_handler.setFormatter(debug_formatter)
            self.debug_logger.addHandler(debug_file_handler)
            self.debug_logger.propagate = False
            self.logger.info("[QueueTracker __init__] debug_logger setup complete.")
            self.debug_logger.info("This is a test message from debug_logger after setup.") # Test message
        except Exception as e:
            self.logger.error(f"[QueueTracker __init__] FAILED to set up debug_logger: {str(e)}", exc_info=True)
    
    def process(self, stop_event) -> None:
        """
        Process queue tracking for all applications.
        
        Args:
            stop_event: Event to check if processing should stop
        """
        self.logger.info("=== QUEUE TRACKING CYCLE STARTED ===")
        
        try:
            # Track queues for different applications
            self.logger.info("Starting Radarr queue tracking process")
            
            try:
                self.track_radarr_queue(stop_event)
                self.logger.info("Radarr queue tracking completed successfully")
            except Exception as e:
                self.logger.error(f"Error during Radarr queue tracking: {str(e)}")
                self.debug_logger.error(f"Error during Radarr queue tracking: {str(e)}", exc_info=True) # Also log to debug with traceback
                self.logger.debug(traceback.format_exc())
            
            self.logger.debug("Starting Sonarr queue tracking")
            self.track_sonarr_queue(stop_event)
            
            self.logger.debug("Starting Lidarr queue tracking")
            self.track_lidarr_queue(stop_event)
            
            self.logger.debug("Starting Readarr queue tracking")
            self.track_readarr_queue(stop_event)
            
            self.logger.debug("Starting Whisparr queue tracking")
            self.track_whisparr_queue(stop_event)
            
            self.logger.debug("Starting Eros queue tracking")
            self.track_eros_queue(stop_event)
            
        except Exception as e:
            self.logger.error(f"Error during queue tracking cycle: {e}", exc_info=True)
    
    def track_radarr_queue(self, stop_event) -> None:
        """
        Track Radarr download queue and update history entries.
        
        Args:
            stop_event: Event to check if processing should stop
        """
        if stop_event.is_set():
            return

        self.debug_logger.info("=== RADARR QUEUE TRACKING STARTED IN DEBUG LOGGER ===")
            
        try:
            # Import necessary modules
            from src.primary.apps.radarr import get_configured_instances
            from src.primary.apps.radarr.api import get_download_queue
            from src.primary.history_manager import get_history, update_history_entry_status
            from src.primary.utils.field_mapper import APP_CONFIG
            
            self.debug_logger.debug("Successfully imported Radarr modules")
            
            # Check if Radarr is configured
            radarr_config = APP_CONFIG.get("radarr")
            if radarr_config:
                self.debug_logger.debug("Radarr configuration found")
            else:
                self.debug_logger.warning("No Radarr configuration found, skipping queue tracking")
                return
            
            # Get all configured Radarr instances
            self.debug_logger.debug("Fetching configured Radarr instances")
            radarr_instances = get_configured_instances()
            
            self.debug_logger.info(f"Found {len(radarr_instances)} Radarr instance(s) for queue tracking")
            for instance in radarr_instances:
                self.debug_logger.debug(f"Instance: {instance.get('instance_name', 'Default')}")
            
            for instance in radarr_instances:
                if stop_event.is_set():
                    return
                    
                instance_name = instance.get("instance_name", "Default")
                self.debug_logger.info(f"Processing queue tracking for Radarr instance: {instance_name}")
                
                api_url = instance.get("api_url")
                api_key = instance.get("api_key")
                api_timeout = instance.get("api_timeout", 120)
                
                if not api_url or not api_key:
                    self.debug_logger.warning(f"Missing API URL or key for Radarr instance: {instance_name}, skipping")
                    continue
                
                # Get history entries for this instance that are in "Searching" state
                self.debug_logger.debug(f"Fetching history entries for Radarr instance: {instance_name}")
                history_data = get_history("radarr", instance_name)
                if not history_data or not history_data.get("entries"):
                    self.debug_logger.debug(f"No history entries found for Radarr instance: {instance_name}, skipping")
                    continue
                
                # Filter for entries in "Searching" state for this instance
                searching_entries = [
                    entry for entry in history_data.get("entries", [])
                    if entry.get("hunt_status") == "Searching" and 
                    entry.get("instance_name") == instance_name
                ]
                
                self.debug_logger.debug(f"Found {len(searching_entries)} entries in 'Searching' state for Radarr instance: {instance_name}")

                if not searching_entries:
                    self.debug_logger.info(f"No 'Searching' Radarr entries to process for {instance_name}.")
                    continue

                # Get queue data once for all movies to avoid multiple API calls
                self.debug_logger.info(f"Fetching Radarr queue from {api_url} for instance {instance_name}")
                
                queue_data = None # Initialize queue_data
                try:
                    queue_data = get_download_queue(api_url, api_key, api_timeout)
                    if isinstance(queue_data, dict) and 'records' in queue_data: # Radarr v3+ returns an object with a 'records' list
                        queue_data = queue_data.get('records', [])
                    elif queue_data is None: # Handle case where API returns None
                        queue_data = []
                    # If it's already a list (older Radarr or other issue), or became an empty list, leave as is.
                except Exception as e:
                    self.debug_logger.error(f"Error fetching Radarr queue for instance {instance_name}: {str(e)}")
                    # Decide if we should continue with an empty queue or skip this instance for the cycle
                    self.debug_logger.warning(f"Skipping queue tracking for Radarr instance {instance_name} for this cycle due to API error.")
                    continue # Skip to the next instance

                if not queue_data: # If queue_data is None or empty after try-except
                    self.debug_logger.info(f"No queue data returned or Radarr queue is empty for instance: {instance_name}")
                    # No need to continue if there's no queue to match against, but still process entries to ensure they are handled (e.g. if they were stuck)
                    # However, if the goal is only to match against an *active* queue, we could 'continue' here.
                    # For now, let's assume we want to iterate entries even with an empty queue, 
                    # as 'Searching' entries might need other updates or checks not tied to queue items.
                    # Update: If queue is empty, no matches will be found, so it's safe to log and proceed.

                self.debug_logger.info(f"Successfully fetched Radarr queue: {len(queue_data) if queue_data else 0} items for instance {instance_name}")

                self.debug_logger.info(f"Checking {len(searching_entries)} history entries against {len(queue_data) if queue_data else 0} queue items for Radarr instance {instance_name}")

                matches_found = 0 # Initialize here, before the loop
                for i, entry in enumerate(searching_entries):
                    self.debug_logger.debug(f"--- Full history entry {i+1} being processed for instance {instance_name} ---")
                    try:
                        self.debug_logger.debug(json.dumps(entry, indent=2))
                    except TypeError as e:
                        self.debug_logger.error(f"Could not serialize history entry to JSON: {e} - Entry: {entry}")
                    self.debug_logger.debug(f"--- End of full history entry {i+1} ---")

                    history_movie_id = entry.get("id")
                    title = entry.get("processed_info", "")

                    self.debug_logger.debug(f"Extracted for matching: HistoryEntryID='{history_movie_id}', Title='{title}'")

                    match_found = False
                    if not queue_data: # Ensure queue_data is not None before iterating
                        self.debug_logger.debug(f"Radarr queue data is empty or None. Cannot find match for '{title}'.")
                    else:
                        for queue_item_idx, queue_item in enumerate(queue_data):
                            queue_title = queue_item.get("title", "")
                            movie_id_from_queue = queue_item.get("movieId") # This is Radarr's ID for the movie in queue
                            
                            self.debug_logger.debug(f"  Comparing with Queue Item {queue_item_idx + 1}: QueueMovieID='{movie_id_from_queue}', QueueTitle='{queue_title}'")

                            # Match either by ID or by title matching
                            id_match = movie_id_from_queue and str(movie_id_from_queue) == str(history_movie_id)
                            title_match = self._title_match(title, queue_title)
                            
                            if id_match or title_match:
                                match_type = "ID" if id_match else "title"
                                self.debug_logger.info(f"Match found by {match_type} for movie '{title}'")
                                
                                # Calculate progress
                                progress = 0
                                if "size" in queue_item and "sizeleft" in queue_item and queue_item["size"] > 0:
                                    downloaded = queue_item["size"] - queue_item["sizeleft"]
                                    progress = round((downloaded / queue_item["size"]) * 100, 2)
                                
                                # Get status
                                status = queue_item.get("status", "unknown")
                                
                                # Update entry with queue information
                                new_status = f"Downloading ({progress}%)"
                                
                                # Create queue_info dictionary
                                queue_info = {
                                    "status": status,
                                    "progress": progress,
                                    "download_client": queue_item.get("downloadClient"),
                                    "title": queue_title,
                                    "time_left": queue_item.get("timeleft"),
                                    "size": queue_item.get("size"),
                                    "protocol": queue_item.get("protocol")
                                }
                                
                                # Update the history entry
                                self.debug_logger.info(f"Updating entry {history_movie_id} with queue status: {new_status}")
                                self.debug_logger.debug(f"Queue info: {queue_info}")
                                
                                try:
                                    update_history_entry_status("radarr", instance_name, history_movie_id, new_status, queue_info)
                                    self.debug_logger.debug(f"History entry {history_movie_id} updated successfully")
                                    matches_found += 1
                                except Exception as e:
                                    self.debug_logger.error(f"Error updating history entry {history_movie_id}: {str(e)}")
                                
                                match_found = True
                                break
                        
                    if not match_found:
                        self.debug_logger.debug(f"No matching queue item found for entry '{title}'")
                
                self.debug_logger.info(f"Queue matching complete: {matches_found} matches found out of {len(searching_entries)} entries")
                
        except Exception as e:
            self.debug_logger.error(f"Error tracking Radarr queue: {e}")
    
    def track_sonarr_queue(self, stop_event) -> None:
        """
        Track Sonarr download queue and update history entries.
        
        Args:
            stop_event: Event to check if processing should stop
        """
        if stop_event.is_set():
            return
            
        try:
            # Import necessary modules
            from src.primary.apps.sonarr import get_configured_instances
            from src.primary.apps.sonarr.api import get_queue
            from src.primary.history_manager import get_history, update_history_entry_status
            from src.primary.utils.field_mapper import APP_CONFIG
            
            # Check if Sonarr is configured
            sonarr_config = APP_CONFIG.get("sonarr")
            if not sonarr_config:
                self.logger.debug("No configuration found for Sonarr, skipping queue tracking")
                return
            
            # Get all configured Sonarr instances
            sonarr_instances = get_configured_instances()
            
            for instance in sonarr_instances:
                if stop_event.is_set():
                    return
                    
                instance_name = instance.get("instance_name", "Default")
                api_url = instance.get("api_url")
                api_key = instance.get("api_key")
                api_timeout = 120  # Default timeout
                
                if not api_url or not api_key:
                    self.logger.debug(f"Missing API URL or key for Sonarr instance: {instance_name}, skipping")
                    continue
                
                # Get history entries for this instance that are in "Searching" state
                history_data = get_history("sonarr")
                if not history_data or not history_data.get("entries"):
                    self.logger.debug(f"No history entries found for Sonarr, skipping")
                    continue
                
                searching_entries = [
                    entry for entry in history_data.get("entries", [])
                    if entry.get("hunt_status") == "Searching" and 
                    entry.get("instance_name") == instance_name
                ]
                
                if not searching_entries:
                    self.logger.debug(f"No searching entries for Sonarr instance: {instance_name}, skipping")
                    continue
                
                # Get queue data
                queue_data = get_queue(api_url, api_key, api_timeout)
                if not queue_data:
                    self.logger.debug(f"No queue data for Sonarr instance: {instance_name}, skipping")
                    continue
                
                self.logger.info(f"Checking {len(searching_entries)} entries against {len(queue_data)} queue items for Sonarr")
                
                # Update entries with queue information
                for entry in searching_entries:
                    entry_id = entry.get("id")
                    title = entry.get("processed_info", "")
                    
                    # Find matching queue item by title (approximate match)
                    for queue_item in queue_data:
                        series_id = queue_item.get("seriesId")
                        if series_id and str(series_id) == str(entry_id):
                            # Calculate progress
                            progress = 0
                            if "size" in queue_item and "sizeleft" in queue_item and queue_item["size"] > 0:
                                downloaded = queue_item["size"] - queue_item["sizeleft"]
                                progress = round((downloaded / queue_item["size"]) * 100, 2)
                            
                            # Get status
                            status = queue_item.get("status", "unknown")
                            episode_info = queue_item.get("episode", {})
                            episode_title = episode_info.get("title", "Unknown episode")
                            
                            # Update entry with queue information
                            new_status = f"Downloading ({progress}%) - {episode_title}"
                            
                            queue_info = {
                                "status": status,
                                "progress": progress,
                                "download_client": queue_item.get("downloadClient"),
                                "title": episode_title,
                                "time_left": queue_item.get("timeleft"),
                                "size": queue_item.get("size"),
                                "protocol": queue_item.get("protocol")
                            }
                            
                            # Update the history entry
                            self.logger.info(f"Updating entry {entry_id} with queue status: {new_status}")
                            update_history_entry_status("sonarr", instance_name, entry_id, new_status, queue_info)
                            break
                
        except Exception as e:
            self.logger.error(f"Error tracking Sonarr queue: {e}")

    
    def track_lidarr_queue(self, stop_event) -> None:
        """
        Track Lidarr download queue and update history entries.
        
        Args:
            stop_event: Event to check if processing should stop
        """
        if stop_event.is_set():
            return
            
        try:
            # Import necessary modules
            from src.primary.apps.lidarr import get_configured_instances
            from src.primary.apps.lidarr.api import get_queue
            from src.primary.history_manager import get_history, update_history_entry_status
            from src.primary.utils.field_mapper import APP_CONFIG
            
            # Check if Lidarr is configured
            lidarr_config = APP_CONFIG.get("lidarr")
            if not lidarr_config:
                self.logger.debug("No configuration found for Lidarr, skipping queue tracking")
                return
            
            # Get all configured Lidarr instances
            lidarr_instances = get_configured_instances()
            
            for instance in lidarr_instances:
                if stop_event.is_set():
                    return
                    
                instance_name = instance.get("instance_name", "Default")
                api_url = instance.get("api_url")
                api_key = instance.get("api_key")
                api_timeout = 120  # Default timeout
                
                if not api_url or not api_key:
                    self.logger.debug(f"Missing API URL or key for Lidarr instance: {instance_name}, skipping")
                    continue
                
                # Get history entries for this instance that are in "Searching" state
                history_data = get_history("lidarr")
                if not history_data or not history_data.get("entries"):
                    self.logger.debug(f"No history entries found for Lidarr, skipping")
                    continue
                
                searching_entries = [
                    entry for entry in history_data.get("entries", [])
                    if entry.get("hunt_status") == "Searching" and 
                    entry.get("instance_name") == instance_name
                ]
                
                if not searching_entries:
                    self.logger.debug(f"No searching entries for Lidarr instance: {instance_name}, skipping")
                    continue
                
                # Get queue data
                queue_data = get_queue(api_url, api_key, api_timeout)
                if not queue_data:
                    self.logger.debug(f"No queue data for Lidarr instance: {instance_name}, skipping")
                    continue
                
                self.logger.info(f"Checking {len(searching_entries)} entries against {len(queue_data)} queue items for Lidarr")
                
                # Update entries with queue information
                for entry in searching_entries:
                    entry_id = entry.get("id")
                    title = entry.get("processed_info", "")
                    
                    # Find matching queue item by artist ID
                    for queue_item in queue_data:
                        artist_id = queue_item.get("artistId")
                        queue_title = queue_item.get("title", "")
                        if (artist_id and str(artist_id) == str(entry_id)) or self._title_match(title, queue_title):
                            # Calculate progress
                            progress = 0
                            if "size" in queue_item and "sizeleft" in queue_item and queue_item["size"] > 0:
                                downloaded = queue_item["size"] - queue_item["sizeleft"]
                                progress = round((downloaded / queue_item["size"]) * 100, 2)
                            
                            # Get status
                            status = queue_item.get("status", "unknown")
                            album_info = queue_item.get("album", {})
                            album_title = album_info.get("title", "Unknown album")
                            
                            # Update entry with queue information
                            new_status = f"Downloading ({progress}%) - {album_title}"
                            
                            queue_info = {
                                "status": status,
                                "progress": progress,
                                "download_client": queue_item.get("downloadClient"),
                                "title": album_title,
                                "time_left": queue_item.get("timeleft"),
                                "size": queue_item.get("size"),
                                "protocol": queue_item.get("protocol")
                            }
                            
                            # Update the history entry
                            self.logger.info(f"Updating entry {entry_id} with queue status: {new_status}")
                            update_history_entry_status("lidarr", instance_name, entry_id, new_status, queue_info)
                            break
                
        except Exception as e:
            self.logger.error(f"Error tracking Lidarr queue: {e}")

    
    def track_readarr_queue(self, stop_event) -> None:
        """
        Track Readarr download queue and update history entries.
        
        Args:
            stop_event: Event to check if processing should stop
        """
        if stop_event.is_set():
            return
            
        try:
            # Import necessary modules
            from src.primary.apps.readarr import get_configured_instances
            from src.primary.apps.readarr.api import get_queue
            from src.primary.history_manager import get_history, update_history_entry_status
            from src.primary.utils.field_mapper import APP_CONFIG
            
            # Check if Readarr is configured
            readarr_config = APP_CONFIG.get("readarr")
            if not readarr_config:
                self.logger.debug("No configuration found for Readarr, skipping queue tracking")
                return
            
            # Get all configured Readarr instances
            readarr_instances = get_configured_instances()
            
            for instance in readarr_instances:
                if stop_event.is_set():
                    return
                    
                instance_name = instance.get("instance_name", "Default")
                api_url = instance.get("api_url")
                api_key = instance.get("api_key")
                api_timeout = 120  # Default timeout
                
                if not api_url or not api_key:
                    self.logger.debug(f"Missing API URL or key for Readarr instance: {instance_name}, skipping")
                    continue
                
                # Get history entries for this instance that are in "Searching" state
                history_data = get_history("readarr")
                if not history_data or not history_data.get("entries"):
                    self.logger.debug(f"No history entries found for Readarr, skipping")
                    continue
                
                searching_entries = [
                    entry for entry in history_data.get("entries", [])
                    if entry.get("hunt_status") == "Searching" and 
                    entry.get("instance_name") == instance_name
                ]
                
                if not searching_entries:
                    self.logger.debug(f"No searching entries for Readarr instance: {instance_name}, skipping")
                    continue
                
                # Get queue data
                queue_data = get_queue(api_url, api_key, api_timeout)
                if not queue_data:
                    self.logger.debug(f"No queue data for Readarr instance: {instance_name}, skipping")
                    continue
                
                self.logger.info(f"Checking {len(searching_entries)} entries against {len(queue_data)} queue items for Readarr")
                
                # Update entries with queue information
                for entry in searching_entries:
                    entry_id = entry.get("id")
                    title = entry.get("processed_info", "")
                    
                    # Find matching queue item by author ID
                    for queue_item in queue_data:
                        author_id = queue_item.get("authorId")
                        queue_title = queue_item.get("title", "")
                        if (author_id and str(author_id) == str(entry_id)) or self._title_match(title, queue_title):
                            # Calculate progress
                            progress = 0
                            if "size" in queue_item and "sizeleft" in queue_item and queue_item["size"] > 0:
                                downloaded = queue_item["size"] - queue_item["sizeleft"]
                                progress = round((downloaded / queue_item["size"]) * 100, 2)
                            
                            # Get status
                            status = queue_item.get("status", "unknown")
                            book_info = queue_item.get("book", {})
                            book_title = book_info.get("title", "Unknown book")
                            
                            # Update entry with queue information
                            new_status = f"Downloading ({progress}%) - {book_title}"
                            
                            queue_info = {
                                "status": status,
                                "progress": progress,
                                "download_client": queue_item.get("downloadClient"),
                                "title": book_title,
                                "time_left": queue_item.get("timeleft"),
                                "size": queue_item.get("size"),
                                "protocol": queue_item.get("protocol")
                            }
                            
                            # Update the history entry
                            self.logger.info(f"Updating entry {entry_id} with queue status: {new_status}")
                            update_history_entry_status("readarr", instance_name, entry_id, new_status, queue_info)
                            break
                
        except Exception as e:
            self.logger.error(f"Error tracking Readarr queue: {e}")

    
    def track_whisparr_queue(self, stop_event) -> None:
        """
        Track Whisparr download queue and update history entries.
        
        Args:
            stop_event: Event to check if processing should stop
        """
        if stop_event.is_set():
            return
            
        try:
            # Import necessary modules
            from src.primary.apps.whisparr import get_configured_instances
            from src.primary.apps.whisparr.api import get_download_queue
            from src.primary.history_manager import get_history, update_history_entry_status
            from src.primary.utils.field_mapper import APP_CONFIG
            
            # Check if Whisparr is configured
            whisparr_config = APP_CONFIG.get("whisparr")
            if not whisparr_config:
                self.logger.debug("No configuration found for Whisparr, skipping queue tracking")
                return
            
            # Get all configured Whisparr instances
            whisparr_instances = get_configured_instances()
            
            for instance in whisparr_instances:
                if stop_event.is_set():
                    return
                    
                instance_name = instance.get("instance_name", "Default")
                api_url = instance.get("api_url")
                api_key = instance.get("api_key")
                api_timeout = 120  # Default timeout
                
                if not api_url or not api_key:
                    self.logger.debug(f"Missing API URL or key for Whisparr instance: {instance_name}, skipping")
                    continue
                
                # Get history entries for this instance that are in "Searching" state
                history_data = get_history("whisparr")
                if not history_data or not history_data.get("entries"):
                    self.logger.debug(f"No history entries found for Whisparr, skipping")
                    continue
                
                searching_entries = [
                    entry for entry in history_data.get("entries", [])
                    if entry.get("hunt_status") == "Searching" and 
                    entry.get("instance_name") == instance_name
                ]
                
                if not searching_entries:
                    self.logger.debug(f"No searching entries for Whisparr instance: {instance_name}, skipping")
                    continue
                
                # Get queue data
                queue_data = get_download_queue(api_url, api_key, api_timeout)
                if not queue_data:
                    self.logger.debug(f"No queue data for Whisparr instance: {instance_name}, skipping")
                    continue
                
                self.logger.info(f"Checking {len(searching_entries)} entries against {len(queue_data)} queue items for Whisparr")
                
                # Update entries with queue information
                for entry in searching_entries:
                    entry_id = entry.get("id")
                    title = entry.get("processed_info", "")
                    
                    # Find matching queue item by movieId
                    for queue_item in queue_data:
                        movie_id = queue_item.get("movieId")
                        if movie_id and str(movie_id) == str(entry_id):
                            # Calculate progress
                            progress = 0
                            if "size" in queue_item and "sizeleft" in queue_item and queue_item["size"] > 0:
                                downloaded = queue_item["size"] - queue_item["sizeleft"]
                                progress = round((downloaded / queue_item["size"]) * 100, 2)
                            
                            # Get status
                            status = queue_item.get("status", "unknown")
                            queue_title = queue_item.get("title", "Unknown item")
                            
                            # Update entry with queue information
                            new_status = f"Downloading ({progress}%)"
                            
                            queue_info = {
                                "status": status,
                                "progress": progress,
                                "download_client": queue_item.get("downloadClient"),
                                "title": queue_title,
                                "time_left": queue_item.get("timeleft"),
                                "size": queue_item.get("size"),
                                "protocol": queue_item.get("protocol")
                            }
                            
                            # Update the history entry
                            self.logger.info(f"Updating entry {entry_id} with queue status: {new_status}")
                            update_history_entry_status("whisparr", instance_name, entry_id, new_status, queue_info)
                            break
                
        except Exception as e:
            self.logger.error(f"Error tracking Whisparr queue: {e}")
    
    def track_eros_queue(self, stop_event) -> None:
        """
        Track Eros download queue and update history entries.
        
        Args:
            stop_event: Event to check if processing should stop
        """
        if stop_event.is_set():
            return
            
        try:
            # Import necessary modules
            from src.primary.apps.eros import get_configured_instances
            from src.primary.apps.eros.api import get_download_queue
            from src.primary.history_manager import get_history, update_history_entry_status
            from src.primary.utils.field_mapper import APP_CONFIG
        except Exception as e:
            self.logger.error(f"Error importing modules for Eros queue tracking: {e}")
            return
            
        try:
            
            # Check if Eros is configured
            eros_config = APP_CONFIG.get("eros")
            if not eros_config:
                self.logger.debug("No configuration found for Eros, skipping queue tracking")
                return
            
            # Get all configured Eros instances
            eros_instances = get_configured_instances()
            
            for instance in eros_instances:
                if stop_event.is_set():
                    return
                    
                instance_name = instance.get("instance_name", "Default")
                api_url = instance.get("api_url")
                api_key = instance.get("api_key")
                api_timeout = 120  # Default timeout
                
                if not api_url or not api_key:
                    self.logger.debug(f"Missing API URL or key for Eros instance: {instance_name}, skipping")
                    continue
                
                # Get history entries for this instance that are in "Searching" state
                history_data = get_history("eros")
                if not history_data or not history_data.get("entries"):
                    self.logger.debug(f"No history entries found for Eros, skipping")
                    continue
                
                # Get entries in Searching state
                searching_entries = [
                    entry for entry in history_data.get("entries", [])
                    if entry.get("hunt_status") == "Searching" and 
                    entry.get("instance_name") == instance_name
                ]
                
                if not searching_entries:
                    self.logger.debug(f"No searching entries for Eros instance: {instance_name}, skipping")
                    continue
                    
                # Process each entry
                for entry in searching_entries:
                    entry_id = entry.get("id")
                    title = entry.get("processed_info", "")
                    
                    # Find matching queue item by movieId
                    for queue_item in queue_data:
                        movie_id = queue_item.get("movieId")
                        if movie_id and str(movie_id) == str(entry_id):
                            # Calculate progress
                            progress = 0
                            if "size" in queue_item and "sizeleft" in queue_item and queue_item["size"] > 0:
                                downloaded = queue_item["size"] - queue_item["sizeleft"]
                                progress = round((downloaded / queue_item["size"]) * 100, 2)
                            
                            # Get status and additional details
                            status = queue_item.get("status", "unknown")
                            queue_title = queue_item.get("title", "Unknown item")
                            quality = queue_item.get("quality", {}).get("quality", {}).get("name", "Unknown")
                            resolution = queue_item.get("resolution", "Unknown")
                            
                            # Update entry with queue information
                            new_status = f"Downloading ({progress}%) - {quality} {resolution}"
                            
                            queue_info = {
                                "status": status,
                                "progress": progress,
                                "download_client": queue_item.get("downloadClient"),
                                "title": queue_title,
                                "time_left": queue_item.get("timeleft"),
                                "size": queue_item.get("size"),
                                "protocol": queue_item.get("protocol"),
                                "quality": quality,
                                "resolution": resolution
                            }
                            
                            # Update the history entry
                            self.logger.info(f"Updating entry {entry_id} with queue status: {new_status}")
                            update_history_entry_status("eros", instance_name, entry_id, new_status, queue_info)
                            break
                
        except Exception as e:
            self.logger.error(f"Error tracking Eros queue: {e}")
    
    def _title_match(self, history_title: str, queue_title: str) -> bool:
        """
        Check if two titles match with enhanced matching logic.
        
        Args:
            history_title: Title from history entry
            queue_title: Title from queue item
            
        Returns:
            True if titles match, False otherwise
        """
        # Immediately return if either title is empty
        if not history_title or not queue_title:
            return False
            
        # Import here to avoid circular dependencies
        import re
        
        # Log the titles we're comparing for debugging
        self.logger.debug(f"Comparing titles: '{history_title}' <-> '{queue_title}'")
        
        # 1. Clean both titles
        # Remove year patterns like (2023) or [2023]
        history_title = re.sub(r'[\(\[\{]\d{4}[\)\]\}]', '', history_title)
        queue_title = re.sub(r'[\(\[\{]\d{4}[\)\]\}]', '', queue_title)
        
        # Remove season/episode patterns like S01E01 or s01e01
        history_title = re.sub(r'\b[Ss]\d{1,2}[Ee]\d{1,2}\b', '', history_title)
        queue_title = re.sub(r'\b[Ss]\d{1,2}[Ee]\d{1,2}\b', '', queue_title)
        
        # Remove special characters and convert to lowercase
        history_title_clean = re.sub(r'[^\w\s]', '', history_title).lower().strip()
        queue_title_clean = re.sub(r'[^\w\s]', '', queue_title).lower().strip()
        
        # Remove common words like "the", "a", etc. that might cause false negatives
        common_words = ['the', 'a', 'an', 'of', 'in', 'on', 'at', 'by', 'for', 'with']
        for word in common_words:
            history_title_clean = re.sub(r'\b' + word + r'\b', '', history_title_clean)
            queue_title_clean = re.sub(r'\b' + word + r'\b', '', queue_title_clean)
        
        # Remove multiple spaces
        history_title_clean = re.sub(r'\s+', ' ', history_title_clean).strip()
        queue_title_clean = re.sub(r'\s+', ' ', queue_title_clean).strip()
        
        self.logger.debug(f"Cleaned titles: '{history_title_clean}' <-> '{queue_title_clean}'")
        
        # 2. Check for exact match after cleaning
        if history_title_clean == queue_title_clean:
            self.logger.debug("Title match: exact match")
            return True
        
        # 3. Check if one is a substring of the other (handles partial titles)
        if history_title_clean in queue_title_clean or queue_title_clean in history_title_clean:
            self.logger.debug("Title match: substring match")
            return True
        
        # 4. Check for word-level similarity (>50% of words match)
        history_words = set(history_title_clean.split())
        queue_words = set(queue_title_clean.split())
        
        if not history_words or not queue_words:
            return False
            
        common_words = history_words.intersection(queue_words)
        similarity_ratio = len(common_words) / max(len(history_words), len(queue_words))
        
        if similarity_ratio > 0.5:  # If more than 50% of words match
            self.logger.debug(f"Title match: word similarity {similarity_ratio:.2f}")
            return True
            
        return False
