# Home Assistant Assist 

OKE I wrote new stuff. here is the current documentation https://www.youtube.com/watch?v=Awu635V2hI8


```
 sudo apt install tmux python3-dateutil python3-dateutil python3-jinja2 python3-rich python3-yaml python3-websocket python3-dotenv
```



## OLD README

The Home Assistant Assist CLI is a Python command-line application designed to interact with Home Assistant via the "Assist" pipeline. It enables users to send text intents directly to Home Assistant, facilitating seamless integration and control over smart home devices through terminal commands or interactive mode.

![Screenshot of my application](/screenshot.png "Application Screenshot")

## Features

- Send text intents to Home Assistant from the command line.
- Interactive mode for real-time text intent communication.
- Authentication via access token for secure connection.

## Installation

If using a Windows machine, download the [latest release](https://github.com/bram-diederik/cmdline-assist/releases/latest). Then, create a .env file in the same directory as the executable with your Home Assistant access token and URL:

```plaintext
HATOKEN=your_access_token_here
HAURL=your_home_assistant_url_here
SSL=0/1; optional
DEFAULT_AGENT=0123456789 ; optional
```

## Installation from source

### Prerequisites

- Python 3.6 or higher
- Home Assistant running instance
- Access to Home Assistant's API via tokens

### Setup

1. Clone the repository to your local machine.

- git clone <repository-url>
- cd <repository-directory>

2. Install required Python packages.

```plaintext
pip install websocket-client python-dotenv
```

3. Create a `.env` file in the root directory of the project with your Home Assistant access token and URL:

```plaintext
HATOKEN=your_access_token_here
HAURL=your_home_assistant_url_here
```

## Usage

To use the Assist CLI, run the script with Python from the command line. There are two modes of operation:

### Direct Intent Mode

You can send a direct intent as an argument:

```plaintext
python assist.py "Turn on the living room lights"
```

### select agent

use --list-agents to list all agents and there ID's use the ID with --agent or in your yaml

### Interactive Mode

Run the script with out text to enter interactive mode, then type your intents:

`python assist.py`
Or 
`python assist.py --agent 123456789`

Enter `exit` to quit interactive mode.

### Comandline mode 
`python assist.py "your command to the agent"`
Will directly send your responce. 
use --cli for clean no additional information return
use --new to start a new conversation 


## Configuration

The `.env` file contains your configuration settings. Ensure your `HATOKEN` and `HAURL` are correctly set to communicate with your Home Assistant instance.
`--env allows multiple .env files for multiple home assistant services 

## Contributing

Contributions are welcome! For major changes, please open an issue first to discuss what you would like to change.

## License

This project is licensed under the MIT License. For more information, see the [LICENSE](LICENSE) file.

---

For more information on Home Assistant and its capabilities, visit [Home Assistant's official website](https://www.home-assistant.io/).
