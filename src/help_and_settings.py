
#!/usr/bin/env python3
"""
Simple Help and Settings TUI for HA CMDLine Assist
"""

import os
import sys
import json
import curses
import requests
import websocket
from pathlib import Path
from datetime import datetime
from dotenv import dotenv_values

# ==================== CONSTANTS ====================
HELP_TEXT = [
    "╔══════════════════════════════════════════════════════════════╗",
    "║                HA CMDLine Assist - Help                      ║",
    "╚══════════════════════════════════════════════════════════════╝",
    "",
    "KEY BINDINGS:",
    "├─ F1: This help & settings screen",
    "├─ F2: Assist - Voice assistant interface",
    "├─ F3: HA Commander - Advanced CLI for HA",
    "├─ F4: Dashboard 1 (Default)",
    "├─ F5: Dashboard 2",
    "├─ F6: Dashboard 3",
    "├─ F7: Dashboard 4",
    "└─ Ctrl+C: Exit current tool",
    "",
    "ASSIST FEATURES:",
    "• Type normally to talk to HA assistant",
    "• Type 'exit' or 'quit' to return to dashboard",
    "• Use !syscmd cli to switch to HA Commander",
    "• Use !syscmd assist to restart assist",
    "• Use --agent <agent_id> to specify different agent",
    "• Use -l to list available agents",
    "",
    "HA COMMANDER FEATURES:",
    "• <entity_id> - Show entity state",
    "• <entity_id> call <service> - Call service",
    "• <entity_id> attribute <attr> - Show attribute",
    "• <entity_id> full - Show all entity details",
    "• <entity_id> graph - Show historical graph",
    "• refresh - Refresh entity cache",
    "• status - Show cache status",
    "",
    "DASHBOARD FEATURES:",
    "• Press 1-4 to switch between dashboards",
    "• Press q to quit dashboard",
    "• Graphs show 24h history by default",
    "",
    "SETTINGS (.env file):",
    "Required:",
    "• HATOKEN: Your Home Assistant long-lived token",
    "• HAURL: Home Assistant URL (hostname:port)",
    "• SSL: 1 for HTTPS/WSS, 0 for HTTP/WS",
    "",
    "Optional:",
    "• DEFAULT_AGENT: Default agent ID for assist",
    "• GRAPH_WIDTH/GRAPH_HEIGHT: Graph dimensions",
    "• DASHBOARD_YAML_1-4: Dashboard config paths",
    "",
    "╔══════════════════════════════════════════════════════════════╗",
    "║                      TUI CONTROLS                            ║",
    "╚══════════════════════════════════════════════════════════════╝",
    "",
    "Navigation:",
    "• Tab: Switch between tabs (Help/Settings)",
    "• ↑/↓: Scroll/Select",
    "• Enter: Edit selected setting",
    "• A: Select agent from list",
    "• S: Save settings",
    "• T: Test connection",
    "• Q: Quit TUI",
    ""
]

# ==================== SETTINGS MANAGER ====================
class SettingsManager:
    def __init__(self, env_path=".env"):
        self.env_path = Path(env_path)
        self.settings = {}
        self.load_settings()
    
    def load_settings(self):
        """Load settings from .env file"""
        if self.env_path.exists():
            self.settings = dotenv_values(self.env_path)
        else:
            # Default settings
            self.settings = {
                "HATOKEN": "",
                "HAURL": "",
                "SSL": "0",
                "DEFAULT_AGENT": "",
                "GRAPH_WIDTH": "50",
                "GRAPH_HEIGHT": "15",
                "DASHBOARD_YAML_1": "yaml/dashboard1.yaml",
                "DASHBOARD_YAML_2": "yaml/dashboard2.yaml",
                "DASHBOARD_YAML_3": "yaml/dashboard3.yaml",
                "DASHBOARD_YAML_4": "yaml/dashboard4.yaml",
            }
    
    def save_settings(self):
        """Save settings to .env file"""
        # Create backup if exists
        if self.env_path.exists():
            backup = self.env_path.with_suffix('.env.backup')
            self.env_path.rename(backup)
        
        # Write new settings
        with open(self.env_path, 'w') as f:
            f.write("# HA CMDLine Assist Configuration\n")
            f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Required settings
            f.write("# REQUIRED SETTINGS\n")
            for key in ["HATOKEN", "HAURL", "SSL"]:
                f.write(f"{key}={self.settings.get(key, '')}\n")
            
            # Optional settings
            f.write("\n# OPTIONAL SETTINGS\n")
            if self.settings.get("DEFAULT_AGENT"):
                f.write(f"DEFAULT_AGENT={self.settings['DEFAULT_AGENT']}\n")
            f.write(f"GRAPH_WIDTH={self.settings.get('GRAPH_WIDTH', '50')}\n")
            f.write(f"GRAPH_HEIGHT={self.settings.get('GRAPH_HEIGHT', '15')}\n\n")
            
            # Dashboard configs
            f.write("# DASHBOARD CONFIGURATIONS\n")
            for i in range(1, 5):
                key = f"DASHBOARD_YAML_{i}"
                f.write(f"{key}={self.settings.get(key, f'yaml/dashboard{i}.yaml')}\n")
        
        return True
    
    def get_agents(self):
        """Get available agents from HA"""
        ha_token = self.settings.get("HATOKEN", "")
        ha_url = self.settings.get("HAURL", "")
        ssl = self.settings.get("SSL", "0") == "1"
        
        if not ha_token or not ha_url:
            return []
        
        try:
            # Create WebSocket connection
            protocol = "wss" if ssl else "ws"
            ws_url = f"{protocol}://{ha_url}/api/websocket"
            
            ws = websocket.WebSocket()
            ws.connect(ws_url, header={"Authorization": f"Bearer {ha_token}"})
            
            # Get auth message
            auth_req = json.loads(ws.recv())
            if auth_req.get("type") == "auth_required":
                # Authenticate
                ws.send(json.dumps({
                    "type": "auth",
                    "access_token": ha_token
                }))
                
                # Get auth response
                auth_resp = json.loads(ws.recv())
                if auth_resp.get("type") != "auth_ok":
                    ws.close()
                    return []
                
                # Request agents list
                ws.send(json.dumps({
                    "id": 1,
                    "type": "assist_pipeline/pipeline/list",
                }))
                
                # Get response
                response = json.loads(ws.recv())
                ws.close()
                
                if response.get("type") == "result" and response.get("success"):
                    agents = []
                    for pipeline in response.get("result", {}).get("pipelines", []):
                        agents.append({
                            "id": pipeline["id"],
                            "name": pipeline["name"],
                            "language": pipeline.get("language", "")
                        })
                    return agents
                
        except Exception:
            pass
        
        return []
    
    def test_connection(self):
        """Test HA connection"""
        ha_token = self.settings.get("HATOKEN", "")
        ha_url = self.settings.get("HAURL", "")
        ssl = self.settings.get("SSL", "0") == "1"
        
        if not ha_token:
            return False, "HATOKEN not set"
        if not ha_url:
            return False, "HAURL not set"
        
        try:
            # Test REST API
            protocol = "https" if ssl else "http"
            url = f"{protocol}://{ha_url}/api/"
            headers = {"Authorization": f"Bearer {ha_token}"}
            
            response = requests.get(url + "states", headers=headers, verify=False, timeout=5)
            if response.status_code != 200:
                return False, f"REST API failed: {response.status_code}"
            
            return True, f"Connected! Found {len(response.json())} entities"
            
        except Exception as e:
            return False, f"Error: {e}"

# ==================== AGENT SELECTOR DIALOG ====================
class AgentSelectorDialog:
    def __init__(self, parent_win, settings_manager):
        self.parent_win = parent_win
        self.settings_manager = settings_manager
        self.agents = []
        self.selected_idx = 0
        self.scroll_offset = 0
        self.result = None
    
    def show(self):
        """Show agent selection dialog and return selected agent ID or None"""
        # Get agents
        self.agents = self.settings_manager.get_agents()
        
        if not self.agents:
            return None
        
        # Get terminal size
        height, width = self.parent_win.getmaxyx()
        
        # Calculate dialog size
        dialog_height = min(len(self.agents) + 8, height - 4)
        dialog_width = min(70, width - 4)
        start_y = (height - dialog_height) // 2
        start_x = (width - dialog_width) // 2
        
        # Create dialog window
        dialog_win = curses.newwin(dialog_height, dialog_width, start_y, start_x)
        dialog_win.keypad(True)
        
        # Find current agent
        current_agent_id = self.settings_manager.settings.get("DEFAULT_AGENT", "")
        if current_agent_id:
            for i, agent in enumerate(self.agents):
                if agent["id"] == current_agent_id:
                    self.selected_idx = i
                    break
        
        # Main loop
        while True:
            dialog_win.erase()
            dialog_win.box()
            
            # Title
            title = " Select Default Agent "
            dialog_win.addstr(0, (dialog_width - len(title)) // 2, title, 
                            curses.A_BOLD | curses.color_pair(1))
            
            # Current selection
            if current_agent_id:
                for agent in self.agents:
                    if agent["id"] == current_agent_id:
                        current_text = f"Current: {agent['name']}"
                        dialog_win.addstr(1, 2, current_text, curses.color_pair(2))
                        break
            
            # Available agents
            dialog_win.addstr(2, 2, "Available Agents:", curses.color_pair(3))
            
            # Calculate visible range
            visible_height = dialog_height - 6
            if self.selected_idx < self.scroll_offset:
                self.scroll_offset = self.selected_idx
            elif self.selected_idx >= self.scroll_offset + visible_height:
                self.scroll_offset = self.selected_idx - visible_height + 1
            
            # Display agents
            for i in range(visible_height):
                agent_idx = i + self.scroll_offset
                if agent_idx < len(self.agents):
                    agent = self.agents[agent_idx]
                    y = 3 + i
                    
                    # Selection indicator
                    if agent_idx == self.selected_idx:
                        dialog_win.addstr(y, 2, "▶ ", curses.color_pair(2) | curses.A_BOLD)
                    else:
                        dialog_win.addstr(y, 2, "  ")
                    
                    # Agent name and ID
                    display_text = f"{agent['name']} ({agent['id']})"
                    if len(display_text) > dialog_width - 6:
                        display_text = display_text[:dialog_width - 9] + "..."
                    
                    if agent_idx == self.selected_idx:
                        dialog_win.addstr(y, 4, display_text, curses.color_pair(2) | curses.A_BOLD)
                    else:
                        dialog_win.addstr(y, 4, display_text)
            
            # Instructions
            instructions = "↑/↓:Select  Enter:Choose  0:Unset  ESC:Cancel"
            dialog_win.addstr(dialog_height - 2, 2, instructions, curses.color_pair(3))
            
            dialog_win.refresh()
            
            # Get input
            key = dialog_win.getch()
            
            if key == curses.KEY_UP:
                self.selected_idx = max(0, self.selected_idx - 1)
            elif key == curses.KEY_DOWN:
                self.selected_idx = min(len(self.agents) - 1, self.selected_idx + 1)
            elif key == ord('0'):
                self.result = ""
                break
            elif key == 10 or key == 13:  # Enter
                selected_agent = self.agents[self.selected_idx]
                self.result = selected_agent["id"]
                break
            elif key == 27:  # ESC
                self.result = None
                break
            elif key == curses.KEY_PPAGE:  # Page up
                self.selected_idx = max(0, self.selected_idx - visible_height)
            elif key == curses.KEY_NPAGE:  # Page down
                self.selected_idx = min(len(self.agents) - 1, self.selected_idx + visible_height)
        
        # Cleanup
        dialog_win.clear()
        del dialog_win
        self.parent_win.touchwin()
        
        return self.result

# ==================== TUI CLASS ====================
class HelpAndSettingsTUI:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.settings_manager = SettingsManager()
        self.current_tab = 0  # 0: Help, 1: Settings
        self.help_scroll = 0
        self.settings_scroll = 0
        self.selected_setting = 0
        self.message = ""
        self.message_type = 0  # 0: info, 1: success, 2: error
        self.message_time = 0
        self.init_colors()
        
    def init_colors(self):
        """Initialize color pairs"""
        curses.start_color()
        curses.use_default_colors()
        
        # Define color pairs
        curses.init_pair(1, curses.COLOR_CYAN, -1)      # Header
        curses.init_pair(2, curses.COLOR_GREEN, -1)     # Success/Selected
        curses.init_pair(3, curses.COLOR_YELLOW, -1)    # Warning/Required
        curses.init_pair(4, curses.COLOR_RED, -1)       # Error
        curses.init_pair(5, curses.COLOR_MAGENTA, -1)   # Tab active
        curses.init_pair(6, curses.COLOR_BLUE, -1)      # Tab inactive
    
    def show_message(self, msg, msg_type=0):
        """Show a temporary message"""
        self.message = msg
        self.message_type = msg_type
        self.message_time = 30  # Show for 30 frames (~3 seconds)
    
    def draw_header(self, height, width):
        """Draw the header with tabs"""
        # Draw top border
        self.stdscr.addstr(0, 0, "╔" + "═" * (width - 2) + "╗", curses.color_pair(1))
        
        # Draw title
        title = " HA CMDLine Assist - Help & Settings "
        title_x = max(0, (width - len(title)) // 2)
        self.stdscr.addstr(1, title_x, title, curses.color_pair(1) | curses.A_BOLD)
        
        # Draw tabs
        tabs = ["[ HELP ]", "[ SETTINGS ]"]
        tab_x = 2
        
        for i, tab in enumerate(tabs):
            if i == self.current_tab:
                color = curses.color_pair(5) | curses.A_BOLD
            else:
                color = curses.color_pair(6)
            
            self.stdscr.addstr(2, tab_x, tab, color)
            tab_x += len(tab) + 2
        
        # Draw bottom border
        self.stdscr.addstr(3, 0, "╚" + "═" * (width - 2) + "╝", curses.color_pair(1))
        
        # Draw controls
        controls = "Tab:Switch  ↑/↓:Scroll  Enter:Edit  A:Agent  S:Save  T:Test  Q:Quit"
        if len(controls) > width - 4:
            controls = controls[:width - 4]
        
        self.stdscr.addstr(4, 2, controls, curses.color_pair(3))
    
    def draw_help(self, start_y, height, width):
        """Draw scrollable help text"""
        content_height = height - start_y - 2
        max_scroll = max(0, len(HELP_TEXT) - content_height)
        
        # Adjust scroll
        if self.help_scroll > max_scroll:
            self.help_scroll = max_scroll
        
        # Display help text
        for i in range(content_height):
            line_idx = i + self.help_scroll
            if line_idx < len(HELP_TEXT):
                line = HELP_TEXT[line_idx]
                if len(line) > width - 2:
                    line = line[:width - 2]
                
                # Style certain lines
                if line.startswith("╔") or line.startswith("╚"):
                    style = curses.color_pair(1)
                elif line.startswith("├") or line.startswith("└"):
                    style = curses.color_pair(3)
                elif line.startswith("•"):
                    style = curses.color_pair(6)
                else:
                    style = curses.color_pair(0)
                
                self.stdscr.addstr(start_y + i, 1, line, style)
        
        # Draw scroll indicator
        if max_scroll > 0:
            scroll_pos = int((self.help_scroll / max_scroll) * (content_height - 1))
            self.stdscr.addstr(start_y + scroll_pos, width - 2, "█", curses.color_pair(3))
    
    def draw_settings(self, start_y, height, width):
        """Draw the settings editor"""
        settings_keys = list(self.settings_manager.settings.keys())
        content_height = height - start_y - 2
        max_scroll = max(0, len(settings_keys) - content_height)
        
        # Adjust scroll
        if self.settings_scroll > max_scroll:
            self.settings_scroll = max_scroll
        
        # Adjust selected setting
        if self.selected_setting >= len(settings_keys):
            self.selected_setting = len(settings_keys) - 1
        if self.selected_setting < 0:
            self.selected_setting = 0
        
        # Ensure selected setting is visible
        if self.selected_setting < self.settings_scroll:
            self.settings_scroll = self.selected_setting
        elif self.selected_setting >= self.settings_scroll + content_height:
            self.settings_scroll = self.selected_setting - content_height + 1
        
        # Display settings
        for i in range(content_height):
            idx = i + self.settings_scroll
            if idx < len(settings_keys):
                key = settings_keys[idx]
                value = self.settings_manager.settings.get(key, "")
                
                # Determine line position
                y = start_y + i
                
                # Determine if this is selected
                is_selected = (idx == self.selected_setting)
                
                # Determine style based on key type
                if key in ["HATOKEN", "HAURL", "SSL"]:
                    base_color = curses.color_pair(3)  # Required - yellow
                else:
                    base_color = curses.color_pair(0)  # Optional - default
                
                if is_selected:
                    style = base_color | curses.A_REVERSE
                else:
                    style = base_color
                
                # Format line
                if key == "HATOKEN" and value:
                    display_value = "****" + value[-4:] if len(value) > 4 else "****"
                elif key == "DEFAULT_AGENT" and not value:
                    display_value = "(unset)"
                else:
                    display_value = value or "(not set)"
                
                line = f"{key:20}: {display_value}"
                if len(line) > width - 2:
                    line = line[:width - 2]
                
                self.stdscr.addstr(y, 1, line, style)
        
        # Draw scroll indicator
        if max_scroll > 0:
            scroll_pos = int((self.settings_scroll / max_scroll) * (content_height - 1))
            self.stdscr.addstr(start_y + scroll_pos, width - 2, "█", curses.color_pair(3))
    
    def draw_message(self, height, width):
        """Draw message if any"""
        if self.message and self.message_time > 0:
            # Determine color based on message type
            if self.message_type == 1:  # Success
                color = curses.color_pair(2) | curses.A_BOLD
            elif self.message_type == 2:  # Error
                color = curses.color_pair(4) | curses.A_BOLD
            else:  # Info
                color = curses.color_pair(3) | curses.A_BOLD
            
            # Center the message
            msg = f" {self.message} "
            x = max(0, (width - len(msg)) // 2)
            y = height - 3
            
            # Draw message
            self.stdscr.addstr(y, x, msg, color)
            
            self.message_time -= 1
    
    def draw_footer(self, height, width):
        """Draw footer with status"""
        # Draw horizontal line
        self.stdscr.addstr(height - 2, 0, "─" * width, curses.color_pair(1))
        
        # Draw status
        if self.current_tab == 0:
            status = f"Help - Line {self.help_scroll + 1}/{len(HELP_TEXT)}"
        else:
            settings_keys = list(self.settings_manager.settings.keys())
            key = settings_keys[self.selected_setting] if self.selected_setting < len(settings_keys) else ""
            status = f"Settings - {key}"
            
            # Add connection status
            ha_url = self.settings_manager.settings.get("HAURL", "")
            if ha_url:
                status += f" | HA: {ha_url}"
        
        self.stdscr.addstr(height - 1, 0, status[:width], curses.color_pair(3) | curses.A_DIM)
    
    def draw(self):
        """Main draw function"""
        self.stdscr.clear()
        height, width = self.stdscr.getmaxyx()
        
        # Ensure minimum size
        if height < 20 or width < 60:
            self.stdscr.addstr(0, 0, "Terminal too small! Please resize to at least 60x20.", curses.color_pair(4))
            self.stdscr.refresh()
            return
        
        # Draw header (first 5 lines)
        self.draw_header(height, width)
        
        # Draw content based on current tab
        content_start = 6  # Start after header and controls
        
        if self.current_tab == 0:
            self.draw_help(content_start, height, width)
        else:
            self.draw_settings(content_start, height, width)
        
        # Draw message
        self.draw_message(height, width)
        
        # Draw footer
        self.draw_footer(height, width)
        
        self.stdscr.refresh()
    
    def get_input(self, prompt, default=""):
        """Get input from user in a popup"""
        height, width = self.stdscr.getmaxyx()
        
        # Create popup window
        popup_height = 5
        popup_width = min(60, width - 4)
        popup_y = (height - popup_height) // 2
        popup_x = (width - popup_width) // 2
        
        # Draw popup border
        popup_win = curses.newwin(popup_height, popup_width, popup_y, popup_x)
        popup_win.box()
        popup_win.addstr(0, 2, "┤ " + prompt + " ├", curses.color_pair(1))
        
        # Show default value
        if default:
            popup_win.addstr(2, 2, f"Current: {default}", curses.color_pair(3))
        
        # Get input
        popup_win.addstr(3, 2, "> ", curses.color_pair(2))
        popup_win.refresh()
        
        # Enable echo for input
        curses.echo()
        
        # Get input
        input_win = curses.newwin(1, popup_width - 6, popup_y + 3, popup_x + 4)
        input_str = ""
        
        while True:
            ch = input_win.getch()
            if ch == 10 or ch == 13:  # Enter
                break
            elif ch == 27:  # ESC
                input_str = default
                break
            elif ch == curses.KEY_BACKSPACE or ch == 127:
                if input_str:
                    input_str = input_str[:-1]
                    input_win.clear()
                    input_win.addstr(0, 0, input_str)
            elif 32 <= ch <= 126:
                input_str += chr(ch)
                input_win.clear()
                input_win.addstr(0, 0, input_str)
            
            input_win.refresh()
        
        # Restore echo settings
        curses.noecho()
        
        return input_str.strip()
    
    def select_agent(self):
        """Open agent selection dialog"""
        # Check if we have connection settings
        if not self.settings_manager.settings.get("HATOKEN") or not self.settings_manager.settings.get("HAURL"):
            self.show_message("Set HATOKEN and HAURL first", 2)
            return
        
        self.show_message("Fetching agents from HA...", 0)
        self.draw()
        
        # Create and show agent selector dialog
        selector = AgentSelectorDialog(self.stdscr, self.settings_manager)
        result = selector.show()
        
        if result is not None:
            if result == "":
                self.settings_manager.settings["DEFAULT_AGENT"] = ""
                self.show_message("DEFAULT_AGENT unset", 1)
            else:
                self.settings_manager.settings["DEFAULT_AGENT"] = result
                # Find agent name for message
                for agent in selector.agents:
                    if agent["id"] == result:
                        self.show_message(f"Agent set: {agent['name']}", 1)
                        break
        self.stdscr.refresh()
    
    def edit_setting(self):
        """Edit the currently selected setting"""
        settings_keys = list(self.settings_manager.settings.keys())
        if self.selected_setting >= len(settings_keys):
            return
        
        key = settings_keys[self.selected_setting]
        current_value = self.settings_manager.settings.get(key, "")
        
        # Special handling for DEFAULT_AGENT
        if key == "DEFAULT_AGENT":
            self.select_agent()
            return
        
        # Special handling for SSL
        if key == "SSL":
            new_value = self.get_input(f"Set {key} (0=HTTP/WS, 1=HTTPS/WSS)", current_value)
            if new_value in ["0", "1"]:
                self.settings_manager.settings[key] = new_value
                self.show_message(f"{key} updated to {new_value}", 1)
            else:
                self.show_message(f"Invalid value for {key}. Must be 0 or 1.", 2)
            return
        
        # Special handling for HATOKEN (mask input)
        if key == "HATOKEN":
            # Temporarily show the screen
            self.stdscr.clear()
            self.stdscr.addstr(0, 0, f"Enter new {key}:")
            if current_value:
                self.stdscr.addstr(1, 0, f"(Current ends with: ...{current_value[-4:]})")
            self.stdscr.addstr(3, 0, "> ")
            self.stdscr.refresh()
            
            # Get input without showing it
            curses.noecho()
            input_str = ""
            while True:
                ch = self.stdscr.getch()
                if ch == 10 or ch == 13:  # Enter
                    break
                elif ch == 27:  # ESC
                    input_str = current_value
                    break
                elif ch == curses.KEY_BACKSPACE or ch == 127:
                    if input_str:
                        input_str = input_str[:-1]
                        self.stdscr.addstr(3, 2, " " * (len(input_str) + 1))
                        self.stdscr.addstr(3, 2, "*" * len(input_str))
                elif 32 <= ch <= 126:
                    input_str += chr(ch)
                    self.stdscr.addstr(3, 2 + len(input_str) - 1, "*")
                
                self.stdscr.refresh()
            
            curses.echo()
            new_value = input_str.strip()
        else:
            # Normal input for other settings
            new_value = self.get_input(f"Set {key}", current_value)
        
        if new_value != current_value:
            self.settings_manager.settings[key] = new_value
            self.show_message(f"{key} updated", 1)
        self.stdscr.refresh()
    
    def test_connection(self):
        """Test HA connection"""
        self.show_message("Testing connection...", 0)
        self.draw()
        
        success, message = self.settings_manager.test_connection()
        
        if success:
            self.show_message(message, 1)
        else:
            self.show_message(message, 2)
        self.stdscr.refresh()
    
    def run(self):
        """Main TUI loop"""
        curses.curs_set(0)  # Hide cursor
        self.stdscr.nodelay(False)  # Make getch blocking
        self.stdscr.keypad(True)
        
        while True:
            self.draw()
            
            try:
                key = self.stdscr.getch()
                
                # Quit
                if key in [ord('q'), ord('Q'), 27]:  # q, Q, or ESC
                    # Break out of loop, let curses wrapper clean up
                    break
                
                # Tab navigation
                elif key == 9:  # Tab key
                    self.current_tab = 1 - self.current_tab
                    if self.current_tab == 1:
                        # Reset to first setting when switching to settings
                        self.selected_setting = 0
                        self.settings_scroll = 0
                
                # Help tab controls
                elif self.current_tab == 0:
                    if key == curses.KEY_UP:
                        self.help_scroll = max(0, self.help_scroll - 1)
                    elif key == curses.KEY_DOWN:
                        self.help_scroll = min(len(HELP_TEXT) - 1, self.help_scroll + 1)
                
                # Settings tab controls
                elif self.current_tab == 1:
                    if key == curses.KEY_UP:
                        self.selected_setting = max(0, self.selected_setting - 1)
                    elif key == curses.KEY_DOWN:
                        self.selected_setting = min(len(self.settings_manager.settings) - 1, 
                                                   self.selected_setting + 1)
                    elif key == 10 or key == 13:  # Enter key
                        self.edit_setting()
                    elif key == ord('s') or key == ord('S'):  # Save
                        if self.settings_manager.save_settings():
                            self.show_message("Settings saved to .env!", 1)
                    elif key == ord('t') or key == ord('T'):  # Test connection
                        self.test_connection()
                    elif key == ord('a') or key == ord('A'):  # Select agent
                        self.select_agent()
            
            except KeyboardInterrupt:
                break
        
        # Just break from loop, let curses wrapper handle cleanup
        return

# ==================== MAIN ====================
def main(stdscr=None):
    """Main function"""
    if stdscr is None:
        # Run in curses wrapper
        curses.wrapper(lambda scr: HelpAndSettingsTUI(scr).run())
    else:
        # Already in curses mode
        HelpAndSettingsTUI(stdscr).run()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="HA CMDLine Assist - Help & Settings")
    parser.add_argument("--test", action="store_true", help="Test HA connection")
    args = parser.parse_args()
    
    # Handle command line arguments
    if args.test:
        # Run without curses for command-line operations
        manager = SettingsManager()
        success, message = manager.test_connection()
        if success:
            print(f"✓ {message}")
        else:
            print(f"✗ {message}")
    else:
        # Check if .env exists, create if not
        if not Path(".env").exists():
            print("No .env file found. Creating default configuration...")
            manager = SettingsManager()
            manager.save_settings()
            print("Default .env created. Please configure your settings.")
        
        # Run the TUI
        main()
