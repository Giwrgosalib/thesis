from flask import Flask, request, jsonify
from flask_cors import CORS
from custom_nlp import EBayNLP
from ebay_service import EBayService
import logging
import csv
import os
from threading import Lock
from pymongo import MongoClient  # Import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv  # Import load_dotenv
import time
from metrics import analyze_feedback_data, analyze_user_preferences, analyze_training_dataset  # Import metrics functions

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