#!/bin/bash
SESSION_NAME="ha_control"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="$SCRIPT_DIR/logs"

mkdir -p "$LOGS_DIR"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

tmux capture-pane -t "$SESSION_NAME:0.0" -S - -E - -p > "$LOGS_DIR/dashboard_${TIMESTAMP}.txt" 2>/dev/null
tmux capture-pane -t "$SESSION_NAME:0.1" -S -100 -p > "$LOGS_DIR/assist_${TIMESTAMP}.txt" 2>/dev/null
tmux list-windows -t "$SESSION_NAME" > "$LOGS_DIR/session_info_${TIMESTAMP}.txt" 2>/dev/null
tmux send-keys -t "$SESSION_NAME:0.1" "echo '📋 Logs saved to logs/ folder' && echo ''" C-m

echo "✅ Logs captured to $LOGS_DIR/"
