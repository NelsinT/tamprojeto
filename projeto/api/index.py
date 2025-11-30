from flask import Flask, request
import psycopg2
import os

app = Flask(__name__)

# --- IMPORTANTE: LIGAÇÃO À BD NA NUVEM ---
# Substitui isto pela Connection String que o Neon.tech te deu!
DATABASE_URL = "postgres://teu_user:tua_pass@ep-x.aws.neon.tech/neondb?sslmode=require"

def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Erro BD: {e}")
        return None

@app.route('/validar', methods=['GET'])
def validar_entrada():
    pin_recebido = request.args.get('id')
    
    conn = get_db_connection()
    if not conn: return "0"

    cur = conn.cursor()
    
    # 1. Verifica funcionario
    cur.execute("SELECT id, nome FROM funcionarios WHERE pin_code = %s AND ativo = TRUE", (pin_recebido,))
    funcionario = cur.fetchone()

    if funcionario:
        user_id = funcionario[0]
        # 2. Logica Entrada/Saida
        cur.execute("SELECT tipo_movimento FROM registos WHERE funcionario_id = %s ORDER BY id DESC LIMIT 1", (user_id,))
        ultimo = cur.fetchone()
        
        novo_movimento = "ENTRADA"
        if ultimo and ultimo[0] == "ENTRADA":
            novo_movimento = "SAIDA"
            
        cur.execute("INSERT INTO registos (funcionario_id, tipo_movimento) VALUES (%s, %s)", (user_id, novo_movimento))
        conn.commit()
        
        cur.close()
        conn.close()
        return "1" # Sucesso
    
    cur.close()
    conn.close()
    return "0" # Erro