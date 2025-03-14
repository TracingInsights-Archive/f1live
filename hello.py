import json
import os
import time
from typing import Dict, List, Optional
from urllib.request import URLError, urlopen

import pandas as pd
from atproto import Client

# Constants
BASE_URL = "https://api.openf1.org/v1/race_control"
HASHTAGS = "#f1 #formula1 #live #AusGP #AustralianGP"
REFRESH_INTERVAL = 5  # seconds


FLAG_EMOJIS = {
    "YELLOW": "⚠️",
    "RED": "🔴",
    "GREEN": "🟢",
    "BLUE": "🔵",
    "CHEQUERED": "🏁",
    "BLACK": "⚫",
    "BLACK_AND_ORANGE": "🟧",
    "BLACK_AND_WHITE": "⬛⬜",
    "WHITE": "⚪",
    "DOUBLE_YELLOW": "⚠️⚠️",
}

CATEGORY_EMOJIS = {
    "SECTOR": "📍",
    "TRACK": "🛣️",
    "FLAG": "🚩",
    "DRIVER": "🏎️",
    "CAR": "🏎️",
    "RACE_CONTROL": "📊",
    "SAFETY_CAR": "🚨",
    "DRS": "💨",
    "WARNING": "⚠️",
    "TRACK_STATUS": "🏁",
}


def fetch_f1_data(url: str) -> Optional[List[Dict]]:
    """
    Fetch data from OpenF1 API
    """
    try:
        response = urlopen(f"{url}?meeting_key%3E=latest")
        return json.loads(response.read().decode("utf-8"))
    except (URLError, json.JSONDecodeError) as e:
        print(f"Error fetching data: {e}")
        return None


def process_f1_data(data: List[Dict]) -> Optional[pd.DataFrame]:
    """
    Process F1 data into a pandas DataFrame
    """
    if not data:
        return None
    return pd.DataFrame(data)


def display_f1_data(df: pd.DataFrame) -> None:
    """
    Display F1 data with formatted output
    """
    if df is not None and not df.empty:
        print("\nLatest F1 Race Control Messages:")
        print(df[["message", "category", "flag", "scope"]].to_string())
    else:
        print("No data available")


def format_bluesky_message(df: pd.DataFrame) -> str:
    """Format F1 data for Bluesky post"""
    if df is None or df.empty:
        return "No F1 updates available"

    latest_message = df.iloc[0]
    return f"🏎 F1 Update:\n{latest_message['message']}\nCategory: {latest_message['category']}\nFlag: {latest_message['flag']}\nScope: {latest_message['scope']}"


def create_hashtag_facets(text: str) -> list:
    facets = []
    for word in text.split():
        if word.startswith("#"):
            start = text.index(word)
            facets.append(
                {
                    "index": {"byteStart": start, "byteEnd": start + len(word)},
                    "features": [
                        {
                            "$type": "app.bsky.richtext.facet#tag",
                            "tag": word[1:],  # Remove # prefix
                        }
                    ],
                }
            )
    return facets


def post_to_bluesky(client: Client, message: str) -> None:
    """Post message to Bluesky with clickable hashtags"""
    try:
        facets = create_hashtag_facets(message)
        client.send_post(text=message, facets=facets)
    except Exception as e:
        print(f"Error posting to Bluesky: {e}")


def monitor_f1_data(bluesky_client: Client):
    """
    Continuously monitor F1 data and post updates to Bluesky
    """
    print("Starting F1 Live Data Monitor with Bluesky integration...")
    previous_messages = set()

    while True:
        data = fetch_f1_data(BASE_URL)
        if data:
            df = process_f1_data(data)
            display_f1_data(df)

            if df is not None and not df.empty:
                current_messages = set(
                    tuple(row)
                    for row in df[["message", "category", "flag", "scope"]].itertuples(
                        index=False
                    )
                )

                new_messages = current_messages - previous_messages

                for message in new_messages:
                    flag_emoji = FLAG_EMOJIS.get(message[2], "")
                    category_emoji = CATEGORY_EMOJIS.get(message[1], "")

                    bluesky_post = f"{category_emoji} {flag_emoji} F1 Update:\n{message[0]}\nCategory: {message[1]}\nFlag: {message[2]}\nScope: {message[3]}\n\n{HASHTAGS}"
                    post_to_bluesky(bluesky_client, bluesky_post)

                previous_messages = current_messages

        print(f"\nRefreshing in {REFRESH_INTERVAL} seconds...")
        time.sleep(REFRESH_INTERVAL)


if __name__ == "__main__":
    try:
        # Setup Bluesky client
        bluesky_client = Client()
        bluesky_client.login(
            "tracing.insights+live@gmail.com",
            "Rg2F8XSw!26aZeZ",
            # os.environ.get("BLUESKY_USERNAME"),
            # os.environ.get("BLUESKY_PASSWORD")
        )

        # Start monitoring with Bluesky integration
        monitor_f1_data(bluesky_client)
    except KeyboardInterrupt:
        print("\nStopping F1 Live Data Monitor...")
