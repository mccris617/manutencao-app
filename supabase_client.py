from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()  # <– carrega .env automaticamente

def get_supabase_client():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("⚠️ Variáveis SUPABASE_URL ou SUPABASE_KEY não foram carregadas!")

    return create_client(url, key)
