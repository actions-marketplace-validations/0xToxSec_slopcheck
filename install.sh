#!/usr/bin/env bash
# slopcheck installer
# Run: curl -fsSL https://raw.githubusercontent.com/0xToxSec/slopcheck/main/install.sh | bash

set -e

echo ""
echo "  ┌─────────────────────────────────┐"
echo "  │  slopcheck installer            │"
echo "  │  Stop AI-hallucinated packages  │"
echo "  └─────────────────────────────────┘"
echo ""

# Check for Python
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "  [!] Python not found. Install Python 3.9+ first."
    echo "      https://python.org/downloads"
    exit 1
fi

PYTHON=$(command -v python3 || command -v python)
echo "  [*] Found Python: $($PYTHON --version)"

# Install slopcheck
echo "  [*] Installing slopcheck from PyPI..."
$PYTHON -m pip install --upgrade slopcheck --quiet

# Verify
if command -v slopcheck &> /dev/null; then
    echo "  [+] slopcheck installed successfully!"
    echo ""
    echo "  Usage:"
    echo "    slopcheck .                        Scan current directory"
    echo "    slopcheck requirements.txt         Scan a specific file"
    echo "    slopcheck flask-gpt-helper --pkg pypi  Check one package"
    echo ""
elif $PYTHON -m slopcheck --help &> /dev/null; then
    echo "  [+] slopcheck installed! (not on PATH, use: python -m slopcheck)"
    echo ""
    echo "  Usage:"
    echo "    python -m slopcheck .                        Scan current directory"
    echo "    python -m slopcheck requirements.txt         Scan a specific file"
    echo "    python -m slopcheck flask-gpt-helper --pkg pypi  Check one package"
    echo ""
else
    echo "  [!] Something went wrong. Try: pip install slopcheck"
    exit 1
fi
