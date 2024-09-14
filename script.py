import os
import re
from collections import defaultdict
from datetime import datetime, timedelta
import plotly.express as px
import pandas as pd

# Define a function to extract and clean the tournament name from the content of the file
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

# Define a function to extract the date, time, and Hero's stack in big blinds
def extract_info(file_path, tournament_counts):
    with open(file_path, 'r') as file:
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
        return {
            "tournament_name": tournament_name,
            "first_hand_time": datetime.strptime(first_hand_time, "%Y/%m/%d %H:%M:%S"),
            "last_hand_time": datetime.strptime(last_hand_time, "%Y/%m/%d %H:%M:%S"),
            "stack_in_bb": int(hero_stack_bb) if hero_stack_bb is not None else None
        }
    else:
        print(f"Could not extract information from file: {file_path}")
        return None

# Function to scan the current directory for all .txt files and process each one
def process_all_files_in_folder():
    current_directory = os.getcwd()
    txt_files = [f for f in os.listdir(current_directory) if f.endswith('.txt')]
    if not txt_files:
        print("No .txt files found in the current directory.")
        return

    tournament_data = defaultdict(list)
    for file_name in txt_files:
        file_path = os.path.join(current_directory, file_name)
        tournament_info = extract_info(file_path, tournament_data)
        if tournament_info:
            tournament_data[tournament_info['tournament_name']].append(tournament_info)
    stats = calculate_statistics(tournament_data)
    return plot_tournament_data(tournament_data, stats)

# Function to calculate and return statistics
def calculate_statistics(tournament_data):
    total_bullets, re_entries, unique_tournaments = 0, 0, len(tournament_data)
    total_duration, peak_duration, peak_start_time = timedelta(), timedelta(), None
    timeline = []

    # Creating a timeline with start and end times to calculate average and peak tables played
    for tournament_name, entries in tournament_data.items():
        total_bullets += len(entries)
        re_entries += len(entries) - 1 if len(entries) > 1 else 0
        for entry in entries:
            duration = entry['last_hand_time'] - entry['first_hand_time']
            total_duration += duration
            timeline.append((entry['first_hand_time'], 1))  # Add event for starting a table
            timeline.append((entry['last_hand_time'], -1))  # Add event for closing a table

    # Sort the timeline based on time
    timeline.sort()

    # Calculating max tables played at a time and average tables played
    max_tables, current_tables = 0, 0
    total_tables_time, last_time = timedelta(), None
    peak_tables, peak_duration = 0, timedelta()

    for time, change in timeline:
        if last_time is not None:
            elapsed_time = time - last_time
            total_tables_time += elapsed_time * current_tables

            # Checking if we are in the peak overlap time
            if current_tables == max_tables:
                peak_duration += elapsed_time

        current_tables += change
        if current_tables > max_tables:
            max_tables = current_tables
            peak_duration = timedelta()  # Reset peak time duration when new max is reached

        last_time = time

    # Calculating average tables played across the full session
    full_session_duration = timeline[-1][0] - timeline[0][0] if timeline else timedelta()
    avg_tables_played = total_tables_time.total_seconds() / full_session_duration.total_seconds() if full_session_duration else 0

    return {
        "Session duration": str(full_session_duration).split('.')[0],
        "Unique tournaments played": unique_tournaments,
        "Re-Entries": re_entries,
        "Total bullets": total_bullets,
        "Average duration per tournament": total_duration / total_bullets if total_bullets else timedelta(),
        "Maximum tables played at a time": max_tables,
        "Average tables played": avg_tables_played,
        "Peak tables played for (total time)": peak_duration
    }

# Function to plot the tournament data using Plotly and export HTML
def plot_tournament_data(tournament_data, stats):
    data = []
    for i, (tournament_name, entries) in enumerate(tournament_data.items()):
        for j, entry in enumerate(entries):
            start_time, end_time = entry['first_hand_time'], entry['last_hand_time']
            bb_stack = entry['stack_in_bb'] if entry['stack_in_bb'] is not None else "N/A"
            entry_type = "Re-entry" if j > 0 else "First entry"
            data.append({
                'Tournament': tournament_name,
                'Start Time': start_time,
                'Formatted Start Time': start_time.strftime('%H:%M'),
                'Stack (BB)': f"{bb_stack} BB" if bb_stack != "N/A" else "N/A",
                'End Time': end_time,
                'Index': i,
                'Entry Type': entry_type
            })

    df = pd.DataFrame(data)

    # Customizing the color scale for first entry and re-entry
    color_discrete_map = {
        'First entry': 'lightgrey',
        'Re-entry': 'red'
    }

    # Create the graph
    fig = px.timeline(
        df,
        x_start="Start Time",
        x_end="End Time",
        y='Index',
        color='Entry Type',
        color_discrete_map=color_discrete_map,
        hover_data={'Formatted Start Time': True, 'Stack (BB)': True, 'Entry Type': False},
        height=600
    )
    fig.update_traces(
        hovertemplate="<b>Registered: %{customdata[0]}<br>Stack: %{customdata[1]}</b>"
    )
    fig.update_layout(
        yaxis=dict(tickvals=df['Index'], ticktext=df['Tournament']),
        xaxis_title="Session time",
        yaxis_title="Tournament",
        margin=dict(l=50, r=50, t=50, b=50),
        paper_bgcolor="#333333",
        plot_bgcolor="#333333",
        font=dict(family="Arial", size=12, color="white")
    )
    fig.update_xaxes(type='date', showgrid=True, gridwidth=1, gridcolor='#444')
    fig.update_yaxes(showgrid=False)

    # Export the graph as an HTML file
    graph_html = fig.to_html(full_html=False)

    # Create the statistics block with better styling and reduced spacing between stats
    stats_html = f"""
        <p><b>Session duration:</b> <span class="highlight">{stats['Session duration']}</span></p>
        <p><b>Unique tournaments played:</b> <span class="highlight">{stats['Unique tournaments played']}</span></p>
        <p><b>Re-Entries:</b> <span class="highlight">{stats['Re-Entries']}</span></p>
        <p><b>Total bullets:</b> <span class="highlight">{stats['Total bullets']}</span></p>
        <p><b>Average duration per tournament:</b> <span class="highlight">{str(stats['Average duration per tournament']).split('.')[0]}</span></p>
        <p><b>Maximum tables played at a time:</b> <span class="highlight">{stats['Maximum tables played at a time']}</span></p>
        <p><b>Average tables played:</b> <span class="highlight">{stats['Average tables played']:.2f}</span></p>
        <p><b>Peak tables played for (total time):</b> <span class="highlight">{str(stats['Peak tables played for (total time)']).split('.')[0]}</span></p>
    """

    # Combine the graph and statistics into one HTML page
    with open("session_stats.html", "w", encoding="utf-8") as f:
        f.write(f"""
        <html>
        <head>
            <title>Seven Goats Session Analyzer</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background-color: #333333;
                    color: white;
                }}
                .container {{
                    width: 90%;
                    margin: 0 auto;
                }}
                .stats {{
                    padding: 15px;
                    background-color: #222;
                    border: 1px solid #444;
                    border-radius: 5px;
                    margin-bottom: 15px;
                }}
                h3 {{
                    color: #58A65A;
                    text-align: center;
                }}
                p {{
                    color: white;
                    margin: 5px 0;  /* Reducing space between paragraphs */
                }}
                .highlight {{
                    color: #58A65A;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="stats">
                    <h3>Session Statistics</h3>
                    {stats_html}
                </div>
                {graph_html}
            </div>
        </body>
        </html>
        """)

if __name__ == "__main__":
    process_all_files_in_folder()