#!/usr/bin/env python3
import websocket
import json
import threading
import signal
import sys
from dotenv import load_dotenv
import os
import argparse
from pathlib import Path
import tempfile

# Globals
message_id_counter = 1
conversation_id = None
conversation_id_override = None
conversation_file_path = None
response_received_event = threading.Event()
interactive_thread = None
ws = None
should_exit = False
list_agents_mode = False
args = None

# Conversation ID file logic
def load_conversation_id():
    global conversation_id_override, conversation_file_path
    if conversation_id_override:
        conversation_file_path = Path(tempfile.gettempdir()) / f"assist_conversation_{conversation_id_override}.txt"
        if conversation_file_path.exists():
            return conversation_file_path.read_text().strip()
    return None

def save_conversation_id(conv_id):
    global conversation_file_path
    if conversation_file_path:
        conversation_file_path.write_text(conv_id)

# Env
def load_environment_variables(env_path=None):
    if env_path:
        env_file_path = env_path
    else:
        env_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '.env')

    if not os.path.isfile(env_file_path):
        print(f"Error: .env file not found at {env_file_path}", file=sys.stderr)
        sys.exit(1)

    load_dotenv(env_file_path)

def generate_message_id():
    global message_id_counter
    message_id = message_id_counter
    message_id_counter += 1
    return message_id

# WebSocket event handlers
def on_message(ws, message):
    global conversation_id

    try:
        message_data = json.loads(message)

        if message_data.get("type") == "auth_required":
            authenticate(ws)

        elif message_data.get("type") == "auth_ok":
            if list_agents_mode:
                ws.send(json.dumps({
                    "id": generate_message_id(),
                    "type": "assist_pipeline/pipeline/list",
                }))
            elif args.text:
                send_assist_intent(ws, args.text)
            else:
                start_interactive_mode(ws)

        elif message_data.get("type") == "result" and message_data.get("success") and list_agents_mode:
            for agent in message_data.get("result", {}).get("pipelines", []):
                print(agent['id'] if args.cli else f"{agent['name']} (ID: {agent['id']})")
            clean_exit()

        elif message_data.get("type") == "event" and message_data.get("event", {}).get("type") == "intent-end":
            speech_text = message_data["event"]["data"]["intent_output"]["response"]["speech"]["plain"]["speech"]
            conversation_id = message_data["event"]["data"]["intent_output"]["conversation_id"]
            save_conversation_id(conversation_id)
            if args.cli:
                print(speech_text)
            else:
                print(f"\033[92m🤖: {speech_text}\033[0m")
            response_received_event.set()
            if args.text and not args.interactive:
                clean_exit()

        elif message_data.get("type") == "error":
            print(f"Error: {message_data.get('message')}", file=sys.stderr)
            clean_exit(1)

        elif message_data.get("type") == "auth_invalid":
            print(f"Auth error: {message_data.get('message')}", file=sys.stderr)
            clean_exit(1)

    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}", file=sys.stderr)
        clean_exit(1)

def authenticate(ws):
    ws.send(json.dumps({
        "type": "auth",
        "access_token": os.getenv("HATOKEN")
    }))

def send_assist_intent(ws, text):
    global response_received_event

    payload = {
        "id": generate_message_id(),
        "type": "assist_pipeline/run",
        "start_stage": "intent",
        "end_stage": "intent",
        "input": {"text": text},
        "conversation_id": None if args.new else conversation_id
    }

    if args.agent:
        payload["pipeline"] = args.agent

    ws.send(json.dumps(payload))
    response_received_event.clear()

def start_interactive_mode(ws):
    global interactive_thread, should_exit

    def loop():
        while not should_exit:
            try:
                if args.cli:
                    intent_text = sys.stdin.readline().strip()
                else:
                    intent_text = input("😊: ")

                if not intent_text:
                    continue
                if intent_text.lower() in ['exit', 'quit']:
                    clean_exit()
                send_assist_intent(ws, intent_text)
                response_received_event.wait()
            except (EOFError, KeyboardInterrupt):
                clean_exit()
            except Exception as e:
                print(f"Loop error: {e}", file=sys.stderr)
                clean_exit(1)

    interactive_thread = threading.Thread(target=loop)
    interactive_thread.daemon = True
    interactive_thread.start()

def on_error(ws, error):
    print(f"WebSocket error: {error}", file=sys.stderr)

def signal_handler(sig, frame):
    clean_exit()

def clean_exit(code=0):
    global ws, should_exit
    should_exit = True
    response_received_event.set()
    if ws:
        try:
            ws.close()
        except:
            pass
    if interactive_thread and interactive_thread.is_alive():
        interactive_thread.join(timeout=1)
    sys.exit(code)

# Main
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='HA Assist CLI')
    parser.add_argument('text', nargs='?', help='Text to send to the assistant')
    parser.add_argument('--agent', '-a', help='Conversation pipeline ID')
    parser.add_argument('--list-agents', '-l', action='store_true', help='List available agents')
    parser.add_argument('--new', '-n', action='store_true', help='Start new conversation')
    parser.add_argument('--interactive', '-i', action='store_true', help='Stay in interactive mode')
    parser.add_argument('--cli', '-c', action='store_true', help='CLI mode (no emojis/status)')
    parser.add_argument('--env', help='Path to .env file')
    parser.add_argument('--conversationid', '--ci', help='Provide session-specific conversation ID')

    args = parser.parse_args()
    conversation_id_override = args.conversationid
    load_environment_variables(args.env)
    list_agents_mode = args.list_agents
    conversation_id = load_conversation_id()

    signal.signal(signal.SIGINT, signal_handler)

    ha_token = os.getenv("HATOKEN")
    ha_url = os.getenv("HAURL")
    protocol = "wss" if os.getenv("SSL", "0") == "1" else "ws"
    ws_url = f"{protocol}://{ha_url}/api/websocket"

    ws = websocket.WebSocketApp(
        ws_url,
        header={"Authorization": f"Bearer {ha_token}"},
        on_message=on_message,
        on_error=on_error,
    )

    try:
        ws.run_forever()
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        clean_exit(1)
