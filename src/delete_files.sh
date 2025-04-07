#!/bin/bash
# Set base directory
BASE_DIR="/volume1/Stream2Frame"

# Create log directory if it doesn't exist
LOG_DIR="${BASE_DIR}/logs/delete_files"
mkdir -p "$LOG_DIR"

# Previous day's date
previous_date=$(date -d "yesterday" '+%Y-%m-%d') #2 days ago
#previous_date="2024-10-31"
YEAR=$(date -d "$previous_date" '+%Y')
MONTH=$(date -d "$previous_date" '+%m')
DAY=$(date -d "$previous_date" '+%d')

# Set up logging (output to both screen and file)
LOG_FILE="${LOG_DIR}/$YEAR-$MONTH-$DAY.txt"
exec &> >(tee -a "$LOG_FILE")

# Print start time
echo "======================================"
echo "SCRIPT START: $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================"
echo

echo "BASE_DIR: $BASE_DIR"
echo "Log file: $LOG_FILE"

echo "$previous_date"

# Delte the main .ubv files
rm -v "/srv/unifi-protect/video/$YEAR/$MONTH/$DAY"/*.ubv
echo "Deleted all .ubv files for $previous_date"

# Read camera config and process both raw and processed videos
grep -v '^#' "${BASE_DIR}/config/utils/cams.yaml" | while IFS=': ' read -r camera mac
do
    if [ ! -z "$camera" ] && [ ! -z "$mac" ]; then
        # Process raw videos
        RAW_PATH="${BASE_DIR}/data/raw_videos/$YEAR-$MONTH-$DAY/$camera"
        if [ -d "$RAW_PATH" ]; then
            rm -v "$RAW_PATH"/*.mp4
            echo "Deleted all .mp4 files for $camera in raw_videos"
            rm -v "$RAW_PATH"/*.txt
            echo "Deleted all .txt files for $camera in raw_videos"
        else
            echo "Directory not found: $RAW_PATH"
        fi

        # Process processed videos
        PROCESSED_PATH="${BASE_DIR}/data/processed_videos/$YEAR-$MONTH-$DAY/$camera"
        if [ -d "$PROCESSED_PATH" ]; then
            rm -v "$PROCESSED_PATH"/*.mp4
            echo "Deleted all .mp4 files for $camera in processed_videos"
            rm -v "$PROCESSED_PATH"/*.csv
            echo "Deleted all .csv files for $camera in processed_videos"
        else
            echo "Directory not found: $PROCESSED_PATH"
        fi
    fi
done

# Print end time
echo
echo "======================================"
echo "SCRIPT END: $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================"
