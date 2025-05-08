def hunting_manager_loop():
    """
    Main hunting manager loop that coordinates hunting across different app types.
    Uses the ProcessorManager to handle each application's specific processing.
    """
    logger = get_logger("hunting")
    logger.info("[HUNTING] Hunting Manager background thread started.")
    
    # Initialize HuntingManager using the updated version that uses stateful directory
    manager = HuntingManager("/config")
    logger.info("[HUNTING] Hunting Manager initialized with stateful directory")
    
    # Initialize the stateful system if needed
    from src.primary.stateful_manager import initialize_stateful_system
    initialize_stateful_system()
    
    # Initialize the processor manager
    from src.primary.background_processors.processor_manager import ProcessorManager
    processor_manager = ProcessorManager(manager)
    logger.info(f"[HUNTING] Processor Manager initialized with {len(processor_manager.processors)} processors")

    # Set up queue tracking interval (check every 2 minutes)
    last_queue_track_time = 0
    queue_track_interval = 120  # 2 minutes
    
    while not hunting_manager_stop_event.is_set():
        logger.info("[HUNTING] === Hunting Manager cycle started ===")
        
        # Process hunting for each application type
        app_types = ["radarr", "sonarr", "lidarr", "readarr", "whisparr", "eros"]
        for app_type in app_types:
            if hunting_manager_stop_event.is_set():
                break
            processor_manager.process_hunting(app_type, hunting_manager_stop_event)
        
        # Check if it's time to track queues
        current_time = time.time()
        if current_time - last_queue_track_time >= queue_track_interval:
            logger.info("[HUNTING] Running queue tracking cycle")
            processor_manager.process_queue_tracking(hunting_manager_stop_event)
            last_queue_track_time = current_time
        
        logger.info("[HUNTING] === Hunting Manager cycle ended ===")
        hunting_manager_stop_event.wait(30)  # Check every 30 seconds
    
    logger.info("[HUNTING] Hunting Manager background thread stopped.")
