from flask import Flask, request
import psycopg2
import os

app = Flask(__name__)

# --- A TUA CONNECTION STRING (JÁ ESTÁ CERTA) ---
DATABASE_URL = "postgresql://neondb_owner:npg_AtR4hBFdcx5K@ep-red-firefly-adwfe8r0-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"

def get_db_connection():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Erro de Conexão: {e}")
        return None

# Rota Principal (Para saberes que o site existe)
@app.route('/')
def home():
    return "Servidor Online e Pronto! Usa o Arduino."

# Rota de Validação (A que o Arduino usa)
@app.route('/validar', methods=['GET'])
def validar_entrada():
    # 1. Receber o ID
    pin_recebido = request.args.get('id')
    
    # 2. Ligar à Base de Dados
    conn = get_db_connection()
    if not conn: 
        return "0" # Falha na conexão

    cur = conn.cursor()
    
    try:
        # 3. Verificar se o funcionário existe e está ativo
        cur.execute("SELECT id, nome FROM funcionarios WHERE pin_code = %s AND ativo = TRUE", (pin_recebido,))
        funcionario = cur.fetchone()

        if funcionario:
            user_id = funcionario[0]
            nome_user = funcionario[1]

            # 4. Descobrir se é ENTRADA ou SAÍDA (Lógica Inteligente)
            cur.execute("SELECT tipo_movimento FROM registos WHERE funcionario_id = %s ORDER BY id DESC LIMIT 1", (user_id,))
            ultimo_registo = cur.fetchone()
            
            novo_movimento = "ENTRADA" # Padrão
            
            if ultimo_registo and ultimo_registo[0] == "ENTRADA":
                novo_movimento = "SAIDA"
            
            # 5. Gravar o movimento na tabela
            cur.execute("INSERT INTO registos (funcionario_id, tipo_movimento) VALUES (%s, %s)", (user_id, novo_movimento))
            conn.commit()
            
            cur.close()
            conn.close()
            
            print(f"✅ SUCESSO: {nome_user} ({novo_movimento})")
            return "1" # <--- RETORNA 1 (Sucesso)
        
        else:
            cur.close()
            conn.close()
            print(f"❌ ID NÃO ENCONTRADO: {pin_recebido}")
            return "0" # <--- RETORNA 0 (Acesso Negado)

    except Exception as e:
        print(f"Erro SQL: {e}")
        if conn: conn.close()
        return "0"
