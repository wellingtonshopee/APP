from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
from datetime import datetime
import pytz

app = Flask(__name__)

# --- Conexão com o banco ---
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# --- Data e hora com timezone Brasil ---
def get_data_hora_brasilia():
    tz_brasilia = pytz.timezone('America/Sao_Paulo')
    return datetime.now(tz_brasilia).strftime('%Y-%m-%d %H:%M:%S')

# --- Validação de CPF ---
def validar_cpf(cpf):
    cpf = ''.join(filter(str.isdigit, cpf))
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    def calcular_digito(digs, peso):
        soma = sum(int(d) * p for d, p in zip(digs, range(peso, 1, -1)))
        resto = soma % 11
        return '0' if resto < 2 else str(11 - resto)
    digito1 = calcular_digito(cpf[:9], 10)
    digito2 = calcular_digito(cpf[:10], 11)
    return cpf[-2:] == digito1 + digito2

# --- Inicializar banco ---
def init_db():
    with get_db_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS registros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                matricula TEXT NOT NULL,
                rota TEXT,
                tipo_entrega TEXT,
                tipo_veiculo TEXT,
                cidade_entrega TEXT,
                data_hora_login DATETIME,
                gaiola TEXT,
                estacao TEXT,
                cpf TEXT NOT NULL,
                em_separacao INTEGER DEFAULT 0
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS historico (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                registro_id INTEGER NOT NULL,
                acao TEXT,
                gaiola TEXT,
                estacao TEXT,
                data_hora DATETIME,
                FOREIGN KEY (registro_id) REFERENCES registros(id)
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS cidades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cidade TEXT NOT NULL
            )
        ''')
        conn.commit()

# --- Rota para autocompletar cidades ---
@app.route('/buscar_cidades')
def buscar_cidades():
    termo = request.args.get('termo', '').lower()
    with get_db_connection() as conn:
        cidades = conn.execute('''
            SELECT cidade FROM cidades
            WHERE LOWER(cidade) LIKE ?
            LIMIT 10
        ''', (f'%{termo}%',)).fetchall()
    return jsonify([c['cidade'] for c in cidades])

# --- Rota para buscar nome pela matrícula ---
@app.route('/buscar_nome', methods=['POST'])
def buscar_nome():
    # Recebe a matrícula do corpo da requisição
    data = request.get_json()
    matricula = data.get('matricula')

    if not matricula:
        return jsonify({'erro': 'Matrícula não informada'}), 400

    # Consulta o banco para procurar o nome pela matrícula
    with get_db_connection() as conn:
        registro = conn.execute('SELECT nome FROM registros WHERE matricula = ?', (matricula,)).fetchone()

    if registro:
        return jsonify({'nome': registro['nome']})
    else:
        return jsonify({'nome': None})

# --- Rota Login ---
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    erro = None
    if request.method == 'POST':
        matricula = request.form['matricula']
        nome = request.form['nome'].title()
        rota = request.form['rota']
        tipo_entrega = request.form['tipo_entrega']
        cidade_entrega = request.form['cidade_entrega']
        data_hora = get_data_hora_brasilia()

        with get_db_connection() as conn:
            registro = conn.execute('SELECT * FROM registros WHERE matricula = ?', (matricula,)).fetchone()
            if registro:
                conn.execute('''
                    UPDATE registros 
                    SET rota = ?, tipo_entrega = ?, cidade_entrega = ?, data_hora_login = ?
                    WHERE matricula = ?
                ''', (rota, tipo_entrega, cidade_entrega, data_hora, matricula))
                conn.commit()
                return redirect(url_for('boas_vindas'))
            else:
                erro = 'Matrícula não cadastrada. Faça o cadastro.'
    return render_template('login.html', erro=erro)

# --- Cadastro ---
@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    erro = None
    if request.method == 'POST':
        nome = request.form['nome'].title()
        matricula = request.form['matricula']
        cpf = ''.join(filter(str.isdigit, request.form['cpf']))
        tipo_veiculo = request.form['tipo_veiculo']
        data_hora = get_data_hora_brasilia()

        if not validar_cpf(cpf):
            erro = "CPF inválido. Verifique e tente novamente."
            return render_template('cadastro.html', erro=erro)

        cpf_formatado = f'{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}'

        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO registros (nome, matricula, cpf, tipo_veiculo, data_hora_login)
                VALUES (?, ?, ?, ?, ?)
            ''', (nome, matricula, cpf_formatado, tipo_veiculo, data_hora))
            conn.commit()

        return redirect(url_for('sucesso'))

    return render_template('cadastro.html', erro=erro)

# --- Sucesso ---
@app.route('/sucesso')
def sucesso():
    return render_template('sucesso.html')

# --- Boas-vindas ---
@app.route('/boas_vindas')
def boas_vindas():
    return render_template('boas_vindas.html')

# --- Todos registros ---
@app.route('/todos_registros')
def todos_registros():
    with get_db_connection() as conn:
        registros = conn.execute('SELECT * FROM registros ORDER BY data_hora_login DESC').fetchall()
    return render_template('todos_registros.html', registros=registros)

# --- Registros com filtro ---
@app.route('/registros')
def registros():
    data = request.args.get('data')
    nome = request.args.get('nome')
    matricula = request.args.get('matricula')
    rota = request.args.get('rota')
    tipo_entrega = request.args.get('tipo_entrega')

    query = 'SELECT * FROM registros WHERE 1=1'
    parametros = []

    # Filtro por data
    if data:
        query += ' AND DATE(data_hora_login) = ?'
        parametros.append(data)

    # Filtro por nome
    if nome:
        query += ' AND nome LIKE ?'
        parametros.append(f'%{nome}%')

    # Filtro por matrícula
    if matricula:
        query += ' AND matricula LIKE ?'
        parametros.append(f'%{matricula}%')

    # Filtro por rota
    if rota:
        query += ' AND rota LIKE ?'
        parametros.append(f'%{rota}%')

    # Filtro por tipo de entrega
    if tipo_entrega:
        query += ' AND tipo_entrega LIKE ?'
        parametros.append(f'%{tipo_entrega}%')

    query += ' ORDER BY data_hora_login DESC'

    with get_db_connection() as conn:
        registros = conn.execute(query, parametros).fetchall()

    return render_template('registros.html', registros=registros, data=data, nome=nome, matricula=matricula, rota=rota, tipo_entrega=tipo_entrega)

# --- Histórico ---
@app.route('/historico')
def historico():
    with get_db_connection() as conn:
        historico = conn.execute('SELECT * FROM historico ORDER BY data_hora DESC').fetchall()
    return render_template('historico.html', historico=historico)

# --- Associação ---
@app.route('/associacao')
def associacao():
    pagina = int(request.args.get('pagina', 1))
    rota = request.args.get('rota')
    tipo_entrega = request.args.get('tipo_entrega')
    registros_por_pagina = 10
    offset = (pagina - 1) * registros_por_pagina

    with get_db_connection() as conn:
        query = '''
            SELECT * FROM registros
            WHERE (rota = ? OR ? IS NULL)
              AND (tipo_entrega = ? OR ? IS NULL)
            ORDER BY data_hora_login DESC
            LIMIT ? OFFSET ?
        '''
        registros = conn.execute(query, (rota, rota, tipo_entrega, tipo_entrega, registros_por_pagina, offset)).fetchall()
        total = conn.execute('''
            SELECT COUNT(*) FROM registros
            WHERE (rota = ? OR ? IS NULL)
              AND (tipo_entrega = ? OR ? IS NULL)
        ''', (rota, rota, tipo_entrega, tipo_entrega)).fetchone()[0]
        total_paginas = (total // registros_por_pagina) + (1 if total % registros_por_pagina else 0)

    return render_template('associacao.html', registros=registros, pagina=pagina, total_paginas=total_paginas, rota=rota, tipo_entrega=tipo_entrega)

# --- Marcar separação ---
@app.route('/marcar_separacao/<int:id>', methods=['POST'])
def marcar_separacao(id):
    with get_db_connection() as conn:
        conn.execute('UPDATE registros SET em_separacao = 1 WHERE id = ?', (id,))
        conn.commit()
        conn.execute('''
            INSERT INTO historico (registro_id, acao, gaiola, estacao, data_hora)
            VALUES (?, ?, ?, ?, ?)
        ''', (id, 'Marcar como separado', None, None, get_data_hora_brasilia()))
        conn.commit()
    return jsonify({'status': 'ok'})

# --- Editar gaiola/estação ---
@app.route('/editar/<int:id>', methods=['POST'])
def editar(id):
    gaiola = request.form['gaiola']
    estacao = request.form['estacao']
    with get_db_connection() as conn:
        conn.execute('UPDATE registros SET gaiola = ?, estacao = ? WHERE id = ?', (gaiola, estacao, id))
        conn.commit()
        conn.execute('''
            INSERT INTO historico (registro_id, acao, gaiola, estacao, data_hora)
            VALUES (?, ?, ?, ?, ?)
        ''', (id, 'Editar gaiola e estação', gaiola, estacao, get_data_hora_brasilia()))
        conn.commit()
    return redirect(url_for('associacao'))

# --- Desassociar ---
@app.route('/desassociar_id/<int:id>', methods=['POST'])
def desassociar_id(id):
    with get_db_connection() as conn:
        conn.execute('UPDATE registros SET gaiola = NULL, estacao = NULL WHERE id = ?', (id,))
        conn.commit()
        conn.execute('''
            INSERT INTO historico (registro_id, acao, gaiola, estacao, data_hora)
            VALUES (?, ?, ?, ?, ?)
        ''', (id, 'Desassociar gaiola e estação', None, None, get_data_hora_brasilia()))
        conn.commit()
    return redirect(url_for('associacao'))

# --- Painel final ---
@app.route('/painel_final')
def painel_final():
    with get_db_connection() as conn:
        registros = conn.execute('SELECT * FROM registros WHERE em_separacao = 1 ORDER BY data_hora_login DESC').fetchall()
    return render_template('painel_final.html', registros=registros)

# --- Rodar a aplicação ---
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
