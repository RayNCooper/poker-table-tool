# extract_gg.py

import re
from datetime import datetime

def extract_tournament_name_from_content(content):
    tournament_name_pattern = re.compile(r'Tournament #\d+, ([^,]+)')
    for line in content:
        match = tournament_name_pattern.search(line)
        if match:
            tournament_name = match.group(1).strip()
            tournament_name = re.sub(r'Hold\'em No Limit.*', '', tournament_name).strip()
            tournament_name = re.sub(r'Level\d+\(.*\)', '', tournament_name).strip()
            return tournament_name
    return "Unknown Tournament"

def extract_info(file_path, category):
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.readlines()
    date_time_pattern = re.compile(r'- (\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})')
    blinds_pattern = re.compile(r'Level\d+\(([\d,]+)/([\d,]+)\)')
    hero_stack_pattern = re.compile(r'Hero \(([\d,]+) in chips\)')

    first_hand, last_hand, hero_stack_bb, big_blind = None, None, None, None
    tournament_name = extract_tournament_name_from_content(content)

    for line in reversed(content):
        if not first_hand:
            first_hand = date_time_pattern.search(line)
        if first_hand and blinds_pattern.search(line):
            blinds_match = blinds_pattern.search(line)
            if blinds_match:
                big_blind = int(blinds_match.group(2).replace(",", ""))
        if first_hand and hero_stack_pattern.search(line):
            hero_match = hero_stack_pattern.search(line)
            if hero_match:
                hero_stack = int(hero_match.group(1).replace(",", ""))
                if big_blind:
                    hero_stack_bb = hero_stack / big_blind
            break

    for line in content:
        if not last_hand:
            last_hand = date_time_pattern.search(line)
        if last_hand:
            break

    if first_hand and last_hand:
        first_hand_time = first_hand.group(1)
        last_hand_time = last_hand.group(1)
        entry = {
            "tournament_name": tournament_name,
            "category": category,  # Include the selected category
            "first_hand_time": datetime.strptime(first_hand_time, "%Y/%m/%d %H:%M:%S"),
            "last_hand_time": datetime.strptime(last_hand_time, "%Y/%m/%d %H:%M:%S"),
            "stack_in_bb": round(hero_stack_bb, 2) if hero_stack_bb is not None else None
        }
        return [entry]
    else:
        print(f"Could not extract information from file: {file_path}")
        return []