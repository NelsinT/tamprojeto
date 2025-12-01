from flask import Flask, request, jsonify
import psycopg2
import requests 
import json
import os
from datetime import datetime
import pytz 

app = Flask(__name__)

# --- CONFIGURAÇÕES ---
# A tua base de dados Neon
DATABASE_URL = "postgresql://neondb_owner:npg_AtR4hBFdcx5K@ep-red-firefly-adwfe8r0-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"

# --- THINGSBOARD ---
THINGSBOARD_HOST = "https://thingsboard.cloud"
# O teu Token
ACCESS_TOKEN = "McUD2Mnr8jdjz1hKNNHP" 

def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Erro BD: {e}")
        return None

def enviar_thingsboard(telemetria):
    """ Envia dados para o gráfico do ThingsBoard """
    try:
        url = f"{THINGSBOARD_HOST}/api/v1/{ACCESS_TOKEN}/telemetry"
        requests.post(url, json=telemetria)
        print("Dados enviados para ThingsBoard!")
    except Exception as e:
        print(f"Erro ao enviar para ThingsBoard: {e}")

def obter_hora_portugal():
    """ Calcula a hora certa em Lisboa """
    try:
        tz_lisboa = pytz.timezone('Europe/Lisbon')
        agora = datetime.now(tz_lisboa)
        return agora.strftime('%d/%m/%Y %H:%M:%S')
    except:
        return datetime.now().strftime('%d/%m/%Y %H:%M:%S')

@app.route('/')
def home():
    return "Servidor Online!"

# --- NOVA ROTA: MUDAR PIN (Chamada pelo ThingsBoard) ---
@app.route('/mudar_pin', methods=['POST'])
def mudar_pin():
    # O ThingsBoard envia: {"nome": "Joao", "novo_pin": "9999"}
    dados = request.json
    
    if not dados or 'nome' not in dados or 'novo_pin' not in dados:
        return jsonify({"erro": "Dados incompletos"}), 400

    nome_funcionario = dados['nome']
    novo_pin = dados['novo_pin']
    
    conn = get_db_connection()
    if not conn: return jsonify({"erro": "Erro na BD"}), 500
    
    cur = conn.cursor()
    try:
        # Atualiza o PIN na base de dados
        cur.execute("UPDATE funcionarios SET pin_code = %s WHERE nome = %s", (novo_pin, nome_funcionario))
        conn.commit()
        
        registos_afetados = cur.rowcount
        cur.close()
        conn.close()
        
        if registos_afetados > 0:
            print(f"✅ PIN alterado para {nome_funcionario}: {novo_pin}")
            return jsonify({"status": "sucesso", "mensagem": f"PIN de {nome_funcionario} alterado!"}), 200
        else:
            print(f"❌ Funcionário não encontrado: {nome_funcionario}")
            return jsonify({"erro": "Funcionario nao encontrado"}), 404

    except Exception as e:
        print(f"Erro SQL: {e}")
        if conn: conn.close()
        return jsonify({"erro": str(e)}), 500
# ----------------------------

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
            
            # 4. Enviar para ThingsBoard
            hora_pt = obter_hora_portugal()
            
            # Cria a string para o histórico (Tabela)
            msg_historico = f"{hora_pt} | {nome_user} | {novo_movimento}"

            dados_tb = {
                "funcionario": nome_user,
                "movimento": novo_movimento,
                "status": "Acesso Permitido",
                "ultimo_id": pin_recebido,
                "log_historico": msg_historico
            }
            
            # Separa as horas para colunas diferentes
            if novo_movimento == "ENTRADA":
                dados_tb["hora_entrada"] = hora_pt
            else:
                dados_tb["hora_saida"] = hora_pt

            enviar_thingsboard(dados_tb)

            cur.close()
            conn.close()
            return "1"
        
        else:
            # Envia erro para o Dashboard
            hora_pt = obter_hora_portugal()
            msg_historico = f"{hora_pt} | DESCONHECIDO | ACESSO NEGADO"
            
            dados_tb = {
                "funcionario": "Desconhecido",
                "status": "Acesso Negado",
                "ultimo_id": pin_recebido,
                "tentativa_erro": hora_pt,
                "log_historico": msg_historico
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
