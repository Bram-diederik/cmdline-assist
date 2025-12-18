#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_NAME="ha_control"
LOGS_DIR="$SCRIPT_DIR/logs"

# Create logs directory if it doesn't exist
mkdir -p "$LOGS_DIR"

# Kill old session if any
tmux kill-session -t "$SESSION_NAME" 2>/dev/null

# Check for .env file
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "No .env file found. Starting setup..."
    python3 "$SCRIPT_DIR/help_and_settings.py"
    
    if [ ! -f "$SCRIPT_DIR/.env" ]; then
        echo "Setup cancelled. Exiting."
        exit 1
    fi
fi

# Start top pane: dashboard.py (50% top)
tmux new-session -d -s "$SESSION_NAME" -n "Main" "python3 \"$SCRIPT_DIR/dashboard.py\""

# Split bottom pane: start a shell (interactive)
tmux split-window -v -t "$SESSION_NAME:0" -p 65

# Focus bottom pane
tmux select-pane -t "$SESSION_NAME:0.1"

# Start assist.py initially in bottom pane
tmux send-keys -t "$SESSION_NAME:0.1" "clear && python3 $SCRIPT_DIR/assist.py" C-m

# Disable status bar
tmux set -g status off

# --- Key Bindings ---

# F1: Help and Settings
tmux bind-key -n F1 run-shell "tmux send-keys -t $SESSION_NAME:0.1 exit C-m; sleep 0.5; tmux send-keys -t $SESSION_NAME:0.1 'clear && python3 $SCRIPT_DIR/help_and_settings.py && python3 $SCRIPT_DIR/assist.py' C-m"

# F2: Assist
tmux bind-key -n F2 run-shell "tmux send-keys -t $SESSION_NAME:0.1 exit C-m; sleep 0.5; tmux send-keys -t $SESSION_NAME:0.1 'clear && python3 $SCRIPT_DIR/assist.py' C-m"

# F3: HA Commander
tmux bind-key -n F3 run-shell "tmux send-keys -t $SESSION_NAME:0.1 exit C-m; sleep 0.5; tmux send-keys -t $SESSION_NAME:0.1 'clear && python3 $SCRIPT_DIR/ha_commander.py' C-m"

# F4: Capture logs - FIXED VERSION
tmux bind-key -n F4 run-shell "
    TIMESTAMP=\$(date +\"%Y%m%d_%H%M%S\")
    mkdir -p \"$LOGS_DIR\"
    
    # Capture dashboard pane
    tmux capture-pane -t \"$SESSION_NAME:0.0\" -S - -E - -p > \"$LOGS_DIR/dashboard_\${TIMESTAMP}.txt\" 2>/dev/null
    
    # Capture assist pane
    tmux capture-pane -t \"$SESSION_NAME:0.1\" -S -100 -p > \"$LOGS_DIR/assist_\${TIMESTAMP}.txt\" 2>/dev/null
    
    # Capture session info
    tmux list-windows -t \"$SESSION_NAME\" > \"$LOGS_DIR/session_info_\${TIMESTAMP}.txt\" 2>/dev/null
    
    # Show notification WITHOUT sending as input - use tmux display-message instead
    tmux display-message \"📋 Logs saved to $LOGS_DIR/\"
    
    # Alternative: Write a temporary message file and cat it
    echo \"📋 Logs saved to $LOGS_DIR/\" > /tmp/log_notice.txt
    tmux pipe-pane -t \"$SESSION_NAME:0.1\" \"cat /tmp/log_notice.txt && echo ''\"
"

# Load different dashboards in top pane
tmux bind-key -n F5 run-shell "tmux send-keys -t $SESSION_NAME:0.0 1"
tmux bind-key -n F6 run-shell "tmux send-keys -t $SESSION_NAME:0.0 2"
tmux bind-key -n F7 run-shell "tmux send-keys -t $SESSION_NAME:0.0 3"
tmux bind-key -n F8 run-shell "tmux send-keys -t $SESSION_NAME:0.0 4"

# Global Exit: Kill the entire session on Ctrl-C
tmux bind-key -n C-c kill-session -t "$SESSION_NAME"

# Attach session
tmux attach-session -t "$SESSION_NAME"
