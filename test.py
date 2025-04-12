from flask import Flask, request, jsonify
from ai_engine import AIEngine
from ebay_service import EBayService
import logging
from typing import Dict, Any
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
ai_engine = AIEngine()
ebay_service = EBayService()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route("/api/recommendations", methods=["POST"])
def get_recommendations() -> Dict[str, Any]:
    """
    Endpoint for product recommendations
    Expected JSON payload: {"query": "search query"}
    Returns: {"recommendations": [...]} or {"error": "message"}
    """
    try:
        data = request.get_json()
        if not data or "query" not in data:
            return jsonify({"error": "Missing query parameter"}), 400

        query = data["query"].strip()
        if not query:
            return jsonify({"error": "Empty query"}), 400

        logger.info(f"Processing query: {query}")

        # Process the query
        processed_data = ai_engine.process_query(query)
        logger.info(f"Processed data: {processed_data}")

        # Get recommendations from eBay
        recommendations = ebay_service.fetch_recommendations(
            processed_data["processed_query"],
            processed_data["price_range"]
        )

        return jsonify({
            "recommendations": recommendations,
            "meta": {
                "original_query": query,
                "processed_query": processed_data["processed_query"],
                "detected_filters": {
                    "price_range": processed_data["price_range"],
                    "brand": processed_data["brand"]
                }
            }
        })

    except Exception as e:
        logger.error(f"Error in recommendation endpoint: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)