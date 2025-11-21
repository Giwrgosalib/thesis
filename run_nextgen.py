import os
import logging
from flask import Flask, jsonify
from flask_cors import CORS
from backend_nextgen.api.experimental import blueprint as nextgen_blueprint

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    CORS(app)  # Enable CORS for all routes

    # Register the Next-Gen blueprint
    app.register_blueprint(nextgen_blueprint)

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "backend": "nextgen"})

    return app

if __name__ == "__main__":
    app = create_app()
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Starting Next-Gen AI Backend on port {port}")
    app.run(host="0.0.0.0", port=port, debug=True)
