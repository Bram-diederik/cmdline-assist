import websocket
import json
import threading
import signal
import sys
from dotenv import load_dotenv
import os
import uuid

# Load environment variables
load_dotenv()

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
	# print json message nicely
	# print(json.dumps(json.loads(message), indent=4))

	global message_id_counter
	global conversation_id
	message_data = json.loads(message)
	if message_data.get("type") == "auth_required":
		authenticate(ws)
	elif message_data.get("type") == "auth_ok":
		print("Authentication successful")
		if len(sys.argv) > 1:
			send_assist_intent(ws, sys.argv[1])
			exit_handler(ws)
		else:
			start_interactive_mode(ws)
	elif message_data.get("type") == "event" and message_data.get("event", {}).get("type") == "intent-end":
		speech_text = message_data["event"]["data"]["intent_output"]["response"]["speech"]["plain"]["speech"]
		conversation_id = message_data["event"]["data"]["intent_output"]["conversation_id"]
		print(f"🤖: {speech_text}")
		response_received_event.set()  # Signal that the response has been received
	elif message_data.get("type") == "error":
		print(f"Error: {message_data.get('message')}")
		response_received_event.set()  # Signal in case of an error too

def authenticate(ws):
	auth_message = {
		"type": "auth",
		"access_token": os.getenv("HATOKEN")
	}
	ws.send(json.dumps(auth_message))
	print("Sent authentication message")

def send_assist_intent(ws, text):
	global response_received_event
	response_received_event.clear()  # Reset the event before sending a new intent
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
			response_received_event.wait()  # Wait here until the event is set (response received)
	thread = threading.Thread(target=run)
	thread.start()

def signal_handler(sig, frame, ws):
	exit_handler(ws)

def exit_handler(ws):
	print('Exiting...')
	ws.close()
	sys.exit(0)

if __name__ == "__main__":
	websocket.enableTrace(False)
	ha_token = os.getenv("HATOKEN")
	ha_url = os.getenv("HAURL")
	ws = websocket.WebSocketApp(f"ws://{ha_url}/api/websocket",
								header={"Authorization": f"Bearer {ha_token}"},
								on_open=lambda ws: print("Connection opened."),
								on_message=on_message,
								on_error=lambda ws, error: print(f"Error: {error}"),
								on_close=lambda ws, close_status_code, close_msg: print("### closed ###"))
	signal.signal(signal.SIGINT, lambda sig, frame: signal_handler(sig, frame, ws))
	ws.run_forever()
