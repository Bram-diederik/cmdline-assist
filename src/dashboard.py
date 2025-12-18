#!/usr/bin/env python3

import asyncio
import json
import os
import ssl
import yaml
import requests
import websockets
import threading
import sys
import termios
import tty
import re
from datetime import datetime, timedelta, timezone
from dateutil.parser import isoparse

from dotenv import load_dotenv
from jinja2 import Environment, BaseLoader

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.columns import Columns
from rich.live import Live
from rich.table import Table
from rich.align import Align
from rich.box import ROUNDED
from rich.layout import Layout

# -------------------- ENV --------------------

load_dotenv()

HAURL = os.getenv("HAURL")
HATOKEN = os.getenv("HATOKEN")
SSL_VERIFY = bool(int(os.getenv("SSL", 1)))

# Base URLs
BASE_URL = f"{'https' if SSL_VERIFY else 'http'}://{HAURL}/api"
WS_URL = f"{'wss' if SSL_VERIFY else 'ws'}://{HAURL}/api/websocket"

DASHBOARD_YAML_1 = os.getenv("DASHBOARD_YAML_1", "yaml/dashboard1.yaml")
DASHBOARD_YAML_2 = os.getenv("DASHBOARD_YAML_2", "yaml/dashboard2.yaml")
DASHBOARD_YAML_3 = os.getenv("DASHBOARD_YAML_3", "yaml/dashboard3.yaml")
DASHBOARD_YAML_4 = os.getenv("DASHBOARD_YAML_4", "yaml/dashboard4.yaml")

console = Console()
current_states = {}
layout_config = []

jinja_env = Environment(loader=BaseLoader())

# -------------------- JINJA --------------------

def ha_jinja_render(template_str, entity_id):
    # Exit if template is empty
    if not template_str:
        return ""
    
    data = current_states.get(entity_id)

    # Helper to mimic Home Assistant states() function
    def states_helper(eid):
        state_data = current_states.get(eid)
        if state_data:
            return state_data.get("state", "unknown")
        return "unknown"

    # Helper to mimic Home Assistant state_attr() function
    def state_attr_helper(eid, attr):
        state_data = current_states.get(eid)
        if state_data:
            return state_data.get("attributes", {}).get(attr, None)
        return None

    try:
        template = jinja_env.from_string(template_str)
        return template.render(
            state=data.get("state") if data else "unknown",
            attributes=data.get("attributes", {}) if data else {},
            states=states_helper,
            state_attr=state_attr_helper
        )
    except Exception as e:
        return f"Jinja error: {e}"

# -------------------- CONFIG --------------------

def load_config_file(file_path):
    global layout_config
    # We no longer overwrite DASHBOARD_YAML_1 here.
    # This ensures the key_listener always uses the original paths from .env
    
    if not os.path.exists(file_path):
        return []
        
    with open(file_path, "r") as f:
        cfg = yaml.safe_load(f)
    
    layout_config = cfg.get("layout", [])
    entity_ids = set()

    # Regex to find entity IDs hidden in Jinja strings (e.g. sensor.xyz)
    entity_pattern = re.compile(r"[a-z0-9_]+\.[a-z0-9_]+")

    def walk(cards):
        for c in cards:
            # 1. Direct entity keys
            eid = c.get("entity") or c.get("entity_id")
            if eid:
                entity_ids.add(eid)
            
            # 2. Extract entities from all string values
            for key, value in c.items():
                if isinstance(value, str):
                    matches = entity_pattern.findall(value)
                    for match in matches:
                        if "." in match:
                            entity_ids.add(match)

            if "cards" in c:
                walk(c["cards"])

    walk(layout_config)
    
    for eid in entity_ids:
        if eid not in current_states:
            current_states[eid] = None
            
    return list(entity_ids)

# -------------------- HA STATE --------------------

def fetch_initial_states(entity_ids):
    headers = {"Authorization": f"Bearer {HATOKEN}"}
    try:
        r = requests.get(f"{BASE_URL}/states", headers=headers, verify=SSL_VERIFY, timeout=10)
        r.raise_for_status()
        for s in r.json():
            if s["entity_id"] in entity_ids:
                current_states[s["entity_id"]] = s
    except Exception:
        pass

# -------------------- HISTORY --------------------

def parse_time_arg(arg: str):
    # Ensure we are working with a clean string
    if not arg or not isinstance(arg, str):
        return datetime.now(timezone.utc) - timedelta(hours=24)
    
    arg = arg.strip()
    now = datetime.now(timezone.utc)

    if arg.startswith("-"):
        try:
            # Extract number and unit (e.g., -24h -> 24 and h)
            unit = arg[-1]
            num = int(arg[1:-1])
            
            if unit == "h": return now - timedelta(hours=num)
            if unit == "d": return now - timedelta(days=num)
            if unit == "m": return now - timedelta(minutes=num)
        except Exception as e:
            # Log error if needed: print(f"Error parsing time: {e}")
            pass
            
    return now - timedelta(hours=24)


def fetch_history(entity_id, begin="-24h", end=None):
    start_time = parse_time_arg(begin)
    end_time = parse_time_arg(end) if end else datetime.now(timezone.utc)
    
    try:
        url = f"{BASE_URL}/history/period/{start_time.isoformat()}"
        headers = {"Authorization": f"Bearer {HATOKEN}"}
        params = {
            "filter_entity_id": entity_id,  
            "end_time": end_time.isoformat(),
            "minimal_response": ""
        }
        r = requests.get(url, headers=headers, params=params, verify=SSL_VERIFY, timeout=10)
        r.raise_for_status()
        data = r.json()
        
        if data and isinstance(data, list) and len(data) > 0:
            return sorted(data[0], key=lambda x: x.get("last_updated", ""))
        return []
    except Exception:
        return []

# -------------------- GRAPH --------------------

def ascii_graph(history, width=30, height=3, attribute=None):
    if not history:
        return "(no data)"
    
    values = []
    times = []
    for h in history:
        try:
            # If attribute is specified, get it from the attributes dict
            if attribute:
                val = h.get("attributes", {}).get(attribute)
            else:
                val = h.get("state")
            
            v = float(val)
            values.append(v)
            times.append(h.get("last_updated", ""))
        except (ValueError, TypeError):
            continue

    if not values:
        return "(no numeric data)"
    
    if len(values) == 1:
        values = [values[0], values[0]]
        times = [times[0], times[0]]

    n = len(values)
    scaled_values = []
    for i in range(width):
        pos = i * (n - 1) / (width - 1)
        left = int(pos)
        right = min(left + 1, n - 1)
        frac = pos - left
        interp_val = values[left] * (1 - frac) + values[right] * frac
        scaled_values.append(interp_val)

    mn, mx = min(values), max(values)
    span = mx - mn or 1
    
    rows = []
    for y in reversed(range(height)):
        if y == height - 1: label = f"{mx:>6.1f} ┐"
        elif y == 0: label = f"{mn:>6.1f} ┘"
        else: label = "       │"
            
        row = "".join("█" if ((v - mn) / span * (height - 1)) >= y else " " for v in scaled_values)
        rows.append(label + row)

    return "\n".join(rows)

def create_graph_card(entity_id, card):
    w = int(card.get("width", 40))
    h = int(card.get("height", 3))
    attr = card.get("attribute") # Get attribute key from YAML
    
    hist = fetch_history(entity_id, begin=card.get("begin", "-24h"))
    
    if not hist:
        curr = current_states.get(entity_id)
        if curr: hist = [curr]
        else: return Panel("Loading history...", title=entity_id)

    # Pass the attribute to the graph renderer
    graph_str = ascii_graph(hist, width=w, height=h, attribute=attr)
    title = card.get("title", entity_id)
    
    return Panel(
        Text(graph_str, style="cyan"),
        title=f"📈 {title}",
        border_style="green",
        box=ROUNDED,
        padding=(0, 1),
        expand=False
    )

# -------------------- UI --------------------

def create_entity_card(entity_id, card):
    data = current_states.get(entity_id)
    if not data:
        return Panel("Pending…", title=entity_id)

    state = data.get("state", "unknown")
    title = card.get("title", card.get("name", entity_id))
    icon = card.get("icon", "📊")
    secondary = ha_jinja_render(card.get("secondary_info", ""), entity_id)

    body = Text()
    body.append(state.upper() + "\n", style="bold cyan")
    if secondary: body.append(secondary, style="dim")

    return Panel(
        Align.center(body, vertical="middle"),
        title=f"{icon} {title}",
        border_style="blue" if state not in ["off", "unavailable"] else "white",
        box=ROUNDED,
        padding=(0, 1),
    )

def build_layout(cards):
    out = []
    for card in cards:
        t = card.get("type", "entity")
        eid = card.get("entity") or card.get("entity_id")
        
        if t == "graph" and eid:
            out.append(create_graph_card(eid, card))
        elif t == "horizontal-stack":
            cols = build_layout(card.get("cards", []))
            if cols: out.append(Columns(cols, expand=True))
        elif t == "vertical-stack":
            out.extend(build_layout(card.get("cards", [])))
        elif eid:
            out.append(create_entity_card(eid, card))
    return out

# -------------------- DASHBOARD --------------------

def generate_dashboard():
    elements = build_layout(layout_config)
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body", ratio=1),
    )
    layout["header"].update(
        Panel(Align.center("🏠 HA CLI Dashboard", vertical="middle"), box=ROUNDED, style="bold blue")
    )
    grid = Table.grid(expand=True)
    for e in elements:
        grid.add_row(e)
    layout["body"].update(grid)
    return layout

# -------------------- WEBSOCKET --------------------

async def ws_handler():
    ctx = ssl.create_default_context() if SSL_VERIFY else None
    try:
        async with websockets.connect(WS_URL, ssl=ctx) as ws:
            await ws.recv()
            await ws.send(json.dumps({"type": "auth", "access_token": HATOKEN}))
            async for msg in ws:
                data = json.loads(msg)
                if data.get("type") == "auth_ok":
                    await ws.send(json.dumps({"id": 1, "type": "subscribe_events", "event_type": "state_changed"}))
                if data.get("type") == "event":
                    ev = data["event"]["data"]
                    eid = ev["entity_id"]
                    if eid in current_states:
                        current_states[eid] = ev["new_state"]
    except: pass

# -------------------- KEY HANDLER --------------------

def key_listener():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch == "1":
                ids = load_config_file(DASHBOARD_YAML_1)
                fetch_initial_states(ids)
            elif ch == "2":
                ids = load_config_file(DASHBOARD_YAML_2)
                fetch_initial_states(ids)
            elif ch == "3":
                ids = load_config_file(DASHBOARD_YAML_3)
                fetch_initial_states(ids)
            elif ch == "4":
                ids = load_config_file(DASHBOARD_YAML_4)
                fetch_initial_states(ids)
            elif ch.lower() == "q": os._exit(0)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

# -------------------- MAIN --------------------

async def main():
    entity_ids = load_config_file(DASHBOARD_YAML_1)
    fetch_initial_states(entity_ids)
    
    threading.Thread(target=key_listener, daemon=True).start()
    ws_task = asyncio.create_task(ws_handler())

    with Live(generate_dashboard(), console=console, screen=True, auto_refresh=False) as live:
        try:
            while True:
                live.update(generate_dashboard(), refresh=True)
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            ws_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
