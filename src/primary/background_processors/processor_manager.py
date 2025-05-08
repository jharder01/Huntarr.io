"""
Processor Manager for coordinating background processors in Huntarr.

This module provides a unified interface for managing and executing
all the different background processors for various applications.
"""
import logging
from typing import Dict, List, Optional, Any
from src.primary.utils.logger import get_logger

# Create logger
logger = get_logger("processor_manager")

class ProcessorManager:
    """Manages and coordinates all background processors"""
    
    def __init__(self, hunting_manager):
        """
        Initialize the processor manager.
        
        Args:
            hunting_manager: The HuntingManager instance
        """
        self.logger = logger
        self.hunting_manager = hunting_manager
        self.processors = {}
        self._initialize_processors()
    
    def _initialize_processors(self):
        """Initialize all the supported processors"""
        try:
            self.logger.info("[_initialize_processors] Starting processor initialization...")
            # Import all processors
            from src.primary.background_processors.radarr_processor import RadarrProcessor
            from src.primary.background_processors.sonarr_processor import SonarrProcessor
            from src.primary.background_processors.lidarr_processor import LidarrProcessor
            from src.primary.background_processors.readarr_processor import ReadarrProcessor
            from src.primary.background_processors.whisparr_processor import WhisparrProcessor
            from src.primary.background_processors.eros_processor import ErosProcessor
            from src.primary.background_processors.queue_tracker import QueueTracker
            self.logger.info("[_initialize_processors] All processor modules imported.")
            
            # Create processor instances
            self.processors = {
                "radarr": RadarrProcessor(self.hunting_manager),
                "sonarr": SonarrProcessor(self.hunting_manager),
                "lidarr": LidarrProcessor(self.hunting_manager),
                "readarr": ReadarrProcessor(self.hunting_manager),
                "whisparr": WhisparrProcessor(self.hunting_manager),
                "eros": ErosProcessor(self.hunting_manager),
            }
            self.logger.info("[_initialize_processors] Base processors initialized.")

            try:
                self.logger.info("[_initialize_processors] Attempting to instantiate QueueTracker...")
                self.processors["queue_tracker"] = QueueTracker()
                self.logger.info("[_initialize_processors] QueueTracker instantiated successfully.")
            except Exception as e_qt:
                self.logger.error(f"[_initialize_processors] FAILED to instantiate QueueTracker: {str(e_qt)}", exc_info=True)
            
            self.logger.info(f"[_initialize_processors] Final processor count: {len(self.processors)} processors initialized.")
        except Exception as e:
            self.logger.error(f"[_initialize_processors] Error initializing processors: {e}", exc_info=True)
    
    def process_hunting(self, app_type: str, stop_event) -> None:
        """
        Process hunting for a specific application type.
        
        Args:
            app_type: The application type (e.g., 'radarr', 'sonarr')
            stop_event: Event to check if processing should stop
        """
        if app_type in self.processors:
            self.logger.info(f"Starting hunting process for {app_type}")
            self.processors[app_type].process(stop_event)
        else:
            self.logger.warning(f"No processor registered for {app_type}")
    
    def process_queue_tracking(self, stop_event) -> None:
        """
        Process queue tracking for all applications.
        
        Args:
            stop_event: Event to check if processing should stop
        """
        if "queue_tracker" in self.processors:
            self.logger.info("Starting queue tracking process")
            self.processors["queue_tracker"].process(stop_event)
        else:
            self.logger.warning("Queue tracker not registered")
    
    def get_processor(self, app_type: str):
        """
        Get a specific processor by app_type.
        
        Args:
            app_type: The application type to get processor for
            
        Returns:
            The processor instance or None if not found
        """
        return self.processors.get(app_type, None)
    
    def get_all_processors(self):
        """
        Get all registered processors.
        
        Returns:
            Dictionary of all processors
        """
        return self.processors
