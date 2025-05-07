#!/usr/bin/env python3

from flask import current_app
from src.primary.utils.logger import get_logger

logger = get_logger("history")

def log_processed_media(app_type, media_name, media_id, instance_name, operation_type="missing"):
    """
    Log when media is processed by an app instance
    
    Parameters:
    - app_type: str - The app type (sonarr, radarr, etc)
    - media_name: str - Name of the processed media
    - media_id: str/int - ID of the processed media
    - instance_name: str - Name of the instance that processed it
    - operation_type: str - Type of operation ("missing" or "upgrade")
    
    Returns:
    - bool - Success or failure
    """
    try:
        logger.debug(f"Logging history entry for {app_type} - {instance_name}: '{media_name}' (ID: {media_id})")
        
        entry_data = {
            "name": media_name,
            "id": str(media_id),
            "instance_name": instance_name,
            "operation_type": operation_type,
            "hunt_status": "Searching"  # Set initial hunt status to Searching
        }
        
        # Get the hunting manager instance from Flask app config
        hunting_manager = current_app.config['HUNTING_MANAGER']
        result = hunting_manager.add_history_entry(app_type, entry_data)
        if result:
            logger.info(f"Logged history entry for {app_type} - {instance_name}: {media_name} ({operation_type})")
            return True
        else:
            logger.error(f"Failed to log history entry for {app_type} - {instance_name}: {media_name}")
            return False
    except Exception as e:
        logger.error(f"Error logging history entry: {str(e)}")
        return False
