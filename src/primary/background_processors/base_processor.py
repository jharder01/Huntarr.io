"""
Base processor for background tasks in Huntarr.

This module provides a base class that all application-specific processors
should inherit from to share common functionality.
"""
import logging
import time
from typing import Dict, List, Optional, Any, Callable

# Create logger
logger = logging.getLogger("hunting")

class BaseProcessor:
    """Base class for all background processors"""
    
    def __init__(self, app_type: str):
        """
        Initialize the processor.
        
        Args:
            app_type: The type of application this processor handles (e.g., 'radarr', 'sonarr')
        """
        self.app_type = app_type
        self.logger = logger
    
    def process(self, stop_event) -> None:
        """
        Process the application's hunting logic.
        
        Args:
            stop_event: Event to check if processing should stop
        """
        self.logger.info(f"[HUNTING] === {self.app_type.capitalize()} hunting cycle started ====")
        try:
            self._process_implementation(stop_event)
        except Exception as e:
            self.logger.error(f"[HUNTING] Error in {self.app_type} processing: {e}")
        self.logger.info(f"[HUNTING] === {self.app_type.capitalize()} hunting cycle completed ====")
    
    def _process_implementation(self, stop_event) -> None:
        """
        Implementation of the process method to be overridden by subclasses.
        
        Args:
            stop_event: Event to check if processing should stop
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    def log_info(self, message: str) -> None:
        """Log an info message with the hunting prefix"""
        self.logger.info(f"[HUNTING] {message}")
    
    def log_error(self, message: str) -> None:
        """Log an error message with the hunting prefix"""
        self.logger.error(f"[HUNTING] {message}")
    
    def log_warning(self, message: str) -> None:
        """Log a warning message with the hunting prefix"""
        self.logger.warning(f"[HUNTING] {message}")
    
    def log_debug(self, message: str) -> None:
        """Log a debug message with the hunting prefix"""
        self.logger.debug(f"[HUNTING] {message}")
