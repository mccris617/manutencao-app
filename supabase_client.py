# supabase_client.py
from supabase import create_client, Client
import streamlit as st
import os
from dotenv import load_dotenv

# Carrega variáveis (local ou Streamlit Cloud)
load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")

if not url or not key:
    url = st.secrets.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY")

if not url or not key:
    raise ValueError("❌ SUPABASE_URL ou SUPABASE_KEY não configurados.")

supabase: Client = create_client(url, key)