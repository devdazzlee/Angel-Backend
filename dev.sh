#!/bin/bash
# Development server startup script
cd "$(dirname "$0")"
source venv/bin/activate
python3 -m fastapi dev main.py


