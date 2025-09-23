#!/usr/bin/env python3
"""
Railway deployment entry point
"""
import os
import sys

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run the main application
from secure_discordbot import main

if __name__ == "__main__":
    main()
