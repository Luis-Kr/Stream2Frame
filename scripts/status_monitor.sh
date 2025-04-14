#!/bin/bash

#=============================================================================
# Stream2Frame Processing Status Monitor
# Version: 1.0
# Description: Provides detailed status monitoring for Stream2Frame processing
#=============================================================================

# Base directory
BASE_DIR="/volume1/Stream2Frame"
STATUS_DIR="${BASE_DIR}/status"
HISTORY_FILE="${STATUS_DIR}/processing_history.csv"
CURRENT_STATUS="${STATUS_DIR}/current_status.txt"
QUEUE_DIR="${BASE_DIR}/queue"

# Create required directories
mkdir -p "${STATUS_DIR}"

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Format date for display
format_date() {
    date -d "$1" "+%Y-%m-%d %H:%M:%S"
}

# Print section header
print_header() {
    local title="$1"
    local length=${#title}
    local line=$(printf '=%.0s' $(seq 1 $((length + 4))))
    
    echo -e "${BOLD}${BLUE}\n${line}"
    echo "| ${title} |"
    echo -e "${line}${NC}\n"
}

# Show current status
show_current_status() {
    print_header "CURRENT PROCESSING STATUS"
    
    if [ -f "${CURRENT_STATUS}" ]; then
        status_line=$(grep "STATUS:" "${CURRENT_STATUS}" | cut -d':' -f2- | xargs)
        updated_line=$(grep "UPDATED:" "${CURRENT_STATUS}" | cut -d':' -f2- | xargs)
        details_line=$(grep "DETAILS:" "${CURRENT_STATUS}" | cut -d':' -f2- | xargs)
        pid_line=$(grep "CURRENT_PID:" "${CURRENT_STATUS}" | cut -d':' -f2- | xargs)
        date_line=$(grep "DATE:" "${CURRENT_STATUS}" | cut -d':' -f2- | xargs)
        
        # Status with color
        echo -n "Status: "
        if [[ "${status_line}" == *"PROCESSING"* ]]; then
            echo -e "${YELLOW}${status_line}${NC}"
        elif [[ "${status_line}" == *"COMPLETED"* ]]; then
            echo -e "${GREEN}${status_line}${NC}"
        elif [[ "${status_line}" == *"FAILED"* || "${status_line}" == *"ERROR"* ]]; then
            echo -e "${RED}${status_line}${NC}"
        elif [[ "${status_line}" == *"QUEUED"* ]]; then
            echo -e "${CYAN}${status_line}${NC}"
        else
            echo -e "${status_line}"
        fi
        
        echo "Last updated: ${updated_line}"
        echo "Details: ${details_line}"
        
        if [ -n "${date_line}" ]; then
            echo "Processing date: ${date_line}"
        fi
        
        if [ -n "${pid_line}" ]; then
            echo -n "Process ID: ${pid_line} "
            
            # Check if process is still running
            if ps -p "${pid_line}" > /dev/null; then
                echo -e "(${GREEN}Running${NC})"
                
                # Show runtime if process is running
                start_time=$(ps -o lstart= -p "${pid_line}")
                if [ -n "${start_time}" ]; then
                    start_seconds=$(date -d "${start_time}" +%s)
                    now_seconds=$(date +%s)
                    runtime_seconds=$((now_seconds - start_seconds))
                    runtime_hours=$((runtime_seconds / 3600))
                    runtime_minutes=$(( (runtime_seconds % 3600) / 60 ))
                    
                    echo "Running time: ${runtime_hours}h ${runtime_minutes}m"
                    
                    # Show resource usage
                    echo "CPU usage: $(ps -p ${pid_line} -o %cpu | tail -1)%"
                    echo "Memory usage: $(ps -p ${pid_line} -o %mem | tail -1)%"
                fi
            else
                echo -e "(${RED}Not running${NC})"
            fi
        fi
    else
        echo -e "${YELLOW}No current status information available${NC}"
    fi
}

# Show queue status
show_queue_status() {
    print_header "PROCESSING QUEUE"
    
    # Show queue status
    queue_count=$(ls -1 "${QUEUE_DIR}" 2>/dev/null | wc -l)
    
    if [ ${queue_count} -eq 0 ]; then
        echo -e "${GREEN}Queue is empty. No pending jobs.${NC}"
    else
        echo -e "Items in queue: ${BOLD}${queue_count}${NC}\n"
        
        echo "Queue entries (oldest first):"
        echo "----------------------------"
        
        count=1
        for entry in $(ls -tr "${QUEUE_DIR}"); do
            read y m d < "${QUEUE_DIR}/${entry}"
            timestamp=$(echo "${entry}" | grep -oE '[0-9]+$')
            queue_date=""
            
            if [ -n "${timestamp}" ]; then
                queue_date=" (queued on $(date -d @${timestamp} '+%Y-%m-%d %H:%M:%S'))"
            fi
            
            if [ ${count} -eq 1 ]; then
                echo -e "${CYAN}${count}. ${y}-${m}-${d}${queue_date} - Will process next${NC}"
            else
                echo "${count}. ${y}-${m}-${d}${queue_date}"
            fi
            
            count=$((count + 1))
        done
    fi
}

# Show processing history
show_processing_history() {
    print_header "RECENT PROCESSING HISTORY"
    
    entries_to_show=10
    
    if [ -f "${HISTORY_FILE}" ]; then
        # Count lines in file excluding header
        total_entries=$(( $(wc -l < "${HISTORY_FILE}") - 1 ))
        
        if [ ${total_entries} -le 0 ]; then
            echo -e "${YELLOW}No processing history available${NC}"
            return
        fi
        
        echo -e "Showing last ${entries_to_show} of ${total_entries} entries\n"
        
        # Print formatted header
        echo -e "${BOLD}DATE        START TIME         END TIME           DURATION    STATUS     Y-M-D${NC}"
        
        # Print last N entries with formatting
        tail -n ${entries_to_show} "${HISTORY_FILE}" | while IFS=, read date start end duration status year month day; do
            # Skip header if present
            if [ "${date}" == "date" ]; then continue; fi
            
            # Add color based on status
            if [ "${status}" == "SUCCESS" ]; then
                status_colored="${GREEN}${status}${NC}"
            elif [ "${status}" == "FAILED" ] || [ "${status}" == "ERROR" ]; then
                status_colored="${RED}${status}${NC}"
            elif [ "${status}" == "TIMEOUT" ]; then
                status_colored="${YELLOW}${status}${NC}"
            else
                status_colored="${status}"
            fi
            
            # Format and print the line
            printf "%-10s  %-18s  %-18s  %-10s  %-20s  %s-%s-%s\n" \
                "${date}" "${start}" "${end}" "${duration}" "${status_colored}" "${year}" "${month}" "${day}"
        done
        
        # Calculate average processing time
        echo -e "\n${BOLD}Processing Statistics:${NC}"
        
        # Using awk to calculate average duration from CSV data
        awk -F, '
        BEGIN {sum_hours=0; sum_mins=0; count=0; success=0; failed=0; timeout=0}
        NR>1 {
            if ($4 ~ /^[0-9]+h [0-9]+m$/) {
                hrs = $4;
                gsub("h", "", hrs);
                hrs = substr(hrs, 1, index(hrs, " ")-1);
                
                mins = $4;
                gsub(".*h ", "", mins);
                gsub("m$", "", mins);
                
                sum_hours += hrs;
                sum_mins += mins;
                count++;
                
                if ($5 == "SUCCESS") success++;
                else if ($5 == "FAILED" || $5 == "ERROR") failed++;
                else if ($5 == "TIMEOUT") timeout++;
            }
        }
        END {
            if (count > 0) {
                total_mins = (sum_hours * 60) + sum_mins;
                avg_mins = int(total_mins / count);
                avg_hours = int(avg_mins / 60);
                avg_mins_remainder = avg_mins % 60;
                success_rate = int((success/count) * 100);
                
                printf "Average processing time: %dh %dm\n", avg_hours, avg_mins_remainder;
                printf "Success rate: %d%% (%d/%d)\n", success_rate, success, count;
                printf "Failed: %d, Timeout: %d\n", failed, timeout;
            } else {
                print "No valid duration data available";
            }
        }' "${HISTORY_FILE}"
    else
        echo -e "${YELLOW}No processing history available${NC}"
    fi
}

# Show system resources
show_system_resources() {
    print_header "SYSTEM RESOURCES"
    
    # CPU load
    echo -e "${BOLD}CPU Load:${NC}"
    uptime | awk -F'[a-z]:' '{ print $2 }'
    
    # Memory usage
    echo -e "\n${BOLD}Memory Usage:${NC}"
    free -h | grep -v + | awk 'NR==1{print "Type\t" $1 "\t" $2 "\t" $3 "\t" $4 "\t" $5 "\t" $6}NR>1{print $1 "\t" $2 "\t" $3 "\t" $4 "\t" $5 "\t" $6}'
    
    # Disk usage
    echo -e "\n${BOLD}Disk Usage:${NC}"
    df -h "${BASE_DIR}" | awk 'NR==1{print $1 "\t" $2 "\t" $3 "\t" $4 "\t" $5 "\t" $6}NR>1{print $1 "\t" $2 "\t" $3 "\t" $4 "\t" $5 "\t" $6}'
}

# Main function
main() {
    clear
    echo -e "${BOLD}${PURPLE}=============================================${NC}"
    echo -e "${BOLD}${PURPLE}    Stream2Frame Processing Status Monitor   ${NC}"
    echo -e "${BOLD}${PURPLE}=============================================${NC}"
    echo -e "Report generated on $(date '+%Y-%m-%d %H:%M:%S')\n"
    
    show_current_status
    echo
    show_queue_status
    echo
    show_processing_history
    echo
    show_system_resources
    
    echo -e "\n${BOLD}${BLUE}==============================================${NC}"
    echo -e "${BOLD}${BLUE} To check again, run: ./scripts/status_monitor.sh${NC}"
    echo -e "${BOLD}${BLUE}==============================================${NC}\n"
}

# Run main function
main
