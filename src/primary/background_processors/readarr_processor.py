"""
Readarr background processor for Huntarr.

This module handles background processing for Readarr instances, including
fetching data, updating history entries, and tracking downloads.
"""
import logging
from typing import Dict, List, Optional, Any

from src.primary.background_processors.base_processor import BaseProcessor

class ReadarrProcessor(BaseProcessor):
    """Handles Readarr background processing"""
    
    def __init__(self, hunting_manager):
        """
        Initialize the Readarr processor.
        
        Args:
            hunting_manager: The HuntingManager instance
        """
        super().__init__("readarr")
        self.hunting_manager = hunting_manager
    
    def _process_implementation(self, stop_event) -> None:
        """
        Process Readarr-specific hunting logic using the unified field handling approach.
        This completely eliminates any translation between API responses and history entries,
        with the field_mapper handling all the JSON structure creation consistently.
        
        Args:
            stop_event: Event to check if processing should stop
        """
        try:
            # Import necessary modules
            from src.primary.apps.readarr import get_configured_instances
            from src.primary.apps.readarr.api import get_author_details, get_books_by_author_id_api, get_queue_api
            from src.primary.history_manager import get_history, update_history_entry_status, add_history_entry
            from src.primary.stateful_manager import get_processed_ids
            from src.primary.utils.field_mapper import determine_hunt_status, get_nested_value, APP_CONFIG, create_history_entry, fetch_api_data_for_item
            from src.primary.settings_manager import get_advanced_setting
            
            # Check if Readarr is configured
            readarr_config = APP_CONFIG.get("readarr")
            if not readarr_config:
                self.log_error("No configuration found for Readarr, cannot process hunting")
                return
            
            # Get all configured Readarr instances
            readarr_instances = get_configured_instances()
            
            for instance in readarr_instances:
                # Skip processing if stop event is set
                if stop_event.is_set():
                    return
                    
                instance_name = instance.get("instance_name", "Default")
                api_url = instance.get("api_url")
                api_key = instance.get("api_key")
                api_timeout = get_advanced_setting("api_timeout", 120)
                
                if not api_url or not api_key:
                    self.log_warning(f"Missing API URL or key for instance: {instance_name}, skipping")
                    continue
                    
                self.log_info(f"Checking processed IDs for instance: {instance_name}")
                
                # Load processed IDs from stateful_manager
                processed_ids = get_processed_ids("readarr", instance_name)
                self.log_info(f"Found {len(processed_ids)} processed IDs for instance {instance_name}")
                
                # Load history entries to check for existing entries
                history_data = get_history("readarr", instance_name)
                
                # Create a dictionary of API handlers for easier access
                api_handlers = {
                    "get_author_by_id": lambda id: get_author_details(api_url, api_key, id, api_timeout),
                    "get_books_by_author_id": lambda id: get_books_by_author_id_api(api_url, api_key, id, api_timeout),
                    "get_queue": lambda: get_queue_api(api_url, api_key, api_timeout)
                }
                
                # Get queue data once for all books to avoid multiple API calls
                queue_data = None
                try:
                    queue_data = api_handlers["get_queue"]()
                    self.log_info(f"Current download queue has {len(queue_data)} items for instance {instance_name}")
                except Exception as e:
                    self.log_error(f"Error fetching download queue for {instance_name}: {e}")
                    queue_data = []
                
                # Process each author ID
                processed_count = 0
                for author_id_str in processed_ids:
                    # Skip processing if stop event is set
                    if stop_event.is_set():
                        return
                        
                    author_id = int(author_id_str)
                    processed_count += 1
                    self.log_info(f"Processing author ID: {author_id} ({processed_count}/{len(processed_ids)}) for instance {instance_name}")
                    
                    try:
                        # Use the unified field handler to fetch all needed data
                        primary_data, book_list_data, _ = fetch_api_data_for_item("readarr", author_id, api_handlers)
                        
                        if not primary_data:
                            self.log_warning(f"No primary data (author details) returned from API for author ID {author_id}, skipping")
                            continue
                        
                        # Log basic details for the author
                        author_name = primary_data.get('authorName', 'Unknown Author')
                        monitored = primary_data.get('monitored', False)
                        
                        self.log_info(f"Author details - ID: {author_id}, Name: {author_name}, Monitored: {monitored}")

                        # Determine hunt status
                        hunt_status = determine_hunt_status("readarr", primary_data, queue_data)
                        
                        # Check if this author is already in history
                        existing_entry = None
                        if history_data.get("entries"):
                            existing_entry = next((entry for entry in history_data["entries"] 
                                                if str(entry.get("id", "")) == str(author_id)), None)
                        
                        # Update or create history entry for the AUTHOR
                        if existing_entry:
                            update_history_entry_status("readarr", instance_name, author_id, hunt_status)
                            previous_status = existing_entry.get("hunt_status", "Not Tracked")
                            if previous_status != hunt_status:
                                self.log_info(f"Updating status for author ID {author_id} from '{previous_status}' to '{hunt_status}'")
                            else:
                                self.log_info(f"Status unchanged for author ID {author_id}: '{hunt_status}'")
                        else:
                            entry_data = create_history_entry("readarr", instance_name, str(author_id), 
                                                           primary_data, file_data=book_list_data, queue_data=queue_data)
                            
                            entry_data["name"] = primary_data.get('authorName', 'Unknown Author')
                            
                            add_history_entry("readarr", entry_data)
                            self.log_info(f"Created new history entry for author ID {author_id}: {hunt_status}")
                        
                        # Track author in memory
                        author_info = {
                            "id": author_id,
                            "authorName": author_name,
                            "status": hunt_status,
                            "instance_name": instance_name
                        }
                        
                        self.hunting_manager.track_item("readarr", author_id, instance_name, author_info)
                        self.log_info(f"Author ID {author_id} is now tracked for instance {instance_name}, status: {hunt_status}")
                        
                    except Exception as e:
                        self.log_error(f"Error processing author ID {author_id}: {e}")
                        continue
                
                self.log_info(f"Processed {processed_count} items for {instance_name}")
            
        except Exception as e:
            self.log_error(f"Error in Readarr hunting process: {str(e)}")
