#!/bin/bash
# Quick setup script for the evaluation framework

set -e

echo "=========================================="
echo "Evaluation Framework Setup"
echo "=========================================="
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
EVAL_DIR="$PROJECT_DIR/evaluations"

cd "$PROJECT_DIR"

# Check Python version
echo "Checking Python version..."
python3 --version || {
    echo "Error: Python 3 is required"
    exit 1
}

# Create virtual environment if it doesn't exist
if [ ! -d "$EVAL_DIR/venv" ]; then
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv "$EVAL_DIR/venv"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source "$EVAL_DIR/venv/bin/activate"

# Upgrade pip
echo ""
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r "$EVAL_DIR/requirements.txt"

# Make scripts executable
echo ""
echo "Making scripts executable..."
chmod +x "$SCRIPT_DIR/run_benchmarks.py"
chmod +x "$SCRIPT_DIR/continuous_eval.py"
chmod +x "$EVAL_DIR/screenshot_eval.py"

# Create necessary directories
echo ""
echo "Creating directories..."
mkdir -p "$EVAL_DIR/screenshots/references"
mkdir -p "$EVAL_DIR/results"
mkdir -p "$EVAL_DIR/charts"
mkdir -p "$EVAL_DIR/data"

# Run test to verify installation
echo ""
echo "Running installation test..."
python3 -c "
import sys
sys.path.insert(0, '$EVAL_DIR')
try:
    import selenium
    print('✓ Selenium installed')
except ImportError:
    print('✗ Selenium not available')

try:
    import matplotlib
    print('✓ Matplotlib installed')
except ImportError:
    print('✗ Matplotlib not available')

try:
    from PIL import Image
    print('✓ Pillow installed')
except ImportError:
    print('✗ Pillow not available')

try:
    import requests
    print('✓ Requests installed')
except ImportError:
    print('✗ Requests not available')

try:
    import watchdog
    print('✓ Watchdog installed')
except ImportError:
    print('✗ Watchdog not available')
"

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit evaluations/eval_config.json to add your models"
echo "2. Run a test benchmark:"
echo "   cd $PROJECT_DIR"
echo "   source evaluations/venv/bin/activate"
echo "   python scripts/run_benchmarks.py --model test_model"
echo ""
echo "3. View the dashboard:"
echo "   open evaluations/dashboard.html"
echo ""
echo "4. Start continuous evaluation:"
echo "   python scripts/continuous_eval.py --watch"
echo ""
echo "For more information, see evaluations/README.md"
echo ""
