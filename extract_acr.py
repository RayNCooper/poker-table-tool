# extract_acr.py

import re
from datetime import datetime, timedelta
import logging

# Configure logging to write to a file for persistent records
logging.basicConfig(
    filename='extract_acr.log',
    filemode='a',
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)

# Define the time gap threshold for considering a new block
TIME_GAP_THRESHOLD = timedelta(minutes=120)

def extract_info(file_path, category):
    """
    Extracts tournament data from an ACR hand history file.

    Parameters:
    - file_path (str): The path to the hand history file.
    - category (str): The category name ("ACR" in this case).

    Returns:
    - List[dict]: A list of dictionaries, each representing a hand entry with block information.
    """

    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    # Split the content into individual games based on the "Game Hand #" identifier
    games = re.split(r'Game Hand\s+#\d+', content)[1:]  # Skip any content before the first game
    extracted_hands = []

    # Define regex patterns
    tournament_info_pattern = re.compile(
        r'-\s+Tournament\s+#(\d+)\s+-\s+Holdem\s+\(No Limit\)\s+-\s+Level\s+(\d+)\s+\(([\d.,]+)/([\d.,]+)\)-\s+(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}:\d{2})\s+UTC',
        re.IGNORECASE
    )
    table_info_pattern = re.compile(
        r"Table\s+'(\d+)'\s+(\d+)-max\s+Seat\s+#(\d+)\s+is\s+the\s+button",
        re.IGNORECASE
    )
    seat_pattern = re.compile(
        r'^\s*Seat\s+#?(\d+):\s+([^()]+)\s+\(([\d,]+\.\d{2})\)',
        re.IGNORECASE | re.MULTILINE
    )
    dealt_to_pattern = re.compile(
        r'Dealt to\s+([^\s]+)\s+\[.*\]',
        re.IGNORECASE
    )
    small_blind_pattern = re.compile(
        r'posts the small blind\s+([\d,.]+)',
        re.IGNORECASE
    )
    big_blind_pattern = re.compile(
        r'posts the big blind\s+([\d,.]+)',
        re.IGNORECASE
    )

    # Initialize a dictionary to keep track of the last hand time per table to identify blocks
    last_hand_time_per_table = {}

    for idx, game in enumerate(games, start=1):
        game = game.strip()
        if not game:
            continue

        logging.info(f"Processing Game {idx} in file: {file_path}")

        # Extract Tournament Information
        tournament_match = tournament_info_pattern.search(game)
        if not tournament_match:
            logging.warning(f"Game {idx}: Tournament information pattern did not match.")
            snippet = game[:200]
            logging.debug(f"Game {idx} content snippet:\n{snippet}\n")
            continue

        tournament_number = tournament_match.group(1)
        level = int(tournament_match.group(2))
        level_blind_small = float(tournament_match.group(3).replace(',', ''))
        level_blind_big = float(tournament_match.group(4).replace(',', ''))
        hand_time_str = tournament_match.group(5)

        # Parse the hand time
        try:
            hand_time = datetime.strptime(hand_time_str, "%Y/%m/%d %H:%M:%S")
            logging.info(f"Game {idx}: Extracted Hand Time: {hand_time}")
        except ValueError as ve:
            logging.error(f"Game {idx}: Date-Time parsing error: {ve}")
            continue

        tournament_name = f"ACR Tournament #{tournament_number}"
        logging.info(f"Game {idx}: Extracted Tournament: {tournament_name}")

        # Extract Table Information
        table_match = table_info_pattern.search(game)
        if not table_match:
            logging.warning(f"Game {idx}: Table information pattern did not match.")
            snippet = game[:200]
            logging.debug(f"Game {idx} content snippet:\n{snippet}\n")
            continue

        table_number = int(table_match.group(1))
        max_players = int(table_match.group(2))
        button_seat = int(table_match.group(3))
        logging.info(f"Game {idx}: Extracted Table Number: {table_number}, Max Players: {max_players}, Button Seat: {button_seat}")

        # Extract Seat Assignments
        seats = seat_pattern.findall(game)
        if not seats:
            logging.warning(f"Game {idx}: No seat assignments found.")
            # Optional: Log entire game content for debugging
            # logging.debug(f"Game {idx} full content:\n{game}\n")
            continue

        # Create a mapping from username to their seat info
        seat_info = {}
        for seat in seats:
            seat_number = int(seat[0])
            username = seat[1].strip()
            stack = float(seat[2].replace(',', ''))
            seat_info[username.lower()] = {
                "seat_number": seat_number,
                "stack": stack
            }

        # Extract Hero's Name
        dealt_to_match = dealt_to_pattern.search(game)
        if dealt_to_match:
            hero_name = dealt_to_match.group(1)
            hero_info = seat_info.get(hero_name.lower())
            if not hero_info:
                logging.warning(f"Game {idx}: Hero '{hero_name}' not found in seat assignments.")
                continue
            hero_stack = hero_info["stack"]
            logging.info(f"Game {idx}: Extracted Hero Name: {hero_name}, Stack: {hero_stack}")
        else:
            logging.warning(f"Game {idx}: Dealt to pattern did not match.")
            snippet = game[:200]
            logging.debug(f"Game {idx} content snippet:\n{snippet}\n")
            continue

        # Extract Blinds
        small_blind_match = small_blind_pattern.search(game)
        if small_blind_match:
            small_blind = float(small_blind_match.group(1).replace(',', ''))
            logging.info(f"Game {idx}: Extracted Small Blind: {small_blind}")
        else:
            logging.warning(f"Game {idx}: Small blind pattern did not match.")
            small_blind = None

        big_blind_match = big_blind_pattern.search(game)
        if big_blind_match:
            big_blind = float(big_blind_match.group(1).replace(',', ''))
            logging.info(f"Game {idx}: Extracted Big Blind: {big_blind}")
        else:
            logging.warning(f"Game {idx}: Big blind pattern did not match.")
            big_blind = None

        # Calculate stack in big blinds
        if big_blind and big_blind > 0:
            stack_in_bb = round(hero_stack / big_blind, 2)
            logging.info(f"Game {idx}: Hero Stack in BB: {stack_in_bb} BB")
        else:
            stack_in_bb = None
            logging.warning(f"Game {idx}: Big blind is zero or not found.")

        # Determine if this hand is a re-entry
        table_key = (tournament_number, table_number)
        last_hand_time = last_hand_time_per_table.get(table_key)
        if last_hand_time:
            time_diff = hand_time - last_hand_time
            is_reentry = time_diff > TIME_GAP_THRESHOLD
        else:
            is_reentry = False  # First hand for this table

        # Update the last_hand_time for this table
        last_hand_time_per_table[table_key] = hand_time

        # Append to extracted_hands
        extracted_hands.append({
            "tournament_name": tournament_name,
            "category": category,
            "game_number": tournament_number,  # Assuming 'game_number' is tournament number
            "table_number": table_number,
            "max_players": max_players,
            "currency": "REAL",  # Assuming REAL currency for ACR
            "first_hand_time": hand_time,
            "last_hand_time": hand_time,  # Each hand has a single timestamp
            "hero_name": hero_name,
            "stack_in_bb": stack_in_bb,
            "is_reentry": is_reentry
        })

    if not extracted_hands:
        logging.warning(f"No games extracted from file: {file_path}")

    return extracted_hands