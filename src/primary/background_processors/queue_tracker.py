"""
Queue tracker for monitoring download progress in different applications.

This module provides functionality to track download queue status and update
history entries with progress information.
"""
import logging
import time
from typing import Dict, List, Optional, Any

# Create logger
logger = logging.getLogger("queue_tracker")

class QueueTracker:
    """Handles queue tracking across different applications"""
    
    def __init__(self):
        """Initialize the queue tracker"""
        self.logger = logger
    
    def process(self, stop_event) -> None:
        """
        Process queue tracking for all applications.
        
        Args:
            stop_event: Event to check if processing should stop
        """
        self.logger.info("=== Queue tracking cycle started ===")
        try:
            # Track queues for different applications
            self.track_radarr_queue(stop_event)
            self.track_sonarr_queue(stop_event)
            self.track_lidarr_queue(stop_event)
            self.track_readarr_queue(stop_event)
            self.track_whisparr_queue(stop_event)
            self.track_eros_queue(stop_event)
        except Exception as e:
            self.logger.error(f"Error in queue tracking: {e}")
        self.logger.info("=== Queue tracking cycle completed ===")
    
    def track_radarr_queue(self, stop_event) -> None:
        """
        Track Radarr download queue and update history entries.
        
        Args:
            stop_event: Event to check if processing should stop
        """
        if stop_event.is_set():
            return
            
        try:
            # Import necessary modules
            from src.primary.apps.radarr import get_configured_instances
            from src.primary.apps.radarr.api import get_download_queue
            from src.primary.history_manager import get_history, update_history_entry_status
            from src.primary.utils.field_mapper import APP_CONFIG
            
            # Check if Radarr is configured
            radarr_config = APP_CONFIG.get("radarr")
            if not radarr_config:
                self.logger.debug("No configuration found for Radarr, skipping queue tracking")
                return
            
            # Get all configured Radarr instances
            radarr_instances = get_configured_instances()
            
            for instance in radarr_instances:
                if stop_event.is_set():
                    return
                    
                instance_name = instance.get("instance_name", "Default")
                api_url = instance.get("api_url")
                api_key = instance.get("api_key")
                api_timeout = 120  # Default timeout
                
                if not api_url or not api_key:
                    self.logger.debug(f"Missing API URL or key for Radarr instance: {instance_name}, skipping")
                    continue
                
                # Get history entries for this instance that are in "Searching" state
                history_data = get_history("radarr")
                if not history_data or not history_data.get("entries"):
                    self.logger.debug(f"No history entries found for Radarr, skipping")
                    continue
                
                searching_entries = [
                    entry for entry in history_data.get("entries", [])
                    if entry.get("hunt_status") == "Searching" and 
                    entry.get("instance_name") == instance_name
                ]
                
                if not searching_entries:
                    self.logger.debug(f"No searching entries for Radarr instance: {instance_name}, skipping")
                    continue
                
                # Get queue data
                queue_data = get_download_queue(api_url, api_key, api_timeout)
                if not queue_data:
                    self.logger.debug(f"No queue data for Radarr instance: {instance_name}, skipping")
                    continue
                
                self.logger.info(f"Checking {len(searching_entries)} entries against {len(queue_data)} queue items for Radarr")
                
                # Update entries with queue information
                for entry in searching_entries:
                    entry_id = entry.get("id")
                    title = entry.get("processed_info", "")
                    
                    # Find matching queue item by title (approximate match)
                    for queue_item in queue_data:
                        queue_title = queue_item.get("title", "")
                        
                        # Check if the title matches (could be improved with fuzzy matching)
                        if self._title_match(title, queue_title):
                            # Calculate progress
                            progress = 0
                            if "size" in queue_item and "sizeleft" in queue_item and queue_item["size"] > 0:
                                downloaded = queue_item["size"] - queue_item["sizeleft"]
                                progress = round((downloaded / queue_item["size"]) * 100, 2)
                            
                            # Get status
                            status = queue_item.get("status", "unknown")
                            
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
                            update_history_entry_status("radarr", instance_name, entry_id, new_status, queue_info)
                            break
                
        except Exception as e:
            self.logger.error(f"Error tracking Radarr queue: {e}")
    
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
                        if artist_id and str(artist_id) == str(entry_id):
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
                        if author_id and str(author_id) == str(entry_id):
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
                
                searching_entries = [
                    entry for entry in history_data.get("entries", [])
                    if entry.get("hunt_status") == "Searching" and 
                    entry.get("instance_name") == instance_name
                ]
                
                if not searching_entries:
                    self.logger.debug(f"No searching entries for Eros instance: {instance_name}, skipping")
                    continue
                
                # Get queue data
                queue_data = get_download_queue(api_url, api_key, api_timeout)
                if not queue_data:
                    self.logger.debug(f"No queue data for Eros instance: {instance_name}, skipping")
                    continue
                
                self.logger.info(f"Checking {len(searching_entries)} entries against {len(queue_data)} queue items for Eros")
                
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
        Check if two titles match (simple version).
        
        Args:
            history_title: Title from history entry
            queue_title: Title from queue item
            
        Returns:
            True if titles match, False otherwise
        """
        # Remove year and clean up titles for comparison
        if not history_title or not queue_title:
            return False
            
        # Clean up by removing common patterns
        import re
        # Remove year patterns like (2023) or [2023]
        history_title = re.sub(r'[\(\[\{]\d{4}[\)\]\}]', '', history_title)
        queue_title = re.sub(r'[\(\[\{]\d{4}[\)\]\}]', '', queue_title)
        
        # Remove special characters and convert to lowercase
        history_title_clean = re.sub(r'[^\w\s]', '', history_title).lower().strip()
        queue_title_clean = re.sub(r'[^\w\s]', '', queue_title).lower().strip()
        
        # Check for exact match after cleaning
        if history_title_clean == queue_title_clean:
            return True
            
        # Check if one is a substring of the other
        return history_title_clean in queue_title_clean or queue_title_clean in history_title_clean
