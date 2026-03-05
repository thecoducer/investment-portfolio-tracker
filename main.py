#!/usr/bin/env python3
"""
Metron — Entry point.

Usage:
    python main.py
"""

from dotenv import load_dotenv
load_dotenv()  # must run before any app imports that read os.environ

from app.server import main

if __name__ == "__main__":
    main()
