#!/usr/bin/env python3
"""
Logging configuration for Huntarr
Supports separate log files for each application type
"""

import logging
import sys
import os
import pathlib
from typing import Dict, Optional

# Use the centralized path configuration
from src.primary.utils.config_paths import LOG_DIR

# Log directory is already created by config_paths module
# LOG_DIR already exists as pathlib.Path object pointing to the correct location

# Default log file for general messages
MAIN_LOG_FILE = LOG_DIR / "huntarr.log"

# App-specific log files
APP_LOG_FILES = {
    "sonarr": LOG_DIR / "sonarr.log", # Updated filename
    "radarr": LOG_DIR / "radarr.log", # Updated filename
    "lidarr": LOG_DIR / "lidarr.log", # Updated filename
    "readarr": LOG_DIR / "readarr.log", # Updated filename
    "whisparr": LOG_DIR / "whisparr.log", # Added Whisparr
    "eros": LOG_DIR / "eros.log",      # Added Eros for Whisparr V3
    "swaparr": LOG_DIR / "swaparr.log",  # Added Swaparr
    "hunting": LOG_DIR / "hunting.log"  # Added Hunt Manager - fixed key
}

# Global logger instances
logger: Optional[logging.Logger] = None
app_loggers: Dict[str, logging.Logger] = {}

def setup_main_logger(debug_mode=None):
    """Set up the main Huntarr logger."""
    global logger
    log_name = "huntarr"
    log_file = MAIN_LOG_FILE

    # Determine debug mode safely
    use_debug_mode = False
    if debug_mode is None:
        try:
            # Use the get_debug_mode function to check general settings
            from src.primary.config import get_debug_mode
            use_debug_mode = get_debug_mode()
        except (ImportError, AttributeError):
            pass # Default to False
    else:
        use_debug_mode = debug_mode

    # Get or create the main logger instance
    current_logger = logging.getLogger(log_name)

    # Reset handlers each time setup is called to avoid duplicates
    # This is important if setup might be called again (e.g., config reload)
    for handler in current_logger.handlers[:]:
        current_logger.removeHandler(handler)

    current_logger.propagate = False # Prevent propagation to root logger
    current_logger.setLevel(logging.DEBUG if use_debug_mode else logging.INFO)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if use_debug_mode else logging.INFO)

    # Create file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG if use_debug_mode else logging.INFO)

    # Set format for the main logger
    log_format = "%(asctime)s - huntarr - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # Add handlers to the main logger
    current_logger.addHandler(console_handler)
    current_logger.addHandler(file_handler)

    if use_debug_mode:
        current_logger.debug("Debug logging enabled for main logger")

    logger = current_logger # Assign to the global variable
    return current_logger

def get_logger(app_type: str) -> logging.Logger:
    """
    Get or create a logger for a specific app type.
    
    Args:
        app_type: The app type (e.g., 'sonarr', 'radarr').
        
    Returns:
        A logger specific to the app type, or the main logger if app_type is invalid.
    """
    if app_type not in APP_LOG_FILES:
        # Fallback to main logger if the app type is not recognized
        global logger
        if logger is None:
            # Ensure main logger is initialized if accessed before module-level setup
            setup_main_logger()
        # We checked logger is not None, so we can assert its type
        assert logger is not None
        return logger

    log_name = f"huntarr.{app_type}"
    if log_name in app_loggers:
        # Return cached logger instance
        return app_loggers[log_name]
    
    # If not cached, set up a new logger for this app type
    app_logger = logging.getLogger(log_name)
    
    # Prevent propagation to the main 'huntarr' logger or root logger
    app_logger.propagate = False
    
    # Determine debug mode setting safely
    try:
        from src.primary.config import get_debug_mode
        debug_mode = get_debug_mode()
    except ImportError:
        debug_mode = False
        
    app_logger.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    
    # Reset handlers in case this logger existed before but wasn't cached
    # (e.g., across restarts without clearing logging._handlers)
    for handler in app_logger.handlers[:]:
        app_logger.removeHandler(handler)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    
    # Create file handler for the specific app log file
    log_file = APP_LOG_FILES[app_type]
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    
    # Set a distinct format for this app log
    log_format = f"%(asctime)s - huntarr.{app_type} - %(levelname)s - %(message)s"
    formatter = logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S")
    
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    # Add the handlers specific to this app logger
    app_logger.addHandler(console_handler)
    app_logger.addHandler(file_handler)
    
    # Cache the configured logger
    app_loggers[log_name] = app_logger

    if debug_mode:
        app_logger.debug(f"Debug logging enabled for {app_type} logger")
        
    return app_logger

def update_logging_levels(debug_mode=None):
    """
    Update all logger levels based on the current debug mode setting.
    Call this after settings are changed in the UI to apply changes immediately.
    
    Args:
        debug_mode: Force a specific debug mode, or None to read from settings
    """
    # Determine debug mode from settings if not specified
    if debug_mode is None:
        try:
            from src.primary.config import get_debug_mode
            debug_mode = get_debug_mode()
        except (ImportError, AttributeError):
            debug_mode = False
    
    # Set level for main logger
    level = logging.DEBUG if debug_mode else logging.INFO
    if logger:
        logger.setLevel(level)
        for handler in logger.handlers:
            handler.setLevel(level)
    
    # Set level for all app loggers
    for app_type, app_logger in app_loggers.items():
        app_logger.setLevel(level)
        for handler in app_logger.handlers:
            handler.setLevel(level)
    
    # Set root logger level too
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for handler in root_logger.handlers:
        handler.setLevel(level)

    # Force Python's logging module to respect the log level for all existing loggers
    for name, logger_instance in logging.Logger.manager.loggerDict.items():
        if isinstance(logger_instance, logging.Logger):
            logger_instance.setLevel(level)
    
    return debug_mode

def debug_log(message: str, data: object = None, app_type: Optional[str] = None) -> None:
    """
    Log debug messages with optional data.
    
    Args:
        message: The message to log.
        data: Optional data to include with the message.
        app_type: Optional app type to log to a specific app's log file.
    """
    current_logger = get_logger(app_type) if app_type else logger
    
    if current_logger.level <= logging.DEBUG:
        current_logger.debug(f"{message}")
        if data is not None:
            try:
                import json
                as_json = json.dumps(data)
                if len(as_json) > 500:
                    as_json = as_json[:500] + "..."
                current_logger.debug(as_json)
            except:
                data_str = str(data)
                if len(data_str) > 500:
                    data_str = data_str[:500] + "..."
                current_logger.debug(data_str)

# Initialize the main logger instance when the module is imported
logger = setup_main_logger()