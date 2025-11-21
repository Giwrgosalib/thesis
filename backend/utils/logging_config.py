"""
Logging configuration for the eBay AI Chatbot backend.
Provides structured logging with proper formatting and handlers.
"""

import logging
import logging.handlers
import os
import sys
from typing import Optional
from datetime import datetime, timezone
import json

class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record):
        """Format log record as JSON."""
        log_entry = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'user_id'):
            log_entry['user_id'] = record.user_id
        if hasattr(record, 'request_id'):
            log_entry['request_id'] = record.request_id
        if hasattr(record, 'ip_address'):
            log_entry['ip_address'] = record.ip_address
        
        return json.dumps(log_entry)

class RequestFormatter(logging.Formatter):
    """Custom formatter for request/response logging."""
    
    def format(self, record):
        """Format request/response log record."""
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        
        if hasattr(record, 'method') and hasattr(record, 'path'):
            # Request log
            return f"{timestamp} - {record.method} {record.path} - {record.getMessage()}"
        elif hasattr(record, 'status_code'):
            # Response log
            return f"{timestamp} - Response {record.status_code} - {record.getMessage()}"
        else:
            # Regular log
            return f"{timestamp} - {record.levelname} - {record.getMessage()}"

def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    max_file_size: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    use_json: bool = False
) -> None:
    """
    Set up logging configuration for the application.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
        max_file_size: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
        use_json: Whether to use JSON formatting
    """
    # Create logs directory if it doesn't exist
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))
    
    if use_json:
        console_formatter = JSONFormatter()
    else:
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_file_size,
            backupCount=backup_count
        )
        file_handler.setLevel(getattr(logging, level.upper()))
        
        if use_json:
            file_formatter = JSONFormatter()
        else:
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # Set specific logger levels
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('pymongo').setLevel(logging.WARNING)
    
    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured - Level: {level}, File: {log_file or 'None'}")

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)

def log_request(logger: logging.Logger, request, **kwargs):
    """
    Log an incoming request.
    
    Args:
        logger: Logger instance
        request: Flask request object
        **kwargs: Additional fields to log
    """
    extra = {
        'method': request.method,
        'path': request.path,
        'ip_address': request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr),
        'user_agent': request.headers.get('User-Agent', 'Unknown')
    }
    extra.update(kwargs)
    
    logger.info(f"Request: {request.method} {request.path}", extra=extra)

def log_response(logger: logging.Logger, status_code: int, **kwargs):
    """
    Log a response.
    
    Args:
        logger: Logger instance
        status_code: HTTP status code
        **kwargs: Additional fields to log
    """
    extra = {
        'status_code': status_code
    }
    extra.update(kwargs)
    
    logger.info(f"Response: {status_code}", extra=extra)

def log_error(logger: logging.Logger, error: Exception, **kwargs):
    """
    Log an error with full context.
    
    Args:
        logger: Logger instance
        error: Exception object
        **kwargs: Additional fields to log
    """
    extra = kwargs.copy()
    logger.error(f"Error: {str(error)}", exc_info=True, extra=extra)

def log_performance(logger: logging.Logger, operation: str, duration: float, **kwargs):
    """
    Log performance metrics.
    
    Args:
        logger: Logger instance
        operation: Operation name
        duration: Duration in seconds
        **kwargs: Additional fields to log
    """
    extra = {
        'operation': operation,
        'duration': duration
    }
    extra.update(kwargs)
    
    logger.info(f"Performance: {operation} took {duration:.3f}s", extra=extra)

class RequestContextFilter(logging.Filter):
    """Filter to add request context to log records."""
    
    def filter(self, record):
        """Add request context to log record."""
        from flask import g, request
        
        # Add request ID if available
        if hasattr(g, 'request_id'):
            record.request_id = g.request_id
        
        # Add user ID if available
        if hasattr(g, 'user_id'):
            record.user_id = g.user_id
        
        # Add IP address
        record.ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        
        return True
