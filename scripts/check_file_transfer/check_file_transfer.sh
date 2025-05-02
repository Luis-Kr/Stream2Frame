#!/bin/bash
# Script to check if all camera files were transferred correctly from 2 days ago
# It checks for MP4 files, their sizes, and number of frames

# Set the base directory for videos
VIDEO_BASE_DIR="/mnt/gsdata/projects/ecosense/AngleCam2_0/data/raw_videos"

# Set the output report file (in JSON format)
REPORT_DIR="/mnt/data/lk1167/projects/Stream2Frame/logs"
DATABASE_DIR="/mnt/data/lk1167/projects/Stream2Frame/data/database"
mkdir -p "$REPORT_DIR"
REPORT_FILE="$REPORT_DIR/file_transfer_report.json"

# Create log directory if it doesn't exist
LOG_DIR="/mnt/data/lk1167/projects/Stream2Frame/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/file_transfer_check.log"

# Email settings for alerts
EMAIL_RECIPIENT="luis1.kremer@gmail.com" 

# Minimum frames threshold for alerts
MIN_FRAMES=500

# List of inactive cameras to exclude from analysis
INACTIVE_CAMERAS=(
  "G5Bullet_37"
  "G5Bullet_55"
  "G5Bullet_56"
  "G5Bullet_57"
  "G5Bullet_58"
  "G5Bullet_59"
  "G5Bullet_60"
  "G5Bullet_61"
  "G5Bullet_62"
  "G5Bullet_63"
  "G5Bullet_64"
  "G5Bullet_65"
  "G5Bullet_66"
  "G5Bullet_67"
  "G5Bullet_68"
  "G5Bullet_69"
  "G5Bullet_70"
  "G5Bullet_71"
)

# Function to check if a camera is in the inactive list
is_inactive_camera() {
  local camera="$1"
  for inactive in "${INACTIVE_CAMERAS[@]}"; do
    if [ "$camera" = "$inactive" ]; then
      return 0  # True, camera is inactive
    fi
  done
  return 1  # False, camera is active
}

# Define how many days to look back
DAYS_AGO=2

# Calculate the date from specified days ago
# Format without leading zeros for month and day to match directory structure (YYYY/M/D)
YEAR=$(date -d "${DAYS_AGO} days ago" '+%Y')
MONTH=$(date -d "${DAYS_AGO} days ago" '+%-m')  # %-m removes leading zero
DAY=$(date -d "${DAYS_AGO} days ago" '+%-d')    # %-d removes leading zero
TWO_DAYS_AGO="$YEAR/$MONTH/$DAY"
DATE_READABLE=$(date -d "${DAYS_AGO} days ago" '+%Y-%m-%d')

echo "Using date format: $TWO_DAYS_AGO" >> "$LOG_FILE"

# Function to count frames from CSV file
count_frames_from_csv() {
    local csv_file="$1"
    
    # If CSV doesn't exist, return 0
    if [ ! -f "$csv_file" ]; then
        echo "0"
        return
    fi
    
    # Count lines in CSV file (minus header line)
    local frame_count=$(wc -l < "$csv_file")
    
    # Subtract 1 for header row
    if [ "$frame_count" -gt 0 ]; then
        frame_count=$((frame_count - 1))
    fi
    
    echo "$frame_count"
}

# Create a SQLite database for the dashboard
DB_FILE="$DATABASE_DIR/camera_stats.db"

# Initialize the SQLite database if it doesn't exist
if [ ! -f "$DB_FILE" ]; then
    echo "Initializing camera stats database..." >> "$LOG_FILE"
    sqlite3 "$DB_FILE" <<EOF
CREATE TABLE camera_stats (
    date TEXT,
    camera TEXT,
    mp4_exists INTEGER,
    mp4_size INTEGER,
    mp4_size_mb REAL,
    frame_count INTEGER,
    is_active INTEGER,
    PRIMARY KEY (date, camera)
);
CREATE INDEX idx_camera_stats_date ON camera_stats(date);
CREATE INDEX idx_camera_stats_camera ON camera_stats(camera);
EOF
fi

# Initialize a Python script to process the data and generate reports
cat > /tmp/process_camera_data.py << 'EOF'
#!/usr/bin/env python3
import json
import sys
import os
import sqlite3
from datetime import datetime
from pathlib import Path
import re

# Function to sort camera names naturally (e.g., G5Bullet_7 comes before G5Bullet_10)
def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

# Initialize or read existing report file
def load_report(report_file):
    try:
        if os.path.exists(report_file):
            with open(report_file, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading report file: {e}", file=sys.stderr)
    
    # Return empty report if file doesn't exist or has issues
    return {"cameras": {}}

# Update report with new data
def update_report(report, date, camera, data):
    if camera not in report["cameras"]:
        report["cameras"][camera] = {}
    
    # Add or update this date's data for this camera
    report["cameras"][camera][date] = data

# Save report back to file, with sorted cameras
def save_report(report, report_file):
    # Create a new dict with sorted camera keys
    sorted_report = {"cameras": {}}
    
    # Get a sorted list of camera names
    sorted_cameras = sorted(report["cameras"].keys(), key=natural_sort_key)
    
    # Rebuild the report with sorted camera keys
    for camera in sorted_cameras:
        sorted_report["cameras"][camera] = report["cameras"][camera]
    
    # Write the sorted report to file
    with open(report_file, 'w') as f:
        json.dump(sorted_report, f, indent=2)
    
    return sorted_report

# Update SQLite database with camera stats
def update_database(db_file, date, camera_data, inactive_cameras):
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        for camera, dates in camera_data.items():
            if date in dates:
                data = dates[date]
                mp4_exists = 1 if data.get("mp4_exists", False) else 0
                mp4_size = data.get("mp4_size", 0)
                mp4_size_mb = round(mp4_size / (1024 * 1024), 2)  # Convert bytes to MB
                frame_count = data.get("frame_count", 0)
                is_active = 0 if camera in inactive_cameras else 1
                
                # Insert or replace the data for this camera and date
                cursor.execute(
                    "INSERT OR REPLACE INTO camera_stats (date, camera, mp4_exists, mp4_size, mp4_size_mb, frame_count, is_active) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (date, camera, mp4_exists, mp4_size, mp4_size_mb, frame_count, is_active)
                )
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"Error updating database: {e}", file=sys.stderr)

# Generate a markdown summary of issues
def generate_markdown_summary(report, date_to_check, min_frames, inactive_cameras):
    issues = []
    
    for camera, dates in report["cameras"].items():
        # Skip inactive cameras
        if camera in inactive_cameras:
            continue
            
        if date_to_check in dates:
            data = dates[date_to_check]
            
            # Check for issues
            if not data["mp4_exists"]:
                issues.append(f"- 🔴 **{camera}**: MP4 file missing")
            elif data["frame_count"] < min_frames:
                issues.append(f"- 🟠 **{camera}**: Only {data['frame_count']} frames (below threshold of {min_frames})")
    
    # Generate markdown content
    if issues:
        md_content = f"# Camera Transfer Issues for {date_to_check}\n\n"
        md_content += "\n".join(issues)
        return md_content
    else:
        return None

# Determine if email alert is needed
def should_send_alert(report, date_to_check, min_frames, inactive_cameras):
    for camera, dates in report["cameras"].items():
        # Skip inactive cameras
        if camera in inactive_cameras:
            continue
            
        if date_to_check in dates:
            data = dates[date_to_check]
            if not data["mp4_exists"] or data["frame_count"] < min_frames:
                return True
    return False

# Main function
def main():
    if len(sys.argv) < 6:
        print("Usage: python process_camera_data.py <report_file> <date> <min_frames> <db_file> <inactive_cameras>")
        sys.exit(1)
        
    report_file = sys.argv[1]
    date_to_check = sys.argv[2]
    min_frames = int(sys.argv[3])
    db_file = sys.argv[4]
    inactive_cameras = sys.argv[5].split(',') if sys.argv[5] else []
    
    # Load existing report
    report = load_report(report_file)
    
    # Read camera data from stdin
    lines = sys.stdin.readlines()
    
    for line in lines:
        try:
            data = json.loads(line.strip())
            update_report(report, date_to_check, data["camera"], data)
        except json.JSONDecodeError:
            print(f"Error parsing line: {line}", file=sys.stderr)
    
    # Save updated report with sorted cameras
    sorted_report = save_report(report, report_file)
    
    # Update the SQLite database
    update_database(db_file, date_to_check, sorted_report["cameras"], inactive_cameras)
    
    # Check if alert is needed
    alert_needed = should_send_alert(sorted_report, date_to_check, min_frames, inactive_cameras)
    
    # Generate markdown summary if issues are found
    if alert_needed:
        md_content = generate_markdown_summary(sorted_report, date_to_check, min_frames, inactive_cameras)
        if md_content:
            summary_file = f"{os.path.dirname(report_file)}/transfer_issues/transfer_issues_{date_to_check.replace('-', '_')}.md"
            with open(summary_file, 'w') as f:
                f.write(md_content)
            print(f"ALERT::{summary_file}")
        
if __name__ == "__main__":
    main()
EOF

# Make the Python script executable
chmod +x /tmp/process_camera_data.py

# Convert inactive cameras array to comma-separated string for passing to Python script
INACTIVE_CAMERAS_STRING=$(IFS=,; echo "${INACTIVE_CAMERAS[*]}")

# Find all camera directories
find "$VIDEO_BASE_DIR" -maxdepth 1 -type d -name "G5Bullet_*" | while read camera_dir; do
    camera_name=$(basename "$camera_dir")
    
    # Skip inactive cameras
    if is_inactive_camera "$camera_name"; then
        echo "Skipping inactive camera: $camera_name" >> "$LOG_FILE"
        # Still record it in the database but mark as inactive
        echo "{\"camera\": \"$camera_name\", \"mp4_exists\": false, \"mp4_size\": 0, \"frame_count\": 0, \"is_inactive\": true}" | \
        python3 /tmp/process_camera_data.py "$REPORT_FILE" "$DATE_READABLE" "$MIN_FRAMES" "$DB_FILE" "$INACTIVE_CAMERAS_STRING"
        continue
    fi
    
    # Construct the path for the specified date
    date_dir="$camera_dir/$TWO_DAYS_AGO"
    
    # Skip if the date directory doesn't exist
    if [ ! -d "$date_dir" ]; then
        # Report that this camera doesn't have data for the specified date
        echo "{\"camera\": \"$camera_name\", \"mp4_exists\": false, \"mp4_size\": 0, \"frame_count\": 0}" | \
        python3 /tmp/process_camera_data.py "$REPORT_FILE" "$DATE_READABLE" "$MIN_FRAMES" "$DB_FILE" "$INACTIVE_CAMERAS_STRING"
        continue
    fi
    
    # Look for MP4 files in the date directory
    mp4_file=$(find "$date_dir" -maxdepth 1 -name "*.mp4" | head -n 1)
    
    if [ -n "$mp4_file" ]; then
        # Get MP4 file size in bytes
        mp4_size=$(stat -c%s "$mp4_file")
        
        # Look for corresponding CSV file (camera name with _frame_data.csv suffix)
        csv_pattern="${camera_name}_frame_data.csv"
        csv_file=$(find "$date_dir" -maxdepth 1 -name "$csv_pattern" | head -n 1)
        
        # If we didn't find the CSV with the pattern, try the default pattern
        if [ -z "$csv_file" ]; then
            csv_file="${mp4_file%.mp4}.csv"
        fi
        
        # Count frames from CSV file
        frame_count=$(count_frames_from_csv "$csv_file")
        
        # Report success with details
        echo "{\"camera\": \"$camera_name\", \"mp4_exists\": true, \"mp4_size\": $mp4_size, \"frame_count\": $frame_count, \"mp4_file\": \"$mp4_file\", \"csv_file\": \"$csv_file\"}" | \
        python3 /tmp/process_camera_data.py "$REPORT_FILE" "$DATE_READABLE" "$MIN_FRAMES" "$DB_FILE" "$INACTIVE_CAMERAS_STRING"
    else
        # Report failure - MP4 missing
        echo "{\"camera\": \"$camera_name\", \"mp4_exists\": false, \"mp4_size\": 0, \"frame_count\": 0}" | \
        python3 /tmp/process_camera_data.py "$REPORT_FILE" "$DATE_READABLE" "$MIN_FRAMES" "$DB_FILE" "$INACTIVE_CAMERAS_STRING"
    fi
done

# Check if we need to send an alert
alert_file=$(grep "ALERT::" "$LOG_FILE" | tail -1 | cut -d':' -f3-)

if [ -n "$alert_file" ]; then
    # Send email alert
    echo "File transfer issues detected. See attached report." | \
    mail -s "🚨 Camera Transfer Alert - $DATE_READABLE" \
         -a "$alert_file" \
         "$EMAIL_RECIPIENT"
    
    echo "Alert sent for issues on $DATE_READABLE" >> "$LOG_FILE"
else
    echo "No issues found for $DATE_READABLE" >> "$LOG_FILE"
fi

# Clean up
rm /tmp/process_camera_data.py

echo "File transfer check completed for $DATE_READABLE" >> "$LOG_FILE"