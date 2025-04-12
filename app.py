from flask import Flask, request, jsonify
from custom_nlp import EBayNLP
from ebay_service import EBayService
from typing import Dict, Any
from flask_cors import CORS  # Import CORS for cross-origin requests

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
nlp = EBayNLP()
ebay = EBayService()

@app.route('/search', methods=['POST'])
def search() -> Dict[str, Any]:
    """Endpoint for live eBay searches"""
    try:
        # Validate input
        if not request.is_json:
            return jsonify({"error": "Request must be JSON"}), 400
        
        data = request.get_json()
        user_query = data.get('query', '').strip()
        if not user_query:
            return jsonify({"error": "Query cannot be empty"}), 400

        # AI Processing
        intent = nlp.extract_entities(user_query)
        
        # Live eBay Search
        # Use the processed query if available, otherwise use the raw query
        query = intent.get('processed_query', user_query)
        if 'processed_query' not in intent:
            query = user_query
            
        results = ebay.search_ebay(
            query=query,
            price_range=intent.get('price_range'),
            category=intent.get('categories')[0] if intent.get('categories') else None
        )

        return jsonify({
            "original_query": user_query,
            "detected_intent": intent,
            "results": results
        })

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
