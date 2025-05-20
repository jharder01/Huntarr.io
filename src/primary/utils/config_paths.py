#!/usr/bin/env python3
"""
Path configuration for Huntarr
Handles cross-platform path resolution for Docker, Windows, and macOS
"""

import os
import sys
import pathlib
import tempfile
import platform
import time

# Determine operating system
OS_TYPE = platform.system()  # 'Windows', 'Darwin' (macOS), or 'Linux'

# Get configuration directory - prioritize Docker environment
CONFIG_DIR = os.environ.get("HUNTARR_CONFIG_DIR")

if not CONFIG_DIR:
    # Docker default (primary option)
    if os.path.exists("/config") and os.access("/config", os.W_OK):
        CONFIG_DIR = "/config"
    # Platform-specific fallbacks (secondary options)
    elif OS_TYPE == "Windows":
        CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Huntarr")
    elif OS_TYPE == "Darwin":  # macOS
        CONFIG_DIR = os.path.join(os.path.expanduser("~"), "Documents", "Huntarr")
    else:  # Linux (non-Docker)
        CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "huntarr")

# Initialize the directory structure
CONFIG_PATH = pathlib.Path(CONFIG_DIR)

# Try to create the directory if it doesn't exist
try:
    CONFIG_PATH.mkdir(parents=True, exist_ok=True)
    
    # Define all app-specific directories
    USER_DIR = CONFIG_PATH / "user"
    LOG_DIR = CONFIG_PATH / "logs"
    HISTORY_DIR = CONFIG_PATH / "history"
    SETTINGS_DIR = CONFIG_PATH
    STATEFUL_DIR = CONFIG_PATH / "stateful"
    RESET_DIR = CONFIG_PATH / "reset"
    SCHEDULER_DIR = CONFIG_PATH / "scheduler"
    SWAPARR_STATE_DIR = CONFIG_PATH / "swaparr"
    
    # Create essential directories
    USER_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    HISTORY_DIR.mkdir(exist_ok=True)
    STATEFUL_DIR.mkdir(exist_ok=True)
    RESET_DIR.mkdir(exist_ok=True)
    SCHEDULER_DIR.mkdir(exist_ok=True)
    SWAPARR_STATE_DIR.mkdir(exist_ok=True)
    print(f"Using configuration directory: {CONFIG_DIR}")
    # Check write permissions with a test file
    test_file = CONFIG_PATH / f"write_test_{int(time.time())}.tmp"
    with open(test_file, "w") as f:
        f.write("test")
    if test_file.exists():
        test_file.unlink()  # Remove the test file
except Exception as e:
    print(f"Warning: Could not create or write to config directory at {CONFIG_DIR}: {str(e)}")
    # Fall back to temp directory as last resort
    temp_base = tempfile.gettempdir()
    CONFIG_DIR = os.path.join(temp_base, f"huntarr_config_{os.getpid()}")
    CONFIG_PATH = pathlib.Path(CONFIG_DIR)
    CONFIG_PATH.mkdir(parents=True, exist_ok=True)
    print(f"Using temporary config directory: {CONFIG_DIR}")
    
    # Also write to desktop log for visibility in case of issues
    try:
        desktop_log = os.path.expanduser("~/Desktop/huntarr_error.log")
        with open(desktop_log, "a") as f:
            f.write(f"\nUsing temporary config directory: {CONFIG_DIR}\n")
            f.write(f"Original error accessing primary config: {str(e)}\n")
    except:
        pass

# Create standard directories
LOG_DIR = CONFIG_PATH / "logs"
SETTINGS_DIR = CONFIG_PATH / "settings"
USER_DIR = CONFIG_PATH / "user"
STATEFUL_DIR = CONFIG_PATH / "stateful"
HISTORY_DIR = CONFIG_PATH / "history"
SCHEDULER_DIR = CONFIG_PATH / "scheduler"
RESET_DIR = CONFIG_PATH / "reset"  # Add reset directory
TALLY_DIR = CONFIG_PATH / "tally"  # Add tally directory for stats
SWAPARR_DIR = CONFIG_PATH / "swaparr"  # Add Swaparr directory
EROS_DIR = CONFIG_PATH / "eros"  # Add Eros directory

# Create all directories
for dir_path in [LOG_DIR, SETTINGS_DIR, USER_DIR, STATEFUL_DIR, HISTORY_DIR, 
                SCHEDULER_DIR, RESET_DIR, TALLY_DIR, SWAPARR_DIR, EROS_DIR]:
    try:
        dir_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create directory {dir_path}: {str(e)}")

# Set environment variables for backwards compatibility
os.environ["HUNTARR_CONFIG_DIR"] = str(CONFIG_PATH)
os.environ["CONFIG_DIR"] = str(CONFIG_PATH)  # For backward compatibility
os.environ["STATEFUL_DIR"] = str(STATEFUL_DIR)

# Helper functions to get paths
def get_path(*args):
    """Get a path relative to the config directory"""
    return CONFIG_PATH.joinpath(*args)

def get_app_config_path(app_type):
    """Get the path to an app's config file"""
    return CONFIG_PATH / f"{app_type}.json"

def get_reset_path(app_type):
    """Get the path to an app's reset file"""
    return RESET_DIR / f"{app_type}.reset"

def get_swaparr_state_path():
    """Get the Swaparr state directory"""
    return SWAPARR_DIR

def get_eros_config_path():
    """Get the Eros config file path"""
    return CONFIG_PATH / "eros.json"
