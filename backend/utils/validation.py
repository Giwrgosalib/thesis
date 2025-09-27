"""
Input validation utilities for the eBay AI Chatbot backend.
Provides decorators and functions for validating user inputs and API requests.
"""

import re
import logging
from functools import wraps
from typing import Any, Dict, List, Optional, Union, Callable
from flask import request, jsonify, current_app
from marshmallow import Schema, fields, ValidationError, validate
from marshmallow.decorators import post_load

logger = logging.getLogger(__name__)

class SearchRequestSchema(Schema):
    """Schema for validating search requests."""
    query = fields.Str(
        required=True,
        validate=[
            validate.Length(min=1, max=500, error="Query must be between 1 and 500 characters"),
            validate.Regexp(r'^[a-zA-Z0-9\s\-_.,!?@#$%&*()+=:;"\'<>/\\|`~]+$', 
                          error="Query contains invalid characters")
        ],
        error_messages={
            'required': 'Query is required',
            'null': 'Query cannot be null'
        }
    )
    
    @post_load
    def sanitize_query(self, data, **kwargs):
        """Sanitize the query by removing extra whitespace and normalizing."""
        if 'query' in data:
            # Remove extra whitespace and normalize
            data['query'] = ' '.join(data['query'].strip().split())
        return data

class AuthRequestSchema(Schema):
    """Schema for validating authentication requests."""
    session_id = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=255),
        error_messages={
            'required': 'Session ID is required',
            'null': 'Session ID cannot be null'
        }
    )

class ClientIdSchema(Schema):
    """Schema for validating client ID parameters."""
    client_id = fields.Str(
        required=True,
        validate=[
            validate.Length(min=1, max=100),
            validate.Regexp(r'^[a-zA-Z0-9_\-]+$', error="Client ID contains invalid characters")
        ],
        error_messages={
            'required': 'Client ID is required',
            'null': 'Client ID cannot be null'
        }
    )

def validate_json_request(schema_class: Schema) -> Callable:
    """
    Decorator to validate JSON request data against a schema.
    
    Args:
        schema_class: Marshmallow schema class to validate against
        
    Returns:
        Decorated function with validation
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # Check if request has JSON data
                if not request.is_json:
                    return jsonify({
                        'error': 'Request must be JSON',
                        'code': 'INVALID_CONTENT_TYPE'
                    }), 400
                
                # Get JSON data
                json_data = request.get_json()
                if json_data is None:
                    return jsonify({
                        'error': 'Request body is empty or invalid JSON',
                        'code': 'INVALID_JSON'
                    }), 400
                
                # Validate against schema
                schema = schema_class()
                validated_data = schema.load(json_data)
                
                # Add validated data to kwargs
                kwargs['validated_data'] = validated_data
                
                return f(*args, **kwargs)
                
            except ValidationError as e:
                logger.warning(f"Validation error in {f.__name__}: {e.messages}")
                return jsonify({
                    'error': 'Validation failed',
                    'details': e.messages,
                    'code': 'VALIDATION_ERROR'
                }), 400
                
            except Exception as e:
                logger.error(f"Unexpected error in validation for {f.__name__}: {str(e)}")
                return jsonify({
                    'error': 'Internal validation error',
                    'code': 'INTERNAL_ERROR'
                }), 500
                
        return decorated_function
    return decorator

def validate_query_params(schema_class: Schema) -> Callable:
    """
    Decorator to validate query parameters against a schema.
    
    Args:
        schema_class: Marshmallow schema class to validate against
        
    Returns:
        Decorated function with validation
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                # Get query parameters
                query_params = request.args.to_dict()
                
                # Validate against schema
                schema = schema_class()
                validated_data = schema.load(query_params)
                
                # Add validated data to kwargs
                kwargs['validated_data'] = validated_data
                
                return f(*args, **kwargs)
                
            except ValidationError as e:
                logger.warning(f"Query parameter validation error in {f.__name__}: {e.messages}")
                return jsonify({
                    'error': 'Invalid query parameters',
                    'details': e.messages,
                    'code': 'INVALID_QUERY_PARAMS'
                }), 400
                
            except Exception as e:
                logger.error(f"Unexpected error in query validation for {f.__name__}: {str(e)}")
                return jsonify({
                    'error': 'Internal validation error',
                    'code': 'INTERNAL_ERROR'
                }), 500
                
        return decorated_function
    return decorator

def sanitize_string(text: str, max_length: int = 1000) -> str:
    """
    Sanitize a string by removing potentially dangerous characters and limiting length.
    
    Args:
        text: Input string to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized string
    """
    if not isinstance(text, str):
        return ""
    
    # Remove null bytes and control characters
    text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
    
    # Limit length
    text = text[:max_length]
    
    # Remove extra whitespace
    text = ' '.join(text.strip().split())
    
    return text

def validate_user_id(user_id: str) -> bool:
    """
    Validate user ID format.
    
    Args:
        user_id: User ID to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(user_id, str):
        return False
    
    # Check length and format
    if len(user_id) < 1 or len(user_id) > 100:
        return False
    
    # Check for valid characters (alphanumeric, underscore, hyphen)
    if not re.match(r'^[a-zA-Z0-9_\-]+$', user_id):
        return False
    
    return True

def validate_session_token(token: str) -> bool:
    """
    Validate session token format.
    
    Args:
        token: Session token to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(token, str):
        return False
    
    # Check length (SHA256 hash should be 64 characters)
    if len(token) != 64:
        return False
    
    # Check for valid hex characters
    if not re.match(r'^[a-f0-9]+$', token):
        return False
    
    return True

def validate_price_range(price_range: Union[str, List]) -> bool:
    """
    Validate price range format.
    
    Args:
        price_range: Price range to validate
        
    Returns:
        True if valid, False otherwise
    """
    if isinstance(price_range, list):
        if len(price_range) != 2:
            return False
        
        min_price, max_price = price_range
        
        # Check if both are numbers or None
        if min_price is not None and not isinstance(min_price, (int, float)):
            return False
        if max_price is not None and not isinstance(max_price, (int, float)):
            return False
        
        # Check if min <= max
        if min_price is not None and max_price is not None:
            if min_price > max_price:
                return False
        
        return True
    
    elif isinstance(price_range, str):
        # Check for valid price range patterns
        patterns = [
            r'^\d+(\.\d{2})?$',  # Single price
            r'^\d+(\.\d{2})?-\d+(\.\d{2})?$',  # Range
            r'^under\s+\$?\d+(\.\d{2})?$',  # Under
            r'^over\s+\$?\d+(\.\d{2})?$',  # Over
            r'^between\s+\$?\d+(\.\d{2})?\s+and\s+\$?\d+(\.\d{2})?$'  # Between
        ]
        
        return any(re.match(pattern, price_range.lower()) for pattern in patterns)
    
    return False

def validate_entity_data(entities: List[Dict[str, Any]]) -> bool:
    """
    Validate entity data structure.
    
    Args:
        entities: List of entity dictionaries
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(entities, list):
        return False
    
    for entity in entities:
        if not isinstance(entity, dict):
            return False
        
        # Check required fields
        if 'label' not in entity or 'value' not in entity:
            return False
        
        # Check field types
        if not isinstance(entity['label'], str) or not isinstance(entity['value'], str):
            return False
        
        # Check label format
        if not re.match(r'^[A-Z_]+$', entity['label']):
            return False
        
        # Check value length
        if len(entity['value']) > 500:
            return False
    
    return True

def rate_limit_key() -> str:
    """
    Generate a rate limit key based on the request.
    
    Returns:
        Rate limit key string
    """
    # Use IP address as the primary key
    ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    if ',' in ip_address:
        ip_address = ip_address.split(',')[0].strip()
    
    return f"rate_limit:{ip_address}"

def validate_request_size() -> bool:
    """
    Validate that the request size is within limits.
    
    Returns:
        True if within limits, False otherwise
    """
    content_length = request.content_length
    if content_length is None:
        return True
    
    max_size = current_app.config.get('MAX_REQUEST_SIZE', 16 * 1024 * 1024)  # 16MB default
    return content_length <= max_size

def _extract_bearer_token(auth_header: str) -> Optional[str]:
    """Extract token from Bearer authorization header."""
    if not auth_header.startswith('Bearer '):
        return None
    return auth_header[7:]  # Remove 'Bearer ' prefix

def validate_authorization_header() -> Optional[str]:
    """
    Validate and extract token from Authorization header.
    
    Returns:
        Token string if valid, None otherwise
    """
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return None
    
    token = _extract_bearer_token(auth_header)
    if not token:
        return None
    
    # Validate token format
    if not validate_session_token(token):
        return None
    
    return token
