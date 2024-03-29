# Home Assistant Assist CLI

The Home Assistant Assist CLI is a Python command-line application designed to interact with Home Assistant via the "Assist" pipeline. It enables users to send text intents directly to Home Assistant, facilitating seamless integration and control over smart home devices through terminal commands or interactive mode.

![Screenshot of my application](/screenshot.png "Application Screenshot")

## Features

- Send text intents to Home Assistant from the command line.
- Interactive mode for real-time text intent communication.
- Authentication via access token for secure connection.

## Installation

If using a Windows machine, download the [latest release](https://github.com/falldeaf/cmdline-assist/releases/latest). Then, create a .env file in the same directory as the executable with your Home Assistant access token and URL:

```plaintext
HATOKEN=your_access_token_here
HAURL=your_home_assistant_url_here
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
python assist_cli.py "Turn on the living room lights"
```

### Interactive Mode

Run the script without any arguments to enter interactive mode, then type your intents:

python assist_cli.py

Enter `exit` to quit interactive mode.

## Configuration

The `.env` file contains your configuration settings. Ensure your `HATOKEN` and `HAURL` are correctly set to communicate with your Home Assistant instance.

## Contributing

Contributions are welcome! If you have improvements or bug fixes, please follow the steps below:

1. Fork the repository.
2. Create a new branch for your feature or fix.
3. Commit your changes with clear commit messages.
4. Push to the branch.
5. Create a Pull Request.


## License

This project is licensed under the MIT License. For more information, see the [LICENSE](LICENSE) file.

---

For more information on Home Assistant and its capabilities, visit [Home Assistant's official website](https://www.home-assistant.io/).