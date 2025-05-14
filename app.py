from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import sqlite3
from datetime import datetime
import pytz



app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta_aqui' # Adicione uma chave secreta para flash messages


# --- Conexão à Base de Dados ---
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# --- Obter data e hora no fuso horário do Brasil no formato ISO ---
def get_data_hora_brasilia():
    tz_brasilia = pytz.timezone('America/Sao_Paulo')
    return datetime.now(tz_brasilia).strftime('%Y-%m-%d - %H:%M:%S')

# --- Filtro para formatar data/hora para o padrão desejado (dd-mm-yyyy) ---
@app.template_filter('formata_data_hora')
def formata_data_hora(valor):
    if not valor:
        return ''
    try:
        if isinstance(valor, datetime):
            dt = valor
        else:
            dt = datetime.strptime(valor, '%Y-%m-%d - %H:%M:%S')
        return dt.strftime('%d-%m-%Y %H:%M')
    except ValueError:
        try:
            dt = datetime.strptime(valor, '%Y-%m-%d %H:%M:%S')
            return dt.strftime('%d-%m-%Y %H:%M')
        except ValueError:
            return valor

# --- Validação de CPF (Cadastro de Pessoa Física brasileiro) ---
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

# --- Inicializar Base de Dados ---
def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # --- Tabela registros ---
        cursor.execute("PRAGMA table_info(registros)")
        columns_registros = [column[1] for column in cursor.fetchall()]
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
                finalizada INTEGER DEFAULT 0,
                hora_finalizacao TEXT,
                cancelado INTEGER DEFAULT 0,
                login_id INTEGER,
                rua TEXT, -- Adicionado a coluna 'rua' aqui
                FOREIGN KEY (login_id) REFERENCES login(id)
            )
        ''')
        if 'hora_finalizacao' not in columns_registros:
            conn.execute('ALTER TABLE registros ADD COLUMN hora_finalizacao TEXT')
            print("Coluna 'hora_finalizacao' adicionada à tabela 'registros'.")
        if 'cancelado' not in columns_registros:
            conn.execute('ALTER TABLE registros ADD COLUMN cancelado INTEGER DEFAULT 0')
            print("Coluna 'cancelado' adicionada à tabela 'registros'.")
        if 'login_id' not in columns_registros:
            conn.execute('ALTER TABLE registros ADD COLUMN login_id INTEGER')
            print("Coluna 'login_id' adicionada à tabela 'registros'.")
        # Adiciona a coluna 'rua' à tabela registros se ela não existir
        if 'rua' not in columns_registros:
            conn.execute('ALTER TABLE registros ADD COLUMN rua TEXT')
            print("Coluna 'rua' adicionada à tabela 'registros'.")

        print("Tabela 'registros' verificada/criada.")


        # --- Tabela login ---
        cursor.execute("PRAGMA table_info(login)")
        columns_login = [column[1] for column in cursor.fetchall()]
        conn.execute('''
            CREATE TABLE IF NOT EXISTS login (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                matricula TEXT NOT NULL UNIQUE,
                cpf TEXT NOT NULL UNIQUE,
                tipo_veiculo TEXT,
                data_cadastro DATETIME
            )
        ''')
        print("Tabela 'login' verificada/criada.")

        # --- Tabela historico ---
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
        print("Tabela 'historico' verificada/creada.")


        # --- Tabela cidades ---
        conn.execute('''
            CREATE TABLE IF NOT EXISTS cidades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cidade TEXT NOT NULL UNIQUE
            )
        ''')
        print("Tabela 'cidades' verificada/criada.")

        # --- Tabela no_show ---
        cursor.execute("PRAGMA table_info(no_show)")
        columns_no_show = [column[1] for column in cursor.fetchall()]
        conn.execute('''
            CREATE TABLE IF NOT EXISTS no_show (
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
                finalizada INTEGER DEFAULT 0,
                hora_finalizacao TEXT,
                cancelado INTEGER DEFAULT 0,
                login_id INTEGER,
                transferred_to_registro_id INTEGER, -- Coluna para o ID do registro de destino
                original_registro_gaiola TEXT, -- Nova coluna para gaiola original do registro
                original_registro_estacao TEXT, -- Nova coluna para estação original do registro
                rua TEXT, -- Nova coluna 'rua'
                FOREIGN KEY (login_id) REFERENCES login(id),
                FOREIGN KEY (transferred_to_registro_id) REFERENCES registros(id)
            )
        ''')
        if 'hora_finalizacao' not in columns_no_show:
            conn.execute('ALTER TABLE no_show ADD COLUMN hora_finalizacao TEXT')
            print("Coluna 'hora_finalizacao' adicionada à tabela 'no_show'.")
        if 'cancelado' not in columns_no_show:
            conn.execute('ALTER TABLE no_show ADD COLUMN cancelado INTEGER DEFAULT 0')
            print("Coluna 'cancelado' adicionada à tabela 'no_show'.")
        if 'login_id' not in columns_no_show:
            conn.execute('ALTER TABLE no_show ADD COLUMN login_id INTEGER')
            print("Coluna 'login_id' adicionada à tabela 'no_show'.")
        if 'transferred_to_registro_id' not in columns_no_show:
             conn.execute('ALTER TABLE no_show ADD COLUMN transferred_to_registro_id INTEGER')
             print("Coluna 'transferred_to_registro_id' adicionada à tabela 'no_show'.")
        # Adiciona as novas colunas se elas não existirem
        if 'original_registro_gaiola' not in columns_no_show:
             conn.execute('ALTER TABLE no_show ADD COLUMN original_registro_gaiola TEXT')
             print("Coluna 'original_registro_gaiola' adicionada à tabela 'no_show'.")
        if 'original_registro_estacao' not in columns_no_show:
             conn.execute('ALTER TABLE no_show ADD COLUMN original_registro_estacao TEXT')
             print("Coluna 'original_registro_estacao' adicionada à tabela 'no_show'.")
        # Adiciona a coluna 'rua' se ela não existir
        if 'rua' not in columns_no_show:
             conn.execute('ALTER TABLE no_show ADD COLUMN rua TEXT')
             print("Coluna 'rua' adicionada à tabela 'no_show'.")
        print("Tabela 'no_show' verificada/criada.")

        # --- Nova Tabela historico_no_show ---
        conn.execute('''
            CREATE TABLE IF NOT EXISTS historico_no_show (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                registro_no_show_id INTEGER NOT NULL,
                acao TEXT,
                gaiola TEXT,
                estacao TEXT,
                data_hora DATETIME,
                FOREIGN KEY (registro_no_show_id) REFERENCES no_show(id)
            )
        ''')
        print("Tabela 'historico_no_show' verificada/criada.")


        conn.commit()

# --- Padronizar Dados Existentes ---
# def padronizar_dados_existentes():
#    with get_db_connection() as conn:
#        registros = conn.execute('SELECT id, nome, rota, tipo_entrega, tipo_veiculo, cidade_entrega, gaiola, estacao FROM registros').fetchall()
#        for r in registros:
#            conn.execute('''
#                UPDATE registros SET
#                    nome = ?,
#                    rota = ?,
#                    tipo_entrega = ?,
#                    tipo_veiculo = ?,
#                    cidade_entrega = ?,
#                    gaiola = ?,
#                    estacao = ?
#                WHERE id = ?
#            ''', (
#                r['nome'].title() if r['nome'] else None,
#                r['rota'].title() if r['rota'] else None,
#                r['tipo_entrega'].title() if r['tipo_entrega'] else None,
#                r['tipo_veiculo'].title() if r['tipo_veiculo'] else None,
#                r['cidade_entrega'].title() if r['cidade_entrega'] else None,
#                r['gaiola'].title() if r['gaiola'] else None,
#                r['estacao'].title() if r['estacao'] else None,
#                r['id']
#            ))
#            conn.commit()

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
        return jsonify({'erro': 'Número de registro não informado'}), 400

    with get_db_connection() as conn:
        usuario = conn.execute('SELECT nome FROM login WHERE matricula = ?', (matricula,)).fetchone()

    if usuario and usuario['nome']:
        return jsonify({'nome': usuario['nome'].title()})
    else:
        return jsonify({'nome': None})
        

#---
@app.route('/', methods=['GET', 'POST'])
def login():
    erro = None
    if request.method == 'POST':
        matricula = request.form['matricula'].lower()
        nome = request.form['nome'].title()
        rota = request.form.get('rota', '').title()
        tipo_entrega = request.form.get('tipo_entrega', '').title()
        cidade_entrega = request.form.get('cidade_entrega', '').title()
        rua = request.form.get('rua', '').title()
        data_hora = get_data_hora_brasilia()

        with get_db_connection() as conn:
            # Verificar se a matrícula existe na tabela login
            user_login = conn.execute('SELECT id, nome FROM login WHERE LOWER(matricula) = ?', (matricula,)).fetchone()

            if user_login:
                login_id = user_login['id']
                nome_motorista = user_login['nome']

                # Buscar CPF e tipo_veiculo para o login_id
                user_data = conn.execute('SELECT cpf, tipo_veiculo FROM login WHERE id = ?', (login_id,)).fetchone()
                if user_data:
                    cpf = user_data['cpf']
                    tipo_veiculo = user_data['tipo_veiculo']

                    # Determinar a tabela de destino com base no tipo_entrega e na matrícula
                    if matricula == '0001' and tipo_entrega == 'No-Show':
                        tabela_destino = 'no_show'
                        # Inserir os dados na tabela no_show, incluindo a rua
                        conn.execute(f'''
                            INSERT INTO {tabela_destino} (nome, matricula, rota, tipo_entrega, cidade_entrega,
                                                        data_hora_login, cpf, tipo_veiculo, em_separacao, finalizada, login_id, rua)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
                        ''', (nome_motorista, matricula, rota, tipo_entrega, cidade_entrega, data_hora, cpf, tipo_veiculo, login_id, rua))
                    else:
                        tabela_destino = 'registros'
                        # Inserir os dados na tabela registros
                        conn.execute(f'''
                            INSERT INTO {tabela_destino} (nome, matricula, rota, tipo_entrega, cidade_entrega,
                                                        data_hora_login, cpf, tipo_veiculo, em_separacao, finalizada, login_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)
                        ''', (nome_motorista, matricula, rota, tipo_entrega, cidade_entrega, data_hora, cpf, tipo_veiculo, login_id))

                    conn.commit()

                    # Pegar o ID da nova sessão criada
                    new_session_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
                    print(f"Nova sessão criada para o número de registro {matricula} (login_id: {login_id}) com ID: {new_session_id} na tabela {tabela_destino}.")

                    # Redireciona para a tela de status do motorista
                    return redirect(url_for('status_motorista', registro_id=new_session_id, nome_motorista=nome_motorista))
                else:
                    erro = 'Erro ao buscar dados do usuário. Por favor, tente novamente.'
                    print(f"Erro ao buscar dados para login_id {login_id}.")
                    return render_template('login.html', erro=erro)

            else:
                erro = 'Número de registro não cadastrado. Por favor, cadastre-se primeiro.'
                print(f"Login falhou para o número de registro {matricula}: Não encontrado na tabela login.")
                return render_template('login.html', erro=erro)

    return render_template('login.html', erro=erro)

# --- Rota Status_motorista ---
@app.route('/status_motorista/<int:registro_id>/<string:nome_motorista>')
def status_motorista(registro_id, nome_motorista):
    """Exibe o status do motorista."""
    with get_db_connection() as conn:
        conn.row_factory = sqlite3.Row  # Para acessar as colunas por nome
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM registros WHERE id = ? AND nome = ?', (registro_id, nome_motorista))
        motorista = cursor.fetchone()

        if motorista:
            return render_template('status_motorista.html', motorista=motorista)
        else:
            return render_template('status_motorista.html', erro="Registro não encontrado.")



@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    """
    Handles initial user registration and records data in the login table.
    Prevents re-registering an existing matricula or CPF.
    """
    erro = None
    if request.method == 'POST':
        nome = request.form['nome'].title()
        matricula = request.form['matricula']
        cpf_input = request.form['cpf']
        tipo_veiculo = request.form['tipo_veiculo'].title()
        data_hora = get_data_hora_brasilia()

        if not validar_cpf(cpf_input):
            erro = "CPF inválido. Por favor, verifique e tente novamente."
            print(f"Cadastro falhou para o número de registro {matricula}: CPF inválido.")
            return render_template('cadastro.html', erro=erro)

        cpf_numeros = ''.join(filter(str.isdigit, cpf_input))
        if len(cpf_numeros) == 11:
            cpf_formatado = f'{cpf_numeros[:3]}.{cpf_numeros[3:6]}.{cpf_numeros[6:9]}-{cpf_numeros[9:]}'
        else:
            cpf_formatado = cpf_numeros

        with get_db_connection() as conn:
            # Verificar se a matrícula já existe na tabela login.
            existente_matricula = conn.execute('SELECT id FROM login WHERE matricula = ?', (matricula,)).fetchone()
            if existente_matricula:
                erro = "Número de registro já cadastrado. Por favor, tente fazer login."
                print(f"Cadastro falhou para o número de registro {matricula}: Número de registro já existe na tabela login.")
                return render_template('cadastro.html', erro=erro)

            # Verificar se o CPF já existe na tabela login.
            existente_cpf = conn.execute('SELECT id FROM login WHERE cpf = ?', (cpf_formatado,)).fetchone()
            if existente_cpf:
                erro = "CPF já cadastrado. Por favor, tente fazer login."
                print(f"Cadastro falhou para o número de registro {matricula}: CPF já existe na tabela login.")
                return render_template('cadastro.html', erro=erro)

            # Inserir os novos dados do usuário na tabela login.
            conn.execute('''
                INSERT INTO login (nome, matricula, cpf, tipo_veiculo, data_cadastro)
                VALUES (?, ?, ?, ?, ?)
            ''', (nome, matricula, cpf_formatado, tipo_veiculo, data_hora))
            conn.commit()

            print(f"Número de registro {matricula} cadastrado com sucesso na tabela login.")
            return redirect(url_for('sucesso'))

    return render_template('cadastro.html', erro=erro)

# The /sucesso and /boas_vindas routes might become less relevant
# if login/registration directly leads to the session/associacao page.
# Consider if you still need them or want to modify their purpose.
@app.route('/sucesso')
def sucesso():
    # This route is now primarily a confirmation page if needed,
    # as registration redirects directly to the session.
    return render_template('sucesso.html')

@app.route('/boas_vindas')
def boas_vindas():
    # This route was likely a post-login landing.
    # Login now redirects directly to the active/new session.
    # Consider if this page is still needed.
    return render_template('boas_vindas.html')


@app.route('/todos_registros')
def todos_registros():
    """Displays all historical and active records."""
    with get_db_connection() as conn:
        # Display all records, ordering active ones first
        registros = conn.execute('''
            SELECT * FROM registros
            ORDER BY CASE WHEN finalizada = 0 AND cancelado = 0 THEN 0 ELSE 1 END, data_hora_login DESC
        ''').fetchall()
    return render_template('todos_registros.html', registros=registros)

@app.route('/registros', methods=['GET', 'POST'])
def registros():
    """Displays records with filtering options."""
    # Parameters to maintain filter state on redirect
    data_filtro = request.args.get('data', '')
    nome_filtro = request.args.get('nome', '')
    matricula_filtro = request.args.get('matricula', '')
    rota_filtro = request.args.get('rota', '')
    tipo_entrega_filtro = request.args.get('tipo_entrega', '')

    # The POST part here handles the 'em_separacao' checkbox from the registrations list view.
    # This logic seems specific to managing the list, not login/registration duplicates.
    if request.method == 'POST':
        if 'registro_id' in request.form and 'em_separacao' in request.form:
            registro_id = request.form['registro_id']
            em_separacao = 1 if request.form.get('em_separacao') == 'on' else 0
            with get_db_connection() as conn:
                # Ensure we only update if the record is not finalized or cancelled
                conn.execute('''
                    UPDATE registros
                    SET em_separacao = ?
                    WHERE id = ? AND finalizada = 0 AND cancelado = 0
                ''', (em_separacao, registro_id))
                conn.commit()
        # Redirect while keeping filters
        return redirect(url_for('registros', data=data_filtro, nome=nome_filtro,
                                 matricula=matricula_filtro, rota=rota_filtro,
                                 tipo_entrega=tipo_entrega_filtro) + f'#registro-{registro_id}')
    # Handle other POST actions if any, or ignore POST requests not for the checkbox

    query = 'SELECT * FROM registros WHERE 1=1'
    parametros = []

    if data_filtro:
        try:
            # Validate the date format before using in query
            datetime.strptime(data_filtro, '%Y-%m-%d')
            # SQLite stores DATETIME as TEXT, so we match the date part
            query += ' AND substr(data_hora_login, 1, 10) = ?'
            parametros.append(data_filtro)
        except ValueError:
            pass  # Ignore invalid date format

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

    # Order by active (not finalizada/cancelado) first, then by login time
    query += ' ORDER BY CASE WHEN finalizada = 0 AND cancelado = 0 THEN 0 ELSE 1 END, data_hora_login DESC'

    with get_db_connection() as conn:
        registros_data = conn.execute(query, parametros).fetchall()

    return render_template('registros.html', registros=registros_data,
                                     data_filtro=data_filtro, nome_filtro=nome_filtro,
                                     matricula_filtro=matricula_filtro, rota_filtro=rota_filtro,
                                     tipo_entrega_filtro=tipo_entrega_filtro)


@app.route('/historico')
def historico():
    """Displays historical actions from the historico table."""
    with get_db_connection() as conn:
        historico_data = conn.execute('SELECT h.*, r.nome, r.matricula FROM historico h JOIN registros r ON h.registro_id = r.id ORDER BY h.data_hora DESC').fetchall()
    return render_template('historico.html', historico=historico_data)




@app.route('/associacao')
def associacao():
    """
    Displays records for association, primarily focusing on active/pending sessions.
    Can display a single record if an ID is provided (e.g., after login/registration).
    """
    id_registro = request.args.get('id', type=int)  # Specific ID from redirect after login/cadastro
    pagina = int(request.args.get('pagina', 1))  # For pagination when viewing lists
    rota_filtro = request.args.get('rota')  # Filters for the list view
    tipo_entrega_filtro = request.args.get('tipo_entrega')  # Filters for the list view
    registros_por_pagina = 10  # Adjusted pagination size for list view - was 1

    with get_db_connection() as conn:
        if id_registro:
            # If an ID is provided, display only that specific active record
            # Check if it's still active (not finalizada or cancelled)
            registro = conn.execute('SELECT * FROM registros WHERE id = ? AND finalizada = 0 AND cancelado = 0', (id_registro,)).fetchone()
            registros_data = [registro] if registro else []
            total_paginas = 1 if registro else 0  # Only one page if viewing a single record
            # Pass filters back even for single view, in case user removes ID from URL
            return render_template('associacao.html', registros=registros_data, pagina=1, total_paginas=total_paginas,
                                   rota=rota_filtro, tipo_entrega=tipo_entrega_filtro, filtro_id=id_registro)
        else:
            # If no specific ID, display paginated list of active records with filters
            base_query = 'SELECT * FROM registros WHERE finalizada = 0 AND cancelado = 0'  # Only active records
            count_query = 'SELECT COUNT(*) FROM registros WHERE finalizada = 0 AND cancelado = 0'
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

            # Order by 'em_separacao' status (0 then 1/2/3), then login time
            base_query += ' ORDER BY em_separacao ASC, data_hora_login DESC LIMIT ? OFFSET ?'
            params.extend([registros_por_pagina, (pagina - 1) * registros_por_pagina])  # Corrected offset calculation

            registros_data = conn.execute(base_query, params).fetchall()

            return render_template('associacao.html', registros=registros_data, pagina=pagina,
                                   total_paginas=total_paginas, rota=rota_filtro,
                                   tipo_entrega=tipo_entrega_filtro, filtro_id=None)


@app.route('/associar/<int:id>', methods=['POST'])
def associar_id(id):
    """Associa um registro com gaiola/estacao e define o status como 'em separacao'."""
    gaiola = request.form.get('gaiola', '').title()
    estacao = request.form.get('estacao', '').title()
    em_separacao = 1  # Ao associar, marca como "em separação"
    data_hora = get_data_hora_brasilia()

    with get_db_connection() as conn:
        # Apenas atualiza se o registro não estiver finalizado ou cancelado
        conn.execute('''
            UPDATE registros
            SET gaiola = ?, estacao = ?, em_separacao = ?
            WHERE id = ? AND finalizada = 0 AND cancelado = 0
        ''', (gaiola, estacao, em_separacao, id))

        # Registra a ação no histórico
        conn.execute('''
            INSERT INTO historico (registro_id, acao, gaiola, estacao, data_hora)
            VALUES (?, 'associated', ?, ?, ?)
        ''', (id, gaiola, estacao, data_hora))
        conn.commit()

        # --- REMOVIDO: Emitir evento WebSocket de status atualizado ---
        # registro = conn.execute('SELECT matricula FROM registros WHERE id = ?', (id,)).fetchone()
        # if registro:
        #     emit_status_update(id, registro['matricula'], gaiola=gaiola, estacao=estacao)
        # ---------------------------------------------------

    # Redireciona de volta para a página de origem, preservando filtros e rolando para o registro
    return redirect(request.referrer + f'#registro-{id}')


@app.route('/desassociar/<int:id>', methods=['POST'])
def desassociar_id(id):
    """Remove a associação de gaiola/estacao e define o status de volta para não 'em separacao'."""
    data_hora = get_data_hora_brasilia()

    with get_db_connection() as conn:
        # Apenas atualiza se o registro não estiver finalizado ou cancelado
        conn.execute('''
            UPDATE registros
            SET gaiola = NULL, estacao = NULL, em_separacao = 0
            WHERE id = ? AND finalizada = 0 AND cancelado = 0
        ''', (id,))
        # Registra a ação no histórico
        conn.execute('''
            INSERT INTO historico (registro_id, acao, data_hora)
            VALUES (?, 'disassociated', ?)
        ''', (id, data_hora))
        conn.commit()
    # Redireciona de volta para a página de origem, preservando filtros e rolando para o registro
    return redirect(request.referrer + f'#registro-{id}')

@app.route('/finalizar_carregamento_status_separacao/<int:id>', methods=['POST'])
def finalizar_carregamento_id_status_separacao(id):
    """Define o status 'em_separacao' para indicar que o carregamento foi finalizado (status 2)."""
    data_hora = get_data_hora_brasilia()
    with get_db_connection() as conn:
        # Apenas atualiza se o registro estiver 'em_separacao' (status 1) e não finalizado/cancelado
        conn.execute('''
            UPDATE registros
            SET em_separacao = 2
            WHERE id = ? AND em_separacao = 1 AND finalizada = 0 AND cancelado = 0
        ''', (id,))
        # Registra a ação no histórico
        conn.execute('''
            INSERT INTO historico (registro_id, acao, data_hora)
            VALUES (?, 'loading_finished_separation_status', ?)
        ''', (id, data_hora))
        conn.commit()
    # Redireciona de volta para a página de origem, preservando filtros e rolando para o registro
    return redirect(request.referrer + f'#registro-{id}')


@app.route('/marcar_como_finalizado/<int:id>', methods=['POST'])
def marcar_como_finalizado_id(id):
    """Marca um registro/sessão como finalizada (concluída)."""
    data_hora = get_data_hora_brasilia()
    with get_db_connection() as conn:
        # Apenas finaliza se o registro não estiver finalizado ou cancelado
        conn.execute('''
            UPDATE registros
            SET finalizada = 1, em_separacao = 3, hora_finalizacao = ?
            WHERE id = ? AND finalizada = 0 AND cancelado = 0
        ''', (data_hora, id))

        # Registra a ação no histórico
        conn.execute('''
            INSERT INTO historico (registro_id, acao, data_hora)
            VALUES (?, 'record_finalized', ?)
        ''', (id, data_hora))
        conn.commit()

        

        # Opcional: Verifica a atualização (para depuração)
        registro_atualizado = conn.execute('SELECT finalizada FROM registros WHERE id = ?', (id,)).fetchone()
        if registro_atualizado and registro_atualizado['finalizada'] == 1:
            print(f"Record {id} successfully marked as finalized in the database.")
        else:
            print(f"Failed to mark record {id} as finalized in the database or it was already finalized/cancelled.")

    # Redireciona de volta para a página de origem, preservando filtros.
    # O registro pode desaparecer da lista ativa, então não precisa rola
    return redirect(request.referrer)

@app.route('/cancelar_registro/<int:id>', methods=['POST'])
def cancelar_registro_id(id):
    """Marca um registro/sessão como cancelada e finalizada."""
    data_hora = get_data_hora_brasilia()
    with get_db_connection() as conn:
        # Apenas cancela se o registro não estiver finalizado ou cancelado
        conn.execute('''
            UPDATE registros
            SET cancelado = 1, finalizada = 1, hora_finalizacao = ?
            WHERE id = ? AND finalizada = 0 AND cancelado = 0
        ''', (data_hora, id))
        # Registra a ação no histórico
        conn.execute('''
            INSERT INTO historico (registro_id, acao, data_hora)
            VALUES (?, 'cancelled', ?)
        ''', (id, data_hora))
        conn.commit()

       

    # Redireciona de volta para a página de origem, preservando filtros.
    # O registro pode desaparecer da lista ativa, então não precisa rola
    return redirect(request.referrer)


@app.route('/voltar_para_associacao/<int:id>', methods=['POST'])
def voltar_para_associacao_id(id):
    """Redefine o status de um registro para torná-lo ativo novamente para associação."""
    data_hora = get_data_hora_brasilia()
    with get_db_connection() as conn:
        # Apenas redefine se o registro estiver finalizado ou cancelado
        conn.execute('''
            UPDATE registros
            SET gaiola = NULL, estacao = NULL, em_separacao = 0, finalizada = 0, cancelado = 0, hora_finalizacao = NULL
            WHERE id = ? AND (finalizada = 1 OR cancelado = 1)
        ''', (id,))
        # Registra a ação no histórico
        conn.execute('''
            INSERT INTO historico (registro_id, acao, data_hora)
            VALUES (?, 'returned_to_association', ?)
        ''', (id, data_hora))
        conn.commit()
    # Redireciona de volta para a página de origem, preservando filtros e rolando para o registro
    return redirect(request.referrer + f'#registro-{id}')

# --- Rota para o painel final ---
@app.route('/painel_final')
def painel_final():
    # O propósito desta rota não está claro no contexto das mudanças de login/cadastro.
    # Considere se esta página ainda é necessária ou onde ela se encaixa na jornada do usuário.
    return render_template('painel_final.html')


@app.route('/registros_finalizados', methods=['GET'])
def registros_finalizados():
    """Retorna todos os registros finalizados para exibição em HTML."""
    with get_db_connection() as conn:
        registros = conn.execute('''
            SELECT * FROM registros WHERE finalizada = 1 AND cancelado = 0
        ''').fetchall()

    registros_list = []
    for registro in registros:
        registros_list.append({
            'nome': registro['nome'],
            'matricula': registro['matricula'],
            'cidade_entrega': registro['cidade_entrega'],
            'rota': registro['rota'],
            'tipo_entrega': registro['tipo_entrega'],
            'data_hora_login': registro['data_hora_login'],  # Adicionado
            'hora_finalizacao': registro['hora_finalizacao'],
            'gaiola_rua': registro['gaiola'], # Mantido gaiola_rua conforme seu código
            'estacao': registro['estacao'],
            'rua': registro['rua'], # Adicionado a coluna rua na lista
            'finalizado': 'Sim' if registro['finalizada'] else 'Não'
        })
    return render_template('registros_finalizados.html', registros=registros_list)

# Rota para exibir a página de registros de No-Show
@app.route('/registro_no_show', methods=['GET'])
def registro_no_show():
    """Exibe os registros da tabela no_show com opções de filtro por status."""
    data_filtro = request.args.get('data', '')
    nome_filtro = request.args.get('nome', '')
    matricula_filtro = request.args.get('matricula', '')
    rota_filtro = request.args.get('rota', '')
    # Removido tipo_entrega_filtro = request.args.get('tipo_entrega', '') # Removido o filtro de tipo_entrega
    status_filtro = request.args.get('status', '') # Captura o novo filtro de status

    query = 'SELECT * FROM no_show WHERE 1=1'
    parametros = []

    if data_filtro:
        try:
            datetime.strptime(data_filtro, '%Y-%m-%d')
            query += ' AND substr(data_hora_login, 1, 10) = ?'
            parametros.append(data_filtro)
        except ValueError:
            pass

    if nome_filtro:
        query += ' AND nome LIKE ?'
        parametros.append(f'%{nome_filtro.title()}%')
    if matricula_filtro:
        query += ' AND matricula LIKE ?'
        parametros.append(f'%{matricula_filtro}%')
    if rota_filtro:
        query += ' AND rota LIKE ?'
        parametros.append(f'%{rota_filtro.title()}%')

    # Adiciona a lógica de filtro por status
    if status_filtro:
        if status_filtro == 'finalizado':
            query += ' AND finalizada = 1 AND cancelado = 0'
        elif status_filtro == 'cancelado':
            query += ' AND cancelado = 1'
        elif status_filtro == 'transferido':
             query += ' AND transferred_to_registro_id IS NOT NULL' # Filtra por registros transferidos
        elif status_filtro == 'separacao':
            query += ' AND em_separacao = 1 AND finalizada = 0 AND cancelado = 0 AND transferred_to_registro_id IS NULL' # Em separação e não finalizado/cancelado/transferido
        elif status_filtro == 'aguardando_entregador':
            query += ' AND em_separacao = 2 AND finalizada = 0 AND cancelado = 0 AND transferred_to_registro_id IS NULL' # Aguardando entregador e não finalizado/cancelado/transferido
        elif status_filtro == 'aguardando':
             # Aguardando associação: não tem gaiola/estacao associada e não está em separacao, finalizado, cancelado ou transferido
             query += ' AND gaiola IS NULL AND estacao IS NULL AND em_separacao = 0 AND finalizada = 0 AND cancelado = 0 AND transferred_to_registro_id IS NULL'
        # Se o status_filtro for 'todos' (string vazia), nenhuma condição de status é adicionada, mostrando todos os registros

    # Mantém a ordenação por data/hora mais recente
    query += ' ORDER BY data_hora_login DESC'


    with get_db_connection() as conn:
        registros_no_show_data = conn.execute(query, parametros).fetchall()

    return render_template('registro_no_show.html', registros_no_show=registros_no_show_data,
                           data_filtro=data_filtro, nome_filtro=nome_filtro,
                           matricula_filtro=matricula_filtro, rota_filtro=rota_filtro,
                           status_filtro=status_filtro) # Passa o status_filtro para o template

# --- Rotas para ações na tabela no_show ---

@app.route('/registro_no_show/associar/<int:id>', methods=['POST'])
def associar_no_show_id(id):
    """Associa um registro de no-show com gaiola/estacao e define o status como 'em separacao'."""
    # Captura os valores dos campos do formulário
    rota_valor = request.form.get('rota', '').title()
    estacao = request.form.get('estacao', '').title()
    rua = request.form.get('rua', '').title()
    em_separacao = 1  # Quando associando, marca como "em separação"
    data_hora = get_data_hora_brasilia()

    with get_db_connection() as conn:
        # Apenas atualiza se o registro não estiver finalizado ou cancelado OU TRANSFERIDO
        # Atualiza as colunas 'rota', 'gaiola', 'estacao' e 'rua'
        conn.execute('''
            UPDATE no_show
            SET rota = ?, gaiola = ?, estacao = ?, em_separacao = ?, rua = ?
            WHERE id = ? AND finalizada = 0 AND cancelado = 0 AND transferred_to_registro_id IS NULL
        ''', (rota_valor, rota_valor, estacao, em_separacao, rua, id)) # Usa o valor da rota para rota e gaiola

        # Registra a ação no histórico de no-show
        conn.execute('''
            INSERT INTO historico_no_show (registro_no_show_id, acao, gaiola, estacao, data_hora)
            VALUES (?, 'associated', ?, ?, ?)
        ''', (id, rota_valor, estacao, data_hora)) # Loga o valor da rota como gaiola no histórico
        conn.commit()

    # Redireciona de volta para a página de origem, preservando filtros e rolando para o registro
    return redirect(request.referrer + f'#no-show-registro-{id}')

@app.route('/registro_no_show/desassociar/<int:id>', methods=['POST'])
def desassociar_no_show_id(id):
    """Remove a associação de gaiola/estacao de um registro de no-show e define o status de volta para não 'em separacao'."""
    data_hora = get_data_hora_brasilia()

    with get_db_connection() as conn:
        # Apenas atualiza se o registro não estiver finalizado ou cancelado OU TRANSFERIDO
        # Limpa os campos rota, gaiola, estacao e rua
        conn.execute('''
            UPDATE no_show
            SET rota = NULL, gaiola = NULL, estacao = NULL, em_separacao = 0, rua = NULL
            WHERE id = ? AND finalizada = 0 AND cancelado = 0 AND transferred_to_registro_id IS NULL
        ''', (id,))

        # Registra a ação no histórico de no-show
        conn.execute('''
            INSERT INTO historico_no_show (registro_no_show_id, acao, data_hora)
            VALUES (?, 'disassociated', ?)
        ''', (id, data_hora))
        conn.commit()

    # Redireciona de volta para a página de origem, preservando filtros e rolando para o registro
    return redirect(request.referrer + f'#no-show-registro-{id}')

@app.route('/registro_no_show/finalizar_carregamento_status_separacao/<int:id>', methods=['POST'])
def finalizar_carregamento_no_show_id_status_separacao(id):
    """Define o status 'em_separacao' de um registro de no-show para indicar que o carregamento foi finalizado (status 2)."""
    data_hora = get_data_hora_brasilia()
    with get_db_connection() as conn:
        # Apenas atualiza se o registro estiver 'em_separacao' (status 1) e não finalizado/cancelado OU TRANSFERIDO
        conn.execute('''
            UPDATE no_show
            SET em_separacao = 2
            WHERE id = ? AND em_separacao = 1 AND finalizada = 0 AND cancelado = 0 AND transferred_to_registro_id IS NULL
        ''', (id,))

        # Registra a ação no histórico de no-show
        conn.execute('''
            INSERT INTO historico_no_show (registro_no_show_id, acao, data_hora)
            VALUES (?, 'loading_finished_separation_status', ?)
        ''', (id, data_hora))
        conn.commit()

    # Redireciona de volta para a página de origem, preservando filtros e rolando para o registro
    return redirect(request.referrer + f'#no-show-registro-{id}')


@app.route('/registro_no_show/marcar_como_finalizado/<int:id>', methods=['POST'])
def marcar_como_finalizado_no_show_id(id):
    """
    Marca um registro/sessão de no-show como finalizada (concluída).
    Verifica o estado atual do registro antes de finalizar.
    Permite finalização de qualquer estado ativo (não finalizado, cancelado ou transferido).
    """
    data_hora = get_data_hora_brasilia()
    with get_db_connection() as conn:
        # Buscar o estado atual do registro
        registro = conn.execute('SELECT finalizada, cancelado, transferred_to_registro_id FROM no_show WHERE id = ?', (id,)).fetchone()

        if not registro:
            flash('Registro No-Show não encontrado.', 'error')
            print(f"Finalização falhou para ID {id}: Registro não encontrado.")
            return redirect(url_for('registro_no_show'))

        # Verificar se o registro já está em um estado final ou transferido
        if registro['finalizada'] == 1:
            flash('Este registro No-Show já está finalizado.', 'warning')
            print(f"Finalização falhou para ID {id}: Já finalizado.")
        elif registro['cancelado'] == 1:
            flash('Este registro No-Show foi cancelado.', 'warning')
            print(f"Finalização falhou para ID {id}: Cancelado.")
        elif registro['transferred_to_registro_id'] is not None:
             flash('Este registro No-Show foi transferido para um registro de carregamento.', 'warning')
             print(f"Finalização falhou para ID {id}: Transferido.")
        else:
            # Se não estiver em um estado final ou transferido, procede com a finalização
            try:
                rows_updated = conn.execute('''
                    UPDATE no_show
                    SET finalizada = 1, em_separacao = 3, hora_finalizacao = ?
                    WHERE id = ? AND finalizada = 0 AND cancelado = 0 AND transferred_to_registro_id IS NULL
                ''', (data_hora, id)).rowcount # Verifica quantas linhas foram atualizadas

                if rows_updated > 0:
                    # Registra a ação no histórico de no-show
                    conn.execute('''
                        INSERT INTO historico_no_show (registro_no_show_id, acao, data_hora)
                        VALUES (?, 'record_finalized', ?)
                    ''', (id, data_hora))
                    conn.commit()
                    flash('Registro No-Show finalizado com sucesso.', 'success')
                    print(f"Registro No-Show {id} finalizado com sucesso. Linhas atualizadas: {rows_updated}")
                else:
                     # Isso pode acontecer se o estado do registro mudou entre a busca e o update
                     flash('Falha ao finalizar o registro No-Show. O estado do registro pode ter mudado.', 'warning')
                     print(f"Falha ao finalizar o registro No-Show {id}. Nenhuma linha atualizada. Estado atual: Finalizado={registro['finalizada']}, Cancelado={registro['cancelado']}, Transferido={registro['transferred_to_registro_id']}")

            except Exception as e:
                conn.rollback() # Desfaz a transação em caso de erro
                flash(f'Ocorreu um erro ao finalizar o registro: {e}', 'error')
                print(f"Erro ao finalizar o registro No-Show {id}: {e}")


    # Redireciona de volta para a página de origem, preservando filtros.
    # O registro pode desaparecer da lista ativa, então não precisa rola
    return redirect(request.referrer)

@app.route('/registro_no_show/cancelar_registro/<int:id>', methods=['POST'])
def cancelar_no_show_registro_id(id):
    """Marca um registro/sessão de no-show como cancelada e finalizada."""
    data_hora = get_data_hora_brasilia()
    with get_db_connection() as conn:
        # Apenas cancela se o registro não estiver finalizado ou cancelado OU TRANSFERIDO
        conn.execute('''
            UPDATE no_show
            SET cancelado = 1, finalizada = 1, hora_finalizacao = ?
            WHERE id = ? AND finalizada = 0 AND cancelado = 0 AND transferred_to_registro_id IS NULL
        ''', (data_hora, id))

        # Registra a ação no histórico de no-show
        conn.execute('''
            INSERT INTO historico_no_show (registro_no_show_id, acao, data_hora)
            VALUES (?, 'cancelled', ?)
        ''', (id, data_hora))
        conn.commit()

    # Redireciona de volta para a página de origem, preservando filtros.
    # O registro pode desaparecer da lista ativa, então não precisa rola
    return redirect(request.referrer)

@app.route('/registro_no_show/voltar_para_associacao/<int:id>', methods=['POST'])
def voltar_para_associacao_no_show_id(id):
    """Redefine o status de um registro de no-show para torná-lo ativo novamente para associação."""
    data_hora = get_data_hora_brasilia()
    with get_db_connection() as conn:
        # Apenas redefine se o registro estiver finalizado ou cancelado OU TRANSFERIDO
        # Inclui a limpeza das colunas rota, gaiola, estacao e rua
        conn.execute('''
            UPDATE no_show
            SET rota = NULL, gaiola = NULL, estacao = NULL, em_separacao = 0, finalizada = 0, cancelado = 0, hora_finalizacao = NULL, transferred_to_registro_id = NULL, original_registro_gaiola = NULL, original_registro_estacao = NULL, rua = NULL
            WHERE id = ? AND (finalizada = 1 OR cancelado = 1 OR em_separacao = 4) # Adicionado em_separacao = 4
        ''', (id,))

        # Registra a ação no histórico de no-show
        conn.execute('''
            INSERT INTO historico_no_show (registro_no_show_id, acao, data_hora)
            VALUES (?, 'returned_to_association', ?)
        ''', (id, data_hora))
        conn.commit()

    # Redireciona de volta para a página de origem, preservando filtros e rolando para o registro
    return redirect(request.referrer + f'#no-show-registro-{id}')

# --- Nova rota para transferir dados de no_show para registros ---
@app.route('/transferir_no_show_para_registro/<int:no_show_id>', methods=['POST'])
def transferir_no_show_para_registro(no_show_id):
    """
    Transfere dados de um registro no_show para um registro ativo correspondente em registros.
    Salva os dados originais do registro de destino na tabela no_show.
    O nome do registro de destino (registros) prevalece e é copiado para o registro no_show.
    Marca o registro no_show como 'Transferido' e o registro em registros como 'Finalizado'.
    """
    data_hora_transferencia = get_data_hora_brasilia()

    with get_db_connection() as conn:
        # 1. Buscar o registro no_show
        # Adicionado verificação para garantir que não foi transferido ainda
        registro_no_show = conn.execute('SELECT * FROM no_show WHERE id = ? AND finalizada = 0 AND cancelado = 0 AND transferred_to_registro_id IS NULL', (no_show_id,)).fetchone()

        if not registro_no_show:
            flash('Registro No-Show não encontrado, já finalizado, cancelado ou transferido.', 'error')
            return redirect(url_for('registro_no_show'))

        # 2. Buscar registros ativos correspondentes na tabela registros
        # Buscamos por registros que não estão finalizados ou cancelados, com a mesma rota e tipo de entrega
        registros_correspondentes = conn.execute('''
            SELECT * FROM registros
            WHERE rota = ? AND tipo_entrega = ? AND finalizada = 0 AND cancelado = 0
            ORDER BY data_hora_login ASC -- Prioriza o mais antigo
        ''', (registro_no_show['rota'], registro_no_show['tipo_entrega'])).fetchall()

        if not registros_correspondentes:
            flash(f'Nenhum registro ativo correspondente encontrado na fila de carregamento para a Rota "{registro_no_show["rota"]}" e Tipo de Entrega "{registro_no_show["tipo_entrega"]}".', 'warning')
            return redirect(url_for('registro_no_show') + f'#no-show-registro-{no_show_id}')

        # 3. Lidar com múltiplos registros correspondentes (opcional, aqui pegamos o primeiro)
        if len(registros_correspondentes) > 1:
             registro_destino = registros_correspondentes[0]
             flash(f'Múltiplos registros ativos correspondentes encontrados. Transferindo para o registro mais antigo (ID: {registro_destino["id"]}).', 'info')
        else:
             registro_destino = registros_correspondentes[0]

        # --- Capture original data from registro_destino BEFORE updating it ---
        original_registro_gaiola = registro_destino['gaiola']
        original_registro_estacao = registro_destino['estacao']
        original_registro_nome = registro_destino['nome'] # Captura o nome original do registro de destino
        original_registro_matricula = registro_destino['matricula'] # Captura a matricula original do registro de destino
        original_registro_cidade_entrega = registro_destino['cidade_entrega'] # Captura a cidade original do registro de destino
        original_registro_cpf = registro_destino['cpf'] # Captura o cpf original do registro de destino
        original_registro_tipo_veiculo = registro_destino['tipo_veiculo'] # Captura o tipo_veiculo original do registro de destino
        original_registro_login_id = registro_destino['login_id'] # Captura o login_id original do registro de destino
        original_registro_rua = registro_destino['rua'] # Captura a rua original do registro de destino
        # Capture other fields if needed

        # 4. Transferir dados (atualizar o registro em 'registros')
        # Copia os campos ROTA, GAIOLA, ESTACAO e RUA do no_show para o registro de destino.
        # Mantém os campos NOME, MATRICULA, CIDADE_ENTREGA, CPF, TIPO_VEICULO e LOGIN_ID originais do registro de destino.
        # Marca o registro de destino como FINALIZADO.
        try:
            rows_updated_registros = conn.execute('''
                UPDATE registros
                SET rota = ?, gaiola = ?, estacao = ?, rua = ?, -- Campos a serem atualizados com dados do no_show
                    em_separacao = 3, finalizada = 1, hora_finalizacao = ? -- Campos de status e hora de finalização
                WHERE id = ? AND finalizada = 0 AND cancelado = 0 -- Garante que só atualiza registros ativos
            ''', (registro_no_show['rota'], registro_no_show['gaiola'],
                  registro_no_show['estacao'], registro_no_show['rua'], # Valores do no_show
                  data_hora_transferencia, registro_destino['id'])).rowcount

            if rows_updated_registros == 0:
                 # Isso pode acontecer se o registro de destino foi finalizado/cancelado por outra operação
                 flash(f'Falha ao atualizar o registro de carregamento (ID: {registro_destino["id"]}). Ele pode ter sido finalizado ou cancelado por outra ação.', 'warning')
                 print(f"Falha ao atualizar registro de carregamento {registro_destino['id']}. Nenhuma linha atualizada.")
                 conn.rollback() # Desfaz as operações se a atualização do registro principal falhar
                 return redirect(url_for('registro_no_show'))


            # 5. Marcar o registro no_show como TRANSFERIDO, vincular ao registro de destino,
            #    e salvar os dados originais do registro de destino (incluindo o nome original).
            # Mantém finalizada = 0 e cancelado = 0 para que apareça na lista de No-Show,
            # mas usa em_separacao = 4 para indicar "Transferido".
            # Inclui a coluna 'rua' na atualização
            rows_updated_no_show = conn.execute('''
                UPDATE no_show
                SET finalizada = 0, cancelado = 0, em_separacao = 4, hora_finalizacao = ?, -- em_separacao = 4 para 'Transferido'
                    transferred_to_registro_id = ?,
                    original_registro_gaiola = ?, original_registro_estacao = ?,
                    nome = ?, matricula = ?, cidade_entrega = ?, cpf = ?, tipo_veiculo = ?, login_id = ?, -- Salva os dados originais do registro de destino
                    rua = ? -- Mantém a rua original do no_show
                WHERE id = ? AND finalizada = 0 AND cancelado = 0 AND transferred_to_registro_id IS NULL -- Garante que só atualiza No-Show ativo e não transferido
            ''', (data_hora_transferencia, registro_destino['id'],
                  original_registro_gaiola, original_registro_estacao,
                  original_registro_nome, original_registro_matricula, original_registro_cidade_entrega, original_registro_cpf, original_registro_tipo_veiculo, original_registro_login_id, # Use the captured original data
                  registro_no_show['rua'], # Usa a rua original do no_show
                  no_show_id)).rowcount

            if rows_updated_no_show == 0:
                 # Isso não deveria acontecer se a primeira verificação passou, mas é uma segurança
                 flash(f'Falha ao marcar o registro No-Show (ID: {no_show_id}) como transferido. O estado do registro pode ter mudado.', 'warning')
                 print(f"Falha ao marcar registro No-Show {no_show_id} como transferido. Nenhuma linha atualizada.")
                 # Decida se quer dar rollback aqui também ou manter a atualização do registro principal.
                 # Mantendo o commit para a atualização do registro principal, mas avisando sobre o No-Show.
                 conn.commit() # Commit da primeira parte
                 return redirect(url_for('registro_no_show'))


            # 6. Registrar a ação no histórico de no_show
            conn.execute('''
                INSERT INTO historico_no_show (registro_no_show_id, acao, data_hora)
                VALUES (?, 'transferred_to_registro', ?)
            ''', (no_show_id, data_hora_transferencia))

            # 7. Registrar a ação no histórico de registros (opcional, mas recomendado)
            conn.execute('''
                 INSERT INTO historico (registro_id, acao, data_hora)
                 VALUES (?, 'data_transferred_from_no_show', ?)
               ''', (registro_destino['id'], data_hora_transferencia))


            conn.commit()

            flash(f'Dados do registro No-Show (ID: {no_show_id}) transferidos com sucesso para o registro de carregamento (ID: {registro_destino["id"]}). O registro de carregamento foi FINALIZADO. O registro No-Show foi marcado como TRANSFERIDO.', 'success')
            print(f"Transferência concluída: No-Show {no_show_id} -> Registro {registro_destino['id']}. Registros atualizados: {rows_updated_registros}, No-Show atualizados: {rows_updated_no_show}")

        except Exception as e:
            conn.rollback() # Desfaz a transação em caso de erro
            flash(f'Ocorreu um erro durante a transferência do registro: {e}', 'error')
            print(f"Erro durante a transferência do registro No-Show {no_show_id}: {e}")


    # Redirecionar de volta para a página de registros no_show
    return redirect(url_for('registro_no_show'))

# --- Nova rota para exibir o formulário de criação de registro No Show ---
@app.route('/associacao_no_show', methods=['GET'])
def associacao_no_show():
    """Exibe o formulário para criar um novo registro No Show."""
    return render_template('associacao_no_show.html')

# --- Nova rota para lidar com a submissão do formulário de criação de registro No Show ---
@app.route('/criar_registro_no_show', methods=['POST'])
def criar_registro_no_show():
    """
    Lida com a submissão do formulário e insere o registro na tabela no_show.
    Retorna uma resposta JSON.
    """
    nome = request.form.get('nome', '').title()
    matricula = request.form.get('matricula', '').title()
    cidade_entrega = request.form.get('cidade_entrega', '').title()
    tipo_entrega = request.form.get('tipo_entrega', '').title()
    # Captura o valor do campo 'rota'
    rota_valor = request.form.get('rota', '').title()
    rua = request.form.get('rua', '').title()
    estacao = request.form.get('estacao', '').title()
    data_hora_login = get_data_hora_brasilia()

    # Buscar CPF e tipo_veiculo da tabela login usando a matrícula
    cpf = None
    tipo_veiculo = None
    login_id = None
    with get_db_connection() as conn:
        user_data = conn.execute('SELECT id, cpf, tipo_veiculo FROM login WHERE matricula = ?', (matricula,)).fetchone()
        if user_data:
            login_id = user_data['id']
            cpf = user_data['cpf']
            tipo_veiculo = user_data['tipo_veiculo']
        else:
            # Se a matrícula não existir na tabela login, retorna JSON de erro
            print(f"Erro ao criar registro No Show: Matrícula {matricula} não encontrada.")
            return jsonify({'success': False, 'message': 'Matrícula não encontrada na base de usuários.'}), 400 # Retorna 400 Bad Request

    try:
        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO no_show (nome, matricula, rota, tipo_entrega, cidade_entrega,
                                     data_hora_login, cpf, tipo_veiculo, em_separacao, finalizada, login_id, rua, estacao, gaiola)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?, ?)
            ''', (nome, matricula, rota_valor, tipo_entrega, cidade_entrega, # Usa rota_valor para rota
                  data_hora_login, cpf, tipo_veiculo, login_id, rua, estacao, rota_valor)) # Usa rota_valor para gaiola
            conn.commit()
            print(f"Novo registro No Show criado: Nome={nome}, Matrícula={matricula}, Rota={rota_valor}, Rua={rua}, Estacao={estacao}, Gaiola={rota_valor}")
            # Retorna JSON de sucesso
            return jsonify({'success': True, 'message': 'Registro No Show criado com sucesso!'})

    except Exception as e:
        conn.rollback() # Desfaz a transação em caso de erro
        print(f"Erro ao criar registro No Show: {e}")
        # Retorna JSON de erro
        return jsonify({'success': False, 'message': f'Ocorreu um erro ao criar o registro No Show: {e}'}), 500 # Retorna 500 Internal Server Error


# --- Rota para exibir o menu principal ---
@app.route('/menu_principal')
def menu_principal():
    """Renderiza a página do menu principal."""
    return render_template('menu_principal.html')


if __name__ == '__main__':
    # Inicializa o banco de dados ao iniciar o aplicativo
    init_db()
    app.run(debug=True)
