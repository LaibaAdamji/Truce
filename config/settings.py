import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    def __init__(self):
        self.SUPABASE_URL = os.environ["SUPABASE_URL"]
        self.SUPABASE_KEY = os.environ["SUPABASE_KEY"]
        self.LLM_BASE_URL = os.environ["LLM_BASE_URL"]
        self.LLM_API_KEY = os.environ["LLM_API_KEY"]
        self.LLM_MODEL_ID = os.environ["LLM_MODEL_ID"]

        self.NEGOTIATION_ROUND_CAP = int(os.environ["NEGOTIATION_ROUND_CAP"])

settings = Settings()