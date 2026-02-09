#!/bin/bash

# Script to create test channels for the IRC application
# Creates: #ai, #lunch, and #random public channels

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Change to the backend directory
cd "$SCRIPT_DIR" || exit 1

# Check if Python is available
if ! command -v python &> /dev/null; then
    echo "Error: Python is not installed or not in PATH"
    exit 1
fi

# Check if we're in a virtual environment or use python3
PYTHON_CMD="python"
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
fi

echo "Creating test channels..."
echo "Channels to create: #ai, #lunch, #random (all public)"
echo ""

# Run the Python script
$PYTHON_CMD create_test_channels.py

# Check exit status
if [ $? -eq 0 ]; then
    echo ""
    echo "Script completed successfully!"
else
    echo ""
    echo "Error: Script failed to execute"
    exit 1
fi
