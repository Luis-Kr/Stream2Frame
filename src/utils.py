import logging 
from pathlib import Path
import hydra
from hydra import compose, initialize
from omegaconf import DictConfig
from typing import List, Tuple

formatter = logging.Formatter('%(asctime)s - Module(%(module)s):Line(%(lineno)d) %(levelname)s - %(message)s')

def check_path(inp_path: str) -> None:
    
    # Create a Path object from the input path
    inp_path_obj = Path(inp_path)
    
    # Check if the path exists
    if not inp_path_obj.exists():
        # If not, create the directories in the path
        inp_path_obj.mkdir(parents=True)
        

def logger_setup(name: str, log_file: Path, level: int = logging.INFO) -> logging.Logger:
    
    # Check if the parent directory of the log file exists, create it if not
    check_path(log_file.parent)

    # Create a file handler for writing log messages to a file
    handler = logging.FileHandler(log_file, mode='a')        
    handler.setFormatter(formatter)

    # Get a logger with the specified name
    logger = logging.getLogger(name)
    
    # Set the logging level for the logger
    logger.setLevel(level)
    logger.addHandler(handler)

    return logger


def clear_hydra_cache() -> None:
    """Clear the Hydra config cache."""
    hydra.core.global_hydra.GlobalHydra.instance().clear()
    

def log_separator(logger: logging.Logger) -> None:
    """Log separator lines to the provided logger."""
    separator = "--------------------------------------------------"
    logger.info(separator)
    logger.info(separator)
    
    
