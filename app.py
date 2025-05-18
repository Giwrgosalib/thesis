from flask import Flask, request, jsonify, redirect, make_response
from flask_cors import CORS
from custom_nlp import EBayNLP
from ebay_service import EBayService
import requests
import logging
import csv
import os
from threading import Lock
from pymongo import MongoClient  # Import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv  # Import load_dotenv
import time
from metrics import analyze_feedback_data, analyze_user_preferences, analyze_training_dataset  # Import metrics functions
from urllib.parse import quote_plus, urljoin  # Ensure urljoin is used for EBAY_REDIRECT_URI
import sys
import json  # Import json for parsing token responses
import jwt  # Import jwt for to ken generation
from datetime import datetime, timedelta  # Import datetime and timedelta for token expiration

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
CORS(app, 
     origins=["http://localhost:8080", "https://secure-openly-moth.ngrok-free.app"],
     supports_credentials=True,
     expose_headers=["Authorization", "Content-Type"])
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

APP_BASE_URL = os.environ.get("APP_BACKEND_URL", "http://localhost:5000")
EBAY_CALLBACK_PATH = "/auth/ebay-callback"
# This variable below is the ACTUAL URL where your app receives the callback.
# This full URL must be registered in the eBay developer portal FOR your EBAY_RUNAME.
YOUR_APPLICATION_CALLBACK_URL = urljoin(APP_BASE_URL, EBAY_CALLBACK_PATH) 

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:8080")

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
        logging.info(f"Successfully connected to MongoDB. Using database '{DB_NAME}', collection '{PREF_COLLECTION}'.")
except ConnectionFailure:
    logging.error("MongoDB connection failed. User preferences will not be saved.")
    mongo_client = None
    db = None
    preferences_collection = None
except Exception as e:
    logging.error(f"An error occurred during MongoDB initialization: {e}", exc_info=True)
    mongo_client = None
    db = None
    preferences_collection = None

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
    if not nlp_processor or not ebay_service:
        logging.error("Attempted search with uninitialized services.")
        return jsonify({"error": "Backend services not available"}), 500

    data = request.json
    query = data.get('query')
    # --- Get user_id from request ---
    user_id = data.get('userId')  # Assuming frontend sends 'userId'

    if not query or not query.strip():
        logging.warning("Received search request with no query.")
        return jsonify({"error": "Query is required"}), 400

    logging.info(f"Received search query: {query}" + (f" from user: {user_id}" if user_id else ""))

    try:
        extracted_data = nlp_processor.extract_entities(query)
        logging.info(f"NLP Extraction Result: {extracted_data}")

        # Log data for continuous learning
        log_feedback(
            query=extracted_data.get("raw_query", query),
            intent=extracted_data.get("intent", "unknown_intent"),
            raw_entities=extracted_data.get("raw_entities", [])
        )

        # --- Save user preferences ---
        if user_id:
            save_user_preference(user_id, extracted_data)
        # --- End saving preferences ---

        # Pass user_id to the search service
        search_results = ebay_service.search(intent=extracted_data, user_id=user_id)  # Pass user_id

        logging.info(f"eBay search successful for query: {query}")
        return jsonify(search_results)

    except Exception as e:
        logging.error(f"Error processing search query '{query}': {e}", exc_info=True)
        return jsonify({"error": "An error occurred processing your request"}), 500

@app.route('/auth/ebay-login', methods=['GET'])
def initiate_ebay_login():
    """Initiates the eBay OAuth flow using the ebay-oauth-python-client library."""
    if not all([EBAY_CLIENT_ID, EBAY_CLIENT_SECRET, EBAY_DEV_ID]):  # Check if credentials were loaded for the library
        logging.error("eBay credentials not properly configured for OAuth client library. Cannot initiate login.")
        return jsonify({"error": "Server configuration error for eBay login (credentials)."}), 500
    try:
        auth_url = ebay_oauth_client.generate_user_authorization_url(
            EBAY_ENVIRONMENT,
            EBAY_SCOPES
        )
        logging.info(f"Redirecting user to eBay auth URL ({EBAY_ENVIRONMENT.config_id}): {auth_url.split('?')[0]}...")
        return redirect(auth_url)
    except Exception as e:
        logging.error(f"Error generating eBay authorization URL: {e}", exc_info=True)
        return jsonify({"error": "Server configuration error for eBay login."}), 500

@app.route(EBAY_CALLBACK_PATH, methods=['GET'])
def handle_ebay_callback():
    """Handles the callback from eBay using the ebay-oauth-python-client library."""
    auth_code = request.args.get('code')

    if not auth_code:
        logging.warning("Authorization code not provided in eBay callback.")
        return redirect(f"{FRONTEND_URL}?auth_error=code_missing")

    try:
        user_oauth_token: oAuth_token = ebay_oauth_client.exchange_code_for_access_token(
            EBAY_ENVIRONMENT,
            auth_code
        )

        if user_oauth_token.error:
            # Use hasattr for safer access to error_description
            error_desc = user_oauth_token.error_description if hasattr(user_oauth_token, 'error_description') and user_oauth_token.error_description else user_oauth_token.error
            logging.error(f"eBay token exchange failed ({EBAY_ENVIRONMENT.config_id}): {error_desc}")
            return redirect(f"{FRONTEND_URL}?auth_error=token_exchange_failed&details={quote_plus(str(error_desc))}")

        user_access_token = user_oauth_token.access_token
        user_refresh_token = user_oauth_token.refresh_token
        
        raw_token_data = {}
        if hasattr(user_oauth_token, 'token_response'):
            if isinstance(user_oauth_token.token_response, dict):
                raw_token_data = user_oauth_token.token_response
            elif isinstance(user_oauth_token.token_response, str):  # Sometimes it might be a string
                try:
                    raw_token_data = json.loads(user_oauth_token.token_response)  # Ensure json is imported if not already
                except json.JSONDecodeError:
                    logging.warning(f"Could not parse token_response string from eBay OAuth library: {user_oauth_token.token_response}")
        
        expires_in = raw_token_data.get('expires_in')

        if not user_access_token:
            logging.error("User access token not found in library's response after successful exchange.")
            return redirect(f"{FRONTEND_URL}?auth_error=token_missing")

        ebay_user_details = get_ebay_user_info(user_access_token)  # Ensure this function is robust
        app_user_id = ebay_user_details.get('userId')  # CRITICAL: Ensure 'userId' is the correct, stable ID field

        if not app_user_id:
            logging.error(f"Could not retrieve a stable eBay user ID from get_ebay_user_info. Response: {ebay_user_details}. Check the 'get_ebay_user_info' function and the eBay API response structure.")
            return redirect(f"{FRONTEND_URL}?auth_error=ebay_user_id_missing")

        # Ensure expires_in is an integer for time calculations
        try:
            expires_in_int = int(expires_in) if expires_in is not None else None
        except ValueError:
            logging.warning(f"Could not convert expires_in ('{expires_in}') to int for user {app_user_id}.")
            expires_in_int = None  # Default to None if conversion fails

        if user_refresh_token and expires_in_int is not None:
            token_data_for_storage = {
                'access_token': user_access_token,
                'refresh_token': user_refresh_token,
                'expires_in': expires_in_int
            }
            store_user_token(app_user_id, token_data_for_storage)
        else:
            logging.warning(f"Refresh token or expires_in missing/invalid from library for user {app_user_id}. Cannot fully store eBay tokens. Expires_in: {expires_in}, Refresh Token Present: {bool(user_refresh_token)}")
            if expires_in_int is not None:  # Store at least access token if expires_in is valid
                token_data_for_storage = {
                    'access_token': user_access_token,
                    'expires_in': expires_in_int
                }
                store_user_token(app_user_id, token_data_for_storage)
        
        application_session_token = generate_session_token(app_user_id)

        logging.info(f"Successfully obtained eBay user token. Creating app session for app_user_id: {app_user_id}")

        # Get secret from environment variables
        JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
        if not JWT_SECRET_KEY:
            logging.warning("JWT_SECRET_KEY not set! Using a temporary key - THIS IS INSECURE")
            JWT_SECRET_KEY = os.urandom(32).hex()  # Fallback (still better than hardcoded)

        # Generate JWT token
        jwt_payload = {
            'user_id': app_user_id,
            'exp': datetime.utcnow() + timedelta(days=1)  # 24 hour expiration
        }
        token = jwt.encode(jwt_payload, JWT_SECRET_KEY, algorithm='HS256')

        # Simplify by just using JWT token in URL parameters
        redirect_url = f'https://ebay.com/?login_success=true&token={token}'
        return redirect(redirect_url)

    except Exception as e:
        logging.error(f"Unexpected error in eBay OAuth callback: {e}", exc_info=True)
        return redirect(f"{FRONTEND_URL}?auth_error=internal_server_error")

@app.route('/auth/status', methods=['GET'])
def check_auth_status():
    """Check if the user is authenticated using JWT token"""
    auth_header = request.headers.get('Authorization', '')
    
    if not auth_header.startswith('Bearer '):
        return jsonify({"authenticated": False})
        
    token = auth_header.split(' ')[1]
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY")
    
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')
        
        if not user_id:
            return jsonify({"authenticated": False})
            
        user_prefs = {}
        if preferences_collection is not None:
            user_prefs = preferences_collection.find_one({'user_id': user_id}) or {}
            
        return jsonify({
            "authenticated": True,
            "userId": user_id,
            "preferences": user_prefs
        })
    except jwt.ExpiredSignatureError:
        return jsonify({"authenticated": False, "error": "Token expired"})
    except jwt.InvalidTokenError:
        return jsonify({"authenticated": False, "error": "Invalid token"})

@app.route('/auth/logout', methods=['POST'])
def logout():
    """Logout the user by invalidating their session"""
    response = make_response(jsonify({"status": "success"}))
    response.delete_cookie('ebay_session')
    return response

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
    if not token or token not in SESSION_TOKENS:
        logging.warning(f"Invalid session token attempted: {token[:10]}...")
        return None
        
    token_data = SESSION_TOKENS.get(token)
    
    if time.time() > token_data['expires_at']:
        SESSION_TOKENS.pop(token, None)
        logging.warning(f"Expired session token: {token[:10]}...")
        return None
        
    logging.debug(f"Valid session for user: {token_data['user_id']}")
    return token_data['user_id']

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

if __name__ == '__main__':
    app.run(debug=True, port=5000)