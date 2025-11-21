from flask import Flask, request, jsonify, redirect, make_response, send_from_directory, g
from flask_cors import CORS
import requests
import logging
import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
import time
from metrics import analyze_feedback_data, analyze_user_preferences, analyze_training_dataset
from urllib.parse import quote_plus, urljoin
import sys
import json
from datetime import datetime, timedelta
import random
import uuid
import re

from typing import Any, Callable, Dict, Optional

# Import new utilities
from config import get_config
from utils.logging_config import setup_logging, get_logger, log_request, log_response, log_error
from utils.error_handlers import (
    register_error_handlers, APIError, ValidationError, AuthenticationError,
    AuthorizationError, NotFoundError, RateLimitError, ExternalServiceError,
    ModelError, DatabaseError, handle_database_error, handle_external_api_error,
    handle_model_error
)
from utils.rate_limiting import rate_limit, rate_limit_by_user, rate_limit_by_endpoint
from utils.validation import (
    validate_query_params,
    AuthRequestSchema,
    ClientIdSchema,
    sanitize_string,
    validate_user_id,
    validate_session_token,
)

# Add the library's parent directory to sys.path to find the oauthclient module
# Assuming app.py is in 'backend' and 'ebay-oauth-python-client' is also in 'backend'
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)  # Adds 'backend' to path

repo_root = os.path.dirname(backend_dir)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

# Optional next-gen experimental API
NEXTGEN_IMPORT_ERROR = None
try:
    from backend_nextgen.api.experimental import (  # type: ignore
        blueprint as nextgen_ai_blueprint,
        configure_preference_loader,
        configure_preference_writer,
    )
except Exception as exc:  # noqa: BLE001
    nextgen_ai_blueprint = None
    NEXTGEN_IMPORT_ERROR = exc
    configure_preference_writer = None
    configure_preference_loader = None

# Now you can import from the library
from ebay_oauth_python_client.oauthclient.oauth2api import oauth2api  # Import for the client instance
from ebay_oauth_python_client.oauthclient.model.model import environment, oAuth_token
from ebay_oauth_python_client.oauthclient.credentialutil import credentialutil
from ebay_oauth_python_client.oauthclient.model.model import credentials as EbayOauthCredentials

# Initialize configuration
config = get_config()

# Initialize Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = config.app.max_request_size

# Setup CORS
CORS(app, origins=[config.app.frontend_url], supports_credentials=True)

# Setup logging
setup_logging(
    level=config.logging.level,
    log_file=config.logging.file_path,
    max_file_size=config.logging.max_file_size,
    backup_count=config.logging.backup_count
)

logger = get_logger(__name__)

# Register error handlers
register_error_handlers(app)

# Register experimental next-gen blueprint if available
if nextgen_ai_blueprint is not None:
    app.register_blueprint(nextgen_ai_blueprint)
    logger.info("Registered next-gen experimental API blueprint at /api/nextgen")
else:
    message = "Next-gen experimental API unavailable (optional dependencies missing)."
    if NEXTGEN_IMPORT_ERROR:
        message += f" Details: {NEXTGEN_IMPORT_ERROR}"
    logger.warning(message)

# --- Configuration Variables ---
EBAY_CALLBACK_PATH = "/auth/ebay-callback"
YOUR_APPLICATION_CALLBACK_URL = urljoin(config.app.app_base_url, EBAY_CALLBACK_PATH)
FRONTEND_BUILD_DIR = os.path.join('..', 'frontend', 'dist')
FRONTEND_URL = config.app.frontend_url
EBAY_ENVIRONMENT = environment.SANDBOX if config.ebay.environment == "SANDBOX" else environment.PRODUCTION
SESSION_EXPIRY = 3600  # 1 hour

# Store active session tokens (for backward compatibility)
SESSION_TOKENS = {}

# --- Setup Data Directory ---
os.makedirs('data', exist_ok=True)

# --- Initialize MongoDB Connection ---
mongo_client = None
db = None
preferences_collection = None
auth_sessions_collection = None

try:
    mongo_client = MongoClient(
        config.database.mongo_uri,
        serverSelectionTimeoutMS=config.database.connection_timeout,
        maxPoolSize=config.database.max_pool_size
    )
    # Test connection
    mongo_client.admin.command('ismaster')
    db = mongo_client[config.database.db_name]
    preferences_collection = db[config.database.pref_collection]
    auth_sessions_collection = db[config.database.session_collection]
    
    logger.info(f"Successfully connected to MongoDB. Database: '{config.database.db_name}'")
except ConnectionFailure as e:
    logger.error(f"MongoDB connection failed: {e}")
    raise DatabaseError("Database connection failed")
except Exception as e:
    logger.error(f"MongoDB initialization error: {e}", exc_info=True)
    raise DatabaseError("Database initialization failed")

# Initialize eBay OAuth client
ebay_oauth_client = oauth2api()

# Create eBay OAuth configuration
ebay_config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ebay_config')
os.makedirs(ebay_config_dir, exist_ok=True)

ebay_config_path = os.path.join(ebay_config_dir, 'ebay-credentials.yaml')

# Create a YAML config file with the structure the library expects
ebay_config_content = {
    environment.SANDBOX.config_id: {
        'appid': config.ebay.client_id,
        'certid': config.ebay.client_secret,
        'devid': config.ebay.dev_id,
        'redirecturi': config.ebay.runame
    },
    environment.PRODUCTION.config_id: {
        'appid': config.ebay.client_id,
        'certid': config.ebay.client_secret,
        'devid': config.ebay.dev_id,
        'redirecturi': config.ebay.runame
    }
}

# Write the config file
try:
    import yaml
    with open(ebay_config_path, 'w') as f:
        yaml.dump(ebay_config_content, f)
    logger.info(f"Created eBay credentials config file at: {ebay_config_path}")
    
    # Load the credentials into the library
    credentialutil.load(ebay_config_path)
    logger.info(f"Successfully loaded eBay credentials for environments: {list(ebay_config_content.keys())}")
except Exception as e:
    logger.error(f"Failed to create or load eBay credentials: {e}", exc_info=True)
    raise ExternalServiceError("eBay", "Failed to initialize OAuth credentials")

# --- Preference Persistence for Next-Gen ---
def persist_preferences(user_id: str, preference_payload: Dict[str, Any]) -> None:
    """Persist structured preference signals for authenticated users."""
    if not preferences_collection or not user_id:
        return

    try:
        entities_section = preference_payload.get("entities") or {}
        entity_buckets = entities_section.get("entities") or entities_section

        def _clean(values: Optional[Any]) -> list[str]:
            cleaned: list[str] = []
            if not values:
                return cleaned
            iterable = values if isinstance(values, (list, tuple, set)) else [values]
            for value in iterable:
                if value is None:
                    continue
                text = sanitize_string(str(value))
                if text:
                    cleaned.append(text)
            return cleaned

        brand_values = _clean(entity_buckets.get("BRAND"))
        category_values = _clean(
            entity_buckets.get("CATEGORY") or entity_buckets.get("PRODUCT_TYPE")
        )
        shipping_values = _clean(entity_buckets.get("SHIPPING"))
        price_values = _clean(entity_buckets.get("PRICE_RANGE"))

        cleaned_query = ""
        if preference_payload.get("query"):
            cleaned_query = sanitize_string(str(preference_payload["query"])) or ""

        entity_snapshot = {
            label: values
            for label in sorted(entity_buckets.keys())
            if (values := _clean(entity_buckets.get(label)))
        }

        search_entry = {
            "query": cleaned_query or preference_payload.get("query", ""),
            "timestamp": datetime.utcnow(),
            "entities": entity_snapshot,
        }

        set_fields: Dict[str, Any] = {
            "updated_at": datetime.utcnow(),
            "authenticated": True,
        }
        if cleaned_query:
            set_fields["last_query"] = cleaned_query
        if preference_payload.get("answer"):
            set_fields["last_answer_excerpt"] = str(preference_payload["answer"])[:256]

        push_fields = {
            "search_history": {
                "$each": [search_entry],
                "$slice": -25,
            }
        }

        add_to_set: Dict[str, Any] = {}
        if brand_values:
            add_to_set["preferred_brands"] = {"$each": brand_values}
        if category_values:
            add_to_set["preferred_categories"] = {"$each": category_values}
        if shipping_values:
            add_to_set["preferred_shipping"] = {"$each": shipping_values}
        if price_values:
            add_to_set["preferred_price_ranges"] = {"$each": price_values}

        update_doc: Dict[str, Any] = {
            "$set": set_fields,
            "$push": push_fields,
            "$setOnInsert": {"created_at": datetime.utcnow()},
        }
        if add_to_set:
            update_doc["$addToSet"] = add_to_set

        preferences_collection.update_one(
            {"user_id": user_id},
            update_doc,
            upsert=True,
        )
    except Exception as exc:
        logger.warning(
            f"Preference persistence failed for user {user_id}: {exc}",
            exc_info=True,
        )


def load_user_preferences(user_id: str) -> Optional[Dict[str, Any]]:
    """Load a concise preference snapshot for downstream personalization."""
    if not preferences_collection or not user_id:
        return None

    try:
        doc = preferences_collection.find_one({"user_id": user_id})
        if not doc:
            return None

        def _extract_list(field: str, limit: int = 5) -> list[str]:
            values = doc.get(field) or []
            cleaned: list[str] = []
            for value in values:
                if value is None:
                    continue
                text = sanitize_string(str(value))
                if text:
                    cleaned.append(text)
                if len(cleaned) >= limit:
                    break
            return cleaned

        history_entries = doc.get("search_history") or []
        recent_history = []
        for entry in history_entries[-5:]:
            query_text = sanitize_string(str(entry.get("query", "")))
            timestamp = entry.get("timestamp")
            if hasattr(timestamp, "isoformat"):
                timestamp_str = timestamp.isoformat()
            else:
                timestamp_str = str(timestamp) if timestamp else ""
            recent_history.append(
                {
                    "query": query_text,
                    "timestamp": timestamp_str,
                    "entities": entry.get("entities", {}),
                }
            )

        snapshot = {
            "brands": _extract_list("preferred_brands"),
            "categories": _extract_list("preferred_categories"),
            "shipping": _extract_list("preferred_shipping"),
            "price_ranges": _extract_list("preferred_price_ranges"),
            "recent_queries": recent_history,
            "updated_at": str(doc.get("updated_at") or ""),
        }
        return snapshot
    except Exception as exc:
        logger.warning(
            f"Preference loader failed for user {user_id}: {exc}",
            exc_info=True,
        )
        return None


if nextgen_ai_blueprint is not None and configure_preference_writer:
    configure_preference_writer(persist_preferences)
    logger.info("Configured preference writer for NextGen AI blueprint.")
if nextgen_ai_blueprint is not None and configure_preference_loader:
    configure_preference_loader(load_user_preferences)
    logger.info("Configured preference loader for NextGen AI blueprint.")

# --- Service Mode ---
logger.info("Legacy NLP pipeline disabled; relying solely on the NextGen AI orchestrator.")

# --- API Endpoints ---
@app.route('/auth/ebay-login', methods=['GET'])
@rate_limit(limit=10, window=60)  # 10 login attempts per minute
def initiate_ebay_login():
    """Initiates the eBay OAuth flow"""
    try:
        # Generate request ID for tracking
        request_id = str(uuid.uuid4())
        g.request_id = request_id
        
        # Log request
        log_request(logger, request, request_id=request_id)
        
        # Get client ID from query parameter
        client_id = request.args.get('client_id')
        
        if not client_id:
            # Generate a client ID if not provided
            client_id = f"client_{int(time.time())}_{random.randint(1000, 9999)}"
        
        # Validate client ID format
        if not re.match(r'^[a-zA-Z0-9_\-]+$', client_id):
            raise ValidationError("Invalid client ID format")
        
        # Store the initial auth request in MongoDB
        current_dt = datetime.utcnow()
        auth_sessions_collection.update_one(
            {'client_id': client_id},
            {
                '$set': {
                    'client_id': client_id,
                    'created_at': current_dt,
                    'is_polling': False,
                    'authenticated': False,
                    'last_poll': current_dt
                }
            },
            upsert=True
        )
        
        # Create an auth URL for eBay with the state parameter
        ebay_environment = environment.SANDBOX if config.ebay.environment == "SANDBOX" else environment.PRODUCTION
        ebay_auth_url = ebay_oauth_client.generate_user_authorization_url(
            env_type=ebay_environment,
            scopes=config.ebay.scopes,
            state=client_id
        )
        
        logger.info(f"eBay OAuth initiated for client: {client_id}")
        return redirect(ebay_auth_url)
        
    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Error initiating eBay login: {e}", exc_info=True)
        raise APIError("Failed to initiate eBay authentication")

@app.route(EBAY_CALLBACK_PATH, methods=['GET'])
def handle_ebay_callback():
    """Handles the callback from eBay"""
    try:
        # Get authorization code and state (our client_id) from query parameters
        code = request.args.get('code')
        client_id = request.args.get('state')
        
        logging.info(f"Callback received for client_id: {client_id}, code: {'present' if code else 'missing'}")

        if not code:
            logging.error(f"Missing authorization code in callback for client_id: {client_id}")
            return redirect(f"{FRONTEND_URL}?error=MissingAuthorizationCode&client_id={client_id if client_id else ''}")
            
        oauth2api_inst = oauth2api()
        token_obj = oauth2api_inst.exchange_code_for_access_token(EBAY_ENVIRONMENT, code) 
        
        if token_obj.error:
            logging.error(f"eBay token exchange error for client_id {client_id}: {token_obj.error}")
            if auth_sessions_collection is not None and client_id:
                auth_sessions_collection.update_one(
                    {'client_id': client_id},
                    {'$set': {'authenticated': False, 'error': f"TokenExchangeFailed: {token_obj.error}", 'updated_at': datetime.utcnow()}}
                )
            return redirect(f"{FRONTEND_URL}?error=TokenExchangeFailed&details={quote_plus(token_obj.error)}&client_id={client_id if client_id else ''}")
        
        access_token = token_obj.access_token
        refresh_token = token_obj.refresh_token
        token_data = getattr(token_obj, 'token_response', {})
            
        user_info = get_ebay_user_info(access_token)
        logging.info(f"eBay user info retrieved: {user_info}")
        user_id = user_info.get('userId') # Or 'userid', check eBay's exact response field
        username = user_info.get('username')
        
        if not user_id:
            logging.error(f"Failed to get user_id from eBay user info for client_id: {client_id}.")
            if auth_sessions_collection is not None and client_id:
                auth_sessions_collection.update_one(
                    {'client_id': client_id},
                    {'$set': {'authenticated': False, 'error': 'UserInfoFailed', 'updated_at': datetime.utcnow()}}
                )
            return redirect(f"{FRONTEND_URL}?error=UserInfoFailed&client_id={client_id if client_id else ''}")
        
        # Store user data and eBay tokens in MongoDB (preferences_collection)
        if preferences_collection is not None:
            preferences_collection.update_one(
                {'user_id': user_id},
                {
                    '$set': {
                        'ebay_username': username,
                        'access_token': access_token,
                        'refresh_token': refresh_token,
                        'token_expiry': datetime.utcnow() + timedelta(seconds=int(token_data.get('expires_in', 7200))),
                        'last_login': datetime.utcnow()
                    }
                },
                upsert=True
            )
        
        # Generate your application's session token
        session_token = generate_session_token(user_id) # Your helper function
        
        # Update the auth_sessions collection for polling
        if auth_sessions_collection is not None and client_id:
            update_result = auth_sessions_collection.update_one(
                {'client_id': client_id},
                {
                    '$set': {
                        'authenticated': True, 
                        'session_token': session_token,
                        'user_id': user_id,
                        'ebay_username': username,
                        'updated_at': datetime.utcnow(),
                        'expires_at': datetime.utcnow() + timedelta(seconds=SESSION_EXPIRY)
                    },
                    '$unset': {'error': ""} 
                }
            )
            if update_result.modified_count > 0 or update_result.upserted_id is not None:
                logging.info(f"Successfully updated auth_sessions for client_id {client_id} with session_token.")
            else:
                logging.warning(f"Did not update auth_sessions for client_id {client_id}. Matched: {update_result.matched_count}")

        else:
            logging.error(f"Failed to update auth_sessions for client_id {client_id}. auth_sessions_collection is None or client_id is missing.")
            
        return redirect(f"{FRONTEND_URL}?auth=success&client_id={client_id}")
        
    except Exception as e:
        client_id_from_req = request.args.get('state') # Try to get client_id even in exception
        logging.error(f"Error in eBay callback for client_id '{client_id_from_req}': {str(e)}", exc_info=True)
        if auth_sessions_collection is not None and client_id_from_req:
            auth_sessions_collection.update_one(
                {'client_id': client_id_from_req},
                {'$set': {'authenticated': False, 'error': f"CallbackProcessingError: {str(e)}", 'updated_at': datetime.utcnow()}}
            )
        error_param = f"&client_id={client_id_from_req}" if client_id_from_req else ""
        return redirect(f"{FRONTEND_URL}?error=CallbackProcessingError{error_param}")

@app.route('/auth/poll-status', methods=['GET'])
def poll_auth_status():
    """Endpoint for polling authentication status"""
    client_id = request.args.get('client_id')
    if not client_id:
        logging.warning("/auth/poll-status: Client ID is missing from request.")
        return jsonify({'error': 'Client ID is required'}), 400

    if auth_sessions_collection is None:
        logging.error("/auth/poll-status: auth_sessions_collection is None. Cannot poll.")
        return jsonify({'authenticated': False, 'error': 'Auth session storage not available'}), 500

    logging.info(f"/auth/poll-status: Polling for client_id: {client_id}")
    session_data = auth_sessions_collection.find_one({'client_id': client_id})

    if not session_data:
        logging.warning(f"/auth/poll-status: No session data found for client_id: {client_id}")
        # It's important to return 'authenticated: False' so frontend continues to poll if appropriate,
        # rather than a 404 which might break the polling loop differently.
        return jsonify({'authenticated': False, 'status': 'pending_creation', 'error': 'No session found for client_id'}), 200

    # Log the full session_data retrieved
    logging.info(f"/auth/poll-status: Found session data for client_id {client_id}: {session_data}")

    if session_data.get('authenticated') and session_data.get('session_token'):
        logging.info(f"/auth/poll-status: Client {client_id} is authenticated. Returning session token.")
        return jsonify({
            'authenticated': True,
            'session_token': session_data.get('session_token'),
            'user_id': session_data.get('user_id'),
            'ebay_username': session_data.get('ebay_username')
        }), 200
    
    # Check if there was an error recorded during the callback for this client_id
    error_message = session_data.get('error')
    if error_message:
        logging.warning(f"/auth/poll-status: Client {client_id} has a recorded error: {error_message}")
        return jsonify({'authenticated': False, 'error': error_message, 'status': 'error'}), 200

    logging.info(f"/auth/poll-status: Client {client_id} is still pending authentication (authenticated flag is false or session_token missing).")
    return jsonify({'authenticated': False, 'status': 'pending_authentication'}), 200

@app.route('/auth/check-session', methods=['POST'])
def check_session():
    """Check if a session token is valid"""
    data = request.json
    session_id = data.get('session_id')
    
    if not session_id or auth_sessions_collection is None:
        return jsonify({'authenticated': False, 'error': 'Invalid token'}), 200
    
    # Look up session in MongoDB
    session = auth_sessions_collection.find_one({'session_token': session_id})
    
    if not session:
        return jsonify({'authenticated': False, 'error': 'Session not found'}), 200
    
    # Check expiration
    # Ensure we compare datetime with datetime
    if 'expires_at' in session and isinstance(session['expires_at'], datetime) and session['expires_at'] < datetime.utcnow():
        auth_sessions_collection.delete_one({'session_token': session_id}) # Clean up expired session
        return jsonify({'authenticated': False, 'error': 'Session expired'}), 200
    elif 'expires_at' in session and not isinstance(session['expires_at'], datetime):
        # Log an error if expires_at is not a datetime object, as it should be
        logging.error(f"Session {session_id} has an invalid expires_at type: {type(session['expires_at'])}")
        return jsonify({'authenticated': False, 'error': 'Invalid session data (expiry format)'}), 200
    
    # Valid session
    return jsonify({
        'authenticated': True,
        'userId': session.get('user_id'),
        'ebayUsername': session.get('ebay_username')
    }), 200

@app.route('/auth/logout', methods=['POST'])
def logout():
    """Logout the user by invalidating their session"""
    data = request.json
    session_id = data.get('session_id')
    
    if session_id and auth_sessions_collection is not None:
        # Find any sessions with this token and mark them as logged out
        auth_sessions_collection.update_many(
            {'session_token': session_id},
            {'$set': {'authenticated': False}}
        )
    
    return jsonify({"status": "success"}), 200

# Helper functions
def get_ebay_user_info(access_token):
    # IMPORTANT: Verify this endpoint and switch between production and sandbox
    user_info_url = 'https://apiz.ebay.com/commerce/identity/v1/user' # For Production
    if EBAY_ENVIRONMENT == environment.SANDBOX:
        user_info_url = 'https://api.sandbox.ebay.com/commerce/identity/v1/user' # For Sandbox
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }
    
    try:
        # Make the request
        response = requests.get(user_info_url, headers=headers)
        
        # Log response details for debugging
        logging.info(f"eBay user info API response status: {response.status_code}")
        
        # Check if response is successful
        response.raise_for_status()
        
        # Parse JSON response
        user_data = response.json()
        
        # Log the keys in the response to help identify the user ID field
        logging.info(f"eBay user info response keys: {list(user_data.keys())}")
        
        return user_data
    except requests.exceptions.RequestException as e:
        logging.error(f"eBay API request failed: {e}")
        if hasattr(e, 'response') and e.response is not None:
            logging.error(f"Response content: {e.response.text}")
        return {}
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in eBay API response: {e}")
        return {}

def store_user_token(user_id, token_data):
    if preferences_collection is not None:  # Changed from "if preferences_collection:"
        preferences_collection.update_one(
            {'user_id': user_id},
            {'$set': {
                'access_token': token_data['access_token'],
                'refresh_token': token_data.get('refresh_token'),
                'token_expiry': time.time() + token_data['expires_in']
            }},
            upsert=True
        )

def generate_session_token(user_id):
    import hashlib
    import time
    current_time = time.time()
    token = hashlib.sha256(f"{user_id}:{current_time}".encode()).hexdigest()
    
    SESSION_TOKENS[token] = {
        'user_id': user_id,
        'expires_at': current_time + SESSION_EXPIRY
    }
    
    logging.info(f"Generated new session token for user: {user_id}")
    return token

def validate_session_token(token):
    """Validate a session token from MongoDB"""
    if not token or auth_sessions_collection is None:
        return None
    
    # Look for the token in MongoDB
    session = auth_sessions_collection.find_one({'session_token': token})
    
    if not session:
        logging.warning(f"Invalid session token attempted")
        return None
    
    # Check if token is expired
    if 'expires_at' in session and datetime.utcnow() > session['expires_at']: # Use datetime.utcnow() for comparison
        logging.warning(f"Expired session token for user {session.get('user_id')}") # Added user_id for context
        # Optionally, delete the expired session here or let cleanup_expired_sessions handle it
        # auth_sessions_collection.delete_one({'session_token': token})
        return None
    
    # Update last used time
    auth_sessions_collection.update_one(
        {'session_token': token},
        {'$set': {'last_used': datetime.utcnow()}} # Use datetime for last_used as well for consistency
    )
    
    logging.debug(f"Valid session for user: {session['user_id']}")
    return session['user_id']

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring."""
    try:
        # Check database connection
        db_status = "healthy"
        try:
            mongo_client.admin.command('ismaster')
        except Exception:
            db_status = "unhealthy"
        
        # Check services
        nextgen_status = "healthy" if nextgen_ai_blueprint is not None else "unavailable"
        
        overall_status = "healthy" if all([
            db_status == "healthy",
            nextgen_status == "healthy",
        ]) else "unhealthy"
        
        return jsonify({
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "database": db_status,
                "nextgen_ai": nextgen_status,
            },
            "version": "1.0.0"
        }), 200 if overall_status == "healthy" else 503
        
    except Exception as e:
        logger.error(f"Health check error: {e}", exc_info=True)
        return jsonify({
            "status": "unhealthy",
            "error": "Health check failed"
        }), 503

@app.route('/metrics/feedback', methods=['GET'])
def get_feedback_metrics():
    result = analyze_feedback_data()
    return jsonify(result)

@app.route('/metrics/users', methods=['GET'])
def get_user_metrics():
    result = analyze_user_preferences(preferences_collection)
    return jsonify(result)

@app.route('/metrics', methods=['GET'])
def get_all_metrics():
    feedback_metrics = analyze_feedback_data()
    user_metrics = analyze_user_preferences(preferences_collection)
    dataset_metrics = analyze_training_dataset()
    
    return jsonify({
        "feedback_metrics": feedback_metrics,
        "user_metrics": user_metrics,
        "dataset_metrics": dataset_metrics
    })

@app.route('/dashboard', methods=['GET'])
def dashboard():
    return app.send_static_file('metrics.html')

# --- Serve Frontend ---
@app.route('/')
def serve_frontend():
    """Serve the main frontend application"""
    return send_from_directory(FRONTEND_BUILD_DIR, 'index.html')

@app.route('/<path:path>')
def serve_static_files(path):
    """Serve static files from the frontend build directory"""
    try:
        return send_from_directory(FRONTEND_BUILD_DIR, path)
    except Exception:
        # If file not found, serve index.html for client-side routing
        return send_from_directory(FRONTEND_BUILD_DIR, 'index.html')

def cleanup_expired_sessions():
    """Remove expired sessions from MongoDB"""
    if auth_sessions_collection is not None:
        current_time_dt = datetime.utcnow() # Use datetime object
        result = auth_sessions_collection.delete_many({
            'expires_at': {'$lt': current_time_dt} # Compare datetime with datetime
        })
        logging.info(f"Cleaned up {result.deleted_count} expired sessions")

# Run cleanup on startup and periodically

if __name__ == '__main__':
    try:
        # Cleanup expired sessions on startup
        cleanup_expired_sessions()
        
        logger.info(f"Starting eBay AI Chatbot backend on {config.app.host}:{config.app.port}")
        logger.info(f"Environment: {config.ebay.environment}")
        logger.info(f"Debug mode: {config.app.debug}")
        
        # Run the application
        app.run(
            debug=config.app.debug,
            port=config.app.port,
            host=config.app.host
        )
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}", exc_info=True)
        sys.exit(1)
