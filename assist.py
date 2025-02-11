#!/usr/bin/python3
import websocket
import json
import threading
import signal
import sys
from dotenv import load_dotenv
import os
import uuid

# Load environment variables
def load_environment_variables():
        if getattr(sys, 'frozen', False):
                application_path = os.path.dirname(sys.executable)
        else:
                application_path = os.path.dirname(os.path.realpath(__file__))

        env_file_path = os.path.join(application_path, '.env')
        if not os.path.isfile(env_file_path):
                print(f"Error: .env file not found at {env_file_path}")
                sys.exit(1)

        load_dotenv(env_file_path)

load_environment_variables()

restart_on_exit =  os.getenv("RESTART",0)


# Initialize a global ID counter
message_id_counter = 1
conversation_id = None
response_received_event = threading.Event()

def generate_message_id():
        global message_id_counter
        message_id = message_id_counter
        message_id_counter += 1
        return message_id

def on_message(ws, message):
        global message_id_counter
        global conversation_id
        message_data = json.loads(message)
        if message_data.get("type") == "auth_required":
                authenticate(ws)
        elif message_data.get("type") == "auth_ok":
                print("Connection established.")
                if len(sys.argv) > 1:
                        send_assist_intent(ws, sys.argv[1])
                else:
                        start_interactive_mode(ws)
        elif message_data.get("type") == "event" and message_data.get("event", {}).get("type") == "intent-end":
                speech_text = message_data["event"]["data"]["intent_output"]["response"]["speech"]["plain"]["speech"]
                conversation_id = message_data["event"]["data"]["intent_output"]["conversation_id"]
                print(f"\033[92m🤖: {speech_text}\033[0m")
                response_received_event.set()  # Signal that the response has been received
                if len(sys.argv) > 1:
                        exit_handler(ws)  # Exit immediately after printing response
        elif message_data.get("type") == "error":
                print(f"💀 Error: {message_data.get('message')}")
                exit_handler(ws)
        elif message_data.get("type") == "auth_invalid":
                print(f"💀 Error: {message_data.get('message')}")
                exit_handler(ws)

def authenticate(ws):
        auth_message = {
                "type": "auth",
                "access_token": os.getenv("HATOKEN")
        }
        ws.send(json.dumps(auth_message))

def send_assist_intent(ws, text):
        global response_received_event
        response_received_event.clear()
        pipeline_message = {
                "id": generate_message_id(),
                "type": "assist_pipeline/run",
                "start_stage": "intent",
                "end_stage": "intent",
                "input": {
                        "text": text
                },
                "conversation_id": conversation_id
        }
        ws.send(json.dumps(pipeline_message))

def start_interactive_mode(ws):
        def run():
                while True:
                        intent_text = input("😊: ")
                        if intent_text.lower() == 'exit':
                                exit_handler(ws)
                        send_assist_intent(ws, intent_text)
                        response_received_event.wait()
        thread = threading.Thread(target=run)
        thread.start()

def signal_handler(sig, frame, ws):
        exit_handler(ws,1)

def exit_handler(ws,code = 0):
    ws.close()
    for thread in threading.enumerate():
        if thread is not threading.main_thread():
            thread.join(timeout=1)  # Wait for non-main threads to exit
    if restart_on_exit:
        print("Restarting script...")
        os.execv(sys.executable, [sys.executable] + sys.argv)  # Restart script
    print('Exiting...')
    sys.exit(code)

if __name__ == "__main__":
        websocket.enableTrace(False)
        ha_token = os.getenv("HATOKEN")
        ha_url = os.getenv("HAURL")
        ssl_enabled = os.getenv("SSL", "0")
        protocol = "wss" if ssl_enabled == "1" else "ws"
        websocket_url = f"{protocol}://{ha_url}/api/websocket"

        ws = websocket.WebSocketApp(websocket_url,
                                                                header={"Authorization": f"Bearer {ha_token}"},
                                                                on_message=on_message,
                                                                on_error=lambda ws, error: print(f"💀 Error: {error}"))
        signal.signal(signal.SIGINT, lambda sig, frame: signal_handler(sig, frame, ws))
        ws.run_forever()
