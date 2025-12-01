from flask import Flask, request
import psycopg2
import requests 
import json
import os
from datetime import datetime
import pytz 

app = Flask(__name__)

# --- CONFIGURAÇÕES ---

# 1. TUA BASE DE DADOS NEON
DATABASE_URL = "postgresql://neondb_owner:npg_AtR4hBFdcx5K@ep-red-firefly-adwfe8r0-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"

# 2. TEU THINGSBOARD
THINGSBOARD_HOST = "https://thingsboard.cloud"
ACCESS_TOKEN = "McUD2Mnr8jdjz1hKNNHP" 

def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Erro BD: {e}")
        return None

def enviar_thingsboard(telemetria):
    try:
        url = f"{THINGSBOARD_HOST}/api/v1/{ACCESS_TOKEN}/telemetry"
        requests.post(url, json=telemetria)
        print("Dados enviados para ThingsBoard!")
    except Exception as e:
        print(f"Erro ao enviar para ThingsBoard: {e}")

def obter_hora_portugal():
    try:
        tz_lisboa = pytz.timezone('Europe/Lisbon')
        agora = datetime.now(tz_lisboa)
        return agora.strftime('%d/%m/%Y %H:%M:%S')
    except:
        return datetime.now().strftime('%d/%m/%Y %H:%M:%S')

@app.route('/')
def home():
    return "Servidor Online!"

@app.route('/validar', methods=['GET'])
def validar_entrada():
    pin_recebido = request.args.get('id')
    
    conn = get_db_connection()
    if not conn: return "0"

    cur = conn.cursor()
    
    try:
        # 1. Verificar funcionário
        cur.execute("SELECT id, nome FROM funcionarios WHERE pin_code = %s AND ativo = TRUE", (pin_recebido,))
        funcionario = cur.fetchone()

        if funcionario:
            user_id = funcionario[0]
            nome_user = funcionario[1]

            # 2. Lógica Entrada/Saída
            cur.execute("SELECT tipo_movimento FROM registos WHERE funcionario_id = %s ORDER BY id DESC LIMIT 1", (user_id,))
            ultimo = cur.fetchone()
            
            novo_movimento = "ENTRADA"
            if ultimo and ultimo[0] == "ENTRADA":
                novo_movimento = "SAIDA"
            
            # 3. Gravar na BD
            cur.execute("INSERT INTO registos (funcionario_id, tipo_movimento) VALUES (%s, %s)", (user_id, novo_movimento))
            conn.commit()
            
            # 4. Enviar para ThingsBoard com HORA
            hora_pt = obter_hora_portugal()
            
            dados_tb = {
                "funcionario": nome_user,
                "movimento": novo_movimento,
                "status": "Acesso Permitido",
                "ultimo_id": pin_recebido,
                "data_hora": hora_pt 
            }
            enviar_thingsboard(dados_tb)

            cur.close()
            conn.close()
            return "1"
        
        else:
            # Enviar erro para ThingsBoard com HORA
            hora_pt = obter_hora_portugal()
            
            dados_tb = {
                "funcionario": "Desconhecido",
                "status": "Acesso Negado",
                "ultimo_id": pin_recebido,
                "data_hora": hora_pt
            }
            enviar_thingsboard(dados_tb)

            cur.close()
            conn.close()
            return "0"

    except Exception as e:
        print(f"Erro: {e}")
        if conn: conn.close()
        return "0"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
