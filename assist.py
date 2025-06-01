#!/usr/bin/python3
import websocket
import json
import threading
import signal
import sys
from dotenv import load_dotenv
import os
import argparse
from pathlib import Path

# Conversation memory storage
CONVERSATION_FILE = Path.home() / ".ha_conversation_id"

def load_conversation_id():
    if CONVERSATION_FILE.exists():
        return CONVERSATION_FILE.read_text().strip()
    return None

def save_conversation_id(conv_id):
    CONVERSATION_FILE.write_text(conv_id)

# Load environment variables
def load_environment_variables():
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.realpath(__file__))

    env_file_path = os.path.join(application_path, '.env')
    if not os.path.isfile(env_file_path):
        print(f"Error: .env file not found at {env_file_path}", file=sys.stderr)
        sys.exit(1)

    load_dotenv(env_file_path)

load_environment_variables()

# Global variables
message_id_counter = 1
conversation_id = load_conversation_id()
response_received_event = threading.Event()
list_agents_mode = False
interactive_thread = None
ws = None
should_exit = False

def generate_message_id():
    global message_id_counter
    message_id = message_id_counter
    message_id_counter += 1
    return message_id

def on_message(ws, message):
    global conversation_id
    
    try:
        message_data = json.loads(message)
        
        if message_data.get("type") == "auth_required":
            authenticate(ws)
        elif message_data.get("type") == "auth_ok":
            if not args.cli:
                print("Connection established.", file=sys.stderr)
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
            if args.cli:
                for agent in message_data.get("result", {}).get("pipelines", []):
                    print(agent['id'])
            else:
                print("\nAvailable Home Assistant Conversation Agents/Pipelines:")
                for agent in message_data.get("result", {}).get("pipelines", []):
                    print(f"- {agent['name']} (ID: {agent['id']})")
                    print(f"  Language: {agent.get('language', 'unknown')}")
                    print(f"  Conversation engine: {agent.get('conversation_engine', 'unknown')}")
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
            print(f"Error: message data {message_data.get('message')}", file=sys.stderr)
            clean_exit(1)
        elif message_data.get("type") == "auth_invalid":
            print(f"Error: auth envail {message_data.get('message')}", file=sys.stderr)
            clean_exit(1)
    except json.JSONDecodeError as e:
        print(f"Error decoding message: {e}", file=sys.stderr)
        clean_exit(1)

def authenticate(ws):
    auth_message = {
        "type": "auth",
        "access_token": os.getenv("HATOKEN")
    }
    ws.send(json.dumps(auth_message))

def send_assist_intent(ws, text):
    global response_received_event
    
    pipeline_message = {
        "id": generate_message_id(),
        "type": "assist_pipeline/run",
        "start_stage": "intent",
        "end_stage": "intent",
        "input": {
            "text": text
        },
        "conversation_id": None if (not args.cli or args.new) else conversation_id
    }
    
    if args.agent:
        pipeline_message["pipeline"] = args.agent
    
    ws.send(json.dumps(pipeline_message))
    response_received_event.clear()

def start_interactive_mode(ws):
    global interactive_thread, should_exit
    
    def interactive_loop():
        while not should_exit:
            try:
                if not args.cli:
                    intent_text = input("😊: ")
                else:
                    intent_text = sys.stdin.readline().strip()
                
                if not intent_text:
                    continue
                if intent_text.lower() in ['exit', 'quit']:
                    clean_exit()
                send_assist_intent(ws, intent_text)
                response_received_event.wait()
            except (EOFError, KeyboardInterrupt):
                clean_exit()
            except Exception as e:
                print(f"Error Exception: {e}", file=sys.stderr)
                clean_exit(1)
    
    interactive_thread = threading.Thread(target=interactive_loop)
    interactive_thread.daemon = True
    interactive_thread.start()

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

    if code != 0 and (not args or not args.cli):
        print(f"Exit Error: {code}", file=sys.stderr)

    sys.exit(code)

def on_error(ws, error):
    if not args.cli:
        if isinstance(error, Exception):
            print(f"WebSocket error: {error}", file=sys.stderr)
        else:
            print(f"WebSocket error (code or message): {repr(error)}", file=sys.stderr)


def signal_handler(sig, frame):
    if not args.cli:
        print("\nExiting...", file=sys.stderr)
    clean_exit()

if __name__ == "__main__":
    # Load default agent from .env
    default_agent = os.getenv("DEFAULT_AGENT")
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Home Assistant Conversation Agent')
    parser.add_argument('text', nargs='?', help='Text to send to the conversation agent')
    parser.add_argument('--agent', '-a', default=default_agent, help='Use a specific agent/pipeline ID (default: from .env)')
    parser.add_argument('--list-agents', '-l', action='store_true', help='List available agents/pipelines from Home Assistant')
    parser.add_argument('--new', '-n', action='store_true', help='Start a new conversation in --cli')
    parser.add_argument('--interactive', '-i', action='store_true', help='Stay in interactive mode after sending text')
    parser.add_argument('--cli', '-c', action='store_true', help='cli mode (no emoji, no status messages)')
    global args
    args = parser.parse_args()
    
    list_agents_mode = args.list_agents
    
    # Setup signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    websocket.enableTrace(False)
    ha_token = os.getenv("HATOKEN")
    ha_url = os.getenv("HAURL")
    ssl_enabled = os.getenv("SSL", "0")
    protocol = "wss" if ssl_enabled == "1" else "ws"
    websocket_url = f"{protocol}://{ha_url}/api/websocket"

    ws = websocket.WebSocketApp(websocket_url,
                              header={"Authorization": f"Bearer {ha_token}"},
                              on_message=on_message,
                              on_error=on_error)
    
    try:
        ws.run_forever()
    except KeyboardInterrupt:
        clean_exit()
    except Exception as e:
        #print(f"Error: {e}", file=sys.stderr)
        clean_exit(1)
