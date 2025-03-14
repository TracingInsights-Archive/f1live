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
    "GREEN": "🟢",
    "RED": "🔴",
    "YELLOW": "🟡",
    "DOUBLE_YELLOW": "🟡🟡",
    "BLUE": "🔵",
    "CHEQUERED": "🏁",
    "BLACK": "⚫",
    "BLACK_AND_ORANGE": "⚫🟧",
    "BLACK_AND_WHITE": "⚫⚪",
    "WHITE": "⚪",
    "CLEAR": "⚪",
}

CATEGORY_EMOJIS = {
    "Other": "ℹ️",
    "Flag": "🚩",
    "Drs": "📡",
    "SafetyCar": "🚨",
    "Incident": "💥",
    "Track": "🛣️",
    "Weather": "🌦️",
    "Technical": "🔧",
    "Timing": "⏱️",
    "Stewards": "👨‍⚖️",
    "SECTOR": "📍",
    "TRACK_STATUS": "🏁",
    "WARNING": "⚠️",
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
    flag_emoji = FLAG_EMOJIS.get(latest_message["flag"], "")
    category_emoji = CATEGORY_EMOJIS.get(latest_message["category"], "ℹ️")

    time_str = (
        latest_message["timestamp"].strftime("%H:%M:%S UTC")
        if "timestamp" in latest_message
        else ""
    )

    message = f"{flag_emoji} {category_emoji} F1 Race Control ({time_str}):\n{latest_message['message']}"

    if latest_message["scope"]:
        message += f"\nScope: {latest_message['scope']}"

    message += f"\n\n{HASHTAGS}"

    return message


def create_hashtag_facets(text: str) -> list:
    facets = []
    byte_text = text.encode("utf-8")
    words = text.split()
    current_position = 0

    for word in words:
        if word.startswith("#"):
            byte_start = len(text[: text.index(word)].encode("utf-8"))
            byte_end = byte_start + len(word.encode("utf-8"))
            facets.append(
                {
                    "index": {"byteStart": byte_start, "byteEnd": byte_end},
                    "features": [
                        {"$type": "app.bsky.richtext.facet#tag", "tag": word[1:]}
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
                # Include timestamp in the comparison tuple
                current_messages = set(
                    tuple(row)
                    for row in df[
                        ["message", "category", "flag", "scope", "timestamp"]
                    ].itertuples(index=False)
                )
                new_messages = current_messages - previous_messages

                for message in new_messages:
                    bluesky_post = format_bluesky_message(
                        pd.DataFrame(
                            [
                                {
                                    "message": message[0],
                                    "category": message[1],
                                    "flag": message[2],
                                    "scope": message[3],
                                    "timestamp": message[4],
                                }
                            ]
                        )
                    )
                    post_to_bluesky(bluesky_client, bluesky_post)
                    print(f"Posted new message: {message[0]}")  # Added logging

                previous_messages = current_messages

        print(f"\nRefreshing in {REFRESH_INTERVAL} seconds...")
        time.sleep(REFRESH_INTERVAL)


if __name__ == "__main__":
    try:
        # Setup Bluesky client
        bluesky_client = Client()
        bluesky_client.login(
            os.environ.get("BLUESKY_USERNAME"), os.environ.get("BLUESKY_PASSWORD")
        )

        # Start monitoring with Bluesky integration
        monitor_f1_data(bluesky_client)
    except KeyboardInterrupt:
        print("\nStopping F1 Live Data Monitor...")
