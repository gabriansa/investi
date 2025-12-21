import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from src.utils.dates import format_timestamp


class UTCFormatter(logging.Formatter):
    """Custom formatter that uses UTC timezone for timestamps."""
    
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        if datefmt:
            return dt.strftime(datefmt)
        return format_timestamp(dt)


class TelegramNetworkFilter(logging.Filter):
    """Filter to simplify telegram network error logging."""
    
    def filter(self, record):
        # Check if this is a telegram network error during polling
        if record.name.startswith('telegram') and record.levelno == logging.ERROR:
            msg = str(record.msg)
            # Simplify transient network errors
            if 'polling for updates' in msg.lower() or 'NetworkError' in str(record.exc_info):
                # Strip the full traceback for transient network errors
                if record.exc_info:
                    # Keep the error but remove exc_info to prevent traceback
                    record.exc_text = None
                    record.exc_info = None
                    # Make the message more concise
                    if 'Temporary failure in name resolution' in msg:
                        record.msg = "Temporary network failure while polling (DNS resolution failed) - will retry"
                    elif 'ConnectError' in msg or 'NetworkError' in msg:
                        record.msg = "Network error while polling for updates - will retry"
        return True


def setup_logger():
    """Configure logging with UTC timestamps."""
    # Create logs directory if it doesn't exist
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # Root logger configuration
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Clear any existing handlers
    logger.handlers = []
    
    # UTC formatter
    formatter = UTCFormatter(
        fmt='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S %Z'
    )
    
    # Create network filter for cleaner telegram logs
    network_filter = TelegramNetworkFilter()
    
    # File handler for general logs
    file_handler = logging.FileHandler('logs/bot-output.log')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(network_filter)
    logger.addHandler(file_handler)
    
    # File handler for errors
    error_handler = logging.FileHandler('logs/bot-errors.log')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    error_handler.addFilter(network_filter)
    logger.addHandler(error_handler)
    
    # Console handler only if stdout is a terminal (not redirected by systemd)
    # This prevents double logging when systemd captures stdout to the log file
    if sys.stdout.isatty():
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        console_handler.addFilter(network_filter)
        logger.addHandler(console_handler)
    
    # Silence noisy third-party loggers
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)
    
    return logger
