#!/usr/bin/env python3
"""
Huntarr - Main entry point for the application
Supports multiple Arr applications running concurrently
"""
import os
import sys
import time
import logging
import signal
import threading
import traceback
from typing import Dict
from pathlib import Path
from threading import Event
import json

# Load version from VERSION file
try:
    version_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "VERSION")
    if os.path.exists(version_file):
        with open(version_file, "r") as f:
            __version__ = f.read().strip()
    else:
        __version__ = "dev"
except Exception:
    __version__ = "unknown"

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

# Import application components
from src.primary import config
from src.primary.settings_manager import get_advanced_setting
from src.primary.utils.logger import get_logger
# Removed keys_manager import as settings_manager handles API details
from src.primary.state import check_state_reset, calculate_reset_time


# Track active threads and stop flag
app_threads: Dict[str, threading.Thread] = {}
stop_event = threading.Event()

def app_specific_loop(app_type: str) -> None:
    """
    Main processing loop for a specific Arr application.

    Args:
        app_type: The type of Arr application (sonarr, radarr, lidarr, readarr)
    """
    # This prevents circular imports while still accessing all features
    from src.primary import settings_manager
    from src.primary.stateful_manager import check_state_reset, initialize_stateful_system
    
    # Initialize settings and get the logger 
    logger = get_logger(app_type)
    initialize_stateful_system()
    settings = settings_manager.load_settings(app_type)
    
    # Skip this loop if app settings are invalid
    if not settings:
        logger.warning(f"No settings found for {app_type}, skipping processing loop.")
        return
    
    # Skip this loop if app is disabled
    if not settings.get("enabled", False):
        logger.warning(f"{app_type} is disabled, skipping processing loop.")
        return
    
    # Import the app-specific modules (dynamic imports to avoid circular dependencies)
    try:
        if app_type == "radarr":
            from src.primary.apps.radarr.processor import RadarrProcessor
            processor = RadarrProcessor()
        elif app_type == "sonarr":
            from src.primary.apps.sonarr.processor import SonarrProcessor
            processor = SonarrProcessor()
        elif app_type == "lidarr":
            from src.primary.apps.lidarr.processor import LidarrProcessor
            processor = LidarrProcessor()
        elif app_type == "readarr":
            from src.primary.apps.readarr.processor import ReadarrProcessor
            processor = ReadarrProcessor()
        elif app_type == "whisparr":
            from src.primary.apps.whisparr.processor import WhisparrProcessor
            processor = WhisparrProcessor()
        elif app_type == "eros":
            from src.primary.apps.eros.processor import ErosProcessor
            processor = ErosProcessor()
        elif app_type == "whisparrv2":
            from src.primary.apps.whisparrv2.processor import WhisparrV2Processor
            processor = WhisparrV2Processor()
        else:
            logger.error(f"Unknown app type: {app_type}")
            return
    except Exception as e:
        logger.error(f"Failed to initialize processor for {app_type}: {e}")
        logger.error(traceback.format_exc())
        return
    
    # Get the app-specific cycle time
    cycle_time = settings.get("cycle_time", 3600)  # Default 1 hour
    
    # Calculate maximum time allowed for a full cycle to complete
    # This uses either instance-specific or global settings
    command_wait_attempts = get_advanced_setting("command_wait_attempts", 600)
    command_wait_delay = get_advanced_setting("command_wait_delay", 1.0)
    api_timeout = get_advanced_setting("api_timeout", 90)
    estimated_max_cycle_time = command_wait_attempts * command_wait_delay + api_timeout + 60
    
    # Ensure minimum cycle time doesn't lead to overlapping runs
    cycle_time = max(cycle_time, estimated_max_cycle_time * 1.2)  # 20% margin
    
    # Main loop, runs until the app is stopped
    logger.info(f"{app_type.upper()} background thread started. Cycle time: {cycle_time}s")
    
    last_reset_check = time.time()
    reset_frequency = 86400  # Check for reset once per day
    should_reset = False
    
    try:
        while not stop_event.is_set():
            logger.info(f"=== {app_type.upper()} cycle starting ===")
            cycle_start_time = time.time()
            
            try:
                # Check for state reset once per day
                current_time = time.time()
                if current_time - last_reset_check > reset_frequency:
                    last_reset_check = current_time
                    # Check if state needs to be reset based on expiration date
                    should_reset = check_state_reset()
                
                # Run the app-specific processing
                processor.run()
                
                # Log success
                logger.info(f"=== {app_type.upper()} cycle completed successfully ===")
            except Exception as e:
                logger.error(f"Error in {app_type} processing: {e}")
                logger.error(traceback.format_exc())
                logger.warning(f"=== {app_type.upper()} cycle completed with errors ===")
            
            # Calculate time to next cycle, accounting for how long this cycle took
            cycle_duration = time.time() - cycle_start_time
            sleep_time = max(1, cycle_time - cycle_duration)  # At least 1 second
            
            if cycle_duration > cycle_time:
                logger.warning(f"{app_type} cycle took {cycle_duration:.2f}s, which exceeds the cycle time of {cycle_time}s")
                sleep_time = 1  # Just a minimal delay
            
            logger.info(f"{app_type.upper()} sleeping for {sleep_time:.2f}s until next cycle")
            
            # Wait for next cycle or until app is stopped
            remaining_time = sleep_time
            check_interval = min(10, sleep_time)  # Check for stop in 10s intervals max
            
            while remaining_time > 0 and not stop_event.is_set():
                wait_time = min(check_interval, remaining_time)
                stop_event.wait(wait_time)
                remaining_time -= wait_time
                
                # Exit the loop early if stop is requested
                if stop_event.is_set():
                    break
    except Exception as e:
        logger.error(f"Fatal error in {app_type} thread: {e}")
        logger.error(traceback.format_exc())
    
    logger.info(f"{app_type.upper()} background thread stopped")


def reset_app_cycle(app_type: str) -> bool:
    """
    Trigger a manual reset of an app's cycle.
    
    Args:
        app_type: The type of Arr application (sonarr, radarr, lidarr, readarr, etc.)
        
    Returns:
        bool: True if the reset was triggered, False if the app is not running
    """
    if app_type not in app_threads or not app_threads[app_type].is_alive():
        logger.warning(f"Cannot reset {app_type} cycle: thread not running")
        return False
    
    # Stop the current thread and start a new one
    old_thread = app_threads[app_type]
    logger.info(f"Stopping {app_type} thread for reset...")
    
    from src.primary import settings_manager
    # Start a new thread
    new_thread = threading.Thread(
        target=app_specific_loop,
        args=(app_type,),
        name=f"{app_type.capitalize()}-Thread",
        daemon=True
    )
    new_thread.start()
    app_threads[app_type] = new_thread
    logger.info(f"Started new {app_type} thread after reset")
    
    return True


def start_app_threads():
    """Start threads for all configured and enabled apps."""
    from src.primary import settings_manager
    
    logger.info("Starting app-specific threads...")
    for app_type in settings_manager.KNOWN_APP_TYPES:
        try:
            # If thread exists and is alive, skip
            if app_type in app_threads and app_threads[app_type].is_alive():
                continue
                
            # Get app settings
            settings = settings_manager.load_settings(app_type)
            
            # Skip if settings don't exist or app is disabled
            if not settings:
                continue
            if not settings.get("enabled", False):
                logger.debug(f"{app_type} is disabled, not starting thread")
                continue
                
            # Start new thread
            logger.info(f"Starting {app_type} thread...")
            thread = threading.Thread(
                target=app_specific_loop,
                args=(app_type,),
                name=f"{app_type.capitalize()}-Thread",
                daemon=True
            )
            thread.start()
            app_threads[app_type] = thread
        except Exception as e:
            logger.error(f"Error starting {app_type} thread: {e}")


def check_and_restart_threads():
    """Check if any threads have died and restart them if the app is still configured."""
    from src.primary import settings_manager
    
    for app_type in list(app_threads.keys()):
        thread = app_threads[app_type]
        if not thread.is_alive():
            logger.warning(f"{app_type} thread died, attempting to restart")
            
            # Check if app is still configured and enabled
            settings = settings_manager.load_settings(app_type)
            if not settings or not settings.get("enabled", False):
                logger.info(f"{app_type} is no longer enabled, not restarting thread")
                continue
                
            # Start new thread
            thread = threading.Thread(
                target=app_specific_loop,
                args=(app_type,),
                name=f"{app_type.capitalize()}-Thread",
                daemon=True
            )
            thread.start()
            app_threads[app_type] = thread
            logger.info(f"Restarted {app_type} thread")


def shutdown_handler(signum, frame):
    """Handle termination signals (SIGINT, SIGTERM)."""
    logger.info(f"Received signal {signum}, initiating shutdown...")
    stop_event.set()


def shutdown_threads():
    """Wait for all threads to finish."""
    logger.info("Waiting for app threads to finish...")
    active_thread_list = list(app_threads.values())
    for thread in active_thread_list:
        thread.join(timeout=15) # Wait up to 15 seconds per thread
        if thread.is_alive():
            logger.warning(f"Thread {thread.name} did not stop gracefully.")
    logger.info("All app threads stopped.")


def start_huntarr():
    """Main entry point for Huntarr background tasks."""
    logger.info(f"--- Starting Huntarr Background Tasks v{__version__} --- ")

    # Perform initial settings migration if specified (e.g., via env var or arg)
    if os.environ.get("HUNTARR_RUN_MIGRATION", "false").lower() == "true":
        logger.info("Running settings migration from huntarr.json (if found)...")
        from src.primary import settings_manager
        settings_manager.migrate_from_huntarr_json()

    # Log initial configuration for all known apps
    from src.primary import settings_manager
    for app_name in settings_manager.KNOWN_APP_TYPES:
        try:
            config.log_configuration(app_name)
        except Exception as e:
            logger.error(f"Error logging initial configuration for {app_name}: {e}")

    try:
        # Main loop: Start and monitor app threads
        while not stop_event.is_set():
            start_app_threads() # Start/Restart threads for configured apps
            # check_and_restart_threads() # This is implicitly handled by start_app_threads checking is_alive
            stop_event.wait(15) # Check for stop signal every 15 seconds

    except Exception as e:
        logger.exception(f"Unexpected error in main monitoring loop: {e}")
    finally:
        logger.info("Background task main loop exited. Shutting down threads...")
        if not stop_event.is_set():
             stop_event.set() # Ensure stop is signaled if loop exited unexpectedly
        shutdown_threads()


# Register signal handlers
signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

# Start if run directly
if __name__ == "__main__":
    start_huntarr()
