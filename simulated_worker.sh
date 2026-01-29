#!/bin/bash

# Simplified version using integer arithmetic

run() {
    local seconds="${1:-5}"
    local pid=$$
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] INFO: Starting backend worker process: $pid"
    
    local counter=0
    local end_time=$(( $(date +%s) + seconds ))
    
    while [ $(date +%s) -lt $end_time ]; do
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] INFO: [$counter] Backend worker process $pid is working..."
        
        # Sleep for random time between 0.3 and 0.8 seconds
        # Using milliseconds for better precision
        sleep_ms=$(( 300 + RANDOM % 501 ))  # 300-800 ms
        sleep_duration=$(echo "scale=3; $sleep_ms / 1000" | bc)
        sleep "$sleep_duration"
        
        ((counter++))
    done
}

# Main execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    run "$@"
fi