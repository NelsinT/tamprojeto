from flask import Flask, request
import psycopg2
import os

app = Flask(__name__)

# --- IMPORTANTE: Confirma se esta string do NEON está correta e tem ?sslmode=require no fim ---
# Copia isto para o teu ficheiro api/index.py
DATABASE_URL = "postgresql://neondb_owner:npg_AtR4hBFdcx5K@ep-red-firefly-adwfe8r0-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"

def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Erro de Conexão: {e}")
        return None

# Rota para a página inicial (para não dar 404 se abrires só o site)
@app.route('/')
def home():
    return "O servidor está online! Usa /validar?id=1234"

@app.route('/validar', methods=['GET'])
def validar_entrada():
    # ... O teu código de validação normal ...
    return "0" # Exemplo
