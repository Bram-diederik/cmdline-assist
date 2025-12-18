#!/usr/bin/env python3
"""
Home Assistant CLI with improved graphing
"""

import os
import time
import requests
from dataclasses import dataclass
from typing import Dict, List
from datetime import datetime, timedelta, timezone
from dateutil.parser import isoparse

from dotenv import load_dotenv
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

# -------------------- ENV --------------------
load_dotenv()

HAURL = os.getenv("HAURL")
HATOKEN = os.getenv("HATOKEN")
SSL_VERIFY = bool(int(os.getenv("SSL", 1)))

GRAPH_WIDTH = int(os.getenv("GRAPH_WIDTH", 50))
GRAPH_HEIGHT = int(os.getenv("GRAPH_HEIGHT", 8))

REST_URL = f"{'https' if SSL_VERIFY else 'http'}://{HAURL}/api"

# -------------------- DATA --------------------
@dataclass
class Entity:
    entity_id: str
    domain: str
    state: str
    attributes: dict
    friendly_name: str

@dataclass
class Service:
    domain: str
    service: str
    description: str

# -------------------- CACHE --------------------
class Cache:
    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.services: Dict[str, List[Service]] = {}
        self.updated = 0
        self.ttl = 300

    def stale(self):
        return time.time() - self.updated > self.ttl

cache = Cache()

# -------------------- API --------------------
def headers():
    return {
        "Authorization": f"Bearer {HATOKEN}",
        "Content-Type": "application/json",
    }

def fetch_entities():
    try:
        r = requests.get(f"{REST_URL}/states", headers=headers(), verify=SSL_VERIFY, timeout=10)
        r.raise_for_status()
        cache.entities = {}
        for s in r.json():
            eid = s["entity_id"]
            cache.entities[eid] = Entity(
                entity_id=eid,
                domain=eid.split(".", 1)[0],
                state=s["state"],
                attributes=s["attributes"],
                friendly_name=s["attributes"].get("friendly_name", eid),
            )
        cache.updated = time.time()
    except Exception as e:
        print(f"Error fetching entities: {e}")

def fetch_services():
    try:
        r = requests.get(f"{REST_URL}/services", headers=headers(), verify=SSL_VERIFY, timeout=10)
        r.raise_for_status()
        cache.services = {}
        for item in r.json():
            domain = item["domain"]
            cache.services[domain] = []
            for name, info in item["services"].items():
                cache.services[domain].append(
                    Service(domain, name, info.get("description", ""))
                )
    except Exception as e:
        print(f"Error fetching services: {e}")

def call_service(domain, service, entity_id, **data):
    try:
        r = requests.post(
            f"{REST_URL}/services/{domain}/{service}",
            headers=headers(),
            json={"entity_id": entity_id, **data},
            verify=SSL_VERIFY,
            timeout=10
        )
        r.raise_for_status()
        return True, f"✓ {domain}.{service} called"
    except requests.exceptions.RequestException as e:
        return False, f"✗ Error calling {domain}.{service}: {e}"

# -------------------- HISTORY --------------------
def parse_time_arg(arg: str):
    """Parse time argument like '-2h', '-3d', or ISO string"""
    now = datetime.now(timezone.utc)
    if arg.startswith("-"):
        try:
            num, unit = int(arg[1:-1]), arg[-1]
            if unit == "h":
                return now - timedelta(hours=num)
            elif unit == "d":
                return now - timedelta(days=num)
            elif unit == "m":
                return now - timedelta(minutes=num)
        except Exception:
            return now - timedelta(hours=24)
    else:
        try:
            return datetime.fromisoformat(arg)
        except ValueError:
            return now - timedelta(hours=24)
    return now - timedelta(hours=24)

def fetch_history(entity_id, begin="-24h", end=None):
    start_time = parse_time_arg(begin)
    end_time = parse_time_arg(end) if end else datetime.now(timezone.utc)
    try:
        r = requests.get(
            f"{REST_URL}/history/period/{start_time.isoformat()}",
            headers=headers(),
            params={"filter_entity_id": entity_id, "end_time": end_time.isoformat()},
            verify=SSL_VERIFY,
            timeout=10
        )
        r.raise_for_status()
        data = r.json()
        return data[0] if data else []
    except Exception as e:
        print(f"Error fetching history: {e}")
        return []

# -------------------- GRAPH --------------------
from datetime import datetime, timedelta
from dateutil.parser import isoparse
import math

def human_delta(td: timedelta) -> str:
    """Convert timedelta to human-readable string"""
    total_seconds = int(td.total_seconds())
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 and days == 0:  # show minutes only if less than a day
        parts.append(f"{minutes}m")
    if seconds > 0 and days == 0 and hours == 0:  # show seconds only if <1h
        parts.append(f"{seconds}s")

    return " ".join(parts) if parts else "0s"

def nice_delta(td: timedelta) -> timedelta:
    """
    Round timedelta to a “nice” human-friendly value.
    Example: 6h 25m -> 6h, 1h42m -> 2h, 125m -> 2h
    """
    total_seconds = td.total_seconds()
    if total_seconds >= 86400:  # more than a day
        days = round(total_seconds / 86400)
        return timedelta(days=days)
    elif total_seconds >= 3600:  # more than an hour
        hours = round(total_seconds / 3600)
        return timedelta(hours=hours)
    elif total_seconds >= 60:  # more than a minute
        minutes = round(total_seconds / 60)
        return timedelta(minutes=minutes)
    else:
        return timedelta(seconds=round(total_seconds))

# -------------------- GRAPH --------------------

def human_delta(td: timedelta) -> str:
    total_seconds = int(td.total_seconds())
    days, rem = divmod(total_seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 and days == 0:
        parts.append(f"{minutes}m")
    if seconds > 0 and days == 0 and hours == 0:
        parts.append(f"{seconds}s")

    return " ".join(parts) if parts else "0s"

def nice_delta(td: timedelta) -> timedelta:
    total_seconds = td.total_seconds()
    if total_seconds >= 86400:
        return timedelta(days=round(total_seconds / 86400))
    elif total_seconds >= 3600:
        return timedelta(hours=round(total_seconds / 3600))
    elif total_seconds >= 60:
        return timedelta(minutes=round(total_seconds / 60))
    else:
        return timedelta(seconds=round(total_seconds))

def ascii_graph(history, width=GRAPH_WIDTH, height=GRAPH_HEIGHT, num_markers=5):
    if not history:
        return "(no data)"

    values = []
    times = []
    for h in history:
        try:
            values.append(float(h["state"]))
        except (ValueError, TypeError, KeyError):
            values.append(0.0)
        times.append(h.get("last_updated", ""))

    n = len(values)
    if n == 0:
        return "(no numeric data)"

    # Interpolate to width
    scaled_values = []
    scaled_times = []
    for i in range(width):
        pos = i * (n - 1) / (width - 1)
        left = int(pos)
        right = min(left + 1, n - 1)
        frac = pos - left
        interp_val = values[left] * (1 - frac) + values[right] * frac
        scaled_values.append(interp_val)
        scaled_times.append(times[left])

    mn, mx = min(scaled_values), max(scaled_values)
    span = mx - mn or 1
    scaled_height = [int((v - mn) / span * (height - 1)) for v in scaled_values]

    label_width = max(len(f"{mx:.2f}"), len(f"{mn:.2f}")) + 2
    rows = []
    for y in reversed(range(height)):
        val = mn + (span * y / (height - 1))
        label = f"{val:>{label_width}.2f} │"
        row = "".join("█" if v >= y else " " for v in scaled_height)
        rows.append(label + row)

    # Markers
    markers = [" "] * width
    step = max(1, width // (num_markers - 1))
    marker_positions = list(range(0, width, step))[:num_markers]
    for pos in marker_positions:
        markers[pos] = "#"
    marker_row = " " * (label_width + 2) + "".join(markers)

    marker_times = [scaled_times[pos] for pos in marker_positions if pos < len(scaled_times)]
    dt_values = [isoparse(t) for t in marker_times if t]
    if len(dt_values) > 1:
        raw_delta = dt_values[1] - dt_values[0]
        delta = nice_delta(raw_delta)
    else:
        delta = timedelta(0)

    begin_time = dt_values[0].strftime("%Y-%m-%d %H:%M") if dt_values else ""
    end_time = dt_values[-1].strftime("%Y-%m-%d %H:%M") if dt_values else ""
    delta_human = human_delta(delta)

    bottom = " " * label_width + " └" + "─" * width
    info_rows = [
        f"begin time: {begin_time}",
        f"end time:   {end_time}",
        f"# delta:     {delta_human}"
    ]

    return "\n".join(rows + [bottom, marker_row] + info_rows)


# -------------------- COMPLETER --------------------
class HACompleter(Completer):
    def get_completions(self, doc: Document, _):
        if cache.stale():
            fetch_entities()
            fetch_services()

        text = doc.text_before_cursor
        words = text.split()
        last_word = text.split()[-1] if text.strip() else ""

        # Complete first word (entity)
        if len(words) <= 1:
            for eid, e in cache.entities.items():
                if last_word.lower() in eid.lower():
                    yield Completion(eid, -len(last_word),
                                     display=f"{e.friendly_name} ({eid})")

        # Complete second word (call, attribute, full, graph)
        if len(words) == 2 or (len(words) == 1 and text.endswith(" ")):
            if words[0] in cache.entities:
                for v in ("call", "attribute", "full", "graph"):
                    if v.startswith(last_word):
                        yield Completion(v, -len(last_word))

        # Complete service after 'call'
        if len(words) >= 2 and words[1] == "call":
            domain = words[0].split(".", 1)[0]
            for s in cache.services.get(domain, []):
                partial = words[2] if len(words) > 2 else ""
                if s.service.startswith(partial):
                    yield Completion(s.service, -len(partial))

        # Complete attribute after 'attribute'
        if len(words) >= 2 and words[1] == "attribute":
            entity = cache.entities.get(words[0])
            if entity:
                partial = words[2] if len(words) > 2 else ""
                for a in entity.attributes:
                    if a.startswith(partial):
                        yield Completion(a, -len(partial))

# -------------------- EXECUTION --------------------
def parse(v):
    if v.isdigit():
        return int(v)
    try:
        return float(v)
    except ValueError:
        return v.strip("\"'")

def execute(cmd):
    try:
        if not cmd:
            return ""

        if cmd in ("exit", "quit"):
            return "EXIT"

        if cmd == "help":
            return HELP

        if cmd == "refresh":
            fetch_entities()
            fetch_services()
            return "✓ cache refreshed"

        if cmd == "status":
            return f"{len(cache.entities)} entities, {len(cache.services)} domains"

        parts = cmd.split()
        eid = parts[0]

        if eid not in cache.entities:
            return "unknown entity"

        entity = cache.entities[eid]

        # Default: state + timestamp
        if len(parts) == 1:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            return f"{entity.friendly_name} ({eid})\nState: {entity.state}\nTime: {ts}"

        # Full
        if len(parts) == 2 and parts[1] == "full":
            out = [f"{entity.friendly_name} ({eid})", f"State: {entity.state}", "Attributes:"]
            for k, v in entity.attributes.items():
                out.append(f"  {k}: {v}")
            return "\n".join(out)

        # Graph with optional begin/end
        if len(parts) >= 2 and parts[1] == "graph":
            begin = None
            end = None
            for p in parts[2:]:
                if p.startswith("begin="):
                    begin = p.split("=",1)[1]
                if p.startswith("end="):
                    end = p.split("=",1)[1]
            hist = fetch_history(eid, begin=begin or "-24h", end=end)
            return ascii_graph(hist)

        # Attribute
        if len(parts) >= 3 and parts[1] == "attribute":
            attr = parts[2]
            if attr not in entity.attributes:
                return "no such attribute"
            if len(parts) == 3:
                return str(entity.attributes[attr])
            if len(parts) == 4 and parts[3] == "graph":
                hist = fetch_history(eid)
                vals = [h["attributes"].get(attr) for h in hist if attr in h["attributes"]]
                return ascii_graph(vals)

        # Call
        if len(parts) >= 3 and parts[1] == "call":
            service = parts[2]
            domain = entity.domain
            data = {}
            for p in parts[3:]:
                if "=" in p:
                    k, v = p.split("=", 1)
                    data[k] = parse(v)
            success, msg = call_service(domain, service, eid, **data)
            return msg

        return "invalid command"
    except Exception as e:
        return f"Error executing command: {e}"

# -------------------- HELP --------------------
HELP = """
<entity>
<entity> call <service> [key=value]
<entity> attribute <attribute> [graph]
<entity> full
<entity> graph [begin=-2h|-2d|ISO] [end=-1h|ISO]

refresh | status | exit
"""

# -------------------- MAIN --------------------
def main():
    print("Home Assistant CLI\n")
    fetch_entities()
    fetch_services()

    session = PromptSession(
        completer=HACompleter(),
        complete_while_typing=True,
        style=Style.from_dict({"": "#ffffff"}),
    )

    bindings = KeyBindings()
    @bindings.add("c-c")
    def _(e):
        e.app.current_buffer.text = ""

    while True:
        try:
            cmd = session.prompt("HA> ", key_bindings=bindings)
            out = execute(cmd)
            if out == "EXIT":
                break
            if out:
                print(out, "\n")
        except (KeyboardInterrupt, EOFError):
            break

if __name__ == "__main__":
    main()
