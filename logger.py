import logging

def setup_logger():
    """Configure and return the application logger"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)

# Create a logger instance for importing by other modules
logger = setup_logger()