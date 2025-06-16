#!/usr/bin/env python3
"""
Settings manager for Huntarr
Handles loading, saving, and providing settings from SQLite database
Supports default configurations for different Arr applications
"""

import os
import json
import pathlib
import logging
import time
from typing import Dict, Any, Optional, List

# Create a simple logger for settings_manager
logging.basicConfig(level=logging.INFO)
settings_logger = logging.getLogger("settings_manager")

# Database integration
from src.primary.utils.database import get_database

# Default configs location
DEFAULT_CONFIGS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'default_configs'))

# Known app types
KNOWN_APP_TYPES = ["sonarr", "radarr", "lidarr", "readarr", "whisparr", "eros", "swaparr", "general"]

# Add a settings cache with timestamps to avoid excessive database reads
settings_cache = {}  # Format: {app_name: {'timestamp': timestamp, 'data': settings_dict}}
CACHE_TTL = 5  # Cache time-to-live in seconds

def clear_cache(app_name=None):
    """Clear the settings cache for a specific app or all apps."""
    global settings_cache
    if app_name:
        if app_name in settings_cache:
            settings_logger.debug(f"Clearing cache for {app_name}")
            settings_cache.pop(app_name, None)
    else:
        settings_logger.debug("Clearing entire settings cache")
        settings_cache = {}

def get_default_config_path(app_name: str) -> pathlib.Path:
    """Get the path to the default config file for a specific app."""
    return pathlib.Path(DEFAULT_CONFIGS_DIR) / f"{app_name}.json"

def load_default_app_settings(app_name: str) -> Dict[str, Any]:
    """Load default settings for a specific app from its JSON file."""
    default_file = get_default_config_path(app_name)
    if default_file.exists():
        try:
            with open(default_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            settings_logger.error(f"Error loading default settings for {app_name} from {default_file}: {e}")
            return {}
    else:
        settings_logger.warning(f"Default settings file not found for {app_name}: {default_file}")
        return {}

def _ensure_config_exists(app_name: str) -> None:
    """Ensure the config exists for an app in the database."""
    try:
        db = get_database()
        
        if app_name == 'general':
            # Check if general settings exist
            existing_settings = db.get_general_settings()
            if not existing_settings:
                # Load defaults and store in database
                default_settings = load_default_app_settings(app_name)
                if default_settings:
                    db.save_general_settings(default_settings)
                    settings_logger.info(f"Created default general settings in database")
                else:
                    settings_logger.warning(f"No default config found for general settings")
        else:
            # Check if app config exists
            config = db.get_app_config(app_name)
            if config is None:
                # Load defaults and store in database
                default_settings = load_default_app_settings(app_name)
                if default_settings:
                    db.save_app_config(app_name, default_settings)
                    settings_logger.info(f"Created default settings in database for {app_name}")
                else:
                    # Create empty config in database
                    db.save_app_config(app_name, {})
                    settings_logger.warning(f"No default config found for {app_name}. Created empty database entry.")
    except Exception as e:
        settings_logger.error(f"Database error for {app_name}: {e}")
        raise

def load_settings(app_type, use_cache=True):
    """
    Load settings for a specific app type from database
    
    Args:
        app_type: The app type to load settings for
        use_cache: Whether to use the cached settings if available and recent
        
    Returns:
        Dict containing the app settings
    """
    global settings_cache
    
    # Only log unexpected app types that are not 'general'
    if app_type not in KNOWN_APP_TYPES and app_type != "general":
        settings_logger.warning(f"load_settings called with unexpected app_type: {app_type}")
    
    # Check if we have a valid cache entry
    if use_cache and app_type in settings_cache:
        cache_entry = settings_cache[app_type]
        cache_age = time.time() - cache_entry.get('timestamp', 0)
        
        if cache_age < CACHE_TTL:
            settings_logger.debug(f"Using cached settings for {app_type} (age: {cache_age:.1f}s)")
            return cache_entry['data']
        else:
            settings_logger.debug(f"Cache expired for {app_type} (age: {cache_age:.1f}s)")
    
    # No valid cache entry, load from database
    current_settings = {}
    
    try:
        db = get_database()
        
        if app_type == 'general':
            current_settings = db.get_general_settings()
            if not current_settings:
                # Config doesn't exist in database, create it
                _ensure_config_exists(app_type)
                current_settings = db.get_general_settings()
        else:
            current_settings = db.get_app_config(app_type)
            if current_settings is None:
                # Config doesn't exist in database, create it
                _ensure_config_exists(app_type)
                current_settings = db.get_app_config(app_type) or {}
            
        settings_logger.debug(f"Loaded {app_type} settings from database")
        
    except Exception as e:
        settings_logger.error(f"Database error loading {app_type}: {e}")
        raise
    
    # Load defaults to check for missing keys
    default_settings = load_default_app_settings(app_type)
    
    # Add missing keys from defaults without overwriting existing values
    updated = False
    for key, value in default_settings.items():
        if key not in current_settings:
            current_settings[key] = value
            updated = True
    
    # Apply Lidarr migration (artist -> album) for Huntarr 7.5.0+
    if app_type == "lidarr":
        if current_settings.get("hunt_missing_mode") == "artist":
            settings_logger.info("Migrating Lidarr hunt_missing_mode from 'artist' to 'album' (Huntarr 7.5.0+)")
            current_settings["hunt_missing_mode"] = "album"
            updated = True
    
    # If keys were added, save the updated settings
    if updated:
        settings_logger.info(f"Added missing default keys to {app_type} settings")
        save_settings(app_type, current_settings)
    
    # Update cache
    settings_cache[app_type] = {
        'timestamp': time.time(),
        'data': current_settings
    }
        
    return current_settings

def save_settings(app_name: str, settings_data: Dict[str, Any]) -> bool:
    """Save settings for a specific app to database."""
    if app_name not in KNOWN_APP_TYPES:
         settings_logger.error(f"Attempted to save settings for unknown app type: {app_name}")
         return False
    
    # Debug: Log the data being saved, especially for general settings
    if app_name == 'general':
        settings_logger.debug(f"Saving general settings: {settings_data}")
        settings_logger.debug(f"Apprise URLs being saved: {settings_data.get('apprise_urls', 'NOT_FOUND')}")
    
    # Validate and enforce hourly_cap maximum limit of 250
    if 'hourly_cap' in settings_data:
        original_cap = settings_data['hourly_cap']
        if isinstance(original_cap, (int, float)) and original_cap > 250:
            settings_data['hourly_cap'] = 250
            settings_logger.warning(f"Hourly cap for {app_name} was {original_cap}, automatically reduced to maximum allowed value of 250")
    
    # Validate and enforce minimum values (no negative numbers allowed)
    numeric_fields = [
        'hourly_cap', 'hunt_missing_items', 'hunt_upgrade_items',
        'hunt_missing_movies', 'hunt_upgrade_movies', 'hunt_missing_books', 'hunt_upgrade_books'
    ]
    
    # Special validation for sleep_duration (minimum 600 seconds = 10 minutes)
    if 'sleep_duration' in settings_data:
        original_value = settings_data['sleep_duration']
        if isinstance(original_value, (int, float)) and original_value < 600:
            settings_data['sleep_duration'] = 600
            settings_logger.warning(f"Sleep duration for {app_name} was {original_value} seconds, automatically set to minimum allowed value of 600 seconds (10 minutes)")
    
    for field in numeric_fields:
        if field in settings_data:
            original_value = settings_data[field]
            if isinstance(original_value, (int, float)) and original_value < 0:
                settings_data[field] = 0
                settings_logger.warning(f"{field} for {app_name} was {original_value}, automatically set to minimum allowed value of 0")
    
    # Also validate numeric fields in instances array
    if 'instances' in settings_data and isinstance(settings_data['instances'], list):
        for i, instance in enumerate(settings_data['instances']):
            if isinstance(instance, dict):
                # Special validation for sleep_duration in instances
                if 'sleep_duration' in instance:
                    original_value = instance['sleep_duration']
                    if isinstance(original_value, (int, float)) and original_value < 600:
                        instance['sleep_duration'] = 600
                        settings_logger.warning(f"Sleep duration for {app_name} instance {i+1} was {original_value} seconds, automatically set to minimum allowed value of 600 seconds (10 minutes)")
                
                for field in numeric_fields:
                    if field in instance:
                        original_value = instance[field]
                        if isinstance(original_value, (int, float)) and original_value < 0:
                            instance[field] = 0
                            settings_logger.warning(f"{field} for {app_name} instance {i+1} was {original_value}, automatically set to minimum allowed value of 0")
    
    try:
        db = get_database()
        
        if app_name == 'general':
            db.save_general_settings(settings_data)
        else:
            db.save_app_config(app_name, settings_data)
            
        settings_logger.info(f"Settings saved successfully for {app_name} to database")
        success = True
        
    except Exception as e:
        settings_logger.error(f"Database error saving {app_name}: {e}")
        return False
    
    if success:
        # Clear cache for this app to ensure fresh reads
        clear_cache(app_name)
        
        # If general settings were saved, also clear timezone cache
        if app_name == 'general':
            try:
                from src.primary.utils.timezone_utils import clear_timezone_cache
                clear_timezone_cache()
                settings_logger.debug("Timezone cache cleared after general settings save")
            except Exception as e:
                settings_logger.warning(f"Failed to clear timezone cache: {e}")
    
    return success

def get_setting(app_name: str, key: str, default: Optional[Any] = None) -> Any:
    """Get a specific setting value for an app."""
    settings = load_settings(app_name)
    return settings.get(key, default)

def get_api_url(app_name: str) -> Optional[str]:
    """Get the API URL for a specific app."""
    return get_setting(app_name, "api_url", "")

def get_api_key(app_name: str) -> Optional[str]:
    """Get the API Key for a specific app."""
    return get_setting(app_name, "api_key", "")

def get_all_settings() -> Dict[str, Dict[str, Any]]:
    """Load settings for all known apps."""
    all_settings = {}
    for app_name in KNOWN_APP_TYPES:
        # Only include apps if their config exists or can be created from defaults
        settings = load_settings(app_name)
        if settings: # Only add if settings were successfully loaded
             all_settings[app_name] = settings
    return all_settings

def get_configured_apps() -> List[str]:
    """Return a list of app names that have basic configuration (API URL and Key)."""
    configured = []
    for app_name in KNOWN_APP_TYPES:
        if app_name == 'general':
            continue  # Skip general settings
            
        settings = load_settings(app_name)
        
        # First check if there are valid instances configured (multi-instance mode)
        if "instances" in settings and isinstance(settings["instances"], list) and settings["instances"]:
            for instance in settings["instances"]:
                if instance.get("enabled", True) and instance.get("api_url") and instance.get("api_key"):
                    configured.append(app_name)
                    break  # One valid instance is enough to consider the app configured
            continue  # Skip the single-instance check if we already checked instances
                
        # Fallback to legacy single-instance config
        if settings.get("api_url") and settings.get("api_key"):
            configured.append(app_name)
    
    settings_logger.info(f"Configured apps: {configured}")
    return configured

def apply_timezone(timezone: str) -> bool:
    """Apply the specified timezone to the container.
    
    Args:
        timezone: The timezone to set (e.g., 'UTC', 'America/New_York')
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Set TZ environment variable
        os.environ['TZ'] = timezone
        
        # Create symlink for localtime (common approach in containers)
        zoneinfo_path = f"/usr/share/zoneinfo/{timezone}"
        if os.path.exists(zoneinfo_path):
            # Remove existing symlink if it exists
            if os.path.exists("/etc/localtime"):
                os.remove("/etc/localtime")
            
            # Create new symlink
            os.symlink(zoneinfo_path, "/etc/localtime")
            
            # Also update /etc/timezone file if it exists
            with open("/etc/timezone", "w") as f:
                f.write(f"{timezone}\n")
                
            settings_logger.info(f"Timezone set to {timezone}")
            return True
        else:
            settings_logger.error(f"Timezone file not found: {zoneinfo_path}")
            return False
    except Exception as e:
        settings_logger.error(f"Error setting timezone: {str(e)}")
        return False

def validate_timezone(timezone_str: str) -> bool:
    """
    Validate if a timezone string is valid using pytz.
    
    Args:
        timezone_str: The timezone string to validate (e.g., 'Europe/Bucharest')
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not timezone_str:
        return False
        
    try:
        import pytz
        pytz.timezone(timezone_str)
        return True
    except pytz.UnknownTimeZoneError:
        return False
    except Exception as e:
        settings_logger.warning(f"Error validating timezone {timezone_str}: {e}")
        return False

def get_safe_timezone(timezone_str: str, fallback: str = "UTC") -> str:
    """
    Get a safe timezone string, falling back to a default if invalid.
    
    Args:
        timezone_str: The timezone string to validate
        fallback: The fallback timezone if validation fails (default: UTC)
        
    Returns:
        str: A valid timezone string
    """
    if validate_timezone(timezone_str):
        return timezone_str
    
    if timezone_str != fallback:
        settings_logger.warning(f"Invalid timezone '{timezone_str}', falling back to '{fallback}'")
    
    # Ensure fallback is also valid
    if validate_timezone(fallback):
        return fallback
    
    # Ultimate fallback to UTC if even the fallback is invalid
    settings_logger.error(f"Fallback timezone '{fallback}' is also invalid, using UTC")
    return "UTC"

def initialize_timezone_from_env():
    """Initialize timezone setting from TZ environment variable if not already set."""
    try:
        # Get the TZ environment variable
        tz_env = os.environ.get('TZ')
        if not tz_env:
            settings_logger.info("No TZ environment variable found, using default UTC")
            return
        
        # Load current general settings
        general_settings = load_settings("general")
        current_timezone = general_settings.get("timezone")
        
        # If timezone is not set in settings, initialize it from TZ environment variable
        if not current_timezone or current_timezone == "UTC":
            settings_logger.info(f"Initializing timezone from TZ environment variable: {tz_env}")
            
            # Use safe timezone validation
            safe_timezone = get_safe_timezone(tz_env)
            
            if safe_timezone == tz_env:
                settings_logger.info(f"TZ environment variable '{tz_env}' is valid")
            else:
                settings_logger.warning(f"TZ environment variable '{tz_env}' is invalid, using '{safe_timezone}' instead")
            
            # Update the settings with the safe timezone
            general_settings["timezone"] = safe_timezone
            save_settings("general", general_settings)
            
            # Apply the timezone to the system
            apply_timezone(safe_timezone)
            
            settings_logger.info(f"Successfully initialized timezone to {safe_timezone}")
        else:
            settings_logger.info(f"Timezone already set in settings: {current_timezone}")
            
            # Validate the existing timezone setting
            safe_timezone = get_safe_timezone(current_timezone)
            if safe_timezone != current_timezone:
                settings_logger.warning(f"Existing timezone setting '{current_timezone}' is invalid, updating to '{safe_timezone}'")
                general_settings["timezone"] = safe_timezone
                save_settings("general", general_settings)
                apply_timezone(safe_timezone)
            
    except Exception as e:
        settings_logger.error(f"Error initializing timezone from environment: {e}")

# Add a list of known advanced settings for clarity and documentation
ADVANCED_SETTINGS = [
    "api_timeout", 
    "command_wait_delay", 
    "command_wait_attempts", 
    "minimum_download_queue_size",
    "log_refresh_interval_seconds",
    "stateful_management_hours",
    "hourly_cap",
    "ssl_verify",  # Add SSL verification setting
    "base_url"     # Add base URL setting
]

def get_advanced_setting(setting_name, default_value=None):
    """
    Get an advanced setting from general settings.
    
    Advanced settings are now centralized in general settings and no longer stored
    in individual app settings files. This function provides a consistent way to
    access these settings from anywhere in the codebase.
    
    Args:
        setting_name: The name of the advanced setting to retrieve
        default_value: The default value to return if the setting is not found
        
    Returns:
        The value of the advanced setting, or default_value if not found
    """
    if setting_name not in ADVANCED_SETTINGS:
        settings_logger.warning(f"get_advanced_setting called with unknown setting: {setting_name}")
    
    general_settings = load_settings("general")
    return general_settings.get(setting_name, default_value)

def get_ssl_verify_setting():
    """
    Get the SSL verification setting from general settings.
    
    Returns:
        bool: True if SSL verification is enabled, False otherwise
    """
    return get_advanced_setting("ssl_verify", True)  # Default to True for security

def get_custom_tag(app_name: str, tag_type: str, default: str) -> str:
    """
    Get a custom tag for a specific app and tag type.
    
    Args:
        app_name: The name of the app (e.g., 'sonarr', 'radarr')
        tag_type: The type of tag (e.g., 'missing', 'upgrade')
        default: The default tag to return if not found
        
    Returns:
        str: The custom tag or the default if not found
    """
    settings = load_settings(app_name)
    custom_tags = settings.get("custom_tags", {})
    return custom_tags.get(tag_type, default)

def initialize_database():
    """Initialize the database with default configurations if needed."""
    try:
        db = get_database()
        defaults_dir = pathlib.Path(DEFAULT_CONFIGS_DIR)
        db.initialize_from_defaults(defaults_dir)
        settings_logger.info("Database initialized with default configurations")
    except Exception as e:
        settings_logger.error(f"Failed to initialize database: {e}")
        raise

# Example usage (for testing purposes, remove later)
if __name__ == "__main__":
    settings_logger.info(f"Known app types: {KNOWN_APP_TYPES}")
    
    # Ensure defaults are copied if needed
    for app in KNOWN_APP_TYPES:
        _ensure_config_exists(app)

    # Test loading Sonarr settings
    sonarr_settings = load_settings("sonarr")
    settings_logger.info(f"Loaded Sonarr settings: {json.dumps(sonarr_settings, indent=2)}")

    # Test getting a specific setting
    sonarr_sleep = get_setting("sonarr", "sleep_duration", 999)
    settings_logger.info(f"Sonarr sleep duration: {sonarr_sleep}")

    # Test saving updated settings (example)
    if sonarr_settings:
        sonarr_settings["sleep_duration"] = 850
        save_settings("sonarr", sonarr_settings)
        reloaded_sonarr_settings = load_settings("sonarr")
        settings_logger.info(f"Reloaded Sonarr settings after save: {json.dumps(reloaded_sonarr_settings, indent=2)}")


    # Test getting all settings
    all_app_settings = get_all_settings()
    settings_logger.info(f"All loaded settings: {json.dumps(all_app_settings, indent=2)}")

    # Test getting configured apps
    configured_list = get_configured_apps()
    settings_logger.info(f"Configured apps: {configured_list}")