import logging
import os
import time
from datetime import datetime, timezone

import fastf1
from atproto import Client
from fastf1.livetiming.client import SignalRClient

# Global hashtags for F1 posts
F1_HASHTAGS = "#F1 #Formula1 #AbuDhabiGP"
MAX_CHARS = 300


def split_message(text, max_length):
    parts = []
    current_part = text

    while len(current_part) > max_length:
        split_index = current_part.rfind(" ", 0, max_length - 5)
        if split_index == -1:
            split_index = max_length - 5

        parts.append(current_part[:split_index] + "...")
        current_part = "..." + current_part[split_index:].strip()

    parts.append(current_part)
    return parts


def setup_logging():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger("F1LiveControl")


def create_signalr_client(logger):
    return SignalRClient(
        filename=None,  # We don't need to save to file
        debug=False,
        timeout=300,  # 5 minute timeout
        logger=logger,
    )


def setup_bluesky():
    client = Client()
    client.login(os.environ.get("BLUESKY_USERNAME"), os.environ.get("BLUESKY_PASSWORD"))
    return client


def format_message(msg):
    time_str = msg["Time"].strftime("%H:%M:%S UTC")

    category_emoji = {
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
    }

    cat_emoji = category_emoji.get(msg["Category"], "ℹ️")
    base_text = f"{cat_emoji} F1 Race Control ({time_str}):\n{msg['Message']}"

    if msg["Flag"]:
        flag_emoji = {
            "GREEN": "🟢",
            "RED": "🔴",
            "YELLOW": "🟡",
            "CHEQUERED": "🏁",
            "CLEAR": "⚪",
        }.get(msg["Flag"], "")
        base_text = f"{flag_emoji} {base_text}"

    full_text = f"{base_text}\n\n{F1_HASHTAGS}"

    if len(full_text) <= MAX_CHARS:
        return [full_text]
    else:
        # For long messages, only include hashtags in the last part
        parts = split_message(base_text, MAX_CHARS)
        parts[-1] = f"{parts[-1]}\n\n{F1_HASHTAGS}"
        return parts


def process_messages(messages, processed_messages, bsky, logger):
    for msg in messages:
        msg_id = f"{msg['Utc']}_{msg['Message']}"

        if msg_id not in processed_messages:
            try:
                msg_dict = {
                    "Time": datetime.fromisoformat(msg["Utc"].replace("Z", "+00:00")),
                    "Message": msg["Message"],
                    "Flag": msg.get("Flag"),
                    "Category": msg["Category"],
                }

                message_parts = format_message(msg_dict)

                # Post first part
                root = bsky.send_post(text=message_parts[0])
                logger.info(f"Posted part 1: {message_parts[0]}")

                # Create thread if there are more parts
                parent = root
                for i, part in enumerate(message_parts[1:], 2):
                    parent = bsky.send_post(text=part, reply_to=parent)
                    logger.info(f"Posted part {i}: {part}")

                processed_messages.add(msg_id)

            except Exception as e:
                logger.error(f"Error processing message {msg_id}: {str(e)}")


def monitor_live_race_control():
    logger = setup_logging()
    client = create_signalr_client(logger)
    bsky = setup_bluesky()
    processed_messages = set()

    logger.info("Starting F1 Live Race Control Monitor...")

    while True:
        try:
            messages = client.get_data("RaceControlMessages")
            if messages:
                process_messages(messages, processed_messages, bsky, logger)
            time.sleep(1)  # Add small delay to prevent excessive polling

        except Exception as e:
            logger.error(f"Connection error: {str(e)}")
            logger.info("Attempting to reconnect...")
            client = create_signalr_client(logger)
            time.sleep(5)  # Wait before reconnecting


if __name__ == "__main__":
    # fastf1.Cache.enable_cache(False)
    logger = setup_logging()

    try:
        logger.info("Initializing F1 Live Race Control Monitor...")
        monitor_live_race_control()
    except KeyboardInterrupt:
        logger.info("Stopping F1 Live Race Control Monitor...")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        raise
    finally:
        logger.info("Shutdown complete")
