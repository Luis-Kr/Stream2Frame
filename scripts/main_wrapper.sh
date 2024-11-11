#!/bin/bash

# Previous day's date
previous_day=$(date -d "yesterday" '+%Y-%m-%d')
#previous_day="2024-10-20"
YEAR=$(date -d "$previous_day" '+%Y')
MONTH=$(date -d "$previous_day" '+%m')
DAY=$(date -d "$previous_day" '+%d')

# Create the log filename
log_file="/volume1/Stream2Frame/logs/NVR_wrapper/NVR_wrapper_${previous_day}.txt"
log_file_main="/volume1/Stream2Frame/logs/NVR_wrapper/NVR_wrapper_main_${previous_day}.txt"
echo "VM wrapper started at $(date)" >> "$log_file"

# Activate the Conda environment
source /root/miniconda3/etc/profile.d/conda.sh
source ~/.bashrc
conda activate dt_ecosense
echo "Conda environment activated: $(conda info --envs | grep '*' | awk '{print $1}')" >> "$log_file"

# Run the VM wrapper
python /volume1/Stream2Frame/src/main.py NVR.year=$YEAR NVR.month=$MONTH NVR.day=$DAY >> "$log_file_main"
echo "VM wrapper completed at $(date)" >> "$log_file"