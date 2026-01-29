"""
Vercel Serverless Function Entry Point
Proxies all requests to the FastAPI app in backend/
"""
from backend.api.main import app

# Vercel expects a variable named "app" or "handler"
# FastAPI app can be used directly
