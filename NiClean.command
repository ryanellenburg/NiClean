#!/bin/bash
# Double-click to run NiClean in this folder
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

python3 NiClean.py

echo ""
echo "Press Enter to close…"
read