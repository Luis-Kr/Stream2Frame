#!/bin/bash

#=============================================================================
# Stream2Frame Processing Queue Manager
# Version: 2.0
# Description: Professional queue manager for Stream2Frame processing
#              Ensures sequential processing, prevents overlaps, and
#              provides comprehensive monitoring capabilities
#=============================================================================

# Base directory
BASE_DIR="/volume1/Stream2Frame"
QUEUE_DIR="${BASE_DIR}/queue"
LOGS_DIR="${BASE_DIR}/logs/NVR_wrapper"
STATUS_DIR="${BASE_DIR}/status"
LOCK_FILE="${BASE_DIR}/process.lock"
CURRENT_STATUS="${STATUS_DIR}/current_status.txt"
HISTORY_FILE="${STATUS_DIR}/processing_history.csv"

# Create required directories
mkdir -p "${QUEUE_DIR}" "${LOGS_DIR}" "${STATUS_DIR}"

# Configure logging
LOG_TIMESTAMP=$(date '+%Y-%m-%d_%H-%M-%S')
MAIN_LOG="${LOGS_DIR}/queue_manager_${LOG_TIMESTAMP}.log"

# Function for logging
log() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] [${level}] ${message}" | tee -a "${MAIN_LOG}"
}

# Initialize the history file if it doesn't exist
if [ ! -f "${HISTORY_FILE}" ]; then
    echo "date,processing_start,processing_end,duration,status,year,month,day" > "${HISTORY_FILE}"
    log "INFO" "Initialized processing history file"
fi

# Check if another instance is running
check_lock() {
    if [ -f "${LOCK_FILE}" ]; then
        pid=$(cat "${LOCK_FILE}")
        if ps -p "${pid}" > /dev/null; then
            log "WARN" "Another processing job is already running (PID: ${pid})"
            return 1
        else
            log "WARN" "Stale lock file found. Previous process might have crashed."
            rm -f "${LOCK_FILE}"
        fi
    fi
    return 0
}

# Create lock file
create_lock() {
    echo $$ > "${LOCK_FILE}"
    log "INFO" "Lock file created (PID: $$)"
}

# Release lock file
release_lock() {
    if [ -f "${LOCK_FILE}" ]; then
        rm -f "${LOCK_FILE}"
        log "INFO" "Lock file released"
    fi
}

# Update current status
update_status() {
    local status="$1"
    local details="$2"
    echo "STATUS: ${status}" > "${CURRENT_STATUS}"
    echo "UPDATED: $(date '+%Y-%m-%d %H:%M:%S')" >> "${CURRENT_STATUS}"
    echo "DETAILS: ${details}" >> "${CURRENT_STATUS}"
    echo "CURRENT_PID: $$" >> "${CURRENT_STATUS}"
    
    if [ -n "$3" ] && [ -n "$4" ] && [ -n "$5" ]; then
        echo "DATE: $3-$4-$5" >> "${CURRENT_STATUS}"
    fi
}

# Record processing in history
record_history() {
    local date_param="$1"
    local start_time="$2"
    local end_time="$3"
    local status="$4"
    local year="$5"
    local month="$6"
    local day="$7"
    
    # Calculate duration
    start_sec=$(date -d "${start_time}" +%s)
    end_sec=$(date -d "${end_time}" +%s)
    duration_sec=$((end_sec - start_sec))
    duration_hr=$((duration_sec / 3600))
    duration_min=$(( (duration_sec % 3600) / 60 ))
    duration="${duration_hr}h ${duration_min}m"
    
    # Add to history file
    echo "${date_param},${start_time},${end_time},${duration},${status},${year},${month},${day}" >> "${HISTORY_FILE}"
}

# Determine which date to process (today or from queue)
determine_processing_date() {
    # Check if there are entries in the queue
    if [ -n "$(ls -A ${QUEUE_DIR} 2>/dev/null)" ]; then
        # Find oldest queue entry
        oldest_file=$(ls -t "${QUEUE_DIR}" | tail -1)
        if [ -n "${oldest_file}" ]; then
            # Read date from the queue file
            read YEAR MONTH DAY < "${QUEUE_DIR}/${oldest_file}"
            log "INFO" "Processing queued date: ${YEAR}-${MONTH}-${DAY} from ${oldest_file}"
            QUEUE_FILE="${QUEUE_DIR}/${oldest_file}"
            return 0
        fi
    fi
    
    # If no queue, process yesterday's date
    previous_day=$(date -d "yesterday" '+%Y-%m-%d')
    YEAR=$(date -d "${previous_day}" '+%Y')
    MONTH=$(date -d "${previous_day}" '+%-m')  # %-m removes leading zeros
    DAY=$(date -d "${previous_day}" '+%-d')    # %-d removes leading zeros
    log "INFO" "No queue entries found. Processing yesterday's date: ${YEAR}-${MONTH}-${DAY}"
    QUEUE_FILE=""
    return 0
}

# Check if today's processing should be queued
check_and_queue() {
    if ! check_lock; then
        # Another process is running, queue today's date
        queue_today
        log "INFO" "Exiting since another process is running. Today's date has been queued."
        exit 0
    fi
}

# Queue today's date for later processing
queue_today() {
    previous_day=$(date -d "yesterday" '+%Y-%m-%d')
    year=$(date -d "${previous_day}" '+%Y')
    month=$(date -d "${previous_day}" '+%-m')
    day=$(date -d "${previous_day}" '+%-d')
    
    queue_file="${QUEUE_DIR}/queue_${year}_${month}_${day}_$(date '+%s')"
    echo "${year} ${month} ${day}" > "${queue_file}"
    log "INFO" "Queued processing for ${year}-${month}-${day} (${queue_file})"
    
    update_status "QUEUED" "Date ${year}-${month}-${day} queued for processing" "${year}" "${month}" "${day}"
}

# Process a specific date
process_date() {
    local y="$1"
    local m="$2"
    local d="$3"
    local queue_file="$4"
    
    log "INFO" "============================================="
    log "INFO" "STARTING PROCESSING FOR DATE: ${y}-${m}-${d}"
    log "INFO" "============================================="
    
    # Create date-specific log files
    date_str="${y}-${m}-${d}"
    log_file="${LOGS_DIR}/NVR_wrapper_${date_str}.txt"
    log_file_main="${LOGS_DIR}/NVR_wrapper_main_${date_str}.txt"
    
    # Record start time
    start_time=$(date '+%Y-%m-%d %H:%M:%S')
    log "INFO" "Processing started at ${start_time}"
    
    # Update status
    update_status "PROCESSING" "Processing ${y}-${m}-${d}" "${y}" "${m}" "${d}"
    
    echo "VM wrapper started at $(date)" > "${log_file}"
    
    # Activate the Conda environment
    source /root/miniforge/etc/profile.d/conda.sh
    source ~/.bashrc
    conda activate dt_ecosense 2>> "${log_file}" || {
        log "ERROR" "Failed to activate conda environment"
        update_status "ERROR" "Failed to activate conda environment for ${y}-${m}-${d}" "${y}" "${m}" "${d}"
        record_history "${date_str}" "${start_time}" "$(date '+%Y-%m-%d %H:%M:%S')" "FAILED" "${y}" "${m}" "${d}"
        return 1
    }
    
    echo "Conda environment activated: $(conda info --envs | grep '*' | awk '{print $1}')" >> "${log_file}"
    
    # Run the processing script with timeout to prevent infinite hang (24h timeout)
    log "INFO" "Running main.py for ${y}-${m}-${d}"
    timeout 86400 python "${BASE_DIR}/src/main.py" NVR.year=${y} NVR.month=${m} NVR.day=${d} > "${log_file_main}" 2>&1
    
    exit_code=$?
    end_time=$(date '+%Y-%m-%d %H:%M:%S')
    
    if [ ${exit_code} -eq 0 ]; then
        status="SUCCESS"
        log "INFO" "Processing completed successfully for ${y}-${m}-${d}"
    elif [ ${exit_code} -eq 124 ]; then
        status="TIMEOUT"
        log "ERROR" "Processing timed out after 24 hours for ${y}-${m}-${d}"
    else
        status="ERROR"
        log "ERROR" "Processing failed with exit code ${exit_code} for ${y}-${m}-${d}"
    fi
    
    echo "VM wrapper completed at ${end_time} with status: ${status}" >> "${log_file}"
    
    # Update history record
    record_history "${date_str}" "${start_time}" "${end_time}" "${status}" "${y}" "${m}" "${d}"
    
    # Remove queue file if processing is complete
    if [ -n "${queue_file}" ] && [ -f "${queue_file}" ]; then
        rm -f "${queue_file}"
        log "INFO" "Removed queue file ${queue_file}"
    fi
    
    log "INFO" "============================================="
    log "INFO" "COMPLETED PROCESSING FOR DATE: ${y}-${m}-${d}"
    log "INFO" "============================================="
    
    return ${exit_code}
}

# Show current status
show_status() {
    echo "Stream2Frame Processing Status"
    echo "=============================="
    
    # Show current processing status
    if [ -f "${CURRENT_STATUS}" ]; then
        cat "${CURRENT_STATUS}"
    else
        echo "No current status information available"
    fi
    
    echo ""
    echo "Queue Status"
    echo "============"
    
    # Show queue status
    queue_count=$(ls -1 "${QUEUE_DIR}" 2>/dev/null | wc -l)
    echo "Items in queue: ${queue_count}"
    
    if [ ${queue_count} -gt 0 ]; then
        echo ""
        echo "Queue entries (oldest first):"
        for entry in $(ls -tr "${QUEUE_DIR}"); do
            read y m d < "${QUEUE_DIR}/${entry}"
            echo "- ${y}-${m}-${d} (${entry})"
        done
    fi
    
    echo ""
    echo "Recent Processing History"
    echo "========================="
    
    # Show processing history (last 5 entries)
    if [ -f "${HISTORY_FILE}" ]; then
        tail -n 6 "${HISTORY_FILE}" | column -t -s ','
    else
        echo "No processing history available"
    fi
}

# Cleanup function for unexpected termination
cleanup() {
    log "WARN" "Script interrupted. Cleaning up..."
    release_lock
    update_status "INTERRUPTED" "Processing was interrupted at $(date '+%Y-%m-%d %H:%M:%S')"
    exit 1
}

# Set trap for cleanup
trap cleanup SIGINT SIGTERM

# Main execution
main() {
    # If called with --status parameter, show status and exit
    if [ "$1" == "--status" ]; then
        show_status
        exit 0
    fi
    
    log "INFO" "Stream2Frame Queue Manager started"
    
    # Check if we should queue today's processing
    check_and_queue
    
    # Create lock to prevent concurrent runs
    create_lock
    
    # Determine which date to process
    determine_processing_date
    
    # Process the determined date
    process_date "${YEAR}" "${MONTH}" "${DAY}" "${QUEUE_FILE}"
    process_exit_code=$?
    
    # Update final status
    if [ ${process_exit_code} -eq 0 ]; then
        update_status "COMPLETED" "Processing for ${YEAR}-${MONTH}-${DAY} completed successfully at $(date '+%Y-%m-%d %H:%M:%S')" "${YEAR}" "${MONTH}" "${DAY}"
    else
        update_status "FAILED" "Processing for ${YEAR}-${MONTH}-${DAY} failed with code ${process_exit_code} at $(date '+%Y-%m-%d %H:%M:%S')" "${YEAR}" "${MONTH}" "${DAY}"
    fi
    
    # Check if there are more items in the queue and process them
    if [ -n "$(ls -A ${QUEUE_DIR} 2>/dev/null)" ]; then
        log "INFO" "More items in queue. Processing next item."
        
        # Find oldest queue entry
        oldest_file=$(ls -tr "${QUEUE_DIR}" | head -1)
        if [ -n "${oldest_file}" ]; then
            # Read date from the queue file
            read next_year next_month next_day < "${QUEUE_DIR}/${oldest_file}"
            log "INFO" "Processing next queued date: ${next_year}-${next_month}-${next_day}"
            
            # Process the next date
            process_date "${next_year}" "${next_month}" "${next_day}" "${QUEUE_DIR}/${oldest_file}"
            next_exit_code=$?
            
            if [ ${next_exit_code} -eq 0 ]; then
                update_status "COMPLETED" "Processing for ${next_year}-${next_month}-${next_day} completed successfully" "${next_year}" "${next_month}" "${next_day}"
            else
                update_status "FAILED" "Processing for ${next_year}-${next-month}-${next-day} failed with code ${next_exit_code}" "${next_year}" "${next_month}" "${next_day}"
            fi
        fi
    fi
    
    # Release lock when all processing is done
    release_lock
    log "INFO" "Stream2Frame Queue Manager completed"
}

# Run the main function with command-line arguments
main "$@"
