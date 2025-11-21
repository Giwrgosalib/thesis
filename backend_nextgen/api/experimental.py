
"""
Experimental Flask blueprint hooking into the next-gen orchestrator.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from flask import Blueprint, current_app, jsonify, request

from backend_nextgen.orchestrator import NextGenAIOrchestrator

PreferenceWriter = Callable[[str, Dict[str, Any]], None]
PreferenceLoader = Callable[[str], Optional[Dict[str, Any]]]
preference_writer: Optional[PreferenceWriter] = None
preference_loader: Optional[PreferenceLoader] = None


def configure_preference_writer(writer: PreferenceWriter) -> None:
    """Allow the host application to register a user-preference persistence callback."""
    global preference_writer
    preference_writer = writer


def configure_preference_loader(loader: PreferenceLoader) -> None:
    """Allow the host application to register a user-preference retrieval callback."""
    global preference_loader
    preference_loader = loader


blueprint = Blueprint("nextgen_ai", __name__, url_prefix="/api/nextgen")
orchestrator = NextGenAIOrchestrator()


@blueprint.route("/query", methods=["POST"])
def handle_query():
    payload = request.get_json(force=True)
    query = payload.get("query", "")
    base_context = payload.get("user_context", {}) or {}
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

    result = orchestrator.handle_query(query, user_context)

    if preference_writer and user_id:
        try:
            preference_writer(str(user_id), result)
        except Exception as exc:  # noqa: BLE001
            current_app.logger.warning(
                "Preference writer failed for user %s: %s", user_id, exc, exc_info=True
            )

    return jsonify(result)


@blueprint.route("/metrics", methods=["GET"])
def metrics_summary():
    try:
        window = int(request.args.get("window", 3600))
    except ValueError:
        window = 3600
    summary = orchestrator.summarize_metrics(window_seconds=window)
    return jsonify(summary)
