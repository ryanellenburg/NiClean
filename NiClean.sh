#!/bin/bash
# Run NiClean in this folder
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
python3 NiClean.py