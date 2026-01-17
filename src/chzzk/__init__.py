import os

from dotenv import load_dotenv

# Load environment variables
ENV_PATH = os.path.join(os.path.join(os.path.dirname(__file__), '.env'))
load_dotenv(dotenv_path=ENV_PATH)

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

__all__ = ["CLIENT_ID", "CLIENT_SECRET"]