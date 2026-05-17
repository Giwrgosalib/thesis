#!/bin/bash
# Start both Flask backends inside a single container.
# Legacy  → port 5000  (python backend/app.py)
# NextGen → port 5001  (python run_nextgen.py)

set -e

echo "[startup] Starting Legacy BiLSTM-CRF backend on :5000..."
PORT=5000 python backend/app.py &
LEGACY_PID=$!

echo "[startup] Starting NextGen DeBERTa backend on :5001..."
PORT=5001 python run_nextgen.py &
NEXTGEN_PID=$!

echo "[startup] Both backends running (legacy=$LEGACY_PID nextgen=$NEXTGEN_PID)"

# Keep container alive; exit cleanly if either process dies
wait -n $LEGACY_PID $NEXTGEN_PID
EXIT_CODE=$?
echo "[startup] A backend process exited (code $EXIT_CODE) — shutting down."
kill $LEGACY_PID $NEXTGEN_PID 2>/dev/null || true
exit $EXIT_CODE
