# extract_888.py

import re
from datetime import datetime
import logging

# Configure logging to display debug information
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

def extract_info(file_path, category):
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    # Split the content into individual games based on the game number identifier
    games = re.split(r'#Game No\s*:\s*\d+', content)[1:]  # Skip any content before the first game
    extracted_games = []

    # Define regex patterns
    tournament_info_pattern = re.compile(
        r'Tournament\s+#(\d+)\s+\$([\d,]+)\s+\+\s+\$([\d,]+).*?-\s+Table\s+#(\d+)\s+(\d+)\s+Max\s+\(([^)]+)\)',
        re.IGNORECASE
    )
    blinds_datetime_pattern = re.compile(
        r'(\d+)/(\d+)\s+Blinds\s+No Limit Holdem\s+-\s+\*\*\*\s+(\d{2})\s+(\d{2})\s+(\d{4})\s+(\d{2}:\d{2}:\d{2})',
        re.IGNORECASE
    )
    dealt_to_pattern = re.compile(
        r'Dealt to\s+([^\s]+)\s+\[.*\]',
        re.IGNORECASE
    )
    seat_pattern = re.compile(
        r'Seat\s+(\d+):\s+([^\s]+)\s+\(\s*([\d,]+)\s*\)',
        re.IGNORECASE
    )

    for idx, game in enumerate(games, start=1):
        game = game.strip()
        if not game:
            continue

        # Extract Tournament Information
        tournament_match = tournament_info_pattern.search(game)
        if tournament_match:
            tournament_number = tournament_match.group(1)
            prize_main = int(tournament_match.group(2).replace(',', ''))
            prize_bonus = int(tournament_match.group(3).replace(',', ''))
            table_number = int(tournament_match.group(4))
            max_players = int(tournament_match.group(5))
            currency = tournament_match.group(6)
            tournament_name = f"888 Tournament #{tournament_number} - ${prize_main} + ${prize_bonus} - {currency}"
            logging.info(f"Game {idx}: Extracted Tournament: {tournament_name}")
        else:
            logging.warning(f"Game {idx}: Tournament information pattern did not match.")
            snippet = game[:200]  # Print first 200 characters for inspection
            logging.debug(f"Game {idx} content snippet:\n{snippet}\n")
            continue

        # Extract Blinds and Date-Time
        blinds_datetime_match = blinds_datetime_pattern.search(game)
        if blinds_datetime_match:
            small_blind = int(blinds_datetime_match.group(1).replace(",", ""))
            big_blind = int(blinds_datetime_match.group(2).replace(",", ""))
            day = blinds_datetime_match.group(3)
            month = blinds_datetime_match.group(4)
            year = blinds_datetime_match.group(5)
            time_str = blinds_datetime_match.group(6)
            try:
                hand_time = datetime.strptime(f"{day} {month} {year} {time_str}", "%d %m %Y %H:%M:%S")
                logging.info(f"Game {idx}: Extracted Hand Time: {hand_time}")
            except ValueError as ve:
                logging.error(f"Game {idx}: Date-Time parsing error: {ve}")
                continue
        else:
            logging.warning(f"Game {idx}: Blinds and Date-Time pattern did not match.")
            snippet = game[:200]
            logging.debug(f"Game {idx} content snippet:\n{snippet}\n")
            continue

        # Extract Hero's Name
        dealt_to_match = dealt_to_pattern.search(game)
        if dealt_to_match:
            hero_name = dealt_to_match.group(1)
            logging.info(f"Game {idx}: Extracted Hero Name: {hero_name}")
        else:
            logging.warning(f"Game {idx}: Dealt to pattern did not match.")
            snippet = game[:200]
            logging.debug(f"Game {idx} content snippet:\n{snippet}\n")
            continue

        # Extract Hero's Initial Stack
        seat_matches = seat_pattern.findall(game)
        hero_stack = None
        for seat in seat_matches:
            seat_number, username, stack = seat
            if username.lower() == hero_name.lower():
                hero_stack = int(stack.replace(",", ""))
                logging.info(f"Game {idx}: Extracted Hero Stack: {hero_stack} chips")
                break
        if hero_stack is None:
            logging.warning(f"Game {idx}: Hero '{hero_name}' not found in seating.")
            continue

        # Calculate stack in big blinds
        if big_blind > 0:
            stack_in_bb = round(hero_stack / big_blind, 2)
            logging.info(f"Game {idx}: Hero Stack in BB: {stack_in_bb} BB")
        else:
            stack_in_bb = None
            logging.warning(f"Game {idx}: Big blind is zero or not found.")

        # Append to extracted_games
        extracted_games.append({
            "tournament_name": tournament_name,
            "category": category,
            "game_number": tournament_number,
            "table_number": table_number,
            "max_players": max_players,
            "currency": currency,
            "first_hand_time": hand_time,
            "last_hand_time": hand_time,  # Each game has a single timestamp
            "hero_name": hero_name,
            "stack_in_bb": stack_in_bb
        })

    if not extracted_games:
        logging.warning(f"No games extracted from file: {file_path}")

    return extracted_games