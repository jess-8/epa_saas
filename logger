##########
# Logger
##########

import logging
import os

# Ensure the log file is created
file_path = "app.log"
if not os.path.exists(file_path):
    with open(file_path, "w") as f:
        pass

# Create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Set the minimum logging level for the logger

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)  # Set the logging level for the console handler

# Create file handler
file_handler = logging.FileHandler("app.log", mode='w', encoding="utf-8")
file_handler.setLevel(logging.DEBUG)  # Set the logging level for the file handler

# Create formatter and add it to handlers
formatter = logging.Formatter(
    "{asctime} - {levelname} - {message}",
    style="{",
    datefmt="%Y-%m-%d %H:%M",
)
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

# Add handlers to the logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)
