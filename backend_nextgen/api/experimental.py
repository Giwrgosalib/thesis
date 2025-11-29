
"""
Experimental Flask blueprint hooking into the next-gen orchestrator.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from flask import Blueprint, current_app, jsonify, request, Response, stream_with_context
import json

# ... (imports remain same)
# from backend_nextgen.orchestrator import orchestrator

# Globals for dependency injection
preference_loader: Optional[Callable[[str], Dict[str, Any]]] = None
preference_writer: Optional[Callable[[str, Dict[str, Any]], None]] = None

def configure_preference_loader(loader: Callable[[str], Dict[str, Any]]) -> None:
    global preference_loader
    preference_loader = loader

def configure_preference_writer(writer: Callable[[str, Dict[str, Any]], None]) -> None:
    global preference_writer
    preference_writer = writer

# Define the blueprint
blueprint = Blueprint("nextgen_experimental", __name__)

@blueprint.route("/query", methods=["POST"])
def handle_query():
    payload = request.get_json(force=True)
    query = payload.get("query", "")
    base_context = payload.get("user_context", {}) or {}
    limit = int(payload.get("limit", 10))
    offset = int(payload.get("offset", 0))
    
    user_context = dict(base_context)
    user_id = user_context.get("userId") or user_context.get("user_id")

    if preference_loader and user_id:
        try:
            snapshot = preference_loader(str(user_id))
        except Exception as exc:  # noqa: BLE001
            snapshot = None
            current_app.logger.warning(
                "Preference loader failed for user %s: %s", user_id, exc, exc_info=True
            )
        if snapshot:
            user_context["preferences"] = snapshot

    try:
        from backend_nextgen.orchestrator import orchestrator
        result = orchestrator.handle_query(query, user_context, limit=limit, offset=offset)
        
        # Save history if configured
        if preference_writer and user_id:
            try:
                # Construct payload for persistence
                # persist_preferences expects: entities, query, answer
                pref_payload = {
                    "query": query,
                    "entities": result.get("entities", {}),
                    "answer": result.get("answer", "")
                }
                preference_writer(str(user_id), pref_payload)
            except Exception as exc:
                current_app.logger.warning(
                    "Preference writer failed for user %s: %s", user_id, exc, exc_info=True
                )

        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Query error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@blueprint.route("/metrics", methods=["GET"])
def metrics_summary():
    try:
        window = int(request.args.get("window", 3600))
    except ValueError:
        window = 3600
    from backend_nextgen.orchestrator import orchestrator
    summary = orchestrator.summarize_metrics(window_seconds=window)
    return jsonify(summary)
    return jsonify(summary)


@blueprint.route("/feedback", methods=["POST"])
def handle_feedback():
    """
    Receive user feedback (clicks, etc.) and update the online learning model.
    Payload:
    - user_id: str
    - item_id: str
    - reward: float (default 1.0 for click)
    - context: dict (optional snapshot of user context at time of action)
    """
    try:
        payload = request.get_json(force=True)
        user_id = payload.get("user_id")
        item_id = payload.get("item_id")
        reward = float(payload.get("reward", 1.0))
        # Context might be useful for more advanced bandits, but simple Thompson Sampling
        # often just updates the feature weights for the chosen arm.
        # For now, we'll pass it through.
        context = payload.get("context", {})

        if not user_id or not item_id:
            return jsonify({"error": "Missing user_id or item_id"}), 400

        from backend_nextgen.orchestrator import orchestrator
        orchestrator.handle_feedback(user_id, item_id, reward, context)
        
        return jsonify({"status": "success", "message": "Feedback received and model updated"})
    except Exception as e:
        current_app.logger.error(f"Feedback error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@blueprint.route("/preferences", methods=["POST"])
def save_preferences():
    """
    Save explicit user preferences (e.g., from onboarding).
    Payload:
    - user_id: str
    - preferences: dict (brands, categories, etc.)
    """
    try:
        payload = request.get_json(force=True)
        user_id = payload.get("user_id")
        prefs = payload.get("preferences", {})

        if not user_id or not prefs:
            return jsonify({"error": "Missing user_id or preferences"}), 400

        if preference_writer:
            # Construct payload for persistence
            # We map the frontend 'preferences' to the backend's expected structure
            # The backend expects 'entities' with keys like 'BRAND', 'CATEGORY'
            
            entity_buckets = {
                "BRAND": prefs.get("brands", []),
                "CATEGORY": prefs.get("categories", []),
                "PRICE_RANGE": prefs.get("price_range", [])
            }
            
            pref_payload = {
                "entities": entity_buckets,
                "query": "explicit_onboarding" # Marker for source
            }
            
            preference_writer(str(user_id), pref_payload)
            return jsonify({"status": "success", "message": "Preferences saved"})
        else:
            return jsonify({"error": "Preference writer not configured"}), 500
            
    except Exception as e:
        current_app.logger.error(f"Preferences error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
