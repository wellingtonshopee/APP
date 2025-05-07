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

# --- Data e hora com timezone Brasil no formato ISO ---
def get_data_hora_brasilia():
    tz_brasilia = pytz.timezone('America/Sao_Paulo')
    return datetime.now(tz_brasilia).strftime('%Y-%m-%d - %H:%M:%S')

# --- Filtro para formatar data/hora no padrão desejado (dd-mm-yyyy) ---
@app.template_filter('formata_data_hora')
def formata_data_hora(valor):
    if not valor:
        return ''
    try:
        # Tenta primeiro o formato que já inclui o timezone, se for o caso
        # Se o valor já for um objeto datetime, não precisa de parse
        if isinstance(valor, datetime):
            dt = valor
        else:
            dt = datetime.strptime(valor, '%Y-%m-%d - %H:%M:%S')
        return dt.strftime('%d-%m-%Y %H:%M')
    except ValueError:
        # Tenta um formato mais simples, caso o parse anterior falhe
        try:
            dt = datetime.strptime(valor, '%Y-%m-%d %H:%M:%S')
            return dt.strftime('%d-%m-%Y %H:%M')
        except ValueError:
            return valor # Retorna o valor original se todos os parses falharem

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
        # Verificar se a coluna 'finalizada' já existe antes de tentar adicioná-la
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(registros)")
        columns = [column[1] for column in cursor.fetchall()]

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
                em_separacao INTEGER DEFAULT 0,
                finalizada INTEGER DEFAULT 0
            )
        ''')

        # Adicionar a coluna 'finalizada' APENAS se ela não existir
        if 'finalizada' not in columns:
            conn.execute('ALTER TABLE registros ADD COLUMN finalizada INTEGER DEFAULT 0')
            print("Coluna 'finalizada' adicionada à tabela 'registros'.")

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

# --- Padronizar dados existentes ---
def padronizar_dados_existentes():
    with get_db_connection() as conn:
        registros = conn.execute('SELECT id, nome, rota, tipo_entrega, tipo_veiculo, cidade_entrega, gaiola, estacao FROM registros').fetchall()
        for r in registros:
            conn.execute('''
                UPDATE registros SET
                    nome = ?,
                    rota = ?,
                    tipo_entrega = ?,
                    tipo_veiculo = ?,
                    cidade_entrega = ?,
                    gaiola = ?,
                    estacao = ?
                WHERE id = ?
            ''', (
                r['nome'].title() if r['nome'] else None,
                r['rota'].title() if r['rota'] else None,
                r['tipo_entrega'].title() if r['tipo_entrega'] else None,
                r['tipo_veiculo'].title() if r['tipo_veiculo'] else None,
                r['cidade_entrega'].title() if r['cidade_entrega'] else None,
                r['gaiola'].title() if r['gaiola'] else None,
                r['estacao'].title() if r['estacao'] else None,
                r['id']
            ))
        conn.commit()

@app.route('/buscar_cidades')
def buscar_cidades():
    termo = request.args.get('termo', '').lower()
    with get_db_connection() as conn:
        cidades = conn.execute('''
            SELECT cidade FROM cidades
            WHERE LOWER(cidade) LIKE ?
            LIMIT 10
        ''', (f'%{termo}%',)).fetchall()
    return jsonify([c['cidade'].title() for c in cidades])

@app.route('/buscar_nome', methods=['POST'])
def buscar_nome():
    data = request.get_json()
    matricula = data.get('matricula')
    if not matricula:
        return jsonify({'erro': 'Matrícula não informada'}), 400
    with get_db_connection() as conn:
        registro = conn.execute('SELECT nome FROM registros WHERE matricula = ? ORDER BY id DESC LIMIT 1', (matricula,)).fetchone() #Pega o mais recente
    return jsonify({'nome': registro['nome'].title() if registro and registro['nome'] else ''})


@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    erro = None
    if request.method == 'POST':
        matricula = request.form['matricula']
        nome = request.form['nome'].title()
        rota = request.form.get('rota', '').title() # Usar .get para campos opcionais
        tipo_entrega = request.form.get('tipo_entrega', '').title()
        cidade_entrega = request.form.get('cidade_entrega', '').title()
        data_hora = get_data_hora_brasilia()

        with get_db_connection() as conn:
            registro_antigo = conn.execute(
                'SELECT cpf, tipo_veiculo FROM registros WHERE matricula = ? ORDER BY id DESC LIMIT 1',
                (matricula,)
            ).fetchone()

            if registro_antigo:
                cpf = registro_antigo['cpf']
                tipo_veiculo = registro_antigo['tipo_veiculo']
            else:
                erro = 'Matrícula não cadastrada. Faça o cadastro primeiro ou verifique a matrícula.'
                return render_template('login.html', erro=erro)

            conn.execute('''
                INSERT INTO registros (nome, matricula, rota, tipo_entrega, cidade_entrega,
                                                data_hora_login, cpf, tipo_veiculo, em_separacao, finalizada)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
            ''', (nome, matricula, rota, tipo_entrega, cidade_entrega, data_hora, cpf, tipo_veiculo))
            conn.commit()
        return redirect(url_for('boas_vindas'))

    return render_template('login.html', erro=erro)

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    erro = None
    if request.method == 'POST':
        nome = request.form['nome'].title()
        matricula = request.form['matricula']
        cpf_input = request.form['cpf'] # Mantém o formato original para validação
        tipo_veiculo = request.form['tipo_veiculo'].title()
        data_hora = get_data_hora_brasilia()

        if not validar_cpf(cpf_input): # Valida o CPF como foi digitado
            erro = "CPF inválido. Verifique e tente novamente."
            return render_template('cadastro.html', erro=erro)

        cpf_numeros = ''.join(filter(str.isdigit, cpf_input))
        cpf_formatado = f'{cpf_numeros[:3]}.{cpf_numeros[3:6]}.{cpf_numeros[6:9]}-{cpf_numeros[9:]}'


        with get_db_connection() as conn:
            # Verificar se a matrícula já existe
            existente = conn.execute('SELECT id FROM registros WHERE matricula = ?', (matricula,)).fetchone()
            if existente:
                erro = "Matrícula já cadastrada. Tente fazer login ou use outra matrícula."
                return render_template('cadastro.html', erro=erro)

            conn.execute('''
                INSERT INTO registros (nome, matricula, cpf, tipo_veiculo, data_hora_login, finalizada)
                VALUES (?, ?, ?, ?, ?, 0)
            ''', (nome, matricula, cpf_formatado, tipo_veiculo, data_hora))
            conn.commit()
        return redirect(url_for('sucesso'))
    return render_template('cadastro.html', erro=erro)

@app.route('/sucesso')
def sucesso():
    return render_template('sucesso.html')

@app.route('/boas_vindas')
def boas_vindas():
    return render_template('boas_vindas.html')

@app.route('/todos_registros')
def todos_registros():
    with get_db_connection() as conn:
        registros = conn.execute('SELECT * FROM registros ORDER BY data_hora_login DESC').fetchall()
    return render_template('todos_registros.html', registros=registros)

@app.route('/registros', methods=['GET', 'POST'])
def registros():
    # Parâmetros para manter o estado do filtro no redirect
    data_filtro = request.args.get('data', '')
    nome_filtro = request.args.get('nome', '')
    matricula_filtro = request.args.get('matricula', '')
    rota_filtro = request.args.get('rota', '')
    tipo_entrega_filtro = request.args.get('tipo_entrega', '')

    if request.method == 'POST':
        # Esta parte é para o checkbox 'em_separacao' que já existia.
        # Se você tiver um formulário específico para isso, ele funcionará.
        # Caso contrário, essa lógica pode não ser acionada como esperado
        # se o POST vier de outro lugar (como o novo botão de finalizar).
        if 'registro_id' in request.form and 'em_separacao' in request.form:
            registro_id = request.form['registro_id']
            em_separacao = 1 if request.form.get('em_separacao') == 'on' else 0
            with get_db_connection() as conn:
                conn.execute('''
                    UPDATE registros
                    SET em_separacao = ?
                    WHERE id = ?
                ''', (em_separacao, registro_id))
                conn.commit()
            # Redirecionar mantendo os filtros
            return redirect(url_for('registros', data=data_filtro, nome=nome_filtro,
                                            matricula=matricula_filtro, rota=rota_filtro,
                                            tipo_entrega=tipo_entrega_filtro) + f'#registro-{registro_id}')


    query = 'SELECT * FROM registros WHERE 1=1'
    parametros = []

    if data_filtro:
        try:
            datetime.strptime(data_filtro, '%Y-%m-%d') # Apenas para validar o formato
            query += ' AND substr(data_hora_login, 1, 10) = ?'
            parametros.append(data_filtro)
        except ValueError:
            pass # Ignora data inválida

    if nome_filtro:
        query += ' AND nome LIKE ?'
        parametros.append(f'%{nome_filtro.title()}%')
    if matricula_filtro:
        query += ' AND matricula LIKE ?'
        parametros.append(f'%{matricula_filtro}%')
    if rota_filtro:
        query += ' AND rota LIKE ?'
        parametros.append(f'%{rota_filtro.title()}%')
    if tipo_entrega_filtro:
        query += ' AND tipo_entrega LIKE ?'
        parametros.append(f'%{tipo_entrega_filtro.title()}%')

    query += ' ORDER BY CASE WHEN finalizada = 0 THEN 0 ELSE 1 END, data_hora_login DESC' # Prioriza não finalizados

    with get_db_connection() as conn:
        registros_data = conn.execute(query, parametros).fetchall()

    return render_template('registros.html', registros=registros_data,
                            data_filtro=data_filtro, nome_filtro=nome_filtro,
                            matricula_filtro=matricula_filtro, rota_filtro=rota_filtro,
                            tipo_entrega_filtro=tipo_entrega_filtro)


@app.route('/historico')
def historico():
    with get_db_connection() as conn:
        historico_data = conn.execute('SELECT h.*, r.nome, r.matricula FROM historico h JOIN registros r ON h.registro_id = r.id ORDER BY h.data_hora DESC').fetchall()
    return render_template('historico.html', historico=historico_data)


@app.route('/associacao')
def associacao():
    id_registro = request.args.get('id', type=int)
    pagina = int(request.args.get('pagina', 1))
    rota_filtro = request.args.get('rota')
    tipo_entrega_filtro = request.args.get('tipo_entrega')
    registros_por_pagina = 1
    offset = (pagina - 1) * registros_por_pagina

    with get_db_connection() as conn:
        if id_registro:
            registro = conn.execute('SELECT * FROM registros WHERE id = ? AND finalizada = 0', (id_registro,)).fetchone() # Só carrega se não finalizado
            registros_data = [registro] if registro else []
            total_paginas = 1 if registro else 0
            return render_template('associacao.html', registros=registros_data, pagina=1, total_paginas=total_paginas, rota=None, tipo_entrega=None, filtro_id=id_registro)
        else:
            base_query = 'SELECT * FROM registros WHERE finalizada = 0 ' # Apenas não finalizados
            count_query = 'SELECT COUNT(*) FROM registros WHERE finalizada = 0 '
            params = []
            count_params = []

            filter_conditions = []
            if rota_filtro:
                filter_conditions.append('rota LIKE ?')
                params.append(f'%{rota_filtro.title()}%')
                count_params.append(f'%{rota_filtro.title()}%')

            if tipo_entrega_filtro:
                filter_conditions.append('tipo_entrega LIKE ?')
                params.append(f'%{tipo_entrega_filtro.title()}%')
                count_params.append(f'%{tipo_entrega_filtro.title()}%')
            
            if filter_conditions:
                base_query += ' AND ' + ' AND '.join(filter_conditions)
                count_query += ' AND ' + ' AND '.join(filter_conditions)


            total = conn.execute(count_query, count_params).fetchone()[0]
            total_paginas = (total + registros_por_pagina - 1) // registros_por_pagina

            base_query += ' ORDER BY em_separacao ASC, data_hora_login DESC LIMIT ? OFFSET ?' # Prioriza os não "em_separacao"
            params.extend([registros_por_pagina, offset])
            registros_data = conn.execute(base_query, params).fetchall()

            return render_template('associacao.html', registros=registros_data, pagina=pagina,
                                            total_paginas=total_paginas, rota=rota_filtro,
                                            tipo_entrega=tipo_entrega_filtro, filtro_id=None)


@app.route('/associar/<int:id>', methods=['POST'])
def associar_id(id):
    gaiola = request.form.get('gaiola', '').title()
    estacao = request.form.get('estacao', '').title()
    em_separacao = 1 # Ao associar, marca como "em separação"
    data_hora = get_data_hora_brasilia()

    with get_db_connection() as conn:
        conn.execute('''
            UPDATE registros
            SET gaiola = ?, estacao = ?, em_separacao = ?
            WHERE id = ? AND finalizada = 0
        ''', (gaiola, estacao, em_separacao, id))

        conn.execute('''
            INSERT INTO historico (registro_id, acao, gaiola, estacao, data_hora)
            VALUES (?, 'associado', ?, ?, ?)
        ''', (id, gaiola, estacao, data_hora))
        conn.commit()

    return redirect(request.referrer + f'#registro-{id}')

@app.route('/desassociar/<int:id>', methods=['POST'])
def desassociar_id(id):
    data_hora = get_data_hora_brasilia()

    with get_db_connection() as conn:
        conn.execute('''
            UPDATE registros
            SET gaiola = NULL, estacao = NULL, em_separacao = 0
            WHERE id = ?
        ''', (id,))
        conn.execute('''
            INSERT INTO historico (registro_id, acao, data_hora)
            VALUES (?, 'desassociado', ?)
        ''', (id, data_hora))
        conn.commit()
    return redirect(request.referrer + f'#registro-{id}')

@app.route('/finalizar_carregamento_status_separacao/<int:id>', methods=['POST'])
def finalizar_carregamento_id_status_separacao(id):
    data_hora = get_data_hora_brasilia()
    with get_db_connection() as conn:
        conn.execute('''
            UPDATE registros
            SET em_separacao = 2
            WHERE id = ?
        ''', (id,))
        conn.execute('''
            INSERT INTO historico (registro_id, acao, data_hora)
            VALUES (?, 'finalizado_carregamento_separacao', ?)
        ''', (id, data_hora))
        conn.commit()
    return redirect(request.referrer + f'#registro-{id}')


@app.route('/marcar_como_finalizado/<int:id>', methods=['POST'])
def marcar_como_finalizado_id(id):
    data_hora = get_data_hora_brasilia()
    with get_db_connection() as conn:
        conn.execute('''
            UPDATE registros
            SET finalizada = 1, em_separacao = 3
            WHERE id = ?
        ''', (id,))

        conn.execute('''
            INSERT INTO historico (registro_id, acao, data_hora)
            VALUES (?, 'finalizado_registro', ?)
        ''', (id, data_hora))
        conn.commit()

        registro_atualizado = conn.execute('SELECT finalizada FROM registros WHERE id = ?', (id,)).fetchone()
        if registro_atualizado and registro_atualizado['finalizada'] == 1:
            print(f"Registro {id} marcado como finalizado com sucesso no banco.")
        else:
            print(f"Falha ao marcar registro {id} como finalizado no banco ou já estava finalizado.")

    return redirect(request.referrer + f'#registro-{id}')


@app.route('/voltar_para_associacao/<int:id>', methods=['POST'])
def voltar_para_associacao_id(id):
    data_hora = get_data_hora_brasilia()
    with get_db_connection() as conn:
        conn.execute('''
            UPDATE registros
            SET gaiola = NULL, estacao = NULL, em_separacao = 0, finalizada = 0
            WHERE id = ?
        ''', (id,))
        conn.execute('''
            INSERT INTO historico (registro_id, acao, data_hora)
            VALUES (?, 'retornado_para_associacao', ?)
        ''', (id, data_hora))
        conn.commit()
    return redirect(request.referrer + f'#registro-{id}')


# --- Inicializar banco ao iniciar ---
init_db()
# padronizar_dados_existentes() # Descomente se precisar rodar uma vez para dados antigos

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
