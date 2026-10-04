"""Global sozlamalar. .env faylidan o'qiladi."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.isdigit()]

# Yashirin sub-bot yaratish buyrug'i va PIN (admin paneldan o'zgartiriladi)
DEFAULT_ROOTER_CMD = "rooter"
DEFAULT_ROOTER_PIN = "9767"

PAGE_SIZE = 8          # ro'yxatda bir sahifadagi elementlar
