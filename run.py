#!/usr/bin/env python3
import uvicorn
from src.config import APP_HOST, APP_PORT

if __name__ == "__main__":
    print(f"Starting CRM Lead Automation at http://{APP_HOST}:{APP_PORT}")
    print("Open http://localhost:8000 for web form")
    uvicorn.run("src.app:app", host=APP_HOST, port=APP_PORT, reload=True)
