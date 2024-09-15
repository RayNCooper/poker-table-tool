import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox
from collections import defaultdict
import datetime
import plotly.express as px
import pandas as pd
import plotly.io as pio
import webbrowser

def select_files():
    files = filedialog.askopenfilenames(title="Select Hand History Files")
    if files:
        root.withdraw()
        process_files(files)
    else:
        messagebox.showerror("Error", "No files selected.")

def extract_tournament_label(file_name):
    patterns = [
        r'Tournament (.+?) \(',
        r'TN-(.+?) GAMETYPE-',
        r'- (.+)\.txt$',
        r'HH\d+ (.+?)\.txt$',
        r'\d+_(.+?)\(\d+\)_real_holdem_no-limit\.txt$',
        r'\d+_(.+?)\.txt$',
    ]
    for pattern in patterns:
        match = re.search(pattern, file_name)
        if match:
            return match.group(1).strip()
    return None

def process_files(file_list):
    hand_histories = []

    for file in file_list:
        if "Summary" in os.path.basename(file):
            print(f"Skipping summary file {file}")
            continue
        try:
            with open(file, 'r', encoding='utf-8') as f:
                content = f.read()
                site = identify_site(content)
                if site:
                    tournament_label = extract_tournament_label(os.path.basename(file))
                    hands, player = parse_hand_history(content, site, tournament_label)
                    if not player:
                        print(f"No player found in file {file}")
                        continue
                    for hand in hands:
                        hand['player'] = player
                    hand_histories.extend(hands)
                else:
                    print(f"Could not identify site for file {file}")
        except Exception as e:
            print(f"Error processing {file}: {e}")

    if not hand_histories:
        messagebox.showerror("Error", "No valid hand histories found.")
        return

    plot_gantt_chart(hand_histories)

def identify_site(content):
    if "PokerStars Hand" in content:
        return "PokerStars"
    elif "Game Hand #" in content and "Tournament #" in content and "Holdem" in content:
        return "ACR"
    elif "888poker Hand History" in content:
        return "888"
    elif "Poker Hand #" in content and "Tournament #" in content:
        return "GG"
    elif "Winamax Poker - Tournament" in content:
        return "Winamax"
    else:
        return None

def parse_hand_history(content, site, tournament_label=None):
    hands = []
    player = None

    if site == "ACR":
        # Extract player
        player_seats = re.findall(r"Seat \d+: (\S+)", content)
        if player_seats:
            player_counts = defaultdict(int)
            for p in player_seats:
                player_counts[p] += 1
            player = max(player_counts, key=player_counts.get)
        else:
            print("Player not found in ACR hand history.")
            return [], None

        # Split into individual hands
        hand_blocks = re.split(r'\n\n+', content)
        if not hand_blocks:
            print("No hands found in ACR hand history.")
            return [], None

        # Extract starting stack and blinds from the first hand
        first_hand = hand_blocks[0]
        starting_stack_pattern = rf"Seat \d+: {re.escape(player)} \(([\d,\.]+)\)"
        blinds_pattern = r"Level \d+ \(([\d,\.]+)/([\d,\.]+)\)"

        starting_stack_match = re.search(starting_stack_pattern, first_hand)
        blinds_match = re.search(blinds_pattern, first_hand)

        if starting_stack_match and blinds_match:
            starting_stack = float(starting_stack_match.group(1).replace(',', ''))
            big_blind = float(blinds_match.group(2).replace(',', ''))
            starting_bb = starting_stack / big_blind
        else:
            starting_bb = None

        # Extract tournament info
        tournament_pattern = r"Tournament #(\d+)"
        date_pattern = r"- (\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})"
        hand_pattern = r"Game Hand #(\d+) - Tournament #(\d+)"

        tournaments = re.findall(tournament_pattern, content)
        dates = re.findall(date_pattern, content)
        hands_info = re.findall(hand_pattern, content)

        tournament_name = tournaments[0] if tournaments else 'Unknown'
        if not tournament_label:
            tournament_label = tournament_name

        for idx, (hand_id, tour_id) in enumerate(hands_info):
            hand_date = dates[idx] if idx < len(dates) else None
            hands.append({
                'site': site,
                'tournament_id': tour_id,
                'hand_id': hand_id,
                'date': parse_date(hand_date, ['%Y/%m/%d %H:%M:%S']),
                'player': player,
                'starting_bb': starting_bb,
                'tournament_name': tournament_name,
                'tournament_label': tournament_label,
            })

    elif site == "GG":
        # Extract player
        player_seats = re.findall(r"Seat \d+: (\S+)", content)
        if player_seats:
            player_counts = defaultdict(int)
            for p in player_seats:
                player_counts[p] += 1
            player = max(player_counts, key=player_counts.get)
        else:
            print("Player not found in GG hand history.")
            return [], None

        # Split into individual hands
        hand_blocks = re.findall(r'(Poker Hand #.*?)(?=Poker Hand #|$)', content, re.DOTALL)
        if not hand_blocks:
            print("No hands found in GG hand history.")
            return [], None

        # Extract starting stack and blinds from the earliest hand
        first_hand = hand_blocks[-1]
        starting_stack_pattern = rf"Seat \d+: {re.escape(player)} \(([\d,]+) in chips\)"
        blinds_pattern = r"Level\d+\(([\d,]+)/([\d,]+)\)"

        starting_stack_match = re.search(starting_stack_pattern, first_hand)
        blinds_match = re.search(blinds_pattern, first_hand)

        if starting_stack_match and blinds_match:
            starting_stack = float(starting_stack_match.group(1).replace(',', ''))
            big_blind = float(blinds_match.group(2).replace(',', ''))
            starting_bb = starting_stack / big_blind
        else:
            starting_bb = None

        # Extract tournament info
        tournament_pattern = r"Tournament #(\d+)"
        date_pattern = r"Level\d+\([\d,]+/[\d,]+\) - (\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})"
        hand_pattern = r"Poker Hand #(\S+): Tournament #(\d+)"

        tournaments = re.findall(tournament_pattern, content)
        dates = re.findall(date_pattern, content)
        hands_info = re.findall(hand_pattern, content)

        tournament_name = tournaments[0] if tournaments else 'Unknown'
        if not tournament_label:
            tournament_label = tournament_name

        # Reverse dates and hands_info since hands are in reverse order
        dates = dates[::-1]
        hands_info = hands_info[::-1]

        for idx, (hand_id, tour_id) in enumerate(hands_info):
            hand_date = dates[idx] if idx < len(dates) else None
            hands.append({
                'site': site,
                'tournament_id': tour_id,
                'hand_id': hand_id,
                'date': parse_date(hand_date, ['%Y/%m/%d %H:%M:%S']),
                'player': player,
                'starting_bb': starting_bb,
                'tournament_name': tournament_name,
                'tournament_label': tournament_label,
            })

    elif site == "PokerStars":
        # Split into individual hands
        hand_blocks = re.findall(r'(PokerStars Hand #.*?)(?=(?:\n\n|\Z))', content, re.DOTALL)
        if not hand_blocks:
            print("No hands found in PokerStars hand history.")
            return [], None

        # Extract player
        player_seats = re.findall(r"Seat \d+: (\S+)(?: \(|$)", content)
        if player_seats:
            player_counts = defaultdict(int)
            for p in player_seats:
                player_counts[p] += 1
            player = max(player_counts, key=player_counts.get)
        else:
            print("Player not found in PokerStars hand history.")
            return [], None

        # Extract starting stack and blinds from the first hand
        first_hand = hand_blocks[0]
        starting_stack_pattern = rf"Seat \d+: {re.escape(player)} \(([\d,]+) in chips"
        blinds_pattern = r"Level \w+ \(([\d,]+)/([\d,]+)\)"

        starting_stack_match = re.search(starting_stack_pattern, first_hand)
        blinds_match = re.search(blinds_pattern, first_hand)

        if starting_stack_match and blinds_match:
            starting_stack = float(starting_stack_match.group(1).replace(',', ''))
            big_blind = float(blinds_match.group(2).replace(',', ''))
            starting_bb = starting_stack / big_blind
        else:
            starting_bb = None

        # Extract tournament info
        tournament_pattern = r"Tournament #(\d+)"
        tournament_match = re.search(tournament_pattern, content)
        tournament_name = tournament_match.group(1) if tournament_match else 'Unknown'
        if not tournament_label:
            tournament_label = tournament_name

        for hand in hand_blocks:
            # Extract hand_id and tournament_id
            hand_info_match = re.search(r"PokerStars Hand #(\d+): Tournament #(\d+)", hand)
            if hand_info_match:
                hand_id, tour_id = hand_info_match.groups()
            else:
                continue

            # Extract date and adjust by adding 2 hours
            date_match = re.search(r"\[([\d/ :]+) (\w+)\]", hand)
            if date_match:
                hand_date = date_match.group(1)
                # date_format should match the date string
                date_format = '%Y/%m/%d %H:%M:%S'
                try:
                    dt = datetime.datetime.strptime(hand_date, date_format)
                    # Add 2 hours to align timezone
                    dt += datetime.timedelta(hours=6)
                    hand_date_parsed = dt
                except:
                    hand_date_parsed = None
            else:
                # Alternative date format without timezone
                date_match_alt = re.search(r"- ([\d/ :]+)", hand)
                if date_match_alt:
                    hand_date = date_match_alt.group(1)
                    date_format = '%Y/%m/%d %H:%M:%S'
                    try:
                        dt = datetime.datetime.strptime(hand_date, date_format)
                        # Add 2 hours to align timezone
                        dt += datetime.timedelta(hours=2)
                        hand_date_parsed = dt
                    except:
                        hand_date_parsed = None
                else:
                    hand_date_parsed = None

            hands.append({
                'site': site,
                'tournament_id': tour_id,
                'hand_id': hand_id,
                'date': hand_date_parsed,
                'player': player,
                'starting_bb': starting_bb,
                'tournament_name': tournament_name,
                'tournament_label': tournament_label,
            })

    elif site == "888":
        # Extract player
        player_seats = re.findall(r"Seat \d+: (\S+)", content)
        if player_seats:
            player_counts = defaultdict(int)
            for p in player_seats:
                player_counts[p] += 1
            player = max(player_counts, key=player_counts.get)
        else:
            print("Player not found in 888 hand history.")
            return [], None

        starting_bb = None  # 888 may not provide starting BB

        # Extract tournament info
        tournament_pattern = r"Tournament #(\d+)"
        date_pattern = r"\*\*\* (.+)"
        hand_pattern = r"Game (\d+)"

        tournaments = re.findall(tournament_pattern, content)
        dates = re.findall(date_pattern, content)
        hands_info = re.findall(hand_pattern, content)

        tournament_name = tournaments[0] if tournaments else 'Unknown'
        if not tournament_label:
            tournament_label = tournament_name

        for idx, hand_id in enumerate(hands_info):
            hand_date = dates[idx] if idx < len(dates) else None
            hands.append({
                'site': site,
                'tournament_id': tournament_name,
                'hand_id': hand_id,
                'date': parse_date(hand_date, ['%d %m %Y %H:%M:%S']),
                'player': player,
                'starting_bb': starting_bb,
                'tournament_name': tournament_name,
                'tournament_label': tournament_label,
            })

    elif site == "Winamax":
        # Extract player
        player_seats = re.findall(r"Seat \d+: (\S+)", content)
        if player_seats:
            player_counts = defaultdict(int)
            for p in player_seats:
                player_counts[p] += 1
            player = max(player_counts, key=player_counts.get)
        else:
            print("Player not found in Winamax hand history.")
            return [], None

        starting_bb = None  # Winamax may not provide starting BB

        # Extract tournament info
        tournament_pattern = r"Tournament \"(.+?)\""
        date_pattern = r"- (\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) UTC"
        hand_pattern = r"HandId: #(\d+)-"

        tournaments = re.findall(tournament_pattern, content)
        dates = re.findall(date_pattern, content)
        hands_info = re.findall(hand_pattern, content)

        tournament_name = tournaments[0] if tournaments else 'Unknown'
        if not tournament_label:
            tournament_label = tournament_name

        for idx, hand_id in enumerate(hands_info):
            hand_date = dates[idx] if idx < len(dates) else None
            if hand_date:
                try:
                    dt = datetime.datetime.strptime(hand_date, '%Y/%m/%d %H:%M:%S')
                    # Assuming UTC, convert to the common timezone by adding 2 hours
                    dt += datetime.timedelta(hours=2)
                    hand_date_parsed = dt
                except:
                    hand_date_parsed = None
            else:
                hand_date_parsed = None

            hands.append({
                'site': site,
                'tournament_id': tournament_name,
                'hand_id': hand_id,
                'date': hand_date_parsed,
                'player': player,
                'starting_bb': starting_bb,
                'tournament_name': tournament_name,
                'tournament_label': tournament_label,
            })

    return hands, player

def parse_date(date_str, date_formats):
    if date_str:
        for fmt in date_formats:
            try:
                dt_naive = datetime.datetime.strptime(date_str.strip(), fmt)
                return dt_naive
            except Exception:
                continue
    return None

def plot_gantt_chart(hands):
    tournament_entries = defaultdict(lambda: {'dates': [], 'starting_bb': None, 'tournament_label': None})
    for hand in hands:
        if hand['date']:
            key = (hand['site'], hand['tournament_id'], hand['player'])
            tournament_entries[key]['dates'].append(hand['date'])
            if tournament_entries[key]['starting_bb'] is None:
                tournament_entries[key]['starting_bb'] = hand['starting_bb']
            if tournament_entries[key]['tournament_label'] is None:
                tournament_entries[key]['tournament_label'] = hand['tournament_label']
            tournament_entries[key]['tournament_name'] = hand['tournament_name']

    entries = []
    for key, value in tournament_entries.items():
        site, tournament_id, player = key
        dates = value['dates']
        starting_bb = value['starting_bb']
        dates = [d for d in dates if d is not None]
        if not dates:
            continue
        dates.sort()
        tournament_label = value['tournament_label']
        tournament_display = f"{tournament_label} ({site})"
        entries_in_tournament = []
        current_entry = [dates[0], dates[0]]
        for i in range(1, len(dates)):
            if (dates[i] - dates[i-1]).total_seconds() > 1800:
                current_entry[1] = dates[i-1]
                entries_in_tournament.append(tuple(current_entry))
                current_entry = [dates[i], dates[i]]
            else:
                current_entry[1] = dates[i]
        current_entry[1] = dates[-1]
        entries_in_tournament.append(tuple(current_entry))
        for idx, (start_time, end_time) in enumerate(entries_in_tournament):
            entries.append({
                'Tournament': tournament_display,
                'Start': start_time,
                'Finish': end_time,
                'Site': site,
                'Player': player,
                'Starting_BB': starting_bb,
            })

    if not entries:
        messagebox.showerror("Error", "No valid dates found in hand histories.")
        return

    df = pd.DataFrame(entries)
    base_colors = {
        'GG': '#ff0000',
        'ACR': '#0000ff',
        'Winamax': '#008000',
        'PokerStars': '#800080',
        '888': '#ffa500'
    }

    df['Start'] = pd.to_datetime(df['Start'], errors='coerce')
    df['Finish'] = pd.to_datetime(df['Finish'], errors='coerce')

    df = df.dropna(subset=['Start', 'Finish'])

    df['Starting_BB_Display'] = df.apply(
        lambda row: f"Starting BB={row['Starting_BB']:.1f}" if pd.notnull(row['Starting_BB']) else "Starting BB=N/A", axis=1
    )

    custom_data = df[['Starting_BB_Display']]

    fig = px.timeline(
        df,
        x_start="Start",
        x_end="Finish",
        y="Tournament",
        color="Site",
        color_discrete_map=base_colors,
        custom_data=custom_data,
    )

    hover_template = '%{customdata[0]}<extra></extra>'

    fig.update_traces(hovertemplate=hover_template)

    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        title="Poker Tournaments",
        xaxis_title="Time",
        yaxis_title="Tournaments",
        legend_title="Site",
        margin=dict(l=20, r=20, t=50, b=20),
    )

    fig_html = pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
    html_str = f'''
    <html>
    <head>
        <title>Poker Tournaments</title>
    </head>
    <body>
        {fig_html}
    </body>
    </html>
    '''

    output_file = 'poker_tournaments.html'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_str)

    webbrowser.open('file://' + os.path.realpath(output_file))

    root.destroy()

root = tk.Tk()
root.title("Poker Hand History Processor")
root.geometry("400x200")

btn_select = tk.Button(root, text="Select Hand History Files", command=select_files)
btn_select.pack(expand=True)

root.mainloop()