from flask import Flask, request, jsonify, redirect, make_response, send_from_directory # Ensure send_from_directory is imported
from flask_cors import CORS
from custom_nlp import EBayNLP
from ebay_service import EBayService
import requests
import logging
import csv
import os # Ensure os is imported
from threading import Lock
from pymongo import MongoClient  # Import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv  # Import load_dotenv
import time
from metrics import analyze_feedback_data, analyze_user_preferences, analyze_training_dataset  # Import metrics functions
from urllib.parse import quote_plus, urljoin  # Ensure urljoin is used for EBAY_REDIRECT_URI
import sys
import json  # Import json for parsing token responses
from datetime import datetime, timedelta  # Import datetime and timedelta for token expiration
import random

# Add the library's parent directory to sys.path to find the oauthclient module
# Assuming app.py is in 'backend' and 'ebay-oauth-python-client' is also in 'backend'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # Adds 'backend' to path

# Now you can import from the library
from ebay_oauth_python_client.oauthclient.oauth2api import oauth2api  # Import for the client instance
from ebay_oauth_python_client.oauthclient.model.model import environment, oAuth_token
from ebay_oauth_python_client.oauthclient.credentialutil import credentialutil
from ebay_oauth_python_client.oauthclient.model.model import credentials as EbayOauthCredentials

# Fix the CORS configuration to allow requests from your frontend
app = Flask(__name__)
load_dotenv()  # Load environment variables from .env

# --- Configuration ---
FEEDBACK_LOG_PATH = os.path.join('data', 'feedback_log.csv')
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
LOG_LEVEL = logging.INFO
MONGO_URI = os.environ.get("MONGO_URI")  # Get MongoDB URI from env
DB_NAME = "ebay_extension_prefs"
PREF_COLLECTION = "user_preferences"

EBAY_CLIENT_ID = os.environ.get("EBAY_CLIENT_ID")
EBAY_CLIENT_SECRET = os.environ.get("EBAY_CLIENT_SECRET")
EBAY_DEV_ID = os.environ.get("EBAY_DEV_ID") # Add this to your .env file
EBAY_RUNAME = os.environ.get("EBAY_RUNAME") # Get RuName from .env

# Use an environment variable for the app's base URL, defaulting for local development
# This URL is where your Flask app is accessible.
APP_BASE_URL = os.environ.get("APP_BACKEND_URL", "https://localhost:5000")  # Default to localhost for local development
EBAY_CALLBACK_PATH = "/auth/ebay-callback"
# This YOUR_APPLICATION_CALLBACK_URL must be registered in your eBay app settings for the EBAY_RUNAME.
YOUR_APPLICATION_CALLBACK_URL = urljoin(APP_BASE_URL, EBAY_CALLBACK_PATH)

# For same-origin, FRONTEND_URL should also be the APP_BASE_URL, as Flask serves the frontend.
FRONTEND_URL = APP_BASE_URL
# Add path to your frontend's build directory
FRONTEND_BUILD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend', 'dist')) # Adjust 'dist' if your build folder has a different name

# Determine eBay Environment from .env (e.g., EBAY_API_ENVIRONMENT="SANDBOX" or "PRODUCTION")
ebay_api_env_str = os.environ.get("EBAY_API_ENVIRONMENT", "PRODUCTION").upper()
if ebay_api_env_str == "SANDBOX":
    EBAY_ENVIRONMENT = environment.SANDBOX
    logging.info("Using eBay SANDBOX environment.")
else:
    EBAY_ENVIRONMENT = environment.PRODUCTION  # Default to PRODUCTION if not specified or invalid
    logging.info("Using eBay PRODUCTION environment.")

EBAY_SCOPES = os.environ.get("EBAY_SCOPES", "https://api.ebay.com/oauth/api_scope").split(' ')  # Library expects a list of scopes

# Store active session tokens
SESSION_TOKENS = {}
# Session expiry time in seconds (24 hours)
SESSION_EXPIRY = 86400 

# --- Setup Logging ---
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
os.makedirs('data', exist_ok=True)
log_lock = Lock()

# --- Initialize MongoDB Connection ---
SESSION_COLLECTION = "auth_sessions"
auth_sessions_collection = None

mongo_client = None
db = None
preferences_collection = None
try:
    if not MONGO_URI:
        logging.warning("MONGO_URI not set in environment variables. User preferences will not be saved.")
    else:
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        # The ismaster command is cheap and does not require auth.
        mongo_client.admin.command('ismaster')
        db = mongo_client[DB_NAME]
        preferences_collection = db[PREF_COLLECTION]
        auth_sessions_collection = db[SESSION_COLLECTION]  # Add this line
        logging.info(f"Successfully connected to MongoDB. Using database '{DB_NAME}', collection '{PREF_COLLECTION}'.")
except ConnectionFailure:
    logging.error("MongoDB connection failed. User preferences will not be saved.")
    mongo_client = None
    db = None
    preferences_collection = None
    auth_sessions_collection = None
except Exception as e:
    logging.error(f"An error occurred during MongoDB initialization: {e}", exc_info=True)
    mongo_client = None
    db = None
    preferences_collection = None
    auth_sessions_collection = None

# Initialize eBay OAuth client
ebay_oauth_client = oauth2api()

# Create a temporary config file with your credentials
# This follows how the library is designed to work
ebay_config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ebay_config')
os.makedirs(ebay_config_dir, exist_ok=True)

ebay_config_path = os.path.join(ebay_config_dir, 'ebay-credentials.yaml')

# Create a YAML config file with the structure the library expects
ebay_config_content = {
    environment.SANDBOX.config_id: {
        'appid': EBAY_CLIENT_ID,
        'certid': EBAY_CLIENT_SECRET,
        'devid': EBAY_DEV_ID,
        'redirecturi': EBAY_RUNAME  # Use the RuName from your eBay Developer Portal
    },
    environment.PRODUCTION.config_id: {
        'appid': EBAY_CLIENT_ID,
        'certid': EBAY_CLIENT_SECRET,
        'devid': EBAY_DEV_ID,
        'redirecturi': EBAY_RUNAME  # Use the RuName from your eBay Developer Portal
    }
}

# Write the config file
try:
    import yaml
    with open(ebay_config_path, 'w') as f:
        yaml.dump(ebay_config_content, f)
    logging.info(f"Created temporary eBay credentials config file at: {ebay_config_path}")
    
    # Load the credentials into the library
    credentialutil.load(ebay_config_path)
    logging.info(f"Successfully loaded eBay credentials for environments: {list(ebay_config_content.keys())}")
except Exception as e:
    logging.error(f"CRITICAL: Failed to create or load eBay credentials: {e}", exc_info=True)
    # Handle this critical error appropriately in your application

# --- Initialize Services ---
try:
    nlp_processor = EBayNLP()
    # Pass the preferences collection to EBayService
    ebay_service = EBayService(preferences_collection=preferences_collection)
    logging.info("NLP and eBay services initialized successfully.")
except Exception as e:
    logging.error(f"Error initializing services: {e}", exc_info=True)
    nlp_processor = None
    ebay_service = None

# --- Helper Function for Logging Feedback ---
def log_feedback(query: str, intent: str, raw_entities: list):
    """Logs query, intent, and entities to the feedback CSV file."""
    entities_str = str(raw_entities)
    with log_lock:
        try:
            file_exists = os.path.isfile(FEEDBACK_LOG_PATH)
            with open(FEEDBACK_LOG_PATH, 'a', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['query', 'intent', 'entities']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                if not file_exists or os.path.getsize(FEEDBACK_LOG_PATH) == 0:
                    writer.writeheader()
                writer.writerow({'query': query, 'intent': intent, 'entities': entities_str})
        except Exception as e:
            logging.error(f"Error writing to feedback log: {e}", exc_info=True)

# --- Helper Function for Saving Preferences ---
def save_user_preference(user_id: str, extracted_data: dict):
    """Saves extracted information as user preferences in MongoDB."""
    if preferences_collection is None or not user_id:
        return

    try:
        update_doc = {
            '$push': {'search_history': {'query': extracted_data.get("raw_query"), 'timestamp': time.time()}},
            '$addToSet': {}  # Use addToSet to avoid duplicates in lists
        }
        # Add preferred brands/categories if found
        if extracted_data.get("BRAND"):
            update_doc['$addToSet']['preferred_brands'] = {'$each': extracted_data["BRAND"]}
        if extracted_data.get("CATEGORY"):
            # Use the consolidated category list
            update_doc['$addToSet']['preferred_categories'] = {'$each': extracted_data["CATEGORY"]}
        if extracted_data.get("SHIPPING"):
            update_doc['$addToSet']['preferred_shipping'] = {'$each': extracted_data["SHIPPING"]}
        # Add more entity types to store
        for entity_type in ["SIZE","WIDTH"]:
            if extracted_data.get(entity_type):
                update_doc['$addToSet'][f'preferred_{entity_type.lower()}'] = {'$each': extracted_data[entity_type]}

        # Perform the update, creating the document if it doesn't exist (upsert=True)
        preferences_collection.update_one(
            {'user_id': user_id},
            update_doc,
            upsert=True
        )
    except Exception as e:
        logging.error(f"Error saving preferences for user {user_id}: {e}", exc_info=True)

# --- API Endpoints ---
@app.route('/search', methods=['POST'])
def search():
    try:
        data = request.json
        query = data.get('query', '')
        
        # Get auth token from header
        auth_header = request.headers.get('Authorization')
        user_id = None
        
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            user_id = validate_session_token(token)
        
        # Check if NLP processor is available
        if nlp_processor is None:
            logging.error("NLP processor is not initialized. Cannot process query.")
            return jsonify({"error": "Search service unavailable"}), 500
            
        # Process query and extract entities directly using the nlp_processor
        extracted_data = nlp_processor.extract_entities(query)
        
        # Log feedback from the query
        log_feedback(
            query, 
            extracted_data.get("intent", "unknown"), 
            extracted_data.get("raw_entities", [])
        )
        
        # Save user preferences if authenticated
        if user_id:
            save_user_preference(user_id, extracted_data)
        
        # Check if eBay service is available
        if ebay_service is None:
            logging.error("eBay service is not initialized. Cannot perform search.")
            return jsonify({"error": "Search service unavailable"}), 500
            
        # Directly use the ebay_service to perform the search
        search_results = ebay_service.search(intent=extracted_data, user_id=user_id)
        
        return jsonify(search_results)
    except Exception as e:
        logging.error(f"Error in search: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/auth/ebay-login', methods=['GET'])
def initiate_ebay_login():
    """Initiates the eBay OAuth flow"""
    # Get client ID from query parameter
    client_id = request.args.get('client_id')
    
    if not client_id:
        # Generate a client ID if not provided
        client_id = f"client_{int(time.time())}_{random.randint(1000, 9999)}" # time.time() is fine for generation
    
    # Store the initial auth request in MongoDB
    if auth_sessions_collection is not None:
        current_dt = datetime.utcnow() # Use datetime object
        auth_sessions_collection.update_one(
            {'client_id': client_id},
            {
                '$set': {
                    'client_id': client_id,
                    'created_at': current_dt, # Store as datetime
                    'is_polling': False,
                    'authenticated': False,
                    'last_poll': current_dt # Store as datetime
                }
            },
            upsert=True
        )
    
    # Create an auth URL for eBay with the state parameter
    ebay_auth_url = ebay_oauth_client.generate_user_authorization_url(
        env_type=EBAY_ENVIRONMENT,
        scopes=EBAY_SCOPES,
        state=client_id
    )
    
    return redirect(ebay_auth_url)

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
    return jsonify({"status": "healthy"}), 200

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
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_vue_app(path):
    if path != "" and os.path.exists(os.path.join(FRONTEND_BUILD_DIR, path)):
        return send_from_directory(FRONTEND_BUILD_DIR, path)
    else:
        # For any path not found in static files, serve index.html for client-side routing
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
    cleanup_expired_sessions()
    # Ensure host is '0.0.0.0' to be accessible externally if needed (e.g. for eBay callback testing with ngrok)
    # or when running in a container. For purely local, 'localhost' or '127.0.0.1' is also fine.
    app.run(debug=True, port=5000, host='0.0.0.0')