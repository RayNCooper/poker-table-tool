# main.py

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from collections import defaultdict
from datetime import datetime, timedelta
import plotly.express as px
import pandas as pd
import webbrowser

# Import extraction modules
import extract_gg
import extract_888

# Mapping categories to their respective extraction modules
EXTRACTION_MODULES = {
    "GG": extract_gg,
    "888": extract_888
}

# Function to calculate and return statistics
def calculate_statistics(tournament_data):
    total_bullets, re_entries, unique_tournaments = 0, 0, len(tournament_data)
    total_duration, peak_duration = timedelta(), timedelta()
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
    peak_duration = timedelta()

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
        "Average duration per tournament": str(total_duration / total_bullets).split('.')[0] if total_bullets else "00:00:00",
        "Maximum tables played at a time": max_tables,
        "Average tables played": round(avg_tables_played, 2),
        "Peak tables played for (total time)": str(peak_duration).split('.')[0]
    }

# Function to plot the tournament data using Plotly and export HTML
# main.py (only the plot_tournament_data function is shown)

def plot_tournament_data(tournament_data, stats):
    data = []
    for i, (tournament_name, entries) in enumerate(tournament_data.items()):
        # Sort the entries by first_hand_time to ensure correct ordering
        sorted_entries = sorted(entries, key=lambda x: x['first_hand_time'])
        for j, entry in enumerate(sorted_entries):
            start_time = entry['first_hand_time']
            end_time = entry['last_hand_time']
            stack_in_bb = entry.get('stack_in_bb', "N/A")
            entry_type = "Re-entry" if j > 0 else "First entry"
            formatted_start_time = start_time.strftime('%H:%M')
            formatted_end_time = end_time.strftime('%H:%M')  # Added for hover info
            data.append({
                'Tournament': tournament_name,
                'Category': entry['category'],
                'Start Time': start_time,
                'Formatted Start Time': formatted_start_time,  # Added
                'End Time': end_time,
                'Formatted End Time': formatted_end_time,      # Added
                'Stack (BB)': f"{stack_in_bb} BB" if stack_in_bb != "N/A" else "N/A",
                'Entry Type': entry_type,
                'Game Number': entry.get('game_number', "N/A"),
                'Table Number': entry.get('table_number', "N/A"),
                'Max Players': entry.get('max_players', "N/A"),
                'Currency': entry.get('currency', "N/A"),
                'Hero Name': entry.get('hero_name', "N/A")
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
        y='Tournament',
        color='Entry Type',
        color_discrete_map=color_discrete_map,
        hover_data={
            'Formatted Start Time': True,  # Changed to True if needed
            'Formatted End Time': True,    # Added
            'Stack (BB)': True,
            'Category': True,
            'Game Number': True,
            'Table Number': True,
            'Max Players': True,
            'Currency': True,
            'Hero Name': True
        },
        height=600,
        title="Tournament Sessions"
    )
    fig.update_traces(
        hovertemplate=(
            "<b>Tournament:</b> %{y}<br>"
            "<b>Entry Type:</b> %{marker.color}<br>"
            "<b>Game Number:</b> %{customdata[0]}<br>"
            "<b>Table Number:</b> %{customdata[1]}<br>"
            "<b>Max Players:</b> %{customdata[2]}<br>"
            "<b>Currency:</b> %{customdata[3]}<br>"
            "<b>Hero Name:</b> %{customdata[4]}<br>"
            "<b>Start Time:</b> %{customdata[5]}<br>"
            "<b>End Time:</b> %{customdata[6]}<br>"
            "<b>Stack:</b> %{customdata[7]}"
        )
    )
    fig.update_layout(
        yaxis_title="Tournament",
        xaxis_title="Session Time",
        legend_title="Entry Type",
        legend=dict(
            title_font_family="Arial",
            font=dict(
                family="Arial",
                size=12,
                color="white"
            )
        ),
        margin=dict(l=150, r=50, t=100, b=50),
        paper_bgcolor="#333333",
        plot_bgcolor="#333333",
        font=dict(family="Arial", size=12, color="white"),
        title_font=dict(color="white", size=20)
    )
    fig.update_xaxes(type='date', showgrid=True, gridwidth=1, gridcolor='#444')
    fig.update_yaxes(showgrid=False, tickfont=dict(color="white"))

    # Export the graph as an HTML file
    graph_html = fig.to_html(full_html=False)

    # Create the statistics block with better styling and reduced spacing between stats
    stats_html = f"""
        <p><b>Session duration:</b> <span class="highlight">{stats['Session duration']}</span></p>
        <p><b>Unique tournaments played:</b> <span class="highlight">{stats['Unique tournaments played']}</span></p>
        <p><b>Re-Entries:</b> <span class="highlight">{stats['Re-Entries']}</span></p>
        <p><b>Total bullets:</b> <span class="highlight">{stats['Total bullets']}</span></p>
        <p><b>Average duration per tournament:</b> <span class="highlight">{stats['Average duration per tournament']}</span></p>
        <p><b>Maximum tables played at a time:</b> <span class="highlight">{stats['Maximum tables played at a time']}</span></p>
        <p><b>Average tables played:</b> <span class="highlight">{stats['Average tables played']}</span></p>
        <p><b>Peak tables played for (total time):</b> <span class="highlight">{stats['Peak tables played for (total time)']}</span></p>
    """

    # Combine the graph and statistics into one HTML page
    with open("session_stats.html", "w", encoding="utf-8") as f:
        f.write(f"""
        <html>
        <head>
            <title>Tournament Session Analyzer</title>
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

    return os.path.abspath("session_stats.html")
    
# Function to process the selected files
def process_selected_files(selected_files, category):
    if not selected_files:
        messagebox.showwarning("No Files Selected", "Please select at least one .txt file to process.")
        return

    if category not in EXTRACTION_MODULES:
        messagebox.showerror("Invalid Category", f"The selected category '{category}' is not supported.")
        return

    extraction_module = EXTRACTION_MODULES[category]

    tournament_data = defaultdict(list)
    for file_path in selected_files:
        extracted_entries = extraction_module.extract_info(file_path, category)
        if extracted_entries:
            for entry in extracted_entries:
                tournament_data[entry['tournament_name']].append(entry)
        else:
            messagebox.showwarning("Extraction Warning", f"No valid data extracted from file: {os.path.basename(file_path)}")

    if not tournament_data:
        messagebox.showerror("Processing Error", "No valid tournament data found in the selected files.")
        return

    stats = calculate_statistics(tournament_data)
    html_path = plot_tournament_data(tournament_data, stats)

    # Open the generated HTML in the default web browser
    webbrowser.open(f'file://{html_path}')

# Function to handle file selection
def select_files():
    file_paths = filedialog.askopenfilenames(
        title="Select Tournament Log Files",
        filetypes=(("Text Files", "*.txt"), ("All Files", "*.*"))
    )
    if file_paths:
        app.selected_files = list(file_paths)
        update_file_list()

# Function to update the file list display
def update_file_list():
    file_listbox.delete(0, tk.END)
    for file in app.selected_files:
        filename = os.path.basename(file)
        file_listbox.insert(tk.END, f"• {filename}")

# Initialize the Tkinter application
app = tk.Tk()
app.title("Tournament Session Analyzer")
app.geometry("700x500")
app.resizable(False, False)

# Store selected files
app.selected_files = []

# Configure grid layout
app.columnconfigure(0, weight=1)
app.rowconfigure(0, weight=1)

# Main frame
main_frame = ttk.Frame(app, padding="20")
main_frame.pack(fill=tk.BOTH, expand=True)

# Dropdown for category selection
category_label = ttk.Label(main_frame, text="Select Category:")
category_label.grid(row=0, column=0, sticky=tk.W, pady=(0, 5))

category_var = tk.StringVar()
category_combobox = ttk.Combobox(main_frame, textvariable=category_var, state="readonly")
category_combobox['values'] = ("GG", "888")
category_combobox.current(0)
category_combobox.grid(row=0, column=1, sticky=tk.W, pady=(0, 5))

# File selection button
select_button = ttk.Button(main_frame, text="Select Files", command=select_files)
select_button.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))

# Listbox to display selected files with a scrollbar
listbox_frame = ttk.Frame(main_frame)
listbox_frame.grid(row=2, column=0, columnspan=2, sticky=tk.W+tk.E, pady=(0, 10))

file_listbox = tk.Listbox(listbox_frame, height=15, width=80, selectmode=tk.BROWSE, bg="#f0f0f0")
file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL, command=file_listbox.yview)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

file_listbox.config(yscrollcommand=scrollbar.set)

# Process & Display button
process_button = ttk.Button(main_frame, text="Process & Display", command=lambda: process_selected_files(app.selected_files, category_var.get()))
process_button.grid(row=3, column=0, columnspan=2, pady=(10, 0))

# Run the application
app.mainloop()