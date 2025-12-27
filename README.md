
# Barstr Bot

Barstr is a Nostr bot that helps users find Bitcoin-friendly bars in their city using data from [BTCmap.org](https://btcmap.org).

## Features

- **Hashtag & Mention Support**: Responds to `#Barstr [City]` and `@Barstr [City]`.
- **Language Detection**: Automatically replies in English or Spanish based on the query.
- **Threaded Replies**: Uses NIP-10 to ensure replies appear correctly in the coversation.
- **Clean Output**: Lists up to 10 locations with direct links to BTCmap.

## Setup

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/Barstr.git
    cd Barstr
    ```

2.  **Create a Virtual Environment**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment**:
    - Copy `.env.example` to `.env`:
      ```bash
      cp .env.example .env
      ```
    - Edit `.env` and add your Nostr Private Key (`nsec` or hex):
      ```bash
      NOSTR_NSEC=nsec1yourprivatekey...
      ```

## Running the Bot

```bash
python main.py
# OR
./run.sh
```

## Tools
- `check_replies.py`: Use this script to verify if the bot's replies are propagating to relays.
