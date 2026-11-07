#!/usr/bin/env bash
# ==============================================================================
# Turku Energia × Since AI 2026: 1-Click Situation Room & Validation Launcher
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "======================================================================"
echo "⚡ TURKU ENERGIA SITUATION ROOM LAUNCHER"
echo "======================================================================"

# 1. Check Virtual Environment
if [ -d ".venv" ]; then
    echo "Found virtual environment: .venv"
    PYTHON=".venv/bin/python"
    STREAMLIT=".venv/bin/streamlit"
    PYTEST=".venv/bin/pytest"
else
    echo "Using system python..."
    PYTHON="python3"
    STREAMLIT="streamlit"
    PYTEST="pytest"
fi

# 2. Run Anti-Leakage CI Tests
echo ""
echo "1. Running Anti-Leakage CI Harness..."
$PYTEST tests/ -q
echo "   [PASS] Zero lookahead bias verified (available_at test passed)."

# 3. Validate Submission File
echo ""
echo "2. Checking Official Submission File (forecast_backtest.csv)..."
if [ -f "forecast_backtest.csv" ]; then
    $PYTHON Dataset/starter_package_v1/validate_submission.py \
        --backtest forecast_backtest.csv \
        --origins Dataset/starter_package_v1/forecast_origins.csv
else
    echo "   [WARNING] forecast_backtest.csv not found! Regenerating..."
    $PYTHON src/backtest/generate_grand_submission.py
fi

# 4. Launch Streamlit Situation Room
echo ""
echo "3. Launching Live Situation Room Dashboard..."
echo "   Dashboard URL: http://localhost:8501"
echo "   Press Ctrl+C to terminate."
echo "======================================================================"
$STREAMLIT run app/dashboard.py

