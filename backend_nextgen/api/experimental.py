
"""
Experimental Flask blueprint hooking into the next-gen orchestrator.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from flask import Blueprint, current_app, jsonify, request, Response, stream_with_context
import json

# ... (imports remain same)

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

    def generate():
        try:
            for event in orchestrator.handle_query_stream(query, user_context, limit=limit, offset=offset):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            current_app.logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')


@blueprint.route("/metrics", methods=["GET"])
def metrics_summary():
    try:
        window = int(request.args.get("window", 3600))
    except ValueError:
        window = 3600
    summary = orchestrator.summarize_metrics(window_seconds=window)
    return jsonify(summary)
