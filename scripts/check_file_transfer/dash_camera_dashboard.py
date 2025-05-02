#!/usr/bin/env python3
"""
Camera Statistics Dashboard
--------------------------
A web-based dashboard to visualize camera frames and statistics over time.
Uses the SQLite database created by the file transfer check script.
"""

import dash
from dash import dcc, html, dash_table
import plotly.express as px
import plotly.graph_objects as go
from dash.dependencies import Input, Output, State
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import os
import re

# Configure paths
DB_FILE = "/mnt/data/lk1167/projects/Stream2Frame/data/database/camera_stats.db"
ASSETS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# Make sure assets directory exists
os.makedirs(ASSETS_PATH, exist_ok=True)

# Modern color palette
COLOR_PALETTE = {
    "primary": "#6366F1",     # Indigo
    "secondary": "#14B8A6",   # Teal
    "success": "#22C55E",     # Green
    "warning": "#F59E0B",     # Amber
    "danger": "#F43F5E",      # Rose
    "gray": "#94A3B8",        # Slate
    "background": "#F8FAFC",  # Slate 50
    "text": "#334155",        # Slate 700
}

# Function to sort camera names naturally (e.g., G5Bullet_7 comes before G5Bullet_10)
def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

# Load data from SQLite database
def load_data(days=30, include_inactive=False):
    try:
        conn = sqlite3.connect(DB_FILE)
        
        # Handle "this_year" special case
        if days == "this_year":
            # Set cutoff to January 1st of current year
            current_year = datetime.now().year
            cutoff_date = f"{current_year}-01-01"
        else:
            # Normal case: last N days
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        # Query for camera stats since the cutoff date, exclude inactive cameras by default
        active_filter = "" if include_inactive else "AND is_active = 1"
        
        query = f"""
        SELECT date, camera, mp4_exists, mp4_size, mp4_size_mb, frame_count, is_active
        FROM camera_stats
        WHERE date >= '{cutoff_date}' {active_filter}
        ORDER BY date DESC, camera
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        return df
    except Exception as e:
        print(f"Error loading data: {e}")
        # Return empty DataFrame with correct columns if there's an error
        return pd.DataFrame(columns=['date', 'camera', 'mp4_exists', 'mp4_size', 'mp4_size_mb', 'frame_count', 'is_active'])

# Get available dates from the database
def get_available_dates(days=90):
    try:
        conn = sqlite3.connect(DB_FILE)
        
        # Handle "this_year" special case
        if days == "this_year":
            # Set cutoff to January 1st of current year
            current_year = datetime.now().year
            cutoff_date = f"{current_year}-01-01"
        else:
            # Normal case: last N days
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        query = f"""
        SELECT DISTINCT date FROM camera_stats
        WHERE date >= '{cutoff_date}'
        ORDER BY date DESC
        """
        
        dates = pd.read_sql_query(query, conn)['date'].tolist()
        conn.close()
        
        return dates
    except Exception as e:
        print(f"Error getting available dates: {e}")
        return []

# Initialize the Dash app
app = dash.Dash(__name__, 
                title="Camera Statistics Dashboard",
                assets_folder=ASSETS_PATH,
                meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}])

# Create some custom CSS for better styling
with open(os.path.join(ASSETS_PATH, "custom.css"), "w") as f:
    f.write(f"""
body {{
    font-family: 'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    margin: 0;
    background-color: {COLOR_PALETTE["background"]};
    color: {COLOR_PALETTE["text"]};
}}
.header {{
    background-color: {COLOR_PALETTE["primary"]};
    color: white;
    padding: 1.5rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
}}
.content {{
    padding: 1.5rem;
    max-width: 1500px;
    margin: 0 auto;
}}
.card {{
    background-color: white;
    border-radius: 0.5rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    padding: 1.5rem;
    margin-bottom: 2.5rem;
}}
.row {{
    display: flex;
    flex-wrap: wrap;
    margin: 0 -0.75rem;
    margin-bottom: 1.5rem;
}}
.row_metrics {{
    display: flex;
    flex-wrap: wrap;
    margin: 0 -0.75rem;
}}
.col {{
    flex: 1;
    padding: 0 0.75rem;
    min-width: 300px;
}}
.date-selector {{
    display: flex;
    align-items: center;
    margin-bottom: 1rem;
}}
.date-selector label {{
    margin-right: 15px;
    font-weight: 600;
    color: {COLOR_PALETTE["text"]};
}}
.date-selector .date-dropdown {{
    flex-grow: 1;
    min-width: 250px;
    max-width: 400px;
}}
.date-selector .date-picker {{
    margin-right: 10px;
    margin-bottom: 10px;
}}
.date-nav-buttons {{
    display: flex;
    margin-left: 15px;
}}
.date-nav-button {{
    background-color: {COLOR_PALETTE["primary"]};
    color: white;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    margin: 0 5px;
    cursor: pointer;
    font-weight: 500;
    transition: background-color 0.2s ease;
}}
.date-nav-button:hover {{
    background-color: {COLOR_PALETTE["primary"]}cc;
}}
.date-nav-button:disabled {{
    background-color: {COLOR_PALETTE["gray"]};
    cursor: not-allowed;
}}
.metric-card {{
    background-color: white;
    border-radius: 0.5rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    padding: 1.5rem;
    margin-bottom: 1rem;
    text-align: center;
    border-left: 5px solid {COLOR_PALETTE["primary"]};
}}
.metric-value {{
    font-size: 2.5rem;
    font-weight: 700;
    color: {COLOR_PALETTE["primary"]};
    margin-bottom: 0.5rem;
}}
.metric-label {{
    font-size: 1.1rem;
    color: {COLOR_PALETTE["gray"]};
    font-weight: 500;
}}
.alert {{
    background-color: {COLOR_PALETTE["danger"]};
    color: white;
    padding: 0.75rem 1.25rem;
    border-radius: 0.5rem;
    margin-bottom: 1rem;
    font-weight: 500;
}}
h2 {{
    color: {COLOR_PALETTE["primary"]};
    margin-top: 0;
    font-weight: 600;
}}
.footer {{
    text-align: center;
    padding: 1.5rem;
    color: {COLOR_PALETTE["gray"]};
    font-size: 0.9rem;
}}
.tabs-content {{
    padding: 1.5rem 0;
}}
table {{
    width: 100%;
    border-collapse: collapse;
}}
th, td {{
    padding: 0.75rem;
    text-align: left;
    border-bottom: 1px solid #e2e8f0;
}}
th {{
    background-color: #f8fafc;
    font-weight: 600;
}}
/* Custom styling for dropdowns */
.dash-dropdown .Select-control {{
    border: 1px solid #e2e8f0;
    border-radius: 0.375rem;
    height: 40px;
}}
.dash-dropdown .Select-placeholder,
.dash-dropdown .Select-input, 
.dash-dropdown .Select-value {{
    padding-top: 5px;
}}
/* Make date dropdowns wider */
.date-dropdown .Select-control {{
    width: 100%;
    min-width: 250px;
}}
/* Custom styling for sliders */
.rc-slider-track {{
    background-color: {COLOR_PALETTE["primary"]};
}}
.rc-slider-handle {{
    border-color: {COLOR_PALETTE["primary"]};
}}
.rc-slider-handle:hover,
.rc-slider-handle:active {{
    border-color: {COLOR_PALETTE["primary"]}cc;
    box-shadow: 0 0 0 5px {COLOR_PALETTE["primary"]}33;
}}
/* Calendar date picker styling */
.SingleDatePickerInput {{
    border: 1px solid #e2e8f0;
    border-radius: 0.375rem;
}}
.DateInput {{
    width: 130px;
}}
.DateInput_input {{
    font-size: 16px;
    line-height: 24px;
    color: {COLOR_PALETTE["text"]};
    padding: 7px 12px;
    border-bottom: none;
}}
.CalendarDay__selected {{
    background: {COLOR_PALETTE["primary"]};
    border: 1px solid {COLOR_PALETTE["primary"]};
}}
.CalendarDay__selected:hover {{
    background: {COLOR_PALETTE["primary"]}cc;
}}
.CalendarDay__hovered_span, 
.CalendarDay__selected_span {{
    background: {COLOR_PALETTE["primary"]}44;
    color: {COLOR_PALETTE["text"]};
}}
.DayPickerKeyboardShortcuts_show__bottomRight::before {{
    border-right-color: {COLOR_PALETTE["primary"]};
}}
""")

# Get initial available dates
available_dates = get_available_dates()
default_date = available_dates[0] if available_dates else datetime.now().strftime('%Y-%m-%d')

# Define app layout
app.layout = html.Div([
    # Header
    html.Div([
        html.H1("Camera Statistics Dashboard", style={"margin": "0"}),
        html.P("Monitor data transfer status for AngleCam cameras"),
    ], className="header"),
    
    # Main content
    html.Div([
        # Filters and controls
        html.Div([
            html.Div([
                html.Label("Time Range:"),
                dcc.Dropdown(
                    id="time-range-dropdown",
                    options=[
                        {"label": "Last 7 days", "value": 7},
                        {"label": "Last 14 days", "value": 14},
                        {"label": "Last 30 days", "value": 30},
                        {"label": "Last 90 days", "value": 90},
                        {"label": "Last 365 days", "value": 365},
                        {"label": "This Year", "value": "this_year"},
                    ],
                    value=30,
                    clearable=False,
                ),
            ], className="col"),
            
            html.Div([
                html.Label("Minimum Frame Count Threshold:"),
                dcc.Slider(
                    id="frame-threshold-slider",
                    min=100,
                    max=1000,
                    step=50,
                    value=500,
                    marks={i: str(i) for i in range(100, 1001, 100)},
                ),
            ], className="col"),
            
            html.Div([
                html.Label("Show Inactive Cameras:"),
                dcc.RadioItems(
                    id="show-inactive-radio",
                    options=[
                        {"label": "Hide Inactive", "value": "hide"},
                        {"label": "Show All", "value": "show"},
                    ],
                    value="hide",
                    labelStyle={"marginRight": "15px", "display": "inline-block"},
                ),
            ], className="col"),
        ], className="row card"),
        
        # Overview metrics
        html.Div([
            html.H2("Overview Metrics"),
            html.Div([
                html.Div([
                    html.Div(id="total-cameras-metric", className="metric-value"),
                    html.Div("Total Active Cameras", className="metric-label"),
                ], className="metric-card col"),
                
                html.Div([
                    html.Div(id="avg-frames-metric", className="metric-value"),
                    html.Div("Avg Frames (Active Cameras)", className="metric-label"),
                ], className="metric-card col"),
                
                html.Div([
                    html.Div(id="avg-filesize-metric", className="metric-value"),
                    html.Div("Avg File Size (MB)", className="metric-label"),
                ], className="metric-card col"),
                
                html.Div([
                    html.Div(id="total-data-metric", className="metric-value"),
                    html.Div("Total Data Volume (GB)", className="metric-label"),
                ], className="metric-card col"),
            ], className="row_metrics"),
            
            html.Div([
                html.Div([
                    html.Div(id="total-frames-metric", className="metric-value"),
                    html.Div("Total Frames (All Cameras)", className="metric-label"),
                ], className="metric-card col"),
            ], className="row_metrics"),
        ], className="card"),
        
        # Alerts section
        html.Div(id="alerts-section", className="card"),
        
        # Visualization tabs
        html.Div([
            html.H2("Visualizations"),
            dcc.Tabs([
                dcc.Tab(label="Frame Count by Camera", children=[
                    html.Div([
                        # Date selector for Frame Count by Camera
                        html.Div([
                            html.Label("Select Date:"),
                            html.Div([
                                dcc.DatePickerSingle(
                                    id="frame-count-date-picker",
                                    display_format="YYYY-MM-DD",
                                    placeholder="Select a date",
                                    className="date-picker",
                                    min_date_allowed="2020-01-01",  # Set a reasonable minimum date
                                    max_date_allowed=datetime.now().strftime('%Y-%m-%d'),  # Today
                                    initial_visible_month=datetime.now().strftime('%Y-%m-%d'),  # Start with current month visible
                                    date=default_date  # Set initial date
                                ),
                                dcc.Dropdown(
                                    id="frame-count-date-dropdown",
                                    options=[{"label": date, "value": date} for date in available_dates],
                                    value=default_date,
                                    clearable=False,
                                    className="date-dropdown"
                                ),
                            ]),
                            html.Div([
                                html.Button("Previous", id="frame-count-prev-button", className="date-nav-button"),
                                html.Button("Next", id="frame-count-next-button", className="date-nav-button"),
                            ], className="date-nav-buttons"),
                        ], className="date-selector"),

                        dcc.Graph(id="frame-count-by-camera"),
                    ], className="tabs-content"),
                ]),
                
                dcc.Tab(label="File Size by Camera", children=[
                    html.Div([
                        # Date selector for File Size by Camera
                        html.Div([
                            html.Label("Select Date:"),
                            html.Div([
                                # Calendar date picker
                                dcc.DatePickerSingle(
                                    id="file-size-date-picker",
                                    display_format="YYYY-MM-DD",
                                    placeholder="Select a date",
                                    className="date-picker",
                                    min_date_allowed="2020-01-01",  # Set a reasonable minimum date
                                    max_date_allowed=datetime.now().strftime('%Y-%m-%d'),  # Today
                                    initial_visible_month=datetime.now().strftime('%Y-%m-%d'),  # Start with current month visible
                                    date=default_date  # Set initial date
                                ),
                                # Keep the dropdown for backward compatibility and quick selection
                                dcc.Dropdown(
                                    id="file-size-date-dropdown",
                                    options=[{"label": date, "value": date} for date in available_dates],
                                    value=default_date,
                                    clearable=False,
                                    className="date-dropdown"
                                ),
                            ]),
                            html.Div([
                                html.Button("Previous", id="file-size-prev-button", className="date-nav-button"),
                                html.Button("Next", id="file-size-next-button", className="date-nav-button"),
                            ], className="date-nav-buttons"),
                        ], className="date-selector"),

                        dcc.Graph(id="file-size-by-camera"),
                    ], className="tabs-content"),
                ]),
                
                dcc.Tab(label="Frame Count over Time", children=[
                    html.Div([
                        dcc.Graph(id="frame-count-over-time"),
                    ], className="tabs-content"),
                ]),
                
                dcc.Tab(label="File Size over Time", children=[
                    html.Div([
                        dcc.Graph(id="file-size-over-time"),
                    ], className="tabs-content"),
                ]),
                
                dcc.Tab(label="Missing Data Calendar", children=[
                    html.Div([
                        dcc.Graph(id="missing-data-calendar"),
                    ], className="tabs-content"),
                ]),
                
                dcc.Tab(label="Data Table", children=[
                    html.Div([
                        dash_table.DataTable(
                            id="data-table",
                            sort_action="native",
                            filter_action="native",
                            page_size=20,
                            style_table={"overflowX": "auto"},
                            style_cell={
                                "textAlign": "left",
                                "padding": "8px",
                                "minWidth": "100px",
                            },
                            style_header={
                                "backgroundColor": "#f8fafc",
                                "fontWeight": "bold",
                            },
                            style_data_conditional=[
                                {
                                    "if": {"filter_query": "{mp4_exists} = 0"},
                                    "backgroundColor": f"{COLOR_PALETTE['danger']}22",
                                },
                                {
                                    "if": {
                                        "filter_query": "{frame_count} < 500 && {mp4_exists} = 1",
                                    },
                                    "backgroundColor": f"{COLOR_PALETTE['warning']}22",
                                },
                            ],
                        ),
                    ], className="tabs-content"),
                ]),
            ]),
        ], className="card"),
        
        # Footer
        html.Div([
            html.P("Camera Statistics Dashboard • AngleCam Monitoring System"),
            html.P(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"),
        ], className="footer"),
        
        # Interval component for auto-refresh
        dcc.Interval(
            id="interval-component",
            interval=300 * 1000,  # in milliseconds (5 minutes)
            n_intervals=0,
        ),
        
        # Store for available dates
        dcc.Store(id="available-dates-store"),
    ], className="content"),
])

# Callback to update all metrics and visualizations
@app.callback(
    [
        Output("total-cameras-metric", "children"),
        Output("avg-frames-metric", "children"),
        Output("avg-filesize-metric", "children"),
        Output("total-data-metric", "children"),
        Output("total-frames-metric", "children"),
        Output("alerts-section", "children"),
        Output("frame-count-over-time", "figure"),
        Output("file-size-over-time", "figure"),
        Output("missing-data-calendar", "figure"),
        Output("data-table", "data"),
        Output("data-table", "columns"),
        Output("available-dates-store", "data"),
        Output("frame-count-date-dropdown", "options"),
        Output("file-size-date-dropdown", "options"),
    ],
    [
        Input("interval-component", "n_intervals"),
        Input("time-range-dropdown", "value"),
        Input("frame-threshold-slider", "value"),
        Input("show-inactive-radio", "value"),
    ],
)
def update_dashboard(n_intervals, time_range, frame_threshold, show_inactive):
    # Determine whether to include inactive cameras
    include_inactive = show_inactive == "show"
    
    # Load data
    df = load_data(days=time_range, include_inactive=include_inactive)
    
    # Get available dates
    available_dates = get_available_dates(days=time_range)
    date_options = [{"label": date, "value": date} for date in available_dates]
    
    if df.empty:
        return ("0", "0", "0", "0", "0", html.Div("No data available"), {}, {}, {}, [], [], 
                available_dates, date_options, date_options)
    
    # Get the most recent date in the data
    most_recent_date = df["date"].max()
    recent_data = df[df["date"] == most_recent_date]
    
    # Filter for cameras with MP4 files for accurate averages
    has_mp4 = recent_data[recent_data["mp4_exists"] == 1]
    
    # Calculate metrics (only for cameras that have MP4 files)
    total_cameras = recent_data.shape[0]
    avg_frames = int(has_mp4["frame_count"].mean()) if not has_mp4.empty else 0
    avg_filesize = round(has_mp4["mp4_size_mb"].mean(), 2) if not has_mp4.empty else 0
    total_data_gb = round(df["mp4_size"].sum() / (1024 * 1024 * 1024), 2)  # Convert to GB
    
    # Calculate total frames and format with comma for thousands
    total_frames = df["frame_count"].sum()
    total_frames_formatted = f"{total_frames:,}".replace(",", ".")
    
    missing_videos = recent_data[recent_data["mp4_exists"] == 0].shape[0]
    low_frame_count = recent_data[(recent_data["mp4_exists"] == 1) & 
                                  (recent_data["frame_count"] < frame_threshold)].shape[0]
    
    # Prepare alerts
    alerts = []
    
    if missing_videos > 0:
        missing_cameras = recent_data[recent_data["mp4_exists"] == 0]["camera"].tolist()
        missing_cameras.sort(key=natural_sort_key)
        alert_text = f"🔴 {missing_videos} cameras missing MP4 files on {most_recent_date}: " + ", ".join(missing_cameras)
        alerts.append(html.Div(alert_text, className="alert"))
    
    if low_frame_count > 0:
        low_frame_cameras = recent_data[(recent_data["mp4_exists"] == 1) & 
                                       (recent_data["frame_count"] < frame_threshold)]["camera"].tolist()
        low_frame_cameras.sort(key=natural_sort_key)
        alert_text = f"🟠 {low_frame_count} cameras with fewer than {frame_threshold} frames on {most_recent_date}: " + ", ".join(low_frame_cameras)
        alerts.append(html.Div(alert_text, className="alert"))
    
    alerts_section = html.Div([
        html.H2("Alerts"),
        html.Div(alerts) if alerts else html.Div("No active alerts", style={"color": COLOR_PALETTE["gray"]})
    ])
    
    # Frame count over time visualization
    # Calculate daily averages - only for cameras with MP4 files
    daily_avg = df.groupby("date").apply(
        lambda x: pd.Series({
            'frame_count': x[x['mp4_exists'] == 1]['frame_count'].mean(),
            'mp4_exists': (x['mp4_exists'].sum() / x.shape[0] * 100),
            'total_cameras': x.shape[0],
            'cameras_with_mp4': x[x['mp4_exists'] == 1].shape[0]
        })
    ).reset_index()
    
    # Fill NaN values with 0 before converting to int
    daily_avg["frame_count"] = daily_avg["frame_count"].fillna(0).round().astype(int)
    daily_avg["mp4_exists"] = daily_avg["mp4_exists"].round(1)
    
    frame_count_over_time = go.Figure()
    
    frame_count_over_time.add_trace(
        go.Scatter(
            x=daily_avg["date"],
            y=daily_avg["frame_count"],
            mode="lines+markers",
            name="Avg Frame Count (with MP4)",
            line=dict(color=COLOR_PALETTE["primary"], width=3),
            marker=dict(size=8),
        )
    )
    
    frame_count_over_time.add_trace(
        go.Scatter(
            x=daily_avg["date"],
            y=daily_avg["mp4_exists"],
            mode="lines+markers",
            name="MP4 Availability (%)",
            line=dict(color=COLOR_PALETTE["secondary"], width=3),
            marker=dict(size=8),
            yaxis="y2",
        )
    )
    
    frame_count_over_time.update_layout(
        title="Average Frame Count (only for cameras with MP4) and MP4 Availability Over Time",
        xaxis=dict(title="Date", gridcolor="#f1f5f9"),
        yaxis=dict(
            title="Average Frame Count", 
            side="left", 
            gridcolor="#f1f5f9",
            zerolinecolor="#e2e8f0"
        ),
        yaxis2=dict(
            title="MP4 Availability (%)",
            side="right",
            overlaying="y",
            gridcolor="#f1f5f9",
            zerolinecolor="#e2e8f0",
            range=[0, 100],
        ),
        margin=dict(l=20, r=60, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    
    # File size over time visualization
    # Calculate daily averages for file size and total daily data volumes
    file_size_data = df.groupby("date").apply(
        lambda x: pd.Series({
            'avg_file_size_mb': x[x['mp4_exists'] == 1]['mp4_size_mb'].mean(),
            'total_file_size_gb': x['mp4_size'].sum() / (1024 * 1024 * 1024),
            'cameras_with_mp4': x[x['mp4_exists'] == 1].shape[0]
        })
    ).reset_index()
    
    file_size_data["avg_file_size_mb"] = file_size_data["avg_file_size_mb"].round(2)
    file_size_data["total_file_size_gb"] = file_size_data["total_file_size_gb"].round(2)
    
    file_size_over_time = go.Figure()
    
    file_size_over_time.add_trace(
        go.Bar(
            x=file_size_data["date"],
            y=file_size_data["total_file_size_gb"],
            name="Total Data Volume (GB)",
            marker_color=COLOR_PALETTE["primary"],
        )
    )
    
    file_size_over_time.add_trace(
        go.Scatter(
            x=file_size_data["date"],
            y=file_size_data["avg_file_size_mb"],
            mode="lines+markers",
            name="Avg File Size (MB)",
            line=dict(color=COLOR_PALETTE["secondary"], width=3),
            marker=dict(size=8),
            yaxis="y2",
        )
    )
    
    file_size_over_time.update_layout(
        title="Data Volume and Average File Size Over Time",
        xaxis=dict(title="Date", gridcolor="#f1f5f9"),
        yaxis=dict(
            title="Total Data Volume (GB)", 
            side="left", 
            gridcolor="#f1f5f9",
            zerolinecolor="#e2e8f0"
        ),
        yaxis2=dict(
            title="Avg File Size (MB)",
            side="right",
            overlaying="y",
            gridcolor="#f1f5f9",
            zerolinecolor="#e2e8f0",
        ),
        margin=dict(l=20, r=60, t=40, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    
    # Missing data calendar
    # Pivot data to get a heatmap of MP4 existence by date and camera
    pivot_df = df.pivot_table(
        index="date", 
        columns="camera", 
        values="mp4_exists",
        aggfunc="max",
        fill_value=0
    )
    
    # Sort columns using natural sort
    pivot_df = pivot_df[sorted(pivot_df.columns, key=natural_sort_key)]
    
    # Create heatmap with consistent 0-1 color scale
    missing_data_calendar = px.imshow(
        pivot_df,
        labels=dict(x="Camera", y="Date", color="MP4 Exists"),
        color_continuous_scale=[
            [0, COLOR_PALETTE["danger"]],
            [1, COLOR_PALETTE["secondary"]]
        ],
        title="MP4 File Availability by Date and Camera",
        height=500,
        zmin=0,
        zmax=1,
    )
    
    missing_data_calendar.update_layout(
        xaxis_tickangle=-45,
        margin=dict(l=20, r=20, t=40, b=100),
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    
    # Prepare data table
    # Format file sizes in MB for display
    display_df = df.copy()
    columns = [
        {"name": "Date", "id": "date"},
        {"name": "Camera", "id": "camera"},
        {"name": "MP4 Exists", "id": "mp4_exists"},
        {"name": "File Size (MB)", "id": "mp4_size_mb"},
        {"name": "Frame Count", "id": "frame_count"},
        {"name": "Is Active", "id": "is_active"}
    ]
    
    table_data = display_df.to_dict("records")
    
    return (
        f"{total_cameras}",
        f"{avg_frames}",
        f"{avg_filesize} MB",
        f"{total_data_gb} GB",
        f"{total_frames_formatted}",
        alerts_section,
        frame_count_over_time,
        file_size_over_time,
        missing_data_calendar,
        table_data,
        columns,
        available_dates,
        date_options,
        date_options,
    )

# Callback for Frame Count by Camera visualization based on selected date
@app.callback(
    Output("frame-count-by-camera", "figure"),
    [
        Input("frame-count-date-dropdown", "value"),
        Input("frame-count-date-picker", "date"),  # Add date picker as input
        Input("frame-threshold-slider", "value"),
        Input("show-inactive-radio", "value"),
    ],
)
def update_frame_count_by_camera(dropdown_date, picker_date, frame_threshold, show_inactive):
    # Use date picker value if it exists, otherwise use dropdown value
    selected_date = picker_date if picker_date else dropdown_date
    
    include_inactive = show_inactive == "show"
    df = load_data(days=365, include_inactive=include_inactive)  # Load more data to ensure all dates are covered
    
    if df.empty or selected_date not in df["date"].values:
        # Return empty figure if no data or date not found
        return go.Figure().update_layout(title=f"No data available for {selected_date}")
    
    # Get all unique cameras from the dataset to maintain consistent order
    all_cameras = sorted(df["camera"].unique(), key=natural_sort_key)
    
    # Filter for the selected date
    date_data = df[df["date"] == selected_date]
    
    # Sort cameras using the consistent order
    date_data_sorted = date_data.copy()
    date_data_sorted["camera"] = pd.Categorical(date_data_sorted["camera"], categories=all_cameras, ordered=True)
    date_data_sorted = date_data_sorted.sort_values("camera")
    
    # Make sure mp4_exists is treated as a category with only 0 and 1 values
    # Convert to integer then to string to ensure consistent categorical treatment
    date_data_sorted["mp4_exists_cat"] = date_data_sorted["mp4_exists"].astype(int).astype(str)
    
    # Create the bar chart with modern colors
    frame_count_by_camera = px.bar(
        date_data_sorted,
        x="camera", 
        y="frame_count",
        color="mp4_exists_cat",
        color_discrete_map={
            "0": COLOR_PALETTE["danger"],
            "1": COLOR_PALETTE["primary"]
        },
        category_orders={"mp4_exists_cat": ["0", "1"], "camera": all_cameras},
        labels={"camera": "Camera", "frame_count": "Frame Count", "mp4_exists_cat": "MP4 Exists"},
        title=f"Frame Count by Camera ({selected_date})",
    )
    
    # Update legend labels to be more user-friendly
    frame_count_by_camera.for_each_trace(
        lambda trace: trace.update(
            name="MP4 Missing" if trace.name == "0" else "MP4 Present"
        )
    )
    
    # Add threshold line
    frame_count_by_camera.add_shape(
        type="line",
        x0=-0.5,
        x1=len(all_cameras) - 0.5,
        y0=frame_threshold,
        y1=frame_threshold,
        line=dict(color=COLOR_PALETTE["warning"], width=2, dash="dash"),
    )
    
    frame_count_by_camera.update_layout(
        xaxis_tickangle=-45,
        margin=dict(l=20, r=20, t=40, b=100),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="white",
        xaxis=dict(gridcolor="#f1f5f9"),
        yaxis=dict(gridcolor="#f1f5f9", zerolinecolor="#e2e8f0"),
    )
    
    return frame_count_by_camera

# Callback for File Size by Camera visualization based on selected date
@app.callback(
    Output("file-size-by-camera", "figure"),
    [
        Input("file-size-date-dropdown", "value"),
        Input("file-size-date-picker", "date"),  # Add date picker as input
        Input("show-inactive-radio", "value"),
    ],
)
def update_file_size_by_camera(dropdown_date, picker_date, show_inactive):
    # Use date picker value if it exists, otherwise use dropdown value
    selected_date = picker_date if picker_date else dropdown_date
    
    include_inactive = show_inactive == "show"
    df = load_data(days=365, include_inactive=include_inactive)  # Load more data to ensure all dates are covered
    
    if df.empty or selected_date not in df["date"].values:
        # Return empty figure if no data or date not found
        return go.Figure().update_layout(title=f"No data available for {selected_date}")
    
    # Get all unique cameras from the dataset to maintain consistent order
    all_cameras = sorted(df["camera"].unique(), key=natural_sort_key)
    
    # Filter for the selected date
    date_data = df[df["date"] == selected_date]
    
    # Sort cameras using the consistent order
    date_data_sorted = date_data.copy()
    date_data_sorted["camera"] = pd.Categorical(date_data_sorted["camera"], categories=all_cameras, ordered=True)
    date_data_sorted = date_data_sorted.sort_values("camera")
    
    # Make sure mp4_exists is treated as a category with only 0 and 1 values
    # Convert to integer then to string to ensure consistent categorical treatment
    date_data_sorted["mp4_exists_cat"] = date_data_sorted["mp4_exists"].astype(int).astype(str)
    
    # Create the bar chart with modern colors
    file_size_by_camera = px.bar(
        date_data_sorted,
        x="camera", 
        y="mp4_size_mb",
        color="mp4_exists_cat",
        color_discrete_map={
            "0": COLOR_PALETTE["danger"],
            "1": COLOR_PALETTE["primary"]
        },
        category_orders={"mp4_exists_cat": ["0", "1"], "camera": all_cameras},
        labels={"camera": "Camera", "mp4_size_mb": "File Size (MB)", "mp4_exists_cat": "MP4 Exists"},
        title=f"MP4 File Size by Camera ({selected_date})",
    )
    
    # Update legend labels to be more user-friendly
    file_size_by_camera.for_each_trace(
        lambda trace: trace.update(
            name="MP4 Missing" if trace.name == "0" else "MP4 Present"
        )
    )
    
    file_size_by_camera.update_layout(
        xaxis_tickangle=-45,
        margin=dict(l=20, r=20, t=40, b=100),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        plot_bgcolor="white",
        xaxis=dict(gridcolor="#f1f5f9"),
        yaxis=dict(gridcolor="#f1f5f9", zerolinecolor="#e2e8f0"),
    )
    
    return file_size_by_camera

# Callback for date navigation with previous/next buttons (Frame Count)
@app.callback(
    Output("frame-count-date-dropdown", "value"),
    [
        Input("frame-count-prev-button", "n_clicks"),
        Input("frame-count-next-button", "n_clicks"),
    ],
    [
        State("frame-count-date-dropdown", "value"),
        State("available-dates-store", "data"),
    ],
)
def navigate_frame_count_dates(prev_clicks, next_clicks, current_date, available_dates):
    # Skip if no clicks (initial render)
    if prev_clicks is None and next_clicks is None:
        return current_date
    
    # Determine which button was clicked
    ctx = dash.callback_context
    if not ctx.triggered:
        return current_date
    
    # Get button ID that triggered the callback
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    
    # Determine the next date
    if available_dates is None or len(available_dates) < 2:
        return current_date
    
    try:
        current_index = available_dates.index(current_date)
        
        if button_id == "frame-count-prev-button" and current_index < len(available_dates) - 1:
            # Previous button = go to older date (next in list since they're sorted desc)
            return available_dates[current_index + 1]
        elif button_id == "frame-count-next-button" and current_index > 0:
            # Next button = go to newer date (previous in list since they're sorted desc)
            return available_dates[current_index - 1]
        else:
            return current_date
    except ValueError:
        # Current date not found in list
        return current_date

# Callback for date navigation with previous/next buttons (File Size)
@app.callback(
    Output("file-size-date-dropdown", "value"),
    [
        Input("file-size-prev-button", "n_clicks"),
        Input("file-size-next-button", "n_clicks"),
    ],
    [
        State("file-size-date-dropdown", "value"),
        State("available-dates-store", "data"),
    ],
)
def navigate_file_size_dates(prev_clicks, next_clicks, current_date, available_dates):
    # Skip if no clicks (initial render)
    if prev_clicks is None and next_clicks is None:
        return current_date
    
    # Determine which button was clicked
    ctx = dash.callback_context
    if not ctx.triggered:
        return current_date
    
    # Get button ID that triggered the callback
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    
    # Determine the next date
    if available_dates is None or len(available_dates) < 2:
        return current_date
    
    try:
        current_index = available_dates.index(current_date)
        
        if button_id == "file-size-prev-button" and current_index < len(available_dates) - 1:
            # Previous button = go to older date (next in list since they're sorted desc)
            return available_dates[current_index + 1]
        elif button_id == "file-size-next-button" and current_index > 0:
            # Next button = go to newer date (previous in list since they're sorted desc)
            return available_dates[current_index - 1]
        else:
            return current_date
    except ValueError:
        # Current date not found in list
        return current_date

# Add callbacks for synchronizing date pickers with dropdowns
# Sync Frame Count date picker with dropdown
@app.callback(
    Output("frame-count-date-picker", "date"),
    [Input("frame-count-date-dropdown", "value")],
)
def sync_frame_count_date_picker(selected_date):
    if selected_date:
        return selected_date
    return None

# Sync File Size date picker with dropdown
@app.callback(
    Output("file-size-date-picker", "date"),
    [Input("file-size-date-dropdown", "value")],
)
def sync_file_size_date_picker(selected_date):
    if selected_date:
        return selected_date
    return None

# Sync Frame Count dropdown with date picker
@app.callback(
    Output("frame-count-date-dropdown", "value", allow_duplicate=True),
    [Input("frame-count-date-picker", "date")],
    [State("frame-count-date-dropdown", "options")],
    prevent_initial_call=True
)
def sync_frame_count_dropdown(date_picker_date, dropdown_options):
    if date_picker_date:
        available_dates = [opt["value"] for opt in dropdown_options]
        if date_picker_date in available_dates:
            return date_picker_date
    return dash.no_update

# Sync File Size dropdown with date picker
@app.callback(
    Output("file-size-date-dropdown", "value", allow_duplicate=True),
    [Input("file-size-date-picker", "date")],
    [State("file-size-date-dropdown", "options")],
    prevent_initial_call=True
)
def sync_file_size_dropdown(date_picker_date, dropdown_options):
    if date_picker_date:
        available_dates = [opt["value"] for opt in dropdown_options]
        if date_picker_date in available_dates:
            return date_picker_date
    return dash.no_update

# Update date dropdowns when time range changes (to always select most recent date)
@app.callback(
    [
        Output("frame-count-date-dropdown", "value", allow_duplicate=True),
        Output("file-size-date-dropdown", "value", allow_duplicate=True),
    ],
    [Input("available-dates-store", "data")],
    prevent_initial_call=True
)
def update_date_selections(available_dates):
    if available_dates and len(available_dates) > 0:
        # Get most recent date (first in the list since they're sorted DESC)
        most_recent_date = available_dates[0]
        return most_recent_date, most_recent_date
    return dash.no_update, dash.no_update

# Run the application
if __name__ == "__main__":
    app.run_server(debug=True, host="0.0.0.0", port=8050)