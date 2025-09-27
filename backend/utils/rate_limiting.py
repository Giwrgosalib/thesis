"""
Rate limiting utilities for the eBay AI Chatbot backend.
Provides decorators and functions for implementing rate limiting.
"""

import time
import logging
from functools import wraps
from typing import Dict, Optional, Callable
from flask import request, jsonify, g
from collections import defaultdict, deque
import threading

logger = logging.getLogger(__name__)

class RateLimiter:
    """Simple in-memory rate limiter using sliding window algorithm."""
    
    def __init__(self):
        self._requests: Dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()
    
    def is_allowed(
        self,
        key: str,
        limit: int,
        window: int,
        current_time: Optional[float] = None
    ) -> bool:
        """
        Check if a request is allowed based on rate limit.
        
        Args:
            key: Unique identifier for the rate limit (e.g., IP address)
            limit: Maximum number of requests allowed
            window: Time window in seconds
            current_time: Current timestamp (for testing)
            
        Returns:
            True if request is allowed, False otherwise
        """
        if current_time is None:
            current_time = time.time()
        
        with self._lock:
            # Clean old requests outside the window
            cutoff_time = current_time - window
            request_times = self._requests[key]
            
            # Remove requests outside the window
            while request_times and request_times[0] <= cutoff_time:
                request_times.popleft()
            
            # Check if we're under the limit
            if len(request_times) < limit:
                request_times.append(current_time)
                return True
            
            return False
    
    def get_remaining_requests(
        self,
        key: str,
        limit: int,
        window: int,
        current_time: Optional[float] = None
    ) -> int:
        """
        Get the number of remaining requests for a key.
        
        Args:
            key: Unique identifier for the rate limit
            limit: Maximum number of requests allowed
            window: Time window in seconds
            current_time: Current timestamp (for testing)
            
        Returns:
            Number of remaining requests
        """
        if current_time is None:
            current_time = time.time()
        
        with self._lock:
            # Clean old requests outside the window
            cutoff_time = current_time - window
            request_times = self._requests[key]
            
            # Remove requests outside the window
            while request_times and request_times[0] <= cutoff_time:
                request_times.popleft()
            
            return max(0, limit - len(request_times))
    
    def get_reset_time(
        self,
        key: str,
        window: int,
        current_time: Optional[float] = None
    ) -> float:
        """
        Get the time when the rate limit will reset.
        
        Args:
            key: Unique identifier for the rate limit
            window: Time window in seconds
            current_time: Current timestamp (for testing)
            
        Returns:
            Timestamp when the rate limit resets
        """
        if current_time is None:
            current_time = time.time()
        
        with self._lock:
            request_times = self._requests[key]
            
            if not request_times:
                return current_time
            
            # Return the time when the oldest request will expire
            return request_times[0] + window

# Constants
RATE_LIMIT_EXCEEDED_MESSAGE = "Rate limit exceeded"

# Global rate limiter instance
rate_limiter = RateLimiter()

def rate_limit(
    limit: int = 60,
    window: int = 60,
    key_func: Optional[Callable] = None,
    per_method: bool = False
):
    """
    Decorator to apply rate limiting to a route.
    
    Args:
        limit: Maximum number of requests allowed
        window: Time window in seconds
        key_func: Function to generate rate limit key (defaults to IP address)
        per_method: Whether to apply rate limit per HTTP method
        
    Returns:
        Decorated function with rate limiting
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Generate rate limit key
            if key_func:
                key = key_func()
            else:
                key = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
                if ',' in key:
                    key = key.split(',')[0].strip()
            
            # Add method to key if per_method is True
            if per_method:
                key = f"{key}:{request.method}"
            
            # Check rate limit
            if not rate_limiter.is_allowed(key, limit, window):
                remaining = rate_limiter.get_remaining_requests(key, limit, window)
                reset_time = rate_limiter.get_reset_time(key, window)
                
                logger.warning(
                    f"Rate limit exceeded for {key}",
                    extra={
                        'ip_address': key,
                        'limit': limit,
                        'window': window,
                        'remaining': remaining,
                        'reset_time': reset_time,
                        'path': request.path,
                        'method': request.method
                    }
                )
                
                return jsonify({
                    'error': RATE_LIMIT_EXCEEDED_MESSAGE,
                    'code': 'RATE_LIMIT_EXCEEDED',
                    'details': {
                        'limit': limit,
                        'window': window,
                        'remaining': remaining,
                        'reset_time': reset_time
                    }
                }), 429
            
            # Add rate limit info to response headers
            remaining = rate_limiter.get_remaining_requests(key, limit, window)
            reset_time = rate_limiter.get_reset_time(key, window)
            
            response = f(*args, **kwargs)
            
            # Add rate limit headers to response
            if isinstance(response, tuple):
                response_obj, status_code = response
                response_obj.headers['X-RateLimit-Limit'] = str(limit)
                response_obj.headers['X-RateLimit-Remaining'] = str(remaining)
                response_obj.headers['X-RateLimit-Reset'] = str(int(reset_time))
                return response_obj, status_code
            else:
                response.headers['X-RateLimit-Limit'] = str(limit)
                response.headers['X-RateLimit-Remaining'] = str(remaining)
                response.headers['X-RateLimit-Reset'] = str(int(reset_time))
                return response
            
        return decorated_function
    return decorator

def rate_limit_by_user(
    limit: int = 100,
    window: int = 60
):
    """
    Decorator to apply rate limiting by user ID.
    
    Args:
        limit: Maximum number of requests allowed
        window: Time window in seconds
        
    Returns:
        Decorated function with user-based rate limiting
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get user ID from request context
            user_id = getattr(g, 'user_id', None)
            if not user_id:
                # Fall back to IP address if no user ID
                key = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
                if ',' in key:
                    key = key.split(',')[0].strip()
            else:
                key = f"user:{user_id}"
            
            # Check rate limit
            if not rate_limiter.is_allowed(key, limit, window):
                remaining = rate_limiter.get_remaining_requests(key, limit, window)
                reset_time = rate_limiter.get_reset_time(key, window)
                
                logger.warning(
                    f"User rate limit exceeded for {key}",
                    extra={
                        'user_id': user_id,
                        'ip_address': request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr),
                        'limit': limit,
                        'window': window,
                        'remaining': remaining,
                        'reset_time': reset_time,
                        'path': request.path,
                        'method': request.method
                    }
                )
                
                return jsonify({
                    'error': RATE_LIMIT_EXCEEDED_MESSAGE,
                    'code': 'RATE_LIMIT_EXCEEDED',
                    'details': {
                        'limit': limit,
                        'window': window,
                        'remaining': remaining,
                        'reset_time': reset_time
                    }
                }), 429
            
            # Add rate limit info to response headers
            remaining = rate_limiter.get_remaining_requests(key, limit, window)
            reset_time = rate_limiter.get_reset_time(key, window)
            
            response = f(*args, **kwargs)
            
            # Add rate limit headers to response
            if isinstance(response, tuple):
                response_obj, status_code = response
                response_obj.headers['X-RateLimit-Limit'] = str(limit)
                response_obj.headers['X-RateLimit-Remaining'] = str(remaining)
                response_obj.headers['X-RateLimit-Reset'] = str(int(reset_time))
                return response_obj, status_code
            else:
                response.headers['X-RateLimit-Limit'] = str(limit)
                response.headers['X-RateLimit-Remaining'] = str(remaining)
                response.headers['X-RateLimit-Reset'] = str(int(reset_time))
                return response
            
        return decorated_function
    return decorator

def rate_limit_by_endpoint(
    limit: int = 30,
    window: int = 60
):
    """
    Decorator to apply rate limiting by endpoint.
    
    Args:
        limit: Maximum number of requests allowed
        window: Time window in seconds
        
    Returns:
        Decorated function with endpoint-based rate limiting
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Generate key based on endpoint and IP
            ip_address = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
            if ',' in ip_address:
                ip_address = ip_address.split(',')[0].strip()
            
            key = f"endpoint:{request.endpoint}:{ip_address}"
            
            # Check rate limit
            if not rate_limiter.is_allowed(key, limit, window):
                remaining = rate_limiter.get_remaining_requests(key, limit, window)
                reset_time = rate_limiter.get_reset_time(key, window)
                
                logger.warning(
                    f"Endpoint rate limit exceeded for {key}",
                    extra={
                        'endpoint': request.endpoint,
                        'ip_address': ip_address,
                        'limit': limit,
                        'window': window,
                        'remaining': remaining,
                        'reset_time': reset_time,
                        'path': request.path,
                        'method': request.method
                    }
                )
                
                return jsonify({
                    'error': RATE_LIMIT_EXCEEDED_MESSAGE,
                    'code': 'RATE_LIMIT_EXCEEDED',
                    'details': {
                        'limit': limit,
                        'window': window,
                        'remaining': remaining,
                        'reset_time': reset_time
                    }
                }), 429
            
            # Add rate limit info to response headers
            remaining = rate_limiter.get_remaining_requests(key, limit, window)
            reset_time = rate_limiter.get_reset_time(key, window)
            
            response = f(*args, **kwargs)
            
            # Add rate limit headers to response
            if isinstance(response, tuple):
                response_obj, status_code = response
                response_obj.headers['X-RateLimit-Limit'] = str(limit)
                response_obj.headers['X-RateLimit-Remaining'] = str(remaining)
                response_obj.headers['X-RateLimit-Reset'] = str(int(reset_time))
                return response_obj, status_code
            else:
                response.headers['X-RateLimit-Limit'] = str(limit)
                response.headers['X-RateLimit-Remaining'] = str(remaining)
                response.headers['X-RateLimit-Reset'] = str(int(reset_time))
                return response
            
        return decorated_function
    return decorator

def get_rate_limit_status(key: str, limit: int, window: int) -> Dict[str, any]:
    """
    Get the current rate limit status for a key.
    
    Args:
        key: Rate limit key
        limit: Maximum number of requests allowed
        window: Time window in seconds
        
    Returns:
        Dictionary with rate limit status information
    """
    remaining = rate_limiter.get_remaining_requests(key, limit, window)
    reset_time = rate_limiter.get_reset_time(key, window)
    
    return {
        'limit': limit,
        'remaining': remaining,
        'reset_time': reset_time,
        'window': window
    }
