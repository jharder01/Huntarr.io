# Application-specific hunting processors have been moved to dedicated modules
# These can be found in the src/primary/background_processors/ directory
# Each application (Radarr, Sonarr, etc.) now has its own processor class that
# handles all API interactions, history tracking, and queue monitoring.
# The ProcessorManager coordinates these processors to maintain modularity and scalability.
