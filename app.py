from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from datetime import datetime

app = Flask(__name__)

# Conexão com o banco de dados
def get_db_connection():
    conn = sqlite3.connect('sistema_cargas.db')
    conn.row_factory = sqlite3.Row
    return conn

# Função para pegar os registros da carga
def obter_registros():
    conn = get_db_connection()
    registros = conn.execute('SELECT * FROM registros').fetchall()
    conn.close()
    return registros

@app.route('/')
def index():
    return render_https://github.com/wellingtonshopee/APP/blob/main/('index.html')

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
    conn.execute('UPDATE registros SET gaiola = ?, posicao = ? WHERE id = ?',
                 (gaiola, posicao, id_registro))
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
    conn.execute('INSERT INTO registros (nome, matricula, rota, dataHora) VALUES (?, ?, ?, ?)',
                 (nome, matricula, rota, data_hora))
    conn.commit()
    conn.close()

    return redirect(url_for('index'))

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

if __name__ == '__main__':
    app.run(debug=True)
