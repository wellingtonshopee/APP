from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)

# Caminho do banco de dados
DB_PATH = 'sistema_cargas.db'

# Conexão com o banco de dados
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Criação da coluna 'em_separacao' caso não exista
def inicializar_banco():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            matricula TEXT NOT NULL,
            rota TEXT NOT NULL,
            dataHora TEXT NOT NULL,
            gaiola TEXT,
            posicao TEXT,
            em_separacao INTEGER DEFAULT 0
        )
    ''')
    # Adiciona coluna se ela não existir
    try:
        conn.execute('SELECT em_separacao FROM registros LIMIT 1')
    except sqlite3.OperationalError:
        conn.execute('ALTER TABLE registros ADD COLUMN em_separacao INTEGER DEFAULT 0')
    conn.commit()
    conn.close()

# Pega todos os registros
def obter_registros():
    conn = get_db_connection()
    registros = conn.execute('SELECT * FROM registros').fetchall()
    conn.close()
    registros_ordenados = sorted(
        registros,
        key=lambda r: bool(r['gaiola']) and bool(r['posicao'])
    )
    return registros_ordenados

@app.route('/')
def index():
    registros = obter_registros()
    sucesso = request.args.get('sucesso')
    return render_template('index.html', registros=registros, sucesso=sucesso)

@app.route('/separacao')
def separacao():
    registros = obter_registros()
    return render_template('separacao.html', registros=registros)

@app.route('/carga')
def carga():
    registros = obter_registros()
    return render_template('carga.html', registros=registros)

@app.route('/painel')
def painel():
    registros = obter_registros()
    return render_template('painel.html', registros=registros)

@app.route('/atualizar', methods=['POST'])
def atualizar():
    gaiola = request.form.get('gaiola')
    posicao = request.form.get('posicao')
    id_registro = request.form.get('id')

    if not gaiola or not posicao or not id_registro:
        return "Erro: Todos os campos são obrigatórios!", 400

    conn = get_db_connection()
    conn.execute(
        'UPDATE registros SET gaiola = ?, posicao = ? WHERE id = ?',
        (gaiola, posicao, id_registro)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('carga'))

@app.route('/enviar', methods=['POST'])
def enviar():
    nome = request.form.get('nome')
    matricula = request.form.get('matricula')
    rota = request.form.get('rota')
    data_hora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if not nome or not matricula or not rota:
        return "Erro: Todos os campos são obrigatórios!", 400

    conn = get_db_connection()
    conn.execute(
        'INSERT INTO registros (nome, matricula, rota, dataHora) VALUES (?, ?, ?, ?)',
        (nome, matricula, rota, data_hora)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('index', sucesso=1))

@app.route('/excluir', methods=['POST'])
def excluir():
    id_registro = request.form.get('id')
    if not id_registro:
        return "Erro: O ID do registro é obrigatório!", 400
    conn = get_db_connection()
    conn.execute('DELETE FROM registros WHERE id = ?', (id_registro,))
    conn.commit()
    conn.close()
    return redirect(url_for('carga'))

@app.route('/separar/<int:id>', methods=['POST'])
def marcar_separacao(id):
    conn = get_db_connection()
    atual = conn.execute('SELECT em_separacao FROM registros WHERE id = ?', (id,)).fetchone()
    novo_estado = 0 if atual['em_separacao'] else 1
    conn.execute('UPDATE registros SET em_separacao = ? WHERE id = ?', (novo_estado, id))
    conn.commit()
    conn.close()
    return '', 204

if __name__ == '__main__':
    inicializar_banco()
    app.run(debug=True)
