import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    DATABASE_URL = os.getenv("DATABASE_URL")
    FINAL_MATCH_LIMIT = 10

    @classmethod
    def validate(cls):
        missing = []
        if not cls.GEMINI_API_KEY:
            missing.append("GEMINI_API_KEY")
        if not cls.DATABASE_URL:
            missing.append("DATABASE_URL")
        
        if missing:
            raise ValueError(f"Missing environment variables: {', '.join(missing)}")
