import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# Configure standard logger for RAG app
logger = logging.getLogger("rag_app")
logger.setLevel(logging.INFO)

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")

# Add handlers if not already present (guarded so uvicorn --reload doesn't duplicate them)
if not logger.handlers:
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        file_handler = RotatingFileHandler(
            os.path.join(_LOG_DIR, "rag_pro.log"),
            maxBytes=5 * 1024 * 1024,  # 5 MB per file
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as e:
        # Logging must never crash the app — fall back to console-only if the
        # log directory can't be created/written (e.g. read-only filesystem).
        logger.warning(f"Could not set up file logging at '{_LOG_DIR}': {e}")
