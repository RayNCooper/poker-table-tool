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

# Function to select files
def select_files():
    files = filedialog.askopenfilenames(title="Select Hand History Files")
    if files:
        root.withdraw()  # Hide the root window
        process_files(files)
    else:
        messagebox.showerror("Error", "No files selected.")

# Function to extract tournament label from file name
def extract_tournament_label(file_name):
    patterns = [
        r'Tournament (.+?) \(',  # Pattern for 888poker example
        r'TN-(.+?) GAMETYPE-',   # Pattern for HH20230320 example
        r'- (.+)\.txt$',         # Pattern for GG example
        r'HH\d+ (.+?)\.txt$',    # Pattern for HH files
        r'\d+_(.+?)\(\d+\)_real_holdem_no-limit\.txt$',  # Pattern for 20230312_MYSTERY KO example
        r'\d+_(.+?)\.txt$',      # Additional pattern for general cases
    ]
    for pattern in patterns:
        match = re.search(pattern, file_name)
        if match:
            return match.group(1).strip()
    return None

# Function to process files
def process_files(file_list):
    hand_histories = []

    for file in file_list:
        # Skip summary files
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
                        continue  # Skip if no player found
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

# Function to identify the site based on content
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

# Function to parse hand history
def parse_hand_history(content, site, tournament_label=None):
    hands = []
    player = None
    if site == "ACR":
        # Regex patterns for ACR
        player_seats = re.findall(r"Seat \d+: (\S+)", content)
        if player_seats:
            player_counts = defaultdict(int)
            for p in player_seats:
                player_counts[p] += 1
            player = max(player_counts, key=player_counts.get)
        else:
            print("Player not found in ACR hand history.")
            return [], None

        tournament_pattern = r"Tournament #(\d+)"
        date_pattern = r"- (\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})"
        hand_pattern = r"Game Hand #(\d+) - Tournament #(\d+)"
        date_format = '%Y/%m/%d %H:%M:%S'

        tournaments = re.findall(tournament_pattern, content)
        dates = re.findall(date_pattern, content)
        hands_info = re.findall(hand_pattern, content)

        # Extract starting stack and blinds
        starting_stack_pattern = rf"Seat \d+: {re.escape(player)} \(([\d\.]+)\)"
        blinds_pattern = r"Level \d+ \(([\d\.]+)/([\d\.]+)\)"

        starting_stack_match = re.search(starting_stack_pattern, content)
        blinds_match = re.search(blinds_pattern, content)

        if starting_stack_match and blinds_match:
            starting_stack = float(starting_stack_match.group(1).replace(',', ''))
            big_blind = float(blinds_match.group(2).replace(',', ''))
            starting_bb = starting_stack / big_blind
        else:
            starting_bb = None

        tournament_name = tournaments[0] if tournaments else 'Unknown'
        if not tournament_label:
            tournament_label = tournament_name

        for idx, (hand_id, tour_id) in enumerate(hands_info):
            hand_date = dates[idx] if idx < len(dates) else None
            hands.append({
                'site': site,
                'tournament_id': tour_id,
                'hand_id': hand_id,
                'date': parse_date(hand_date, [date_format]),
                'player': player,
                'starting_bb': starting_bb,
                'tournament_name': tournament_name,
                'tournament_label': tournament_label,
            })

    elif site == "888":
        # Similar code for 888
        player_seats = re.findall(r"Seat \d+: (\S+)", content)
        if player_seats:
            player_counts = defaultdict(int)
            for p in player_seats:
                player_counts[p] += 1
            player = max(player_counts, key=player_counts.get)
        else:
            print("Player not found in 888 hand history.")
            return [], None

        tournament_pattern = r"Tournament #(\d+)"
        date_pattern = r"\*\*\* (.+)"
        hand_pattern = r"Game (\d+)"
        date_format = '%d %m %Y %H:%M:%S'

        tournaments = re.findall(tournament_pattern, content)
        dates = re.findall(date_pattern, content)
        hands_info = re.findall(hand_pattern, content)

        # Do not extract starting_bb for 888
        starting_bb = None

        tournament_name = tournaments[0] if tournaments else 'Unknown'
        if not tournament_label:
            tournament_label = tournament_name

        for idx, hand_id in enumerate(hands_info):
            hand_date = dates[idx] if idx < len(dates) else None
            hands.append({
                'site': site,
                'tournament_id': tournament_name,
                'hand_id': hand_id,
                'date': parse_date(hand_date, [date_format]),
                'player': player,
                'starting_bb': starting_bb,
                'tournament_name': tournament_name,
                'tournament_label': tournament_label,
            })

    elif site == "GG":
        # Similar code for GG
        player_seats = re.findall(r"Seat \d+: (\S+) \(", content)
        if player_seats:
            player_counts = defaultdict(int)
            for p in player_seats:
                player_counts[p] += 1
            player = max(player_counts, key=player_counts.get)
        else:
            print("Player not found in GG hand history.")
            return [], None

        tournament_pattern = r"Tournament #(\d+)"
        date_pattern = r"Level\d+\([\d,]+/[\d,]+\) - (\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})"
        hand_pattern = r"Poker Hand #(\S+): Tournament #(\d+)"
        date_format = '%Y/%m/%d %H:%M:%S'

        tournaments = re.findall(tournament_pattern, content)
        dates = re.findall(date_pattern, content)
        hands_info = re.findall(hand_pattern, content)

        starting_stack_pattern = rf"Seat \d+: {re.escape(player)} \(([\d,]+) in chips\)"
        blinds_pattern = r"Level\d+\(([\d,]+)/([\d,]+)\)"

        starting_stack_match = re.search(starting_stack_pattern, content)
        blinds_match = re.search(blinds_pattern, content)

        if starting_stack_match and blinds_match:
            starting_stack = float(starting_stack_match.group(1).replace(',', ''))
            big_blind = float(blinds_match.group(2).replace(',', ''))
            starting_bb = starting_stack / big_blind
        else:
            starting_bb = None

        tournament_name = tournaments[0] if tournaments else 'Unknown'
        if not tournament_label:
            tournament_label = tournament_name

        for idx, (hand_id, tour_id) in enumerate(hands_info):
            hand_date = dates[idx] if idx < len(dates) else None
            hands.append({
                'site': site,
                'tournament_id': tour_id,
                'hand_id': hand_id,
                'date': parse_date(hand_date, [date_format]),
                'player': player,
                'starting_bb': starting_bb,
                'tournament_name': tournament_name,
                'tournament_label': tournament_label,
            })

    elif site == "PokerStars":
        # Similar code for PokerStars
        player_seats = re.findall(r"Seat \d+: (\S+) \(", content)
        if player_seats:
            player_counts = defaultdict(int)
            for p in player_seats:
                player_counts[p] += 1
            player = max(player_counts, key=player_counts.get)
        else:
            print("Player not found in PokerStars hand history.")
            return [], None

        tournament_pattern = r"Tournament #(\d+)"
        date_pattern = r"\[([^\]]+)\]"
        hand_pattern = r"PokerStars Hand #(\d+): Tournament #(\d+)"
        date_formats = ['%Y/%m/%d %H:%M:%S ET', '%Y/%m/%d %H:%M:%S CET']

        tournaments = re.findall(tournament_pattern, content)
        dates = re.findall(date_pattern, content)
        hands_info = re.findall(hand_pattern, content)

        starting_stack_pattern = rf"Seat \d+: {re.escape(player)} \(([\d,]+) in chips"
        blinds_pattern = r"Level \w+ \(([\d,]+)/([\d,]+)\)"

        starting_stack_match = re.search(starting_stack_pattern, content)
        blinds_match = re.search(blinds_pattern, content)

        if starting_stack_match and blinds_match:
            starting_stack = float(starting_stack_match.group(1).replace(',', ''))
            big_blind = float(blinds_match.group(2).replace(',', ''))
            starting_bb = starting_stack / big_blind
        else:
            starting_bb = None

        tournament_name = tournaments[0] if tournaments else 'Unknown'
        if not tournament_label:
            tournament_label = tournament_name

        for idx, (hand_id, tour_id) in enumerate(hands_info):
            hand_date = dates[idx] if idx < len(dates) else None
            hand_date_parsed = parse_date(hand_date, date_formats)
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

    elif site == "Winamax":
        # Similar code for Winamax
        player_seats = re.findall(r"Seat \d+: (\S+)", content)
        if player_seats:
            player_counts = defaultdict(int)
            for p in player_seats:
                player_counts[p] += 1
            player = max(player_counts, key=player_counts.get)
        else:
            print("Player not found in Winamax hand history.")
            return [], None

        tournament_pattern = r"Tournament \"(.+?)\""
        date_pattern = r"- (\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) UTC"
        hand_pattern = r"HandId: #(\d+)-"
        date_format = '%Y/%m/%d %H:%M:%S'

        tournaments = re.findall(tournament_pattern, content)
        dates = re.findall(date_pattern, content)
        hands_info = re.findall(hand_pattern, content)

        # Do not extract starting_bb for Winamax
        starting_bb = None

        tournament_name = tournaments[0] if tournaments else 'Unknown'
        if not tournament_label:
            tournament_label = tournament_name

        for idx, hand_id in enumerate(hands_info):
            hand_date = dates[idx] if idx < len(dates) else None
            hand_date_parsed = parse_date(hand_date, [date_format])
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

# Function to parse date
def parse_date(date_str, date_formats):
    if date_str:
        for fmt in date_formats:
            try:
                return datetime.datetime.strptime(date_str.strip(), fmt)
            except:
                continue
    return None

# Function to plot Gantt chart using plotly
def plot_gantt_chart(hands):
    # Prepare data
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
        dates.sort()
        tournament_label = value['tournament_label']
        # Detect re-entries based on time gaps
        entries_in_tournament = []
        current_entry = [dates[0], dates[0]]
        for i in range(1, len(dates)):
            if (dates[i] - dates[i-1]).total_seconds() > 1800:  # Gap of more than 30 minutes
                current_entry[1] = dates[i-1]
                entries_in_tournament.append(tuple(current_entry))
                current_entry = [dates[i], dates[i]]
            else:
                current_entry[1] = dates[i]
        current_entry[1] = dates[-1]
        entries_in_tournament.append(tuple(current_entry))
        for idx, (start_time, end_time) in enumerate(entries_in_tournament):
            entry_type = 'Entry' if idx == 0 else 'Re-Entry'
            category = site  # Use only 'site' for coloring to limit legend items to 5
            entries.append({
                'Tournament': tournament_label,
                'Start': start_time,
                'Finish': end_time,
                'Site': site,
                'Category': category,
                'Player': player,
                'Entry': entry_type,
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

    # Compute statistics
    session_start = df['Start'].min()
    session_end = df['Finish'].max()
    session_duration = session_end - session_start

    unique_tournaments = df['Tournament'].nunique()
    total_bullets = len(df)
    re_entries = total_bullets - unique_tournaments

    df['Duration'] = df['Finish'] - df['Start']
    tournament_durations = df.groupby('Tournament')['Duration'].sum()
    avg_duration_per_tournament = tournament_durations.mean()

    # Compute tables played over time
    events = []
    for index, row in df.iterrows():
        events.append((row['Start'], 'start'))
        events.append((row['Finish'], 'end'))
    events.sort()

    current_tables = 0
    max_tables = 0
    time_of_last_event = None
    table_time = defaultdict(datetime.timedelta)

    for time, event_type in events:
        if time_of_last_event is not None:
            duration = time - time_of_last_event
            table_time[current_tables] += duration
        if event_type == 'start':
            current_tables += 1
            if current_tables > max_tables:
                max_tables = current_tables
        elif event_type == 'end':
            current_tables -= 1
        time_of_last_event = time

    total_session_duration = session_end - session_start

    total_weighted_time = sum(tables * duration.total_seconds() for tables, duration in table_time.items())
    average_tables = total_weighted_time / total_session_duration.total_seconds() if total_session_duration.total_seconds() > 0 else 0

    peak_tables_time = table_time[max_tables]

    # Format statistics
    stats_text = (
        f"<b>Session Duration:</b> {str(session_duration)}<br>"
        f"<b>Unique Tournaments Played:</b> {unique_tournaments}<br>"
        f"<b>Re-Entries:</b> {re_entries}<br>"
        f"<b>Total Bullets:</b> {total_bullets}<br>"
        f"<b>Avg Duration per Tournament:</b> {str(avg_duration_per_tournament)}<br>"
        f"<b>Maximum Tables Played at a Time:</b> {max_tables}<br>"
        f"<b>Average Tables Played:</b> {average_tables:.2f}<br>"
        f"<b>Peak Tables Played For:</b> {str(peak_tables_time)}"
    )

    # Create the plot
    df['Start_str'] = df['Start'].dt.strftime('%Y-%m-%d %H:%M:%S')
    df['Finish_str'] = df['Finish'].dt.strftime('%Y-%m-%d %H:%M:%S')

    # Prepare hover data
    # Create a new column 'Starting_BB_Display' for hover data
    df['Starting_BB_Display'] = df.apply(
        lambda row: f"{row['Starting_BB']:.1f}" if row['Site'] in ['ACR', 'PokerStars', 'GG'] and pd.notnull(row['Starting_BB']) else None, axis=1
    )

    # Define hover data columns
    hover_data = {
        'Site': True,
        'Start_str': True,
        'Finish_str': True,
        'Tournament': True,
        'Entry': True,
        'Starting_BB_Display': True,
    }

    # Build custom hover template
    hover_template = (
        'Site=%{customdata[0]}<br>'
        'Start=%{customdata[1]}<br>'
        'Finish=%{customdata[2]}<br>'
        'Tournament=%{customdata[3]}<br>'
        'Entry Type=%{customdata[4]}<br>'
    )
    hover_template += '%{customdata[5]}<extra></extra>'

    # Prepare custom data for hover
    df['Starting_BB_Hover'] = df.apply(
        lambda row: f"Starting BB={row['Starting_BB_Display']}" if row['Starting_BB_Display'] else '', axis=1
    )

    custom_data = df[['Site', 'Start_str', 'Finish_str', 'Tournament', 'Entry', 'Starting_BB_Hover']]

    fig = px.timeline(
        df,
        x_start="Start",
        x_end="Finish",
        y="Tournament",
        color="Site",
        color_discrete_map=base_colors,
        hover_data=None,
        custom_data=custom_data,
    )

    fig.update_traces(hovertemplate=hover_template)

    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        title="Poker Tournaments",
        xaxis_title="Time",
        yaxis_title="Tournaments",
        legend_title="Site",
        margin=dict(l=20, r=20, t=50, b=20),
    )

    # Generate HTML output
    fig_html = pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
    html_str = f'''
    <html>
    <head>
        <title>Poker Tournaments</title>
        <style>
            .stats-box {{
                padding: 10px;
                border: 1px solid #ccc;
                margin-bottom: 20px;
                background-color: #f9f9f9;
                width: 80%;
                margin-left: auto;
                margin-right: auto;
            }}
            .stats-box h2 {{
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="stats-box">
            <h2>Session Summary</h2>
            <p>{stats_text}</p>
        </div>
        {fig_html}
    </body>
    </html>
    '''

    # Save HTML file
    output_file = 'poker_tournaments.html'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_str)

    # Open the HTML file in the default web browser
    webbrowser.open('file://' + os.path.realpath(output_file))

    # Close the Tkinter root window
    root.destroy()

# Main GUI setup
root = tk.Tk()
root.title("Poker Hand History Processor")
root.geometry("400x200")

btn_select = tk.Button(root, text="Select Hand History Files", command=select_files)
btn_select.pack(expand=True)

root.mainloop()