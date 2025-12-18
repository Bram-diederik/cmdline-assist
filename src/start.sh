#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION_NAME="ha_control"

# Kill old session if any
tmux kill-session -t "$SESSION_NAME" 2>/dev/null

# Start top pane: dashboard.py (50% top)
tmux new-session -d -s "$SESSION_NAME" -n "Main" "python3 \"$SCRIPT_DIR/dashboard.py\""

# Split bottom pane: start a shell (interactive)
tmux split-window -v -t "$SESSION_NAME:0" -p 50

# Focus bottom pane
tmux select-pane -t "$SESSION_NAME:0.1"

# Start assist.py initially in bottom pane
tmux send-keys -t "$SESSION_NAME:0.1" "clear && python3 $SCRIPT_DIR/assist.py" C-m

# Disable status bar
tmux set -g status off

# --- Key Bindings ---

# Switch tools in the bottom pane
tmux bind-key -n F1 run-shell "tmux send-keys -t $SESSION_NAME:0.1 exit C-m; sleep 1; tmux send-keys -t $SESSION_NAME:0.1 'clear && python3 $SCRIPT_DIR/assist.py' C-m"
tmux bind-key -n F2 run-shell "tmux send-keys -t $SESSION_NAME:0.1 exit C-m; sleep 1; tmux send-keys -t $SESSION_NAME:0.1 'clear && python3 $SCRIPT_DIR/ha_commander.py' C-m"

# Load different dashboards in top pane
tmux bind-key -n F5 run-shell "tmux send-keys -t $SESSION_NAME:0.0 1"
tmux bind-key -n F6 run-shell "tmux send-keys -t $SESSION_NAME:0.0 2"
tmux bind-key -n F7 run-shell "tmux send-keys -t $SESSION_NAME:0.0 3"
tmux bind-key -n F8 run-shell "tmux send-keys -t $SESSION_NAME:0.0 4"

# Global Exit: Kill the entire session on Ctrl-C
tmux bind-key -n C-c kill-session -t "$SESSION_NAME"

# Attach session
tmux attach-session -t "$SESSION_NAME"
