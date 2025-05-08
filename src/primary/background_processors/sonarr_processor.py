"""
Sonarr background processor for Huntarr.

This module handles background processing for Sonarr instances, including
fetching data, updating history entries, and tracking downloads.
"""
import logging
from typing import Dict, List, Optional, Any

from src.primary.background_processors.base_processor import BaseProcessor

class SonarrProcessor(BaseProcessor):
    """Handles Sonarr background processing"""
    
    def __init__(self, hunting_manager):
        """
        Initialize the Sonarr processor.
        
        Args:
            hunting_manager: The HuntingManager instance
        """
        super().__init__("sonarr")
        self.hunting_manager = hunting_manager
    
    def _process_implementation(self, stop_event) -> None:
        """
        Process Sonarr-specific hunting logic using the unified field handling approach.
        This completely eliminates any translation between API responses and history entries,
        with the field_mapper handling all the JSON structure creation consistently.
        
        Args:
            stop_event: Event to check if processing should stop
        """
        try:
            # Import necessary modules
            from src.primary.apps.sonarr import get_configured_instances
            from src.primary.apps.sonarr.api import get_series_by_id, get_episode, get_queue
            from src.primary.history_manager import get_history, update_history_entry_status, add_history_entry
            from src.primary.stateful_manager import get_processed_ids
            from src.primary.utils.field_mapper import determine_hunt_status, get_nested_value, APP_CONFIG, create_history_entry, fetch_api_data_for_item
            from src.primary.settings_manager import settings_manager
            
            # Check if Sonarr is configured
            sonarr_config = APP_CONFIG.get("sonarr")
            if not sonarr_config:
                self.log_error("No configuration found for Sonarr, cannot process hunting")
                return
            
            # Get all configured Sonarr instances
            sonarr_instances = get_configured_instances()
            
            for instance in sonarr_instances:
                # Skip processing if stop event is set
                if stop_event.is_set():
                    return
                    
                instance_name = instance.get("instance_name", "Default")
                api_url = instance.get("api_url")
                api_key = instance.get("api_key")
                api_timeout = settings_manager.get_advanced_setting("api_timeout", 120)
                
                if not api_url or not api_key:
                    self.log_warning(f"Missing API URL or key for instance: {instance_name}, skipping")
                    continue
                    
                self.log_info(f"Checking processed IDs for instance: {instance_name}")
                
                # Load processed IDs from stateful_manager
                processed_ids = get_processed_ids("sonarr", instance_name)
                self.log_info(f"Found {len(processed_ids)} processed IDs for instance {instance_name}")
                
                # Load history entries to check for existing entries
                history_data = get_history("sonarr", instance_name)
                
                # Create a dictionary of API handlers for easier access
                api_handlers = {
                    "get_series_by_id": lambda id: get_series_by_id(api_url, api_key, id, api_timeout),
                    "get_episode": lambda id: get_episode(api_url, api_key, id, api_timeout),
                    "get_queue": lambda: get_queue(api_url, api_key, api_timeout)
                }
                
                # Get queue data once for all series to avoid multiple API calls
                queue_data = None
                try:
                    queue_data = api_handlers["get_queue"]()
                    self.log_info(f"Current download queue has {len(queue_data)} items for instance {instance_name}")
                except Exception as e:
                    self.log_error(f"Error fetching download queue for {instance_name}: {e}")
                    queue_data = []
                
                # Process each series ID
                processed_count = 0
                for series_id in processed_ids:
                    # Skip processing if stop event is set
                    if stop_event.is_set():
                        return
                        
                    processed_count += 1
                    self.log_info(f"Processing series ID: {series_id} ({processed_count}/{len(processed_ids)}) for instance {instance_name}")
                    
                    try:
                        # Use the unified field handler to fetch all needed data
                        primary_data, episode_data, _ = fetch_api_data_for_item("sonarr", series_id, api_handlers)
                        
                        if not primary_data:
                            self.log_warning(f"No data returned from API for series ID {series_id}, skipping")
                            continue
                        
                        # Log basic details
                        title = primary_data.get('title', 'Unknown')
                        year = primary_data.get('year', 'Unknown')
                        has_file = primary_data.get('hasFile', False)
                        monitored = primary_data.get('monitored', False)
                        
                        self.log_info(f"Series details - ID: {series_id}, Title: {title}, "
                                     f"Year: {year}, Status: {'Downloaded' if has_file else 'Missing'}, "
                                     f"Monitored: {monitored}")
                        
                        # Check if series is in queue
                        series_in_queue = False
                        queue_item_data = None
                        if queue_data:
                            for queue_item in queue_data:
                                if queue_item.get('seriesId') == int(series_id):
                                    series_in_queue = True
                                    queue_item_data = queue_item
                                    progress = queue_item.get('progress', 0)
                                    status = queue_item.get('status', 'Unknown')
                                    protocol = queue_item.get('protocol', 'Unknown')
                                    self.log_info(f"Series in download queue - ID: {series_id}, Title: {title}, "
                                                f"Progress: {progress}%, Status: {status}, Protocol: {protocol}")
                                    break
                        
                        if not series_in_queue and not has_file and monitored:
                            self.log_info(f"Series not in download queue and not downloaded - "
                                        f"ID: {series_id}, Title: {title}, Monitored: {monitored}")
                        
                        # Determine hunt status
                        hunt_status = determine_hunt_status("sonarr", primary_data, queue_data)
                        
                        # Check if this series is already in history
                        existing_entry = None
                        if history_data.get("entries"):
                            existing_entry = next((entry for entry in history_data["entries"] 
                                                if str(entry.get("id", "")) == str(series_id)), None)
                        
                        # Update or create history entry
                        if existing_entry:
                            # Just update the status if it exists
                            update_history_entry_status("sonarr", instance_name, series_id, hunt_status)
                            
                            # Log status changes
                            previous_status = existing_entry.get("hunt_status", "Not Tracked")
                            if previous_status != hunt_status:
                                self.log_info(f"Updating status for series ID {series_id} from '{previous_status}' to '{hunt_status}'")
                            else:
                                self.log_info(f"Status unchanged for series ID {series_id}: '{hunt_status}'")
                        else:
                            # Create a new history entry with the unified approach
                            entry_data = create_history_entry("sonarr", instance_name, series_id, 
                                                           primary_data, episode_data, queue_data)
                            
                            # Add required name field for history_manager
                            entry_data["name"] = f"{title} ({year})"
                            
                            # Add the entry to history
                            add_history_entry("sonarr", entry_data)
                            self.log_info(f"Created new history entry for series ID {series_id}: {hunt_status}")
                        
                        # Track series in memory
                        series_info = {
                            "id": series_id,
                            "title": title,
                            "year": year,
                            "status": hunt_status,
                            "instance_name": instance_name
                        }
                        
                        # Add to tracking or update
                        self.hunting_manager.track_series(series_id, instance_name, series_info)
                        self.log_info(f"Series ID {series_id} is now tracked for instance {instance_name}, status: {hunt_status}")
                        
                    except Exception as e:
                        self.log_error(f"Error processing series ID {series_id}: {e}")
                        continue
                
                self.log_info(f"Processed {processed_count} items for {instance_name}")
            
        except Exception as e:
            self.log_error(f"Error in Sonarr hunting process: {str(e)}")
