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
from urllib.parse import quote_plus

app = Flask(__name__)
CORS(app)
load_dotenv()  # Load environment variables from .env

# --- Configuration ---
FEEDBACK_LOG_PATH = os.path.join('data', 'feedback_log.csv')
LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
LOG_LEVEL = logging.INFO
MONGO_URI = os.environ.get("MONGO_URI")  # Get MongoDB URI from env
DB_NAME = "ebay_extension_prefs"
PREF_COLLECTION = "user_preferences"

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
    """Initiates the eBay OAuth flow"""
    # Get the client ID from eBay service
    client_id = ebay_service.client_id
    redirect_uri = request.args.get('redirect_uri', 'http://localhost:5000/auth/ebay-callback')
    
    # Build the eBay authorization URL
    auth_url = f"https://auth.ebay.com/oauth2/authorize?client_id={client_id}&response_type=code&redirect_uri={quote_plus(redirect_uri)}&scope=https://api.ebay.com/oauth/api_scope"
    
    # Redirect the user to eBay's login page
    return redirect(auth_url)

@app.route('/auth/ebay-callback', methods=['GET'])
def handle_ebay_callback():
    """Handles the callback from eBay after user authorizes"""
    code = request.args.get('code')
    if not code:
        return jsonify({"error": "No authorization code provided"}), 400
    
    try:
        # Exchange code for token
        token_response = requests.post(
            'https://api.ebay.com/identity/v1/oauth2/token',
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': f'Basic {ebay_service._get_basic_auth_token()}'
            },
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': request.base_url  # Use the same redirect_uri used in the request
            }
        )
        token_data = token_response.json()
        
        # Get user info with the token
        user_info = get_ebay_user_info(token_data['access_token'])
        
        # Create a session or JWT for the user
        user_id = user_info.get('userId', 'default_user_id')
        
        # Store the token in the database for future use
        store_user_token(user_id, token_data)
        
        # Redirect back to the frontend with a session cookie or token
        response = redirect('http://localhost:8080')  # Frontend URL
        response.set_cookie('ebay_session', generate_session_token(user_id), httponly=True, secure=True)
        return response
        
    except Exception as e:
        logging.error(f"Error in eBay OAuth callback: {e}", exc_info=True)
        return jsonify({"error": "Authentication failed"}), 500

@app.route('/auth/status', methods=['GET'])
def check_auth_status():
    """Check if the user is authenticated"""
    session_token = request.cookies.get('ebay_session')
    if not session_token:
        return jsonify({"authenticated": False})
    
    # Validate the session token and get user_id
    user_id = validate_session_token(session_token)
    if not user_id:
        return jsonify({"authenticated": False})
    
    # Get user preferences if needed
    user_prefs = {}
    if preferences_collection:
        user_prefs = preferences_collection.find_one({'user_id': user_id}) or {}
        
    return jsonify({
        "authenticated": True,
        "userId": user_id,
        "preferences": user_prefs
    })

@app.route('/auth/logout', methods=['POST'])
def logout():
    """Logout the user by invalidating their session"""
    response = make_response(jsonify({"status": "success"}))
    response.delete_cookie('ebay_session')
    return response

# Helper functions
def get_ebay_user_info(access_token):
    # This implementation depends on the eBay API endpoints available to you
    # You may need to adjust based on the specific eBay API you're using
    try:
        response = requests.get(
            'https://api.ebay.com/commerce/identity/v1/user',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        return response.json()
    except Exception as e:
        logging.error(f"Error getting eBay user info: {e}")
        return {}

def store_user_token(user_id, token_data):
    # Store token in your database
    if preferences_collection:
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
    # In production, use a proper JWT library
    import hashlib
    import time
    current_time = time.time()
    token = hashlib.sha256(f"{user_id}:{current_time}".encode()).hexdigest()
    
    # Store the token with user_id and expiry time
    SESSION_TOKENS[token] = {
        'user_id': user_id,
        'expires_at': current_time + SESSION_EXPIRY
    }
    
    logging.info(f"Generated new session token for user: {user_id}")
    return token

def validate_session_token(token):
    """
    Validates a session token and returns the associated user_id if valid.
    Returns None if token is invalid or expired.
    """
    if not token or token not in SESSION_TOKENS:
        logging.warning(f"Invalid session token attempted: {token[:10]}...")
        return None
        
    # Get token data
    token_data = SESSION_TOKENS.get(token)
    
    # Check if token has expired
    if time.time() > token_data['expires_at']:
        # Remove expired token
        SESSION_TOKENS.pop(token, None)
        logging.warning(f"Expired session token: {token[:10]}...")
        return None
        
    # Valid token, return the user_id
    logging.debug(f"Valid session for user: {token_data['user_id']}")
    return token_data['user_id']

@app.route('/health', methods=['GET'])
def health_check():
    # Basic health check
    return jsonify({"status": "healthy"}), 200

@app.route('/metrics/feedback', methods=['GET'])
def get_feedback_metrics():
    """Generate metrics and visualizations from feedback data."""
    result = analyze_feedback_data()
    return jsonify(result)

@app.route('/metrics/users', methods=['GET'])
def get_user_metrics():
    """Generate metrics and visualizations from user preferences."""
    result = analyze_user_preferences(preferences_collection)
    return jsonify(result)

@app.route('/metrics', methods=['GET'])
def get_all_metrics():
    """Generate all available metrics and visualizations."""
    feedback_metrics = analyze_feedback_data()
    user_metrics = analyze_user_preferences(preferences_collection)
    dataset_metrics = analyze_training_dataset()  # Assuming this function is defined in metrics.py
    
    return jsonify({
        "feedback_metrics": feedback_metrics,
        "user_metrics": user_metrics,
        "dataset_metrics": dataset_metrics
    })

@app.route('/dashboard', methods=['GET'])
def dashboard():
    """Render the dashboard page."""
    return app.send_static_file('metrics.html')

if __name__ == '__main__':
    # Consider using a production-ready server like Gunicorn or Waitress
    # For development:
    app.run(debug=True, port=5000)  # debug=True enables auto-reloading