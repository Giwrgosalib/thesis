from flask import Flask, request, jsonify
from custom_nlp import EBayNLP
from ebay_service import EBayService
from typing import Dict, Any, List
from flask_cors import CORS  # Import CORS for cross-origin requests
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Configure CORS to allow requests from the frontend
CORS(app, resources={r"/*": {"origins": ["http://localhost:8080", "chrome-extension://*"]}})

nlp = EBayNLP()
ebay = EBayService()

@app.route('/search', methods=['POST', 'OPTIONS'])
def search() -> Dict[str, Any]:
    """Endpoint for AI-powered eBay searches"""
    # Handle preflight OPTIONS request
    if request.method == 'OPTIONS':
        return '', 204
        
    try:
        # Validate input
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
        
        data = request.get_json()
        user_query = data.get('query', '').strip()
        if not user_query:
            return jsonify({"error": "Query cannot be empty"}), 400

        logger.info(f"Processing search query: {user_query}")
        
        # AI Processing - Extract structured intent from natural language
        intent = nlp.extract_entities(user_query)
        logger.info(f"Extracted intent: {intent}")
        
        # Use the improved search method that takes the full intent object
        results = ebay.search(intent)
        
        # Format the response with additional metadata
        response = {
            "original_query": user_query,
            "detected_intent": {
                "intent_type": intent.get('intent', 'general_search'),
                "brands": intent.get('brands', []),
                "categories": intent.get('categories', []),
                "price_range": intent.get('price_range'),
            },
            "results_count": len(results),
            "results": results
        }
        
        logger.info(f"Search completed. Found {len(results)} results.")
        return jsonify(response)

    except Exception as e:
        logger.error(f"Error processing search request: {str(e)}", exc_info=True)
        return jsonify({
            "error": "Failed to process search request",
            "message": str(e),
            "status": "error"
        }), 500

@app.route('/health', methods=['GET'])
def health_check() -> Dict[str, str]:
    """Simple health check endpoint"""
    return jsonify({"status": "ok"})

@app.route('/analyze', methods=['POST'])
def analyze_query() -> Dict[str, Any]:
    """Endpoint to analyze a query without performing a search"""
    try:
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
        
        data = request.get_json()
        user_query = data.get('query', '').strip()
        if not user_query:
            return jsonify({"error": "Query cannot be empty"}), 400
            
        # Just extract and return the intent analysis
        intent = nlp.extract_entities(user_query)
        
        return jsonify({
            "query": user_query,
            "analysis": intent
        })
        
    except Exception as e:
        logger.error(f"Error analyzing query: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logger.info("Starting eBay AI Search API")
    app.run(host='0.0.0.0', port=5000, debug=True)