"""
Vercel Serverless Function Entry Point

This file wraps the FastAPI application for Vercel's serverless Python runtime.
Vercel expects Python functions in the /api directory.
"""

import sys
from pathlib import Path

# Add the project root to Python path so imports work
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import the FastAPI app
from backend.api.main import app

# Vercel handler - the app object is automatically detected by Vercel
