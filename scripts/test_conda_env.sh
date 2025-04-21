#!/bin/bash

# Test script to verify the new conda environment location
# This script can be run without disrupting the main process

echo "=== Testing Conda Environment Configuration ==="

# Store the original conda environment path
ORIGINAL_CONDA_PATH="/root/miniforge"
NEW_CONDA_PATH="/volume1/miniconda"

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Create log file for test results
TEST_LOG="${PROJECT_ROOT}/logs/conda_env_test_$(date '+%Y-%m-%d_%H-%M-%S').log"
mkdir -p "$(dirname "$TEST_LOG")"

# Log function
log() {
  echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$TEST_LOG"
}

log "Starting conda environment test"
log "Checking if new conda path exists: $NEW_CONDA_PATH"

if [ ! -d "$NEW_CONDA_PATH" ]; then
  log "❌ ERROR: New conda path not found: $NEW_CONDA_PATH"
  exit 1
fi

log "✅ New conda path exists"

# Check activation script
log "Testing conda activation from new location"
if [ -f "$NEW_CONDA_PATH/bin/activate" ]; then
  log "✅ Found conda activation script at $NEW_CONDA_PATH/bin/activate"
else
  log "❌ ERROR: Conda activation script not found at $NEW_CONDA_PATH/bin/activate"
  exit 1
fi

# Create a temporary wrapper script that modifies our main_wrapper.sh
TEMP_WRAPPER="${SCRIPT_DIR}/temp_conda_test.sh"

cat > "$TEMP_WRAPPER" << EOF
#!/bin/bash

# Temporary script to test conda environment
echo "=== Conda Environment Test ===" > "$TEST_LOG.output"

# Try activating with new path
echo "Testing new conda path: $NEW_CONDA_PATH" >> "$TEST_LOG.output"
source "$NEW_CONDA_PATH/bin/activate" 2>> "$TEST_LOG.output"

if [ \$? -ne 0 ]; then
  echo "❌ Failed to source conda activate from new location" >> "$TEST_LOG.output"
  exit 1
fi

# Try activating the environment
echo "Activating environment" >> "$TEST_LOG.output"
conda activate dt_ecosense 2>> "$TEST_LOG.output"

if [ \$? -ne 0 ]; then
  echo "❌ Failed to activate conda environment" >> "$TEST_LOG.output"
  exit 1
fi

# Check Python location
echo "✅ Environment activated successfully" >> "$TEST_LOG.output"
echo "Python location: \$(which python)" >> "$TEST_LOG.output"
echo "Python version: \$(python --version 2>&1)" >> "$TEST_LOG.output"
echo "Active environment: \$(conda info --envs | grep '*')" >> "$TEST_LOG.output"

# Test importing key libraries
echo "Testing OpenCV import..." >> "$TEST_LOG.output"
python -c "import cv2; print(f'OpenCV version: {cv2.__version__}')" >> "$TEST_LOG.output"
if [ \$? -ne 0 ]; then
  echo "❌ Failed to import OpenCV" >> "$TEST_LOG.output"
  exit 1
fi

echo "Testing numpy import..." >> "$TEST_LOG.output"
python -c "import numpy; print(f'NumPy version: {numpy.__version__}')" >> "$TEST_LOG.output"
if [ \$? -ne 0 ]; then
  echo "❌ Failed to import NumPy" >> "$TEST_LOG.output"
  exit 1
fi

echo "✅ All library imports successful" >> "$TEST_LOG.output"
exit 0
EOF

chmod +x "$TEMP_WRAPPER"

# Run the temporary test script
log "Running conda environment test..."
"$TEMP_WRAPPER"

# Capture result
TEST_RESULT=$?

# Display results
if [ -f "$TEST_LOG.output" ]; then
  log "----- Test Output -----"
  cat "$TEST_LOG.output" | tee -a "$TEST_LOG"
  log "----------------------"
fi

# Clean up
rm -f "$TEMP_WRAPPER" "$TEST_LOG.output"

if [ $TEST_RESULT -eq 0 ]; then
  log "✅ Conda environment test PASSED!"
  log "The new conda environment at $NEW_CONDA_PATH is working correctly"
  
  # Create the modified wrapper script for the main program
  UPDATED_WRAPPER="${SCRIPT_DIR}/main_wrapper_new.sh"
  
  log "Creating updated main_wrapper.sh with new conda path at $UPDATED_WRAPPER"
  
  # Copy the original script and replace the conda path
  sed "s|source /root/miniforge/etc/profile.d/conda.sh|source $NEW_CONDA_PATH/bin/activate|" "${SCRIPT_DIR}/main_wrapper.sh" > "$UPDATED_WRAPPER"
  sed -i "s|conda activate dt_ecosense|conda activate dt_ecosense|" "$UPDATED_WRAPPER"
  
  chmod +x "$UPDATED_WRAPPER"
  
  log "✅ Created updated wrapper script: $UPDATED_WRAPPER"
  log "To use the new configuration, run: $UPDATED_WRAPPER"
  log "After verifying it works, you can replace the original script"
else
  log "❌ Conda environment test FAILED!"
  log "Please check the log for details: $TEST_LOG"
fi

log "Test completed"
exit $TEST_RESULT