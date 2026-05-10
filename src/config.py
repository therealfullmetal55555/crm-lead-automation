import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# HubSpot
HUBSPOT_API_KEY = os.getenv("HUBSPOT_API_KEY", "")
HUBSPOT_BASE_URL = "https://api.hubapi.com"

# OpenAI / GPT-6 Sol
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")  # for Sol-compatible endpoint

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# App
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))

# CRM
DEAL_PIPELINE = os.getenv("HUBSPOT_DEAL_PIPELINE", "default")
DEAL_STAGE = os.getenv("HUBSPOT_DEAL_STAGE", "appointmentscheduled")

# Mock mode flags
USE_MOCK_CRM = not bool(HUBSPOT_API_KEY)
USE_MOCK_LLM = not bool(OPENAI_API_KEY)
