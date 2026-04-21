#!/bin/bash
# Start both Flask backends inside a single container.
# Legacy  → port 5000
# NextGen → port 5001

set -e

echo "[startup] Starting Legacy BiLSTM-CRF backend on :5000..."
python backend/app.py &
LEGACY_PID=$!

echo "[startup] Starting NextGen DeBERTa backend on :5001..."
python run_nextgen.py &
NEXTGEN_PID=$!

echo "[startup] Both backends running (PIDs: legacy=$LEGACY_PID nextgen=$NEXTGEN_PID)"

# Keep container alive; exit if either process dies
wait -n $LEGACY_PID $NEXTGEN_PID
echo "[startup] A backend process exited — shutting down container."
kill $LEGACY_PID $NEXTGEN_PID 2>/dev/null || true
