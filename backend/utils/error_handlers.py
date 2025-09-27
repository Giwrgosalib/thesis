"""
Error handling utilities for the eBay AI Chatbot backend.
Provides custom error classes and handlers for better error management.
"""

import logging
from typing import Dict, Any, Optional
from flask import jsonify, request, current_app
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)

class APIError(Exception):
    """Base class for API errors."""
    
    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}

class ValidationError(APIError):
    """Error for validation failures."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            status_code=400,
            error_code="VALIDATION_ERROR",
            details=details
        )

class AuthenticationError(APIError):
    """Error for authentication failures."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            status_code=401,
            error_code="AUTHENTICATION_ERROR"
        )

class AuthorizationError(APIError):
    """Error for authorization failures."""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(
            message=message,
            status_code=403,
            error_code="AUTHORIZATION_ERROR"
        )

class NotFoundError(APIError):
    """Error for resource not found."""
    
    def __init__(self, message: str = "Resource not found"):
        super().__init__(
            message=message,
            status_code=404,
            error_code="NOT_FOUND"
        )

class RateLimitError(APIError):
    """Error for rate limit exceeded."""
    
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED"
        )

class ExternalServiceError(APIError):
    """Error for external service failures."""
    
    def __init__(self, service: str, message: str = "External service error"):
        super().__init__(
            message=f"{service}: {message}",
            status_code=502,
            error_code="EXTERNAL_SERVICE_ERROR",
            details={"service": service}
        )

class ModelError(APIError):
    """Error for ML model failures."""
    
    def __init__(self, message: str = "Model error"):
        super().__init__(
            message=message,
            status_code=500,
            error_code="MODEL_ERROR"
        )

class DatabaseError(APIError):
    """Error for database failures."""
    
    def __init__(self, message: str = "Database error"):
        super().__init__(
            message=message,
            status_code=500,
            error_code="DATABASE_ERROR"
        )

def register_error_handlers(app):
    """Register error handlers for the Flask application."""
    
    @app.errorhandler(APIError)
    def handle_api_error(error: APIError):
        """Handle custom API errors."""
        logger.warning(
            f"API Error: {error.error_code} - {error.message}",
            extra={
                'error_code': error.error_code,
                'status_code': error.status_code,
                'details': error.details,
                'path': request.path,
                'method': request.method
            }
        )
        
        response = {
            'error': error.message,
            'code': error.error_code
        }
        
        if error.details:
            response['details'] = error.details
        
        return jsonify(response), error.status_code
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        """Handle HTTP exceptions."""
        logger.warning(
            f"HTTP Error: {error.code} - {error.description}",
            extra={
                'status_code': error.code,
                'path': request.path,
                'method': request.method
            }
        )
        
        return jsonify({
            'error': error.description,
            'code': f'HTTP_{error.code}'
        }), error.code
    
    @app.errorhandler(ValidationError)
    def handle_validation_error(error: ValidationError):
        """Handle validation errors."""
        logger.warning(
            f"Validation Error: {error.message}",
            extra={
                'error_code': error.error_code,
                'details': error.details,
                'path': request.path,
                'method': request.method
            }
        )
        
        response = {
            'error': error.message,
            'code': error.error_code
        }
        
        if error.details:
            response['details'] = error.details
        
        return jsonify(response), error.status_code
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        """Handle unexpected errors."""
        logger.error(
            f"Unexpected Error: {str(error)}",
            exc_info=True,
            extra={
                'path': request.path,
                'method': request.method
            }
        )
        
        # Don't expose internal errors in production
        if current_app.config.get('DEBUG', False):
            message = str(error)
        else:
            message = "An unexpected error occurred"
        
        return jsonify({
            'error': message,
            'code': 'INTERNAL_ERROR'
        }), 500

def handle_database_error(error: Exception) -> DatabaseError:
    """Convert database errors to API errors."""
    error_message = str(error)
    
    # Check for specific MongoDB errors
    if "connection" in error_message.lower():
        return DatabaseError("Database connection failed")
    elif "timeout" in error_message.lower():
        return DatabaseError("Database operation timed out")
    elif "duplicate" in error_message.lower():
        return DatabaseError("Duplicate entry found")
    else:
        return DatabaseError("Database operation failed")

def handle_external_api_error(error: Exception, service: str) -> ExternalServiceError:
    """Convert external API errors to API errors."""
    error_message = str(error)
    
    # Check for specific HTTP errors
    if "timeout" in error_message.lower():
        return ExternalServiceError(service, "Request timed out")
    elif "connection" in error_message.lower():
        return ExternalServiceError(service, "Connection failed")
    elif "unauthorized" in error_message.lower():
        return ExternalServiceError(service, "Authentication failed")
    elif "forbidden" in error_message.lower():
        return ExternalServiceError(service, "Access denied")
    else:
        return ExternalServiceError(service, "Service unavailable")

def handle_model_error(error: Exception) -> ModelError:
    """Convert model errors to API errors."""
    error_message = str(error)
    
    # Check for specific model errors
    if "cuda" in error_message.lower() or "gpu" in error_message.lower():
        return ModelError("GPU processing error")
    elif "memory" in error_message.lower():
        return ModelError("Insufficient memory for model processing")
    elif "model" in error_message.lower() and "not found" in error_message.lower():
        return ModelError("Model file not found")
    else:
        return ModelError("Model processing failed")

def create_error_response(
    message: str,
    status_code: int = 500,
    error_code: str = "INTERNAL_ERROR",
    details: Optional[Dict[str, Any]] = None
) -> tuple:
    """Create a standardized error response."""
    response = {
        'error': message,
        'code': error_code
    }
    
    if details:
        response['details'] = details
    
    return jsonify(response), status_code

def log_and_raise(error: Exception, logger: logging.Logger, **context):
    """Log an error and raise it as an API error."""
    logger.error(f"Error: {str(error)}", exc_info=True, extra=context)
    
    if isinstance(error, APIError):
        raise error
    else:
        raise APIError(str(error))
