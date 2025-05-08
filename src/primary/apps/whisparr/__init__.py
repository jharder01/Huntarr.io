"""
Whisparr app module for Huntarr
Contains functionality for missing items and quality upgrades in Whisparr

Exclusively supports the v2 API (legacy).
"""

# Module exports
from src.primary.apps.whisparr.missing import process_missing_items
from src.primary.apps.whisparr.upgrade import process_cutoff_upgrades
from src.primary.settings_manager import load_settings
from src.primary.utils.logger import get_logger

# Define logger for this module
whisparr_logger = get_logger("whisparr")

# For backward compatibility
process_missing_scenes = process_missing_items

def get_configured_instances():
    """Get all configured and enabled Whisparr instances"""
    settings = load_settings("whisparr")
    instances = []
    # Use debug level to avoid log spam on new installations
    whisparr_logger.debug(f"Loaded Whisparr settings for instance check: {settings}")

    if not settings:
        whisparr_logger.debug("No settings found for Whisparr")
        return instances

    # Always use Whisparr V2 API
    # Use debug level to avoid log spam on new installations
    whisparr_logger.debug("Using Whisparr V2 API exclusively")

    # Check if instances are configured
    if "instances" in settings and isinstance(settings["instances"], list) and settings["instances"]:
        # Use debug level to avoid log spam on new installations
        whisparr_logger.debug(f"Found 'instances' list with {len(settings['instances'])} items. Processing...")
        for idx, instance in enumerate(settings["instances"]):
            whisparr_logger.debug(f"Checking instance #{idx}: {instance}")
            # Enhanced validation
            api_url = instance.get("api_url", "").strip()
            api_key = instance.get("api_key", "").strip()

            # Enhanced URL validation - ensure URL has proper scheme
            if api_url and not (api_url.startswith('http://') or api_url.startswith('https://')):
                whisparr_logger.warning(f"Instance '{instance.get('name', 'Unnamed')}' has URL without http(s) scheme: {api_url}")
                api_url = f"http://{api_url}"
                whisparr_logger.warning(f"Auto-correcting URL to: {api_url}")

            is_enabled = instance.get("enabled", True)

            # Only include properly configured instances
            if is_enabled and api_url and api_key:
                instance_name = instance.get("name", "Default")
                
                # Create a settings object for this instance by combining global settings with instance-specific ones
                instance_settings = settings.copy()
                
                # Remove instances list to avoid confusion
                if "instances" in instance_settings:
                    del instance_settings["instances"]
                
                # Override with instance-specific settings
                instance_settings["api_url"] = api_url
                instance_settings["api_key"] = api_key
                instance_settings["instance_name"] = instance_name
                
                # Add timeout setting with default if not present
                if "api_timeout" not in instance_settings:
                    instance_settings["api_timeout"] = 30
                
                # Use debug level to prevent log spam
                whisparr_logger.debug(f"Adding configured Whisparr instance: {instance_name}")
                instances.append(instance_settings)
            else:
                name = instance.get("name", "Unnamed")
                if not is_enabled:
                    whisparr_logger.debug(f"Skipping disabled instance: {name}")
                else:
                    # For brand new installations, don't spam logs with warnings about default instances
                    if name == 'Default':
                        # Use debug level for default instances to avoid log spam on new installations
                        whisparr_logger.debug(f"Skipping instance {name} due to missing API URL or API Key")
                    else:
                        # Still log warnings for non-default instances
                        whisparr_logger.warning(f"Skipping instance {name} due to missing API URL or API Key")
    else:
        whisparr_logger.debug("No instances array found in settings or it's empty")
    
    # Use debug level to avoid spamming logs, especially with 0 instances
    whisparr_logger.debug(f"Found {len(instances)} configured and enabled Whisparr instances")
    return instances

__all__ = ["process_missing_items", "process_missing_scenes", "process_cutoff_upgrades", "get_configured_instances"]