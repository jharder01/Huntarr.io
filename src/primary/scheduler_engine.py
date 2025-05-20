#!/usr/bin/env python3
"""
Scheduler Engine for Huntarr
Handles execution of scheduled actions from schedule.json
"""

import os
import json
import threading
import datetime
import time
import traceback
from typing import Dict, List, Any
import collections

# Import settings_manager to handle cache refreshing
from src.primary.settings_manager import clear_cache

from src.primary.utils.logger import get_logger
# Add import for stateful_manager's check_expiration
from src.primary.stateful_manager import check_expiration as check_stateful_expiration

# Initialize logger
scheduler_logger = get_logger("scheduler")

# Scheduler constants
SCHEDULE_CHECK_INTERVAL = 60  # Check schedule every minute
# Use the centralized path configuration
from src.primary.utils.config_paths import SCHEDULER_DIR, CONFIG_PATH, SETTINGS_DIR

# Convert Path object to string for compatibility with os.path functions
SCHEDULE_DIR = str(SCHEDULER_DIR)
SCHEDULE_FILE = os.path.join(SCHEDULE_DIR, "schedule.json")

# Track last executed actions to prevent duplicates
last_executed_actions = {}

# Track execution history for logging
max_history_entries = 50
execution_history = collections.deque(maxlen=max_history_entries)

stop_event = threading.Event()
scheduler_thread = None

def load_schedule():
    """Load the schedule configuration from file"""
    try:
        os.makedirs(SCHEDULE_DIR, exist_ok=True)  # Ensure directory exists
        
        if os.path.exists(SCHEDULE_FILE):
            try:
                # Check if file is empty
                if os.path.getsize(SCHEDULE_FILE) == 0:
                    return {"global": [], "sonarr": [], "radarr": [], "lidarr": [], "readarr": [], "whisparr": [], "eros": []}
                
                # Attempt to load JSON
                with open(SCHEDULE_FILE, 'r') as f:
                    content = f.read()
                    scheduler_logger.debug(f"Schedule file content (first 100 chars): {content[:100]}...")
                    schedule_data = json.loads(content)
                    
                    # Ensure the schedule data has the expected structure
                    for app_type in ["global", "sonarr", "radarr", "lidarr", "readarr", "whisparr", "eros"]:
                        if app_type not in schedule_data:
                            schedule_data[app_type] = []
                    
                    return schedule_data
            except json.JSONDecodeError as json_err:
                scheduler_logger.error(f"Invalid JSON in schedule file: {json_err}")
                scheduler_logger.error(f"Attempting to repair JSON file...")
                
                # Backup the corrupted file
                backup_file = f"{SCHEDULE_FILE}.backup.{int(time.time())}"
                os.rename(SCHEDULE_FILE, backup_file)
                scheduler_logger.info(f"Backed up corrupted file to {backup_file}")
                
                # Create a new empty schedule file
                default_schedule = {"global": [], "sonarr": [], "radarr": [], "lidarr": [], "readarr": [], "whisparr": [], "eros": []}
                with open(SCHEDULE_FILE, 'w') as f:
                    json.dump(default_schedule, f, indent=2)
                scheduler_logger.info(f"Created new empty schedule file")
                
                return default_schedule
        else:
            # Create the default schedule file
            default_schedule = {"global": [], "sonarr": [], "radarr": [], "lidarr": [], "readarr": [], "whisparr": [], "eros": []}
            with open(SCHEDULE_FILE, 'w') as f:
                json.dump(default_schedule, f, indent=2)
            scheduler_logger.info(f"Created new schedule file with default structure")
            return default_schedule
    except Exception as e:
        scheduler_logger.error(f"Error loading schedule: {e}")
        scheduler_logger.error(traceback.format_exc())
        return {"global": [], "sonarr": [], "radarr": [], "lidarr": [], "readarr": [], "whisparr": [], "eros": []}

def add_to_history(action_entry, status, message):
    """Add an action execution to the history log"""
    now = datetime.datetime.now()
    time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    
    history_entry = {
        "timestamp": time_str,
        "id": action_entry.get("id", "unknown"),
        "action": action_entry.get("action", "unknown"),
        "app": action_entry.get("app", "unknown"),
        "status": status,
        "message": message
    }
    
    execution_history.appendleft(history_entry)
    scheduler_logger.debug(f"Scheduler history: {time_str} - {action_entry.get('action')} for {action_entry.get('app')} - {status} - {message}")

def execute_action(action_entry):
    """Execute a scheduled action"""
    action_type = action_entry.get("action")
    app_type = action_entry.get("app")
    app_id = action_entry.get("id")
    
    # Generate a unique key for this action to track execution
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    execution_key = f"{app_id}_{current_date}"
    
    # Check if this action was already executed today
    if execution_key in last_executed_actions:
        message = f"Action {app_id} for {app_type} already executed today, skipping"
        scheduler_logger.debug(message)
        add_to_history(action_entry, "skipped", message)
        return False  # Already executed
    
    try:
        # Handle both old "pause" and new "disable" terminology
        if action_type == "pause" or action_type == "disable":
            # Disable logic for global or specific app
            if app_type == "global":
                message = "Executing global pause action"
                scheduler_logger.info(message)
                try:
                    apps = ['sonarr', 'radarr', 'lidarr', 'readarr', 'whisparr', 'eros']
                    for app in apps:
                        config_file = os.path.join(str(SETTINGS_DIR), f"{app}.json")
                        if os.path.exists(config_file):
                            with open(config_file, 'r') as f:
                                config_data = json.load(f)
                            # Update root level enabled field
                            config_data['enabled'] = False
                            # Also update enabled field in instances array if it exists
                            if 'instances' in config_data and isinstance(config_data['instances'], list):
                                for instance in config_data['instances']:
                                    if isinstance(instance, dict):
                                        instance['enabled'] = False
                            with open(config_file, 'w') as f:
                                json.dump(config_data, f, indent=2)
                            # Clear cache for this app to ensure the UI refreshes
                            clear_cache(app)
                    result_message = "All apps disabled successfully"
                    scheduler_logger.info(result_message)
                    add_to_history(action_entry, "success", result_message)
                except Exception as e:
                    error_message = f"Error disabling all apps: {str(e)}"
                    scheduler_logger.error(error_message)
                    add_to_history(action_entry, "error", error_message)
                    return False
            else:
                message = f"Executing disable action for {app_type}"
                scheduler_logger.info(message)
                try:
                    config_file = os.path.join(str(SETTINGS_DIR), f"{app_type}.json")
                    if os.path.exists(config_file):
                        with open(config_file, 'r') as f:
                            config_data = json.load(f)
                        # Update root level enabled field
                        config_data['enabled'] = False
                        # Also update enabled field in instances array if it exists
                        if 'instances' in config_data and isinstance(config_data['instances'], list):
                            for instance in config_data['instances']:
                                if isinstance(instance, dict):
                                    instance['enabled'] = False
                        with open(config_file, 'w') as f:
                            json.dump(config_data, f, indent=2)
                        # Clear cache for this app to ensure the UI refreshes
                        clear_cache(app_type)
                    result_message = f"{app_type} disabled successfully"
                    scheduler_logger.info(result_message)
                    add_to_history(action_entry, "success", result_message)
                except Exception as e:
                    error_message = f"Error disabling {app_type}: {str(e)}"
                    scheduler_logger.error(error_message)
                    add_to_history(action_entry, "error", error_message)
                    return False
        
        # Handle both old "resume" and new "enable" terminology
        elif action_type == "resume" or action_type == "enable":
            # Enable logic for global or specific app
            if app_type == "global":
                message = "Executing global enable action"
                scheduler_logger.info(message)
                try:
                    apps = ['sonarr', 'radarr', 'lidarr', 'readarr', 'whisparr', 'eros']
                    for app in apps:
                        config_file = os.path.join(str(SETTINGS_DIR), f"{app}.json")
                        if os.path.exists(config_file):
                            with open(config_file, 'r') as f:
                                config_data = json.load(f)
                            # Update root level enabled field
                            config_data['enabled'] = True
                            # Also update enabled field in instances array if it exists
                            if 'instances' in config_data and isinstance(config_data['instances'], list):
                                for instance in config_data['instances']:
                                    if isinstance(instance, dict):
                                        instance['enabled'] = True
                            with open(config_file, 'w') as f:
                                json.dump(config_data, f, indent=2)
                            # Clear cache for this app to ensure the UI refreshes
                            clear_cache(app)
                    result_message = "All apps enabled successfully"
                    scheduler_logger.info(result_message)
                    add_to_history(action_entry, "success", result_message)
                except Exception as e:
                    error_message = f"Error enabling all apps: {str(e)}"
                    scheduler_logger.error(error_message)
                    add_to_history(action_entry, "error", error_message)
                    return False
            else:
                message = f"Executing enable action for {app_type}"
                scheduler_logger.info(message)
                try:
                    config_file = os.path.join(str(SETTINGS_DIR), f"{app_type}.json")
                    if os.path.exists(config_file):
                        with open(config_file, 'r') as f:
                            config_data = json.load(f)
                        # Update root level enabled field
                        config_data['enabled'] = True
                        # Also update enabled field in instances array if it exists
                        if 'instances' in config_data and isinstance(config_data['instances'], list):
                            for instance in config_data['instances']:
                                if isinstance(instance, dict):
                                    instance['enabled'] = True
                        with open(config_file, 'w') as f:
                            json.dump(config_data, f, indent=2)
                        # Clear cache for this app to ensure the UI refreshes
                        clear_cache(app_type)
                    result_message = f"{app_type} enabled successfully"
                    scheduler_logger.info(result_message)
                    add_to_history(action_entry, "success", result_message)
                except Exception as e:
                    error_message = f"Error enabling {app_type}: {str(e)}"
                    scheduler_logger.error(error_message)
                    add_to_history(action_entry, "error", error_message)
                    return False
        
        # Handle the API limit actions based on the predefined values
        elif action_type.startswith("api-") or action_type.startswith("API Limits "):
            # Extract the API limit value from the action type
            try:
                # Handle both formats: "api-5" and "API Limits 5"
                if action_type.startswith("api-"):
                    api_limit = int(action_type.replace("api-", ""))
                else:
                    api_limit = int(action_type.replace("API Limits ", ""))
                
                if app_type == "global":
                    message = f"Setting global API cap to {api_limit}"
                    scheduler_logger.info(message)
                    try:
                        apps = ['sonarr', 'radarr', 'lidarr', 'readarr', 'whisparr', 'eros']
                        for app in apps:
                            config_file = os.path.join(str(SETTINGS_DIR), f"{app}.json")
                            if os.path.exists(config_file):
                                with open(config_file, 'r') as f:
                                    config_data = json.load(f)
                                config_data['hourly_cap'] = api_limit
                                with open(config_file, 'w') as f:
                                    json.dump(config_data, f, indent=2)
                        result_message = f"API cap set to {api_limit} for all apps"
                        scheduler_logger.info(result_message)
                        add_to_history(action_entry, "success", result_message)
                    except Exception as e:
                        error_message = f"Error setting global API cap to {api_limit}: {str(e)}"
                        scheduler_logger.error(error_message)
                        add_to_history(action_entry, "error", error_message)
                        return False
                else:
                    message = f"Setting API cap for {app_type} to {api_limit}"
                    scheduler_logger.info(message)
                    try:
                        config_file = os.path.join(str(SETTINGS_DIR), f"{app_type}.json")
                        if os.path.exists(config_file):
                            with open(config_file, 'r') as f:
                                config_data = json.load(f)
                            config_data['hourly_cap'] = api_limit
                            with open(config_file, 'w') as f:
                                json.dump(config_data, f, indent=2)
                        result_message = f"API cap set to {api_limit} for {app_type}"
                        scheduler_logger.info(result_message)
                        add_to_history(action_entry, "success", result_message)
                    except Exception as e:
                        error_message = f"Error setting API cap for {app_type} to {api_limit}: {str(e)}"
                        scheduler_logger.error(error_message)
                        add_to_history(action_entry, "error", error_message)
                        return False
            except ValueError:
                error_message = f"Invalid API limit format: {action_type}"
                scheduler_logger.error(error_message)
                add_to_history(action_entry, "error", error_message)
                return False
        
        # Mark this action as executed for today
        last_executed_actions[execution_key] = datetime.datetime.now()
        return True
    
    except Exception as e:
        scheduler_logger.error(f"Error executing action {action_type} for {app_type}: {e}")
        scheduler_logger.error(traceback.format_exc())
        return False

def should_execute_schedule(schedule_entry):
    """Check if a schedule entry should be executed now"""
    schedule_id = schedule_entry.get("id", "unknown")
    
    # Debug log the schedule we're checking
    scheduler_logger.debug(f"Checking if schedule {schedule_id} should be executed")
    
    # Log exact system time for debugging
    exact_time = datetime.datetime.now()
    scheduler_logger.info(f"EXACT CURRENT TIME: {exact_time.strftime('%Y-%m-%d %H:%M:%S.%f')}")
    
    if not schedule_entry.get("enabled", True):
        scheduler_logger.debug(f"Schedule {schedule_id} is disabled, skipping")
        return False
    
    # Check if specific days are configured
    days = schedule_entry.get("days", [])
    scheduler_logger.debug(f"Schedule {schedule_id} days: {days}")
    
    # Get today's day of week in lowercase
    current_day = datetime.datetime.now().strftime("%A").lower()  # e.g., 'monday'
    
    # Debug what's being compared
    scheduler_logger.info(f"CRITICAL DEBUG - Today: '{current_day}', Schedule days: {days}")
    
    # If days array is empty, treat as "run every day"
    if not days:
        scheduler_logger.debug(f"Schedule {schedule_id} has no days specified, treating as 'run every day'")
    else:
        # Make sure all day comparisons are done with lowercase strings
        lowercase_days = [str(day).lower() for day in days]
        
        # If today is not in the schedule days, skip this schedule
        if current_day not in lowercase_days:
            scheduler_logger.info(f"FAILURE: Schedule {schedule_id} not configured to run on {current_day}, skipping")
            return False
        else:
            scheduler_logger.info(f"SUCCESS: Schedule {schedule_id} IS configured to run on {current_day}")

    
    # Get current time with second-level precision for accurate timing
    current_time = datetime.datetime.now()
    
    # Extract scheduled time from different possible formats
    try:
        # First try the flat format
        schedule_hour = schedule_entry.get("hour")
        schedule_minute = schedule_entry.get("minute")
        
        # If not found, try nested format
        if schedule_hour is None or schedule_minute is None:
            schedule_hour = schedule_entry.get("time", {}).get("hour")
            schedule_minute = schedule_entry.get("time", {}).get("minute")
        
        # Convert to integers to ensure proper comparison
        schedule_hour = int(schedule_hour)
        schedule_minute = int(schedule_minute)
    except (TypeError, ValueError):
        scheduler_logger.warning(f"Invalid schedule time format in entry: {schedule_entry}")
        return False
    
    # Add detailed logging for time debugging
    scheduler_logger.info(f"Schedule {schedule_id} time: {schedule_hour:02d}:{schedule_minute:02d}, " 
                         f"current time: {current_time.hour:02d}:{current_time.minute:02d}:{current_time.second:02d}")
    
    # ===== STRICT TIME COMPARISON - PREVENT EARLY EXECUTION =====
    
    # If current hour is BEFORE scheduled hour, NEVER execute
    if current_time.hour < schedule_hour:
        scheduler_logger.info(f"BLOCKED EXECUTION: Current hour {current_time.hour} is BEFORE scheduled hour {schedule_hour}")
        return False
    
    # If same hour but current minute is BEFORE scheduled minute, NEVER execute
    if current_time.hour == schedule_hour and current_time.minute < schedule_minute:
        scheduler_logger.info(f"BLOCKED EXECUTION: Current minute {current_time.minute} is BEFORE scheduled minute {schedule_minute}")
        return False
    
    # ===== 4-MINUTE EXECUTION WINDOW =====
    
    # We're in the scheduled hour and minute, or later - check 4-minute window
    if current_time.hour == schedule_hour:
        # Execute if we're in the scheduled minute or up to 3 minutes after the scheduled minute
        if current_time.minute >= schedule_minute and current_time.minute < schedule_minute + 4:
            scheduler_logger.info(f"EXECUTING: Current time {current_time.hour:02d}:{current_time.minute:02d} is within the 4-minute window after {schedule_hour:02d}:{schedule_minute:02d}")
            return True
    
    # Handle hour rollover case (e.g., scheduled for 6:59, now it's 7:00, 7:01, or 7:02)
    if current_time.hour == schedule_hour + 1:
        # Only apply if scheduled minute was in the last 3 minutes of the hour (57-59)
        # and current minute is in the first (60 - schedule_minute) minutes of the next hour
        if schedule_minute >= 57 and current_time.minute < (60 - schedule_minute):
            scheduler_logger.info(f"EXECUTING: Hour rollover within 4-minute window after {schedule_hour:02d}:{schedule_minute:02d}")
            return True
    
    # We've missed the 4-minute window
    scheduler_logger.info(f"MISSED WINDOW: Current time {current_time.hour:02d}:{current_time.minute:02d} " 
                        f"is past the 4-minute window for {schedule_hour:02d}:{schedule_minute:02d}")
    return False

def check_and_execute_schedules():
    """Check all schedules and execute those that should run now"""
    try:
        # Format time
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        scheduler_logger.debug(f"Checking schedules at {current_time}")
        
        # Check if schedule file exists and log its status
        if not os.path.exists(SCHEDULE_FILE):
            scheduler_logger.debug(f"Schedule file does not exist: {SCHEDULE_FILE}")
            add_to_history({"action": "check"}, "debug", f"Schedule file not found at {SCHEDULE_FILE}")
            return
        
        scheduler_logger.debug(f"Schedule file exists at {SCHEDULE_FILE} with size {os.path.getsize(SCHEDULE_FILE)} bytes")
        
        # Load the schedule
        schedule_data = load_schedule()
        if not schedule_data:
            return
        
        # Log schedule data summary
        schedule_summary = {app: len(schedules) for app, schedules in schedule_data.items()}
        scheduler_logger.debug(f"Loaded schedules: {schedule_summary}")
        
        # Add to history that we've checked schedules
        add_to_history({"action": "check"}, "debug", f"Checking schedules at {current_time}")
        
        # Initialize counter for schedules found
        schedules_found = 0
        
        # Check for schedules to execute
        for app_type, schedules in schedule_data.items():
            for schedule_entry in schedules:
                schedules_found += 1
                if should_execute_schedule(schedule_entry):
                    # Check if we already executed this entry in the last 5 minutes
                    entry_id = schedule_entry.get("id")
                    if entry_id and entry_id in last_executed_actions:
                        last_time = last_executed_actions[entry_id]
                        now = datetime.datetime.now()
                        delta = (now - last_time).total_seconds() / 60  # Minutes
                        
                        if delta < 5:  # Don't re-execute if less than 5 minutes have passed
                            scheduler_logger.info(f"Skipping recently executed schedule '{entry_id}' ({delta:.1f} minutes ago)")
                            add_to_history(
                                schedule_entry, 
                                "skipped", 
                                f"Already executed {delta:.1f} minutes ago"
                            )
                            continue
                    
                    # Execute the action
                    schedule_entry["appType"] = app_type
                    execute_action(schedule_entry)
                    
                    # Update last executed time
                    if entry_id:
                        last_executed_actions[entry_id] = datetime.datetime.now()
        
        # No need to log anything when no schedules are found, as this is expected
    
    except Exception as e:
        error_msg = f"Error checking schedules: {e}"
        scheduler_logger.error(error_msg)
        scheduler_logger.error(traceback.format_exc())
        add_to_history({"action": "check"}, "error", error_msg)

def scheduler_loop():
    """Main scheduler loop - runs in a background thread"""
    scheduler_logger.info("Scheduler loop started.")
    while not stop_event.is_set():
        try:
            # Check for stateful management expiration first
            scheduler_logger.debug("Checking for stateful management expiration...")
            check_stateful_expiration() # Call the imported function
            
            scheduler_logger.debug("Checking and executing schedules...")
            check_and_execute_schedules()
            
            # Sleep until the next check
            stop_event.wait(SCHEDULE_CHECK_INTERVAL)
            
        except Exception as e:
            scheduler_logger.error(f"Error in scheduler loop: {e}")
            scheduler_logger.error(traceback.format_exc())
            # Sleep briefly to avoid rapidly repeating errors
            time.sleep(5)
    
    scheduler_logger.info("Scheduler loop stopped")

def get_execution_history():
    """Get the execution history for the scheduler"""
    return list(execution_history)

def start_scheduler():
    """Start the scheduler engine"""
    global scheduler_thread
    
    if scheduler_thread and scheduler_thread.is_alive():
        scheduler_logger.info("Scheduler already running")
        return
    
    # Reset the stop event
    stop_event.clear()
    
    # Create and start the scheduler thread
    scheduler_thread = threading.Thread(target=scheduler_loop, name="SchedulerEngine", daemon=True)
    scheduler_thread.start()
    
    # Add a startup entry to the history
    startup_entry = {
        "id": "system",
        "action": "startup",
        "app": "scheduler"
    }
    add_to_history(startup_entry, "info", "Scheduler engine started")
    
    scheduler_logger.info(f"Scheduler engine started. Thread is alive: {scheduler_thread.is_alive()}")
    return True

def stop_scheduler():
    """Stop the scheduler engine"""
    global scheduler_thread
    
    if not scheduler_thread or not scheduler_thread.is_alive():
        scheduler_logger.info("Scheduler not running")
        return
    
    # Signal the thread to stop
    stop_event.set()
    
    # Wait for the thread to terminate (with timeout)
    scheduler_thread.join(timeout=5.0)
    
    if scheduler_thread.is_alive():
        scheduler_logger.warning("Scheduler did not terminate gracefully")
    else:
        scheduler_logger.info("Scheduler stopped gracefully")
