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

# --- ROTA CRON: SAÍDA AUTOMÁTICA (Para fechar o dia) ---
@app.route('/cron/saida_automatica', methods=['GET'])
def saida_automatica():
    # 1. Liga à Base de Dados
    conn = get_db_connection()
    if not conn: return "Erro na Base de Dados"
    
    cur = conn.cursor()
    count_saidas = 0
    
    try:
        # 2. Busca todos os funcionários
        cur.execute("SELECT id, nome FROM funcionarios WHERE ativo = TRUE")
        todos = cur.fetchall()
        
        hora_pt = obter_hora_portugal()

        for func in todos:
            u_id = func[0]
            u_nome = func[1]
            
            # 3. Verifica o último movimento de cada um
            cur.execute("SELECT tipo_movimento FROM registos WHERE funcionario_id = %s ORDER BY id DESC LIMIT 1", (u_id,))
            ultimo = cur.fetchone()
            
            # 4. Se estiver "DENTRO", força a SAÍDA
            if ultimo and ultimo[0] == "ENTRADA":
                # Regista SAIDA na BD
                cur.execute("INSERT INTO registos (funcionario_id, tipo_movimento) VALUES (%s, 'SAIDA')", (u_id,))
                conn.commit()
                count_saidas += 1
                
                # Envia para o ThingsBoard
                msg_historico = f"{hora_pt} | {u_nome} | SAIDA (AUTO)"
                dados_tb = {
                    "funcionario": u_nome,
                    "movimento": "SAIDA",
                    "status": "Saída Automática (Fim do Dia)",
                    "log_historico": msg_historico,
                    "hora_saida": hora_pt
                }
                enviar_thingsboard(dados_tb)
        
        cur.close()
        conn.close()
        return f"Processo concluído. Foram fechadas {count_saidas} saídas."

    except Exception as e:
        if conn: conn.close()
        return f"Erro: {str(e)}"
# -----------------------------------------------------

# --- ROTA: MUDAR PIN POR ID ---
@app.route('/mudar_pin', methods=['POST'])
def mudar_pin():
    # O ThingsBoard agora envia: {"id_antigo": "1234", "id_novo": "9999"}
    dados = request.json
    
    if not dados or 'id_antigo' not in dados or 'id_novo' not in dados:
        return jsonify({"erro": "Dados incompletos. Envie id_antigo e id_novo"}), 400

    id_antigo = dados['id_antigo']
    id_novo = dados['id_novo']
    
    conn = get_db_connection()
    if not conn: return jsonify({"erro": "Erro na BD"}), 500
    
    cur = conn.cursor()
    try:
        # Atualiza o PIN onde o PIN antigo corresponde
        cur.execute("UPDATE funcionarios SET pin_code = %s WHERE pin_code = %s", (id_novo, id_antigo))
        conn.commit()
        
        registos_afetados = cur.rowcount
        cur.close()
        conn.close()
        
        if registos_afetados > 0:
            print(f"✅ PIN alterado de {id_antigo} para {id_novo}")
            return jsonify({"status": "sucesso", "mensagem": "PIN alterado com sucesso!"}), 200
        else:
            print(f"❌ ID Antigo não encontrado: {id_antigo}")
            return jsonify({"erro": "ID Antigo nao existe"}), 404

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
            msg_historico = f"{hora_pt} | {nome_user} | {novo_movimento}"

            dados_tb = {
                "funcionario": nome_user,
                "movimento": novo_movimento,
                "status": "Acesso Permitido",
                "ultimo_id": pin_recebido,
                "log_historico": msg_historico
            }
            if novo_movimento == "ENTRADA":
                dados_tb["hora_entrada"] = hora_pt
            else:
                dados_tb["hora_saida"] = hora_pt

            enviar_thingsboard(dados_tb)

            cur.close()
            conn.close()
            return "1"
        
        else:
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
