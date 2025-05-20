from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import sqlite3
from datetime import datetime
import pytz
# Importe as bibliotecas necessárias
from flask import Flask, jsonify, render_template, request # Certifique-se que jsonify, render_template, request estão importados
import requests # Para fazer requisições HTTP (útil se não usar feedparser ou para outras APIs)
import feedparser # Para parsear feeds RSS
from math import ceil # Importe ceil para arredondar para cima - CORRIGIDO: AGORA EXPLICITAMENTE INCLUÍDO AQUI
from datetime import datetime # Útil se precisar de timestamps, embora não essencial para este ticker
from io import BytesIO # Precisamos de BytesIO para dados binários do Excel


app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua_chave_secreta_aqui' # Adicione uma chave secreta para flash messages

# --- Conexão à Base de Dados ---
def get_db_connection():
    """
    Estabelece e retorna uma conexão com o banco de dados SQLite.
    Configura row_factory para retornar linhas como dicionários.
    """
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# --- Obter data e hora no fuso horário do Brasil no formato ISO ---
def get_data_hora_brasilia():
    """
    Obtém a data e hora atuais no fuso horário de São Paulo (Brasil)
    e formata como string-MM-DD - HH:MM:SS.
    """
    tz_brasilia = pytz.timezone('America/Sao_Paulo')
    return datetime.now(tz_brasilia).strftime('%Y-%m-%d - %H:%M:%S')

# --- Filtro para formatar data/hora para o padrão desejado (dd-mm-yyyy) ---
@app.template_filter('formata_data_hora')
def formata_data_hora(valor):
    """
    Filtro de template para formatar strings de data/hora (ISO ou-MM-DD - HH:MM:SS)
    para o formato DD-MM-YYYY HH:MM.
    """
    if not valor:
        return ''
    try:
        if isinstance(valor, datetime):
            dt = valor
        else:
            # Tenta analisar o formato-MM-DD - HH:MM:SS
            dt = datetime.strptime(valor, '%Y-%m-%d - %H:%M:%S')
        return dt.strftime('%d-%m-%Y %H:%M')
    except ValueError:
        try:
            # Tenta analisar o formato-MM-DD HH:MM:SS (sem o ' - ')
            dt = datetime.strptime(valor, '%Y-%m-%d %H:%M:%S')
            return dt.strftime('%d-%m-%Y %H:%M')
        except ValueError:
            # Retorna o valor original se nenhum formato conhecido for encontrado
            return valor

# --- Validação de CPF (Cadastro de Pessoa Física brasileiro) ---
def validar_cpf(cpf):
    """
    Valida um número de CPF brasileiro.
    Retorna True se o CPF for válido, False caso contrário.
    """
    cpf = ''.join(filter(str.isdigit, cpf))
    # Verifica se o CPF tem 11 dígitos e não é uma sequência de dígitos iguais
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    # Calcula os dígitos verificadores
    def calcular_digito(digs, peso):
        soma = sum(int(d) * p for d, p in zip(digs, range(peso, 1, -1)))
        resto = soma % 11
        return '0' if resto < 2 else str(11 - resto)
    digito1 = calcular_digito(cpf[:9], 10)
    digito2 = calcular_digito(cpf[:10], 11)
    # Verifica se os dígitos calculados correspondem aos dígitos finais do CPF
    return cpf[-2:] == digito1 + digito2

# --- Inicializar Base de Dados ---
def init_db():
    """
    Inicializa o banco de dados, criando as tabelas se não existirem
    e adicionando colunas se necessário para manter a compatibilidade.
    """
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
        # Adiciona colunas se não existirem (para compatibilidade com versões anteriores)
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
#    """Padroniza o case de alguns campos existentes no banco de dados."""
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

# --- Rotas ---

@app.route('/buscar_cidades')
def buscar_cidades():
    """
    Retorna uma lista de cidades que correspondem a um termo de busca (para autocomplete).
    """
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
    """
    Busca o nome de um usuário na tabela 'login' pela matrícula.
    Usado para preencher o campo nome automaticamente no formulário de login.
    """
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


@app.route('/', methods=['GET', 'POST'])
def login():
    """
    Lida com o processo de login.
    Verifica se a matrícula existe e cria um novo registro (em 'registros' ou 'no_show').
    Após o login bem-sucedido e a criação do registro, redireciona para a página de boas-vindas
    (que por sua vez redirecionará para a página de status do motorista).
    """
    erro = None
    if request.method == 'POST':
        matricula = request.form['matricula']
        nome = request.form['nome'].title()
        rota = request.form.get('rota', '').title()
        tipo_entrega = request.form.get('tipo_entrega', '').title()
        cidade_entrega = request.form.get('cidade_entrega', '').title()  # Captura a cidade de entrega
        rua = request.form.get('rua', '').title() # Captura a rua
        data_hora = get_data_hora_brasilia()

        with get_db_connection() as conn:
            # Verificar se a matrícula existe na tabela login
            user_login = conn.execute('SELECT id FROM login WHERE matricula = ?', (matricula,)).fetchone()

            if user_login:
                login_id = user_login['id']

                # Remover a verificação de sessão ativa
                # Sempre criaremos um novo registro, independentemente de sessões ativas

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
                        ''', (nome, matricula, rota, tipo_entrega, cidade_entrega, data_hora, cpf, tipo_veiculo, login_id, rua))
                    else:
                        tabela_destino = 'registros'
                         # Inserir os dados na tabela registros
                        conn.execute(f'''
                            INSERT INTO {tabela_destino} (nome, matricula, rota, tipo_entrega, cidade_entrega,
                                                          data_hora_login, cpf, tipo_veiculo, em_separacao, finalizada, login_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)
                        ''', (nome, matricula, rota, tipo_entrega, cidade_entrega, data_hora, cpf, tipo_veiculo, login_id))

                    conn.commit()

                    # Pegar o ID da nova sessão criada (opcional, não usado no redirecionamento, mas útil para logs)
                    new_session_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
                    print(f"Nova sessão criada para o número de registro {matricula} (login_id: {login_id}) com ID: {new_session_id} na tabela {tabela_destino}.")

                    # Redireciona para a tela de boas-vindas, passando a matrícula como parâmetro
                    # MODIFICAÇÃO AQUI: Redireciona para boas_vindas com a matrícula
                    return redirect(url_for('boas_vindas', matricula=matricula))
                else:
                    erro = 'Erro ao buscar dados do usuário. Por favor, tente novamente.'
                    print(f"Erro ao buscar dados para login_id {login_id}.")
                    # Se houver erro ao buscar dados do usuário, renderiza a página de login novamente
                    return render_template('login.html', erro=erro)

            else:
                erro = 'Número de registro não cadastrado. Por favor, cadastre-se primeiro.'
                print(f"Login falhou para o número de registro {matricula}: Não encontrado na tabela login.")
                # Se a matrícula não for encontrada, renderiza a página de login novamente
                return render_template('login.html', erro=erro)

    # Para requisições GET, apenas renderiza o formulário de login
    return render_template('login.html', erro=erro)




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
    """Página de sucesso de cadastro."""
    # This route is now primarily a confirmation page if needed,
    # as registration redirects directly to the session.
    return render_template('sucesso.html')

@app.route('/boas_vindas')
def boas_vindas():
    """Página de boas-vindas após login/cadastro (pode ser redirecionada para associacao)."""
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
# Defina quantos registros por página você quer exibir
# CORRIGIDO: Definido fora da função para ser acessível globalmente

REGISTROS_POR_PAGINA = 20 # Ajuste este valor conforme necessário

@app.route('/registros', methods=['GET', 'POST'])
def registros():
    from datetime import datetime
    from math import ceil

    # Parâmetros de filtro da URL
    data_inicio_filtro = request.args.get('data_inicio', '')
    data_fim_filtro = request.args.get('data_fim', '')
    nome_filtro = request.args.get('nome', '')
    matricula_filtro = request.args.get('matricula', '')
    rota_filtro = request.args.get('rota', '')
    tipo_entrega_filtro = request.args.get('tipo_entrega', '')
    em_separacao_filtro = request.args.get('em_separacao', '')
    finalizado_filtro = request.args.get('finalizado', '')
    pagina = request.args.get('pagina', 1, type=int)

    # POST: Atualiza 'em_separacao'
    if request.method == 'POST':
        if 'registro_id' in request.form and 'em_separacao' in request.form:
            registro_id = request.form['registro_id']
            em_separacao = 1 if request.form.get('em_separacao') == 'on' else 0
            with get_db_connection() as conn:
                conn.execute('''
                    UPDATE registros
                    SET em_separacao = ?
                    WHERE id = ? AND finalizada = 0 AND cancelado = 0
                ''', (em_separacao, registro_id))
                conn.commit()

            args = request.args.to_dict()
            args.pop('registro_id', None)
            args.pop('em_separacao', None)
            args['pagina'] = pagina
            return redirect(url_for('registros', **args))

    # Filtros base
    query_base = 'SELECT * FROM registros WHERE 1=1'
    parametros_base = []

    # Filtro de intervalo de data usando substr para contornar o formato irregular
    if data_inicio_filtro:
        try:
            datetime.strptime(data_inicio_filtro, '%Y-%m-%d')
            query_base += ' AND substr(data_hora_login, 1, 10) >= ?'
            parametros_base.append(data_inicio_filtro)
        except ValueError:
            pass

    if data_fim_filtro:
        try:
            datetime.strptime(data_fim_filtro, '%Y-%m-%d')
            query_base += ' AND substr(data_hora_login, 1, 10) <= ?'
            parametros_base.append(data_fim_filtro)
        except ValueError:
            pass

    if nome_filtro:
        query_base += ' AND nome LIKE ?'
        parametros_base.append(f'%{nome_filtro.title()}%')

    if matricula_filtro:
        query_base += ' AND matricula LIKE ?'
        parametros_base.append(f'%{matricula_filtro}%')

    if rota_filtro:
        query_base += ' AND LOWER(rota) LIKE ?'
        parametros_base.append(f'%{rota_filtro.lower()}%')

    if tipo_entrega_filtro:
        query_base += ' AND LOWER(tipo_entrega) LIKE ?'
        parametros_base.append(f'%{tipo_entrega_filtro.lower()}%')

    if em_separacao_filtro != '':
        query_base += ' AND em_separacao = ?'
        parametros_base.append(int(em_separacao_filtro))

    if finalizado_filtro != '':
        query_base += ' AND finalizada = ?'
        parametros_base.append(int(finalizado_filtro))

    with get_db_connection() as conn:
        # Total de registros
        count_query = query_base.replace("SELECT *", "SELECT COUNT(*)", 1)
        total_registros = conn.execute(count_query, parametros_base).fetchone()[0]
        total_paginas = ceil(total_registros / REGISTROS_POR_PAGINA) if total_registros > 0 else 1
        offset = (pagina - 1) * REGISTROS_POR_PAGINA

        # Ordenação: ativos primeiro, depois por separação e data
        query_paginada = query_base + '''
            ORDER BY CASE WHEN finalizada = 0 AND cancelado = 0 THEN 0 ELSE 1 END,
                     em_separacao ASC,
                     data_hora_login DESC
            LIMIT ? OFFSET ?
        '''
        parametros_paginada = parametros_base + [REGISTROS_POR_PAGINA, offset]
        registros_data = conn.execute(query_paginada, parametros_paginada).fetchall()

        cidades_query = '''
            SELECT DISTINCT cidade_entrega
            FROM registros
            WHERE cidade_entrega IS NOT NULL AND cidade_entrega != ""
            ORDER BY cidade_entrega
        '''
        cidades_data = [row[0] for row in conn.execute(cidades_query).fetchall()]

    return render_template('registros.html',
                           registros=registros_data,
                           total_paginas=total_paginas,
                           pagina=pagina,
                           data_inicio=data_inicio_filtro,
                           data_fim=data_fim_filtro,
                           rota=rota_filtro,
                           tipo_entrega=tipo_entrega_filtro,
                           em_separacao=em_separacao_filtro,
                           finalizado=finalizado_filtro,
                           cidades=cidades_data)

@app.route('/historico')
def historico():
    """Displays historical actions from the historico table."""
    with get_db_connection() as conn:
        historico_data = conn.execute('SELECT h.*, r.nome, r.matricula FROM historico h JOIN registros r ON h.registro_id = r.id ORDER BY h.data_hora DESC').fetchall()
    return render_template('historico.html', historico=historico_data)
# ... (suas importações e configuração do Flask) ...

# ... (Rota Exportar) ...

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

    # --- DEBUG PRINT: Verifica se o ID está sendo recebido na rota ---
    print(f"DEBUG /associacao: Rota acessada. id_registro recebido: {id_registro}")
    print(f"DEBUG /associacao: Página: {pagina}, Rota Filtro: {rota_filtro}, Tipo Entrega Filtro: {tipo_entrega_filtro}")


    with get_db_connection() as conn:
        if id_registro:
            # If an ID is provided, display only that specific active record
            # Check if it's still active (not finalizada or cancelled)
            query = 'SELECT * FROM registros WHERE id = ? AND finalizada = 0 AND cancelado = 0'
            print(f"DEBUG /associacao: Executando query para ID específico: {query} com parâmetro {id_registro}")
            registro = conn.execute(query, (id_registro,)).fetchone()

            if registro:
                print(f"DEBUG /associacao: Registro encontrado para ID {id_registro}: {registro}")
                registros_data = [registro]
                total_paginas = 1
            else:
                print(f"DEBUG /associacao: Nenhum registro ATIVO encontrado para ID {id_registro}.")
                # Se o registro não for encontrado (pode ter sido finalizado/cancelado),
                # podemos optar por mostrar a lista completa ou uma mensagem.
                # Para depuração, vamos mostrar a lista completa neste caso.
                # Em produção, você pode querer redirecionar para a lista principal ou mostrar uma mensagem de "não encontrado/finalizado".
                print("DEBUG /associacao: Redirecionando para a lista completa pois o registro específico não foi encontrado como ativo.")
                return redirect(url_for('associacao')) # Redireciona para a lista completa sem ID

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

            print(f"DEBUG /associacao: Executando query para lista paginada: {base_query} com parâmetros {params}")
            registros_data = conn.execute(base_query, params).fetchall()
            print(f"DEBUG /associacao: Total de registros na lista paginada: {len(registros_data)}")


            return render_template('associacao.html', registros=registros_data, pagina=pagina,
                                   total_paginas=total_paginas, rota=rota_filtro,
                                   tipo_entrega=tipo_entrega_filtro, filtro_id=None)

### Rota Associação ID
@app.route('/associar/<int:id>', methods=['POST'])
def associar_id(id):
    """
    Associa um registro com gaiola/estacao/rua.
    Verifica se há um registro No-Show correspondente para transferir dados.
    Se um registro No-Show correspondente (matrícula '0001', mesma rota, status 'Aguardando Motorista')
    for encontrado, transfere os dados (rota, gaiola, estacao, rua) do No-Show para o registro
    na tabela 'registros', marca ambos como processados e finaliza o registro em 'registros'.
    Caso contrário, realiza a associação manual com os dados do formulário.
    """
    print(f"DEBUG: /associar/{id} - Rota acessada.")
    gaiola_form = request.form.get('gaiola', '').title()
    estacao_form = request.form.get('estacao', '').title()
    rua_form = request.form.get('rua', '').title() # Captura a rua do formulário
    data_hora = get_data_hora_brasilia()

    with get_db_connection() as conn:
        # 1. Buscar o registro na tabela 'registros' que está sendo associado
        registro_registros = conn.execute('SELECT * FROM registros WHERE id = ?', (id,)).fetchone()

        if not registro_registros:
            flash('Registro não encontrado.', 'error')
            print(f"DEBUG: /associar/{id} - Registro com ID {id} não encontrado.")
            # Retorna para a página anterior ou associacao, sem hash se o registro não existe
            return redirect(request.referrer or url_for('associacao'))

        # Verificar se o registro já está finalizado ou cancelado
        if registro_registros['finalizada'] == 1 or registro_registros['cancelado'] == 1:
            flash('Este registro já está finalizado ou cancelado e não pode ser associado.', 'warning')
            print(f"DEBUG: /associar/{id} - Registro com ID {id} já finalizado/cancelado.")
            # Redireciona de volta para a página de associação principal, pois o registro não estará mais na lista ativa
            return redirect(url_for('associacao'))

        # 2. Tentar encontrar um registro No-Show correspondente para transferência
        # Critérios: matricula '0001', mesma rota do registro 'registros',
        # status 'Aguardando Motorista' (em_separacao = 3), não finalizado, não cancelado, não transferido.
        registro_no_show_correspondente = conn.execute('''
            SELECT *
            FROM no_show
            WHERE matricula = '0001'
              AND rota = ?
              AND em_separacao = 3 -- Status 'Aguardando Motorista'
              AND finalizada = 0
              AND cancelado = 0
              AND transferred_to_registro_id IS NULL
            ORDER BY data_hora_login ASC -- Pega o mais antigo se houver múltiplos
            LIMIT 1
        ''', (registro_registros['rota'],)).fetchone()

        if registro_no_show_correspondente:
            print(f"DEBUG: /associar/{id} - Encontrado registro No-Show correspondente (ID: {registro_no_show_correspondente['id']}). Realizando transferência.")
            # --- Lógica de Transferência ---
            try:
                # Inicia uma transação para garantir atomicidade
                conn.execute('BEGIN')

                # Atualiza o registro na tabela 'registros' com os dados do No-Show
                # E marca como finalizado (status 3 em em_separacao e finalizada=1)
                conn.execute('''
                    UPDATE registros
                    SET rota = ?, gaiola = ?, estacao = ?, rua = ?, -- Campos copiados do No-Show
                        em_separacao = 3, finalizada = 1, hora_finalizacao = ? -- Status de finalização após transferência
                    WHERE id = ?
                ''', (registro_no_show_correspondente['rota'], registro_no_show_correspondente['gaiola'],
                      registro_no_show_correspondente['estacao'], registro_no_show_correspondente['rua'],
                      data_hora, id))

                # Atualiza o registro No-Show correspondente
                # Marca como transferido (em_separacao = 4) e vincula ao registro de destino
                conn.execute('''
                    UPDATE no_show
                    SET em_separacao = 4, transferred_to_registro_id = ?, hora_finalizacao = ?
                    WHERE id = ?
                ''', (id, data_hora, registro_no_show_correspondente['id']))

                # Registra a ação no histórico de registros
                conn.execute('''
                    INSERT INTO historico (registro_id, acao, data_hora)
                    VALUES (?, 'data_transferred_from_no_show', ?)
                ''', (id, data_hora))

                # Registra a ação no histórico de no-show
                conn.execute('''
                    INSERT INTO historico_no_show (registro_no_show_id, acao, data_hora)
                    VALUES (?, 'transferred_to_registro', ?)
                ''', (registro_no_show_correspondente['id'], data_hora))

                conn.commit() # Confirma a transação

                flash('Dados transferidos de registro No-Show e registro de carregamento finalizado com sucesso!', 'success')
                print(f"DEBUG: /associar/{id} - Transferência e finalização concluídas para registro {id}.")

            except Exception as e:
                conn.rollback() # Desfaz a transação em caso de erro
                flash(f'Ocorreu um erro durante a transferência do registro: {e}', 'error')
                print(f"DEBUG: /associar/{id} - Erro durante a transferência: {e}")

            # Após a transferência, o registro em 'registros' foi finalizado,
            # então ele não aparecerá mais na lista padrão de /associacao.
            # Redirecionar para a página principal de associação sem o hash.
            return redirect(url_for('associacao'))

        else:
            # --- Lógica de Associação Manual (se nenhum No-Show correspondente for encontrado) ---
            print(f"DEBUG: /associar/{id} - Nenhum registro No-Show correspondente encontrado. Realizando associação manual.")
            try:
                # Apenas atualiza se o registro não estiver finalizado ou cancelado
                # Define o status como 'em separacao' (em_separacao = 1)
                conn.execute('''
                    UPDATE registros
                    SET gaiola = ?, estacao = ?, rua = ?, em_separacao = ?
                    WHERE id = ? AND finalizada = 0 AND cancelado = 0
                ''', (gaiola_form, estacao_form, rua_form, 1, id)) # Usa os dados do formulário e define em_separacao = 1

                # Registra a ação no histórico de registros
                conn.execute('''
                    INSERT INTO historico (registro_id, acao, gaiola, estacao, data_hora)
                    VALUES (?, 'associated_manual', ?, ?, ?) -- Ação 'associated_manual' para diferenciar
                ''', (id, gaiola_form, estacao_form, data_hora))
                conn.commit()

                flash('Registro associado manualmente com sucesso!', 'success')
                print(f"DEBUG: /associar/{id} - Associação manual concluída para registro {id}.")

            except Exception as e:
                conn.rollback() # Desfaz a transação em caso de erro
                flash(f'Ocorreu um erro durante a associação manual: {e}', 'error')
                print(f"DEBUG: /associar/{id} - Erro durante a associação manual: {e}")

            # --- MODIFICAÇÃO AQUI ---
            # Redireciona de volta para a página de associação, adicionando o hash do registro E o ID como parâmetro de query
            return redirect(url_for('associacao', id=id) + f'#registro-{id}')


@app.route('/desassociar/<int:id>', methods=['POST'])
def desassociar_id(id):
    """Remove a associação de gaiola/estacao e define o status de volta para não 'em separacao'."""
    data_hora = get_data_hora_brasilia()

    with get_db_connection() as conn:
        # Apenas atualiza se o registro não estiver finalizado ou cancelado
        conn.execute('''
            UPDATE registros
            SET gaiola = NULL, estacao = NULL, rua = NULL, em_separacao = 0 -- Reseta o campo rua e em_separacao
            WHERE id = ? AND finalizada = 0 AND cancelado = 0
        ''', (id,))
        # Registra a ação no histórico
        conn.execute('''
            INSERT INTO historico (registro_id, acao, data_hora)
            VALUES (?, 'disassociated', ?)
        ''', (id, data_hora))
        conn.commit()
    flash('Associação removida com sucesso!', 'success')
    # --- MODIFICAÇÃO AQUI ---
    # Redireciona de volta para a página de associação, adicionando o hash do registro E o ID como parâmetro de query
    return redirect(url_for('associacao', id=id) + f'#registro-{id}')

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
    flash('Carregamento marcado como concluído!', 'success')
    # --- MODIFICAÇÃO AQUI ---
    # Redireciona de volta para a página de associação, adicionando o hash do registro E o ID como parâmetro de query
    return redirect(url_for('associacao', id=id) + f'#registro-{id}')


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

    flash('Registro finalizado com sucesso!', 'success')
    # --- SEM MODIFICAÇÃO AQUI ---
    # Redireciona de volta para a página de associação principal sem o hash,
    # pois o registro finalizado não aparecerá mais na lista ativa.
    return redirect(url_for('associacao'))

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
    flash('Registro cancelado com sucesso!', 'success')
    # --- SEM MODIFICAÇÃO AQUI ---
    # Redireciona de volta para a página de associação principal sem o hash,
    # pois o registro cancelado não aparecerá mais na lista ativa.
    return redirect(url_for('associacao'))


@app.route('/voltar_para_associacao/<int:id>', methods=['POST'])
def voltar_para_associacao_id(id):
    """Redefine o status de um registro para torná-lo ativo novamente para associação."""
    data_hora = get_data_hora_brasilia()
    with get_db_connection() as conn:
        # Apenas redefine se o registro estiver finalizado ou cancelado
        conn.execute('''
            UPDATE registros
            SET gaiola = NULL, estacao = NULL, rua = NULL, em_separacao = 0, finalizada = 0, cancelado = 0, hora_finalizacao = NULL
            WHERE id = ? AND (finalizada = 1 OR cancelado = 1)
        ''', (id,))
        # Registra a ação no histórico
        conn.execute('''
            INSERT INTO historico (registro_id, acao, data_hora)
            VALUES (?, 'returned_to_association', ?)
        ''', (id, data_hora))
        conn.commit()
    flash('Registro reativado para associação!', 'success')
    # --- MODIFICAÇÃO AQUI ---
    # Redireciona de volta para a página de associação, adicionando o hash do registro E o ID como parâmetro de query
    return redirect(url_for('associacao', id=id) + f'#registro-{id}')

# ... (outras rotas) ...


# --- Rota para o painel final ---
@app.route('/painel_final')
def painel_final():
    """Renderiza a página do painel final."""
    return render_template('painel_final.html')


# ---- Registros Finalizados -------
@app.route('/registros_finalizados', methods=['GET', 'POST'])
def registros_finalizados():
    """
    Exibe os registros finalizados. Com opção de exibir todos os registros (finalizados e não finalizados).
    """
    # Obtém parâmetros de filtro
    data_filtro = request.args.get('data', '')
    tipo_entrega_filtro = request.args.get('tipo_entrega', '')
    rota_filtro = request.args.get('rota', '')
    finalizado_filtro = request.args.get('finalizado', '')  # Filtro para status finalizado (1 ou 0)

    # --- Obtém o número da página atual ---
    pagina = request.args.get('pagina', 1, type=int)

    # Lógica para filtrar registros de acordo com o status 'finalizado'
    query_base = 'SELECT * FROM registros WHERE 1=1'
    parametros_base = []

    if data_filtro:
        try:
            datetime.strptime(data_filtro, '%Y-%m-%d')
            query_base += ' AND substr(data_hora_login, 1, 10) = ?'
            parametros_base.append(data_filtro)
        except ValueError:
            pass

    if tipo_entrega_filtro:
        query_base += ' AND LOWER(tipo_entrega) LIKE ?'
        parametros_base.append(f'%{tipo_entrega_filtro.lower()}%')

    if rota_filtro:
        query_base += ' AND LOWER(rota) LIKE ?'
        parametros_base.append(f'%{rota_filtro.lower()}%')

    # Adiciona a filtragem para o campo 'finalizado' apenas se o filtro for passado
    if finalizado_filtro != '':  # Se não for vazio, aplica o filtro
        query_base += ' AND finalizada = ?'
        parametros_base.append(int(finalizado_filtro))  # Converte para inteiro (1 ou 0)

    with get_db_connection() as conn:
        # Contar o total de registros com os filtros aplicados
        count_query = query_base.replace("SELECT *", "SELECT COUNT(*)", 1)
        total_registros = conn.execute(count_query, parametros_base).fetchone()[0]

        # Calcular o total de páginas
        total_paginas = ceil(total_registros / REGISTROS_POR_PAGINA) if total_registros > 0 else 1

        # Ajusta a query para buscar os registros da página atual
        offset = (pagina - 1) * REGISTROS_POR_PAGINA
        query_paginada = query_base + ' ORDER BY data_hora_login DESC LIMIT ? OFFSET ?'
        parametros_paginada = parametros_base + [REGISTROS_POR_PAGINA, offset]

        registros_data = conn.execute(query_paginada, parametros_paginada).fetchall()

    return render_template('registros_finalizados.html',
                           registros=registros_data,
                           total_paginas=total_paginas,
                           pagina=pagina,
                           data=data_filtro,
                           tipo_entrega=tipo_entrega_filtro,
                           rota=rota_filtro,
                           finalizado=finalizado_filtro)  # Passa o filtro 'finalizado'
# ---- Fim da Rota

# --- Nova Rota para Status do Motorista ---
# --- Rota para exibir o status do motorista (agora por matrícula) ---
@app.route('/status_motorista/<string:matricula>', methods=['GET'])
def status_motorista(matricula):
    """
    Renderiza a página de status do motorista, passando a matrícula.
    """
    print(f"DEBUG: /status_motorista/{matricula} - Rota acessada.")
    # Passa a matrícula para o template
    return render_template('status_motorista.html', matricula=matricula)

# ... (seu código Flask existente da parte 1, 2 e 3 antes desta rota)

# --- Nova rota API para buscar o status do registro mais recente não finalizado pela matrícula ---
# --- Rota API para buscar o status do motorista pela matrícula ---
@app.route('/api/status_registro_by_matricula/<string:matricula>', methods=['GET'])
def api_status_registro_by_matricula(matricula):
    print(f"DEBUG: /api/status_registro_by_matricula/{matricula} - Rota API acessada.")
    
    # Parâmetro opcional 'tipo_entrega' para permitir a filtragem explícita
    # Ex: /api/status_registro_by_matricula/123?tipo_entrega=Normal
    requested_tipo_entrega = request.args.get('tipo_entrega') 
    print(f"DEBUG: 'tipo_entrega' solicitado via query param: {requested_tipo_entrega}")

    registro_registros_data = None
    registro_noshow_data = None
    response_data = None
    tabela_origem = None # Para logs e depuração

    with get_db_connection() as conn:
        # --- 1. Tentar buscar o registro ativo mais recente na tabela 'registros' para a matrícula fornecida ---
        # Prioriza um registro "Normal" para a matrícula específica, a menos que o No-Show seja solicitado explicitamente.
        
        query_registros = '''
            SELECT *
            FROM registros
            WHERE matricula = ? AND finalizada = 0 AND cancelado = 0
        '''
        params_registros = [matricula]

        # Se um tipo de entrega foi solicitado e NÃO é 'No-Show' (ou se a matrícula não é '0001'),
        # filtra a busca por 'registros' para esse tipo.
        # Caso contrário, tentaremos pegar o registro "Normal" por padrão para esta matrícula.
        if requested_tipo_entrega and requested_tipo_entrega.lower() != 'no-show':
            query_registros += ' AND tipo_entrega = ?'
            params_registros.append(requested_tipo_entrega)
        elif not requested_tipo_entrega: # Se não pediu um tipo específico, e não é '0001', assume 'Normal'
            # Isso impede que um 'No-Show' por acidente em 'registros' seja pego para uma matrícula que não é '0001'
            query_registros += ' AND tipo_entrega = "Normal"' 

        query_registros += ' ORDER BY data_hora_login DESC LIMIT 1'
        registro_registros_data = conn.execute(query_registros, params_registros).fetchone()

        if registro_registros_data:
            response_data = dict(registro_registros_data)
            tabela_origem = 'registros'
            print(f"DEBUG: Encontrado registro ativo em 'registros' para matrícula {matricula} (ID: {response_data.get('id')}, Rota: {response_data.get('rota')}, Tipo: {response_data.get('tipo_entrega')}).")

            # Apenas para a matrícula '0001' e se o tipo for 'No-Show', tentaremos buscar no 'no_show'.
            # Caso contrário, se é um motorista Normal com um registro Normal, este é o que interessa.
            # A lógica de combinação de "No-Show correspondente" é removida aqui, pois ela causava a confusão.
            # O 'No-Show' da matrícula '0001' é um registro independente, não uma "carga" para um registro Normal.

        # --- 2. Se nenhum registro ativo foi encontrado em 'registros' para a matrícula OU se o tipo 'No-Show' foi explicitamente solicitado (e a matrícula é '0001') ---
        if not response_data or (matricula == '0001' and requested_tipo_entrega and requested_tipo_entrega.lower() == 'no-show'):
            print(f"DEBUG: Nenhum registro ativo 'Normal' encontrado para matrícula {matricula} OU 'No-Show' explicitamente solicitado para '0001'. Verificando 'no_show' agora.")
            
            # Buscar na tabela 'no_show'. A matrícula deve ser '0001' para este fluxo de 'no_show' direto.
            # E agora, se 'tipo_entrega' foi especificado, usá-lo como filtro.
            query_noshow = '''
                SELECT *
                FROM no_show
                WHERE matricula = '0001'
                  AND finalizada = 0
                  AND cancelado = 0
                  AND transferred_to_registro_id IS NULL
            '''
            params_noshow = []

            # Se um tipo de entrega foi solicitado (e for 'No-Show'), adiciona ao filtro.
            if requested_tipo_entrega and requested_tipo_entrega.lower() == 'no-show':
                query_noshow += ' AND tipo_entrega = "No-Show"' # Garante que só busca tipo "No-Show"
            elif not requested_tipo_entrega and matricula == '0001': # Se 0001 e não pediu nada, assume No-Show
                query_noshow += ' AND tipo_entrega = "No-Show"' 
                
            query_noshow += ' ORDER BY data_hora_login DESC LIMIT 1'
            
            registro_noshow_data = conn.execute(query_noshow, params_noshow).fetchone()

            if registro_noshow_data:
                # Se encontrarmos um registro em 'no_show', ele se torna o response_data principal.
                response_data = dict(registro_noshow_data)
                tabela_origem = 'no_show_direto'
                print(f"DEBUG: Encontrado registro relevante em 'no_show' (ID: {response_data.get('id')}, Rota: {response_data.get('rota')}, Tipo: {response_data.get('tipo_entrega')}) diretamente para matrícula '0001'.")
            else:
                print(f"DEBUG: Nenhuma registro ativo relevante encontrado para matrícula {matricula} com os critérios fornecidos em 'registros' ou 'no_show'.")


    # --- Preparar os dados de resposta e determinar status ---
    if response_data:
        # Garante que todos os campos esperados estejam presentes, mesmo que sejam None.
        # Isso evita erros no frontend ao tentar acessar chaves inexistentes.
        default_fields = {
            'id': None, 'nome': None, 'matricula': None, 'data_hora_login': None,
            'cpf': None, 'tipo_veiculo': None, 'login_id': None, 'rota': None,
            'tipo_entrega': None, 'cidade_entrega': None, 'rua': None, 
            'gaiola': None, 'estacao': None, 'em_separacao': None,
            'finalizada': None, 'cancelado': None, 'transferred_to_registro_id': None,
            'hora_finalizacao': None, 'tabela_origem': tabela_origem # Adiciona a origem para debug no frontend
        }
        final_response_data = {**default_fields, **response_data}


        # Lógica para determinar 'status_text' e 'status_class' com base nos dados do registro encontrado
        status_text = 'Status Desconhecido'
        status_class = 'bg-gray-500' # Default

        if final_response_data.get('finalizada') == 1:
            status_text = 'Registro Finalizado'
            status_class = 'status-finalizado'
        elif final_response_data.get('cancelado') == 1:
            status_text = 'Registro Cancelado'
            status_class = 'status-cancelado'
        # A prioridade aqui é do 'transferred_to_registro_id' e 'em_separacao = 4' para No-Show transferido
        elif final_response_data.get('transferred_to_registro_id') is not None and final_response_data.get('em_separacao') == 4:
            status_text = 'Registro No-Show Transferido para Carregamento'
            status_class = 'status-transferido'
        elif final_response_data.get('em_separacao') == 2:
            status_text = 'Liberado para Carregamento'
            status_class = 'status-carregamento-finalizado'
        elif final_response_data.get('em_separacao') == 1:
            status_text = 'Em Separação (Aguardando Carregamento)'
            status_class = 'status-em-separacao'
        elif final_response_data.get('em_separacao') == 3:
            status_text = 'Aguardando Motorista'
            status_class = 'status-aguardando-motorista'
            # Se for um No-Show direto e status 3, podemos dar um toque extra na mensagem
            if final_response_data.get('tabela_origem') == 'no_show_direto' and final_response_data.get('matricula') == '0001':
                status_text = 'No-Show: Aguardando Associação/Motorista'
                status_class = 'status-no-show-especifico' # Uma cor diferente para o No-Show da 0001
        elif final_response_data.get('em_separacao') == 0:
            status_text = 'Aguardando Associação/Carregamento'
            status_class = 'status-em-fila' # Ou 'status-aguardando' conforme sua preferência
        
        final_response_data['status_text'] = status_text
        final_response_data['status_class'] = status_class

        print(f"DEBUG: Dados de resposta final (Origem: {tabela_origem}): {final_response_data}")
        return jsonify(final_response_data)
    else:
        print(f"DEBUG: /api/status_registro_by_matricula/{matricula} - Nenhum registro ativo relevante encontrado para a matrícula com os critérios.")
        return jsonify({'message': 'Nenhum registro ativo encontrado para esta matrícula com os critérios especificados.'}), 404


#Fim status Motorista

# --- Rotas para registros No-Show ---
@app.route('/registro_no_show', methods=['GET', 'POST']) # Mantido POST para o checkbox, mas GET para a carga inicial e filtros
def registro_no_show():
    """Exibe registros No-Show com opções de filtro e paginação."""
    print("DEBUG: /registro_no_show - Rota acessada.")
    # Parâmetros para manter o estado do filtro no redirecionamento
    data_filtro = request.args.get('data', '')
    nome_filtro = request.args.get('nome', '')
    matricula_filtro = request.args.get('matricula', '')
    rota_filtro = request.args.get('rota', '')
    tipo_entrega_filtro = request.args.get('tipo_entrega', '')
    status_filtro = request.args.get('status', '') # Adicionado filtro por status

    print(f"DEBUG: /registro_no_show - Filtros recebidos: data='{data_filtro}', nome='{nome_filtro}', matricula='{matricula_filtro}', rota='{rota_filtro}', tipo_entrega='{tipo_entrega_filtro}', status='{status_filtro}'")


    pagina = int(request.args.get('pagina', 1))
    registros_por_pagina = 10 # Mantido 10 como no seu código, mas a constante é 20. Ajuste se necessário.

    # A parte POST aqui lida com a checkbox 'em_separacao' da lista de registros.
    if request.method == 'POST':
        print("DEBUG: /registro_no_show - Método POST recebido.")
        if 'registro_id' in request.form and 'em_separacao' in request.form:
            registro_id = request.form['registro_id']
            em_separacao = 1 if request.form.get('em_separacao') == 'on' else 0
            print(f"DEBUG: /registro_no_show - POST: Atualizando registro_id={registro_id} para em_separacao={em_separacao}")
            with get_db_connection() as conn:
                # Apenas atualiza se o registro não estiver finalizado ou cancelado
                conn.execute('''
                    UPDATE registros
                    SET em_separacao = ?
                    WHERE id = ? AND finalizada = 0 AND cancelado = 0
                ''', (em_separacao, registro_id))
                conn.commit()
                print(f"DEBUG: /registro_no_show - POST: Update executado para registro_id={registro_id}")
        # Redireciona mantendo os filtros na URL
        # Adicionado status_filtro ao redirecionamento POST
        print(f"DEBUG: /registro_no_show - Redirecionando para: {request.referrer}")
        return redirect(request.referrer)
    # Lida com outras ações POST, ou ignora requisições POST não relacionadas à checkbox

    query_base = 'SELECT * FROM no_show WHERE 1=1' # Começa selecionando todos
    parametros_base = []
    filter_conditions = [] # Usar uma lista para as condições de filtro

    if data_filtro:
        try:
            datetime.strptime(data_filtro, '%Y-%m-%d')
            filter_conditions.append('substr(data_hora_login, 1, 10) = ?')
            parametros_base.append(data_filtro)
        except ValueError:
            pass

    if nome_filtro:
        filter_conditions.append('LOWER(nome) LIKE ?') # Usar LOWER para busca case-insensitive
        parametros_base.append(f'%{nome_filtro.lower()}%') # Passar o filtro em minúsculas

    if matricula_filtro:
        filter_conditions.append('matricula LIKE ?')
        parametros_base.append(f'%{matricula_filtro}%')

    if rota_filtro:
        filter_conditions.append('LOWER(gaiola) LIKE ?') # Assumindo que 'gaiola' é o campo para 'rota' no no_show
        parametros_base.append(f'%{rota_filtro.lower()}%')

    if tipo_entrega_filtro:
        filter_conditions.append('LOWER(tipo_entrega) LIKE ?')
        parametros_base.append(f'%{tipo_entrega_filtro.lower()}%')

    # Adicionar filtro por status (em_separacao, finalizada, cancelado, transferred_to_registro_id)
    # Se status_filtro for vazio (''), nenhuma condição de status é adicionada, mostrando todos.
    if status_filtro:
        print(f"DEBUG: /registro_no_show - Aplicando filtro de status: {status_filtro}")
        if status_filtro == 'aguardando': # Filtra estritamente por "Aguardando Motorista" (estado inicial)
            filter_conditions.append('(gaiola IS NULL OR gaiola = "") AND (estacao IS NULL OR estacao = "") AND em_separacao = 0 AND finalizada = 0 AND cancelado = 0 AND transferred_to_registro_id IS NULL')
        elif status_filtro == 'separacao': # No-show 'em separacao' (status 1)
            filter_conditions.append('em_separacao = 1 AND finalizada = 0 AND cancelado = 0 AND transferred_to_registro_id IS NULL')
        elif status_filtro == 'carregamento_finalizado': # No-show 'carregamento finalizado' (status 2)
            filter_conditions.append('em_separacao = 2 AND finalizada = 0 AND cancelado = 0 AND transferred_to_registro_id IS NULL')
        elif status_filtro == 'finalizado': # No-show finalizado (status 3)
            filter_conditions.append('finalizada = 1') # Pode ser finalizado diretamente ou via cancelamento
        elif status_filtro == 'cancelado': # No-show cancelado (status 1)
            filter_conditions.append('cancelado = 1')
        elif status_filtro == 'transferido': # No-show transferido (status 4)
            filter_conditions.append('em_separacao = 4 AND transferred_to_registro_id IS NOT NULL')
        else:
            print(f"DEBUG: /registro_no_show - Status de filtro desconhecido: {status_filtro}. Nenhum filtro de status aplicado.")


    if filter_conditions:
        query_base += ' AND ' + ' AND '.join(filter_conditions)

    # Ordena para mostrar registros não finalizados, não cancelados e não transferidos primeiro
    # e depois por data de login mais recente.
    # A condição `em_separacao != 4` exclui os transferidos da prioridade de "não finalizados".
    # A ordenação agora prioriza qualquer registro que não esteja finalizado, cancelado ou transferido.
    query_paginada = query_base + ' ORDER BY CASE WHEN finalizada = 0 AND cancelado = 0 AND em_separacao != 4 THEN 0 ELSE 1 END, data_hora_login DESC LIMIT ? OFFSET ?'
    parametros_paginada = parametros_base + [registros_por_pagina, (pagina - 1) * registros_por_pagina]

    print(f"DEBUG: /registro_no_show - Query SQL final: {query_paginada}")
    print(f"DEBUG: /registro_no_show - Parâmetros da Query: {parametros_paginada}")


    with get_db_connection() as conn:
        # Para a contagem total, use apenas a query_base com as condições de filtro
        count_query = query_base.replace("SELECT *", "SELECT COUNT(*)", 1)
        total = conn.execute(count_query, parametros_base).fetchone()[0]
        total_paginas = (total + registros_por_pagina - 1) // registros_por_pagina
        registros_data = conn.execute(query_paginada, parametros_paginada).fetchall()

    print(f"DEBUG: /registro_no_show - Total de registros encontrados (antes da paginação): {total}")
    print(f"DEBUG: /registro_no_show - Registros retornados para esta página: {len(registros_data)}")


    return render_template('registro_no_show.html', registros_no_show=registros_data, # Note: passing as registros_no_show to match HTML
                           data_filtro=data_filtro, nome_filtro=nome_filtro,
                           matricula_filtro=matricula_filtro, rota_filtro=rota_filtro,
                           tipo_entrega_filtro=tipo_entrega_filtro, status_filtro=status_filtro,
                           pagina=pagina, total_paginas=total_paginas)

# --- Rotas para ações em registros No-Show ---
@app.route('/registro_no_show/associar/<int:id>', methods=['POST'])
def associar_no_show_id(id):
    """Associa um registro no-show com gaiola/estacao/rua e define o status como 'em separacao'."""
    print(f"DEBUG: /registro_no_show/associar/{id} - Rota acessada.")
    gaiola = request.form.get('gaiola', '').title()
    estacao = request.form.get('estacao', '').title()
    rua = request.form.get('rua', '').title() # Captura a rua
    em_separacao = 1 # Ao associar, marca como "em separação"
    data_hora = get_data_hora_brasilia()
    print(f"DEBUG: /registro_no_show/associar/{id} - Dados recebidos: gaiola='{gaiola}', estacao='{estacao}', rua='{rua}'")


    with get_db_connection() as conn:
        # Apenas atualiza se o registro não estiver finalizado ou cancelado.
        # REMOVIDA a condição AND transferred_to_registro_id IS NULL para permitir re-associação manual.
        conn.execute('''
            UPDATE no_show
            SET gaiola = ?, estacao = ?, rua = ?, em_separacao = ?
            WHERE id = ? AND finalizada = 0 AND cancelado = 0
        ''', (gaiola, estacao, rua, em_separacao, id))

        # Registra a ação no histórico de no-show
        # Nota: O histórico não precisa saber o transferred_to_registro_id, apenas a ação e os dados associados.
        conn.execute('''
            INSERT INTO historico_no_show (registro_no_show_id, acao, gaiola, estacao, rua, data_hora)
            VALUES (?, 'associated', ?, ?, ?, ?)
        ''', (id, gaiola, estacao, rua, data_hora)) # Adicionado 'rua' no histórico
        conn.commit()
        print(f"DEBUG: /registro_no_show/associar/{id} - Update e histórico registrados.")


    # Redireciona de volta para a página de origem, preservando filtros e rolando para o registro
    # request.referrer contém a URL da página que originou a requisição POST
    redirect_url = request.referrer if request.referrer else url_for('registro_no_show')
    print(f"DEBUG: /registro_no_show/associar/{id} - Redirecionando para: {redirect_url + f'#no-show-registro-{id}'}")
    return redirect(redirect_url + f'#no-show-registro-{id}')


## Fim registro No Show Associar

@app.route('/registro_no_show/desassociar/<int:id>', methods=['POST'])
def desassociar_no_show_id(id):
    """Remove a associação de gaiola/estacao/rua de um registro no-show e define o status de volta para não 'em separacao'."""
    print(f"DEBUG: /registro_no_show/desassociar/{id} - Rota acessada.")
    data_hora = get_data_hora_brasilia()

    with get_db_connection() as conn:
        # Apenas atualiza se o registro não estiver finalizado, cancelado ou transferido
        conn.execute('''
            UPDATE no_show
            SET gaiola = NULL, estacao = NULL, rua = NULL, em_separacao = 0
            WHERE id = ? AND finalizada = 0 AND cancelado = 0 AND transferred_to_registro_id IS NULL
        ''', (id,))
        # Registra a ação no histórico de no-show
        conn.execute('''
            INSERT INTO historico_no_show (registro_no_show_id, acao, data_hora)
            VALUES (?, 'disassociated', ?)
        ''', (id, data_hora))
        conn.commit()
        print(f"DEBUG: /registro_no_show/desassociar/{id} - Update e histórico registrados.")

    # Redireciona de volta para a página de origem, preservando filtros e rolando para o registro
    print(f"DEBUG: /registro_no_show/desassociar/{id} - Redirecionando para: {request.referrer + f'#no-show-registro-{id}'}")
    return redirect(request.referrer + f'#no-show-registro-{id}')

@app.route('/registro_no_show/finalizar_carregamento_status_separacao/<int:id>', methods=['POST'])
def finalizar_carregamento_no_show_id_status_separacao(id):
    """Define o status 'em_separacao' de um registro no-show para indicar que o carregamento foi finalizado (status 2)."""
    print(f"DEBUG: /registro_no_show/finalizar_carregamento_status_separacao/{id} - Rota acessada.")
    data_hora = get_data_hora_brasilia()
    with get_db_connection() as conn:
        # Apenas atualiza se o registro estiver 'em_separacao' (status 1) e não finalizado, cancelado ou transferido
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
        print(f"DEBUG: /registro_no_show/finalizar_carregamento_status_separacao/{id} - Update e histórico registrados.")

    # Redireciona de volta para a página de origem, preservando filtros e rolando para o registro
    print(f"DEBUG: /registro_no_show/finalizar_carregamento_status_separacao/{id} - Redirecionando para: {request.referrer + f'#no-show-registro-{id}'}")
    return redirect(request.referrer + f'#no-show-registro-{id}')


@app.route('/registro_no_show/marcar_como_finalizado/<int:id>', methods=['POST'])
def marcar_como_finalizado_no_show_id(id):
    """
    Marca um registro/sessão de no-show como finalizada (concluída).
    Verifica o estado atual do registro antes de finalizar.
    Permite finalização de qualquer estado ativo (não finalizado, cancelado ou transferido).
    """
    print(f"DEBUG: /registro_no_show/marcar_como_finalizado/{id} - Rota acessada.")
    data_hora = get_data_hora_brasilia()
    with get_db_connection() as conn:
        # Buscar o estado atual do registro
        registro = conn.execute('SELECT finalizada, cancelado, transferred_to_registro_id FROM no_show WHERE id = ?', (id,)).fetchone()
        print(f"DEBUG: /registro_no_show/marcar_como_finalizado/{id} - Estado atual do registro: {registro}")


        if not registro:
            flash('Registro No-Show não encontrado.', 'error')
            print(f"DEBUG: /registro_no_show/marcar_como_finalizado/{id} - Registro não encontrado.")
            return redirect(url_for('registro_no_show'))

        # Verificar se o registro já está em um estado final ou transferido
        if registro['finalizada'] == 1:
            flash('Este registro No-Show já está finalizado.', 'warning')
            print(f"DEBUG: /registro_no_show/marcar_como_finalizado/{id} - Já finalizado.")
        elif registro['cancelado'] == 1:
            flash('Este registro No-Show foi cancelado.', 'warning')
            print(f"DEBUG: /registro_no_show/marcar_como_finalizado/{id} - Cancelado.")
        elif registro['transferred_to_registro_id'] is not None:
             flash('Este registro No-Show foi transferido para um registro de carregamento.', 'warning')
             print(f"DEBUG: /registro_no_show/marcar_como_finalizado/{id} - Transferido.")
        else:
            # Se não estiver em um estado final ou transferido, procede com a finalização
            try:
                rows_updated = conn.execute('''
                    UPDATE no_show
                    SET finalizada = 1, em_separacao = 3, hora_finalizacao = ?
                    WHERE id = ? AND finalizada = 0 AND cancelado = 0 AND transferred_to_registro_id IS NULL
                ''', (data_hora, id)).rowcount # Verifica quantas linhas foram atualizadas
                print(f"DEBUG: /registro_no_show/marcar_como_finalizado/{id} - Linhas atualizadas: {rows_updated}")


                if rows_updated > 0:
                    # Registra a ação no histórico de no-show
                    conn.execute('''
                        INSERT INTO historico_no_show (registro_no_show_id, acao, data_hora)
                        VALUES (?, 'record_finalized', ?)
                    ''', (id, data_hora))
                    conn.commit()
                    flash('Registro No-Show finalizado com sucesso.', 'success')
                    print(f"DEBUG: /registro_no_show/marcar_como_finalizado/{id} - Registro No-Show finalizado com sucesso.")
                else:
                    # Isso pode acontecer se o estado do registro mudou entre a busca e o update
                    flash('Falha ao finalizar o registro No-Show. O estado do registro pode ter mudado.', 'warning')
                    print(f"DEBUG: /registro_no_show/marcar_como_finalizado/{id} - Falha ao finalizar. Estado atual: Finalizado={registro['finalizada']}, Cancelado={registro['cancelado']}, Transferido={registro['transferred_to_registro_id']}")

            except Exception as e:
                conn.rollback() # Desfaz a transação em caso de erro
                flash(f'Ocorreu um erro ao finalizar o registro: {e}', 'error')
                print(f"DEBUG: /registro_no_show/marcar_como_finalizado/{id} - Erro: {e}")


    # Redireciona de volta para a página de origem, preservando filtros.
    # O registro pode desaparecer da lista ativa, então não precisa rola
    print(f"DEBUG: /registro_no_show/marcar_como_finalizado/{id} - Redirecionando para: {request.referrer}")
    return redirect(request.referrer)

@app.route('/registro_no_show/cancelar_registro/<int:id>', methods=['POST'])
def cancelar_no_show_registro_id(id):
    """Marca um registro/sessão de no-show como cancelada e finalizada."""
    print(f"DEBUG: /registro_no_show/cancelar_registro/{id} - Rota acessada.")
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
        print(f"DEBUG: /registro_no_show/cancelar_registro/{id} - Update e histórico registrados.")

    # Redireciona de volta para a página de origem, preservando filtros.
    # O registro pode desaparecer da lista ativa, então não precisa rola
    print(f"DEBUG: /registro_no_show/cancelar_registro/{id} - Redirecionando para: {request.referrer}")
    return redirect(request.referrer)

@app.route('/registro_no_show/voltar_para_associacao/<int:id>', methods=['POST'])
def voltar_para_associacao_no_show_id(id):
    """Redefine o status de um registro de no-show para torná-lo ativo novamente para associação."""
    print(f"DEBUG: /registro_no_show/voltar_para_associacao/{id} - Rota acessada.")
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
        print(f"DEBUG: /registro_no_show/voltar_para_associacao/{id} - Update e histórico registrados.")

    # Redireciona de volta para a página de origem, preservando filtros e rolando para o registro
    print(f"DEBUG: /registro_no_show/voltar_para_associacao/{id} - Redirecionando para: {request.referrer + f'#no-show-registro-{id}'}")
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
    print(f"DEBUG: /transferir_no_show_para_registro/{no_show_id} - Rota acessada.")
    data_hora_transferencia = get_data_hora_brasilia()

    with get_db_connection() as conn:
        # 1. Buscar o registro no_show
        # Adicionado verificação para garantir que não foi transferido ainda
        registro_no_show = conn.execute('SELECT * FROM no_show WHERE id = ? AND finalizada = 0 AND cancelado = 0 AND transferred_to_registro_id IS NULL', (no_show_id,)).fetchone()

        if not registro_no_show:
            flash('Registro No-Show não encontrado, já finalizado, cancelado ou transferido.', 'error')
            print(f"DEBUG: /transferir_no_show_para_registro/{no_show_id} - Registro No-Show não encontrado, finalizado, cancelado ou transferido.")
            return redirect(url_for('registro_no_show'))

        # 2. Buscar registros ativos correspondentes na tabela registros
        # Buscamos por registros que não estão finalizados ou cancelados, com a mesma rota e tipo de entrega
        registros_correspondentes = conn.execute('''
            SELECT * FROM registros
            WHERE rota = ? AND tipo_entrega = ? AND finalizada = 0 AND cancelado = 0
            ORDER BY data_hora_login ASC -- Prioriza o mais antigo
        ''', (registro_no_show['rota'], registro_no_show['tipo_entrega'])).fetchall()
        print(f"DEBUG: /transferir_no_show_para_registro/{no_show_id} - Registros correspondentes encontrados: {len(registros_correspondentes)}")


        if not registros_correspondentes:
            flash(f'Nenhum registro ativo correspondente encontrado na fila de carregamento para a Rota "{registro_no_show["rota"]}" e Tipo de Entrega "{registro_no_show["tipo_entrega"]}".', 'warning')
            print(f"DEBUG: /transferir_no_show_para_registro/{no_show_id} - Nenhum registro correspondente encontrado.")
            return redirect(url_for('registro_no_show') + f'#no-show-registro-{no_show_id}')

        # 3. Lidar com múltiplos registros correspondentes (opcional, aqui pegamos o primeiro)
        if len(registros_correspondentes) > 1:
             registro_destino = registros_correspondentes[0]
             flash(f'Múltiplos registros ativos correspondentes encontrados. Transferindo para o registro mais antigo (ID: {registro_destino["id"]}).', 'info')
             print(f"DEBUG: /transferir_no_show_para_registro/{no_show_id} - Múltiplos encontrados. Usando o primeiro: ID {registro_destino['id']}.")
        else:
             registro_destino = registros_correspondentes[0]
             print(f"DEBUG: /transferir_no_show_para_registro/{no_show_id} - Usando registro de destino: ID {registro_destino['id']}.")


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
        print(f"DEBUG: /transferir_no_show_para_registro/{no_show_id} - Dados originais do registro de destino (ID {registro_destino['id']}) capturados.")
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
            print(f"DEBUG: /transferir_no_show_para_registro/{no_show_id} - Linhas atualizadas em 'registros': {rows_updated_registros}")

            if rows_updated_registros == 0:
                 # Isso pode acontecer se o registro de destino foi finalizado/cancelado por outra operação
                 flash(f'Falha ao atualizar o registro de carregamento (ID: {registro_destino["id"]}). Ele pode ter sido finalizado ou cancelado por outra ação.', 'warning')
                 print(f"DEBUG: /transferir_no_show_para_registro/{no_show_id} - Falha ao atualizar registro de carregamento. Nenhuma linha atualizada.")
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
            print(f"DEBUG: /transferir_no_show_para_registro/{no_show_id} - Linhas atualizadas em 'no_show': {rows_updated_no_show}")


            if rows_updated_no_show == 0:
                 # Isso não deveria acontecer se a primeira verificação passou, mas é uma segurança
                 flash(f'Falha ao marcar o registro No-Show (ID: {no_show_id}) como transferido. O estado do registro pode ter mudado.', 'warning')
                 print(f"DEBUG: /transferir_no_show_para_registro/{no_show_id} - Falha ao marcar No-Show como transferido. Nenhuma linha atualizada.")
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
            print(f"DEBUG: /transferir_no_show_para_registro/{no_show_id} - Transferência concluída.")

        except Exception as e:
            conn.rollback() # Desfaz a transação em caso de erro
            flash(f'Ocorreu um erro durante a transferência do registro: {e}', 'error')
            print(f"DEBUG: /transferir_no_show_para_registro/{no_show_id} - Erro durante a transferência: {e}")


    # Redirecionar de volta para a página de registros no_show
    print(f"DEBUG: /transferir_no_show_para_registro/{no_show_id} - Redirecionando para: {url_for('registro_no_show')}")
    return redirect(url_for('registro_no_show'))

# --- Nova rota para exibir o formulário de criação de registro No Show ---
@app.route('/associacao_no_show', methods=['GET'])
def associacao_no_show():
    """Exibe o formulário para criar um novo registro No Show."""
    print("DEBUG: /associacao_no_show - Rota acessada.")
    return render_template('associacao_no_show.html')

# --- Nova rota para lidar com a submissão do formulário de criação de registro No Show ---
# --- Nova rota para lidar com a submissão do formulário de criação de registro No Show ---
@app.route('/criar_registro_no_show', methods=['POST'])
def criar_registro_no_show():
    """
    Lida com a submissão do formulário e insere o registro na tabela no_show.
    Define em_separacao como 3 (Aguardando Motorista) ao criar.
    Retorna uma resposta JSON.
    """
    print("DEBUG: /criar_registro_no_show - Rota acessada (POST).")
    nome = request.form.get('nome', '').title()
    matricula = request.form.get('matricula', '').title()
    cidade_entrega = request.form.get('cidade_entrega', '').title()
    tipo_entrega = request.form.get('tipo_entrega', '').title()
    # Captura o valor do campo 'rota'
    rota_valor = request.form.get('rota', '').title()
    rua = request.form.get('rua', '').title()
    estacao = request.form.get('estacao', '').title()
    data_hora_login = get_data_hora_brasilia()

    print(f"DEBUG: /criar_registro_no_show - Dados do formulário: nome='{nome}', matricula='{matricula}', cidade_entrega='{cidade_entrega}', tipo_entrega='{tipo_entrega}', rota='{rota_valor}', rua='{rua}', estacao='{estacao}'")

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
            print(f"DEBUG: /criar_registro_no_show - Dados do usuário encontrados: login_id={login_id}, cpf='{cpf}', tipo_veiculo='{tipo_veiculo}'")
        else:
            # Se a matrícula não existir na tabela login, retorna JSON de erro
            print(f"DEBUG: /criar_registro_no_show - Erro: Matrícula {matricula} não encontrada.")
            return jsonify({'success': False, 'message': 'Matrícula não encontrada na base de usuários.'}), 400 # Retorna 400 Bad Request

    try:
        with get_db_connection() as conn:
            # Modifique a linha abaixo para inserir 3 em vez de 0 para em_separacao
            conn.execute('''
                INSERT INTO no_show (nome, matricula, rota, tipo_entrega, cidade_entrega,
                                     data_hora_login, cpf, tipo_veiculo, em_separacao, finalizada, login_id, rua, estacao, gaiola)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 3, 0, ?, ?, ?, ?) -- <--- MUDANÇA AQUI: 3 em vez de 0 para em_separacao
            ''', (nome, matricula, rota_valor, tipo_entrega, cidade_entrega, # Usa rota_valor para rota
                  data_hora_login, cpf, tipo_veiculo, login_id, rua, estacao, rota_valor)) # Usa rota_valor para gaiola
            conn.commit()
            print(f"DEBUG: /criar_registro_no_show - Novo registro No Show criado com sucesso com em_separacao = 3.")
            # Retorna JSON de sucesso
            return jsonify({'success': True, 'message': 'Registro No Show criado com sucesso!'})

    except Exception as e:
        conn.rollback() # Desfaz a transação em caso de erro
        print(f"DEBUG: /criar_registro_no_show - Erro ao criar registro No Show: {e}")
        # Retorna JSON de erro
        return jsonify({'success': False, 'message': f'Ocorreu um erro ao criar o registro No Show: {e}'}), 500 # Retorna 500 Internal Server Error


# --- Rota para exibir o menu principal ---
@app.route('/menu_principal')
def menu_principal():
    """Renderiza a página do menu principal."""
    print("DEBUG: /menu_principal - Rota acessada.")
    return render_template('menu_principal.html')
# Sua rota para servir a página midia.html
@app.route('/midia')
def exibir_midia():
    """Renderiza a página HTML com a exibição de mídia (vídeos e slides)."""
    print("DEBUG: Rota /midia acessada. Renderizando midia.html")
    return render_template('midia.html')

# --- Rota API para retornar registros 'no_show' aguardando motorista ---
@app.route('/api/noshow/aguardando-motorista', methods=['GET'])
def api_noshow_aguardando_motorista():
    """Retorna registros da tabela 'no_show' com status 'Aguardando Motorista'
     (em_separacao = 3) em JSON."""
    print("DEBUG: /api/noshow/aguardando-motorista - Rota acessada.")
    with get_db_connection() as conn:
        # Busca registros na tabela 'no_show' que estão 'Aguardando Motorista' (em_separacao = 3)
        # e que não foram finalizados, cancelados ou transferidos.
        registros_aguardando_motorista = conn.execute('''
            SELECT id, nome, matricula, rota, tipo_entrega, cidade_entrega, data_hora_login,
                   gaiola, estacao, cpf, rua, em_separacao, finalizada, cancelado, transferred_to_registro_id
            FROM no_show
            WHERE em_separacao = 3
              AND finalizada = 0
              AND cancelado = 0
              AND transferred_to_registro_id IS NULL
            ORDER BY data_hora_login ASC -- Opcional: ordena por data de login mais antiga
        ''').fetchall()

        # Converte os resultados (Row objects) para uma lista de dicionários para retornar como JSON
        no_show_list = [dict(row) for row in registros_aguardando_motorista]
        print(f"DEBUG: /api/noshow/aguardando-motorista - Registros encontrados: {len(no_show_list)}")

    return jsonify(no_show_list)
    

# --- Rota API para registros 'em separacao' ---
@app.route('/api/registros/em-separacao', methods=['GET'])
def api_registros_em_separacao():
    """Retorna registros da tabela 'registros' com status 'em separacao' (em_separacao = 1) em JSON."""
    print("DEBUG: /api/registros/em-separacao - Rota acessada.")
    with get_db_connection() as conn:
        # Busca registros na tabela 'registros' que estão 'em separacao' (em_separacao = 1)
        # e que não foram finalizados ou cancelados.
        registros_separacao = conn.execute('''
            SELECT id, nome, matricula, rota, tipo_entrega, cidade_entrega, data_hora_login,
                   gaiola, estacao, cpf, rua
            FROM registros
            WHERE em_separacao = 1 AND finalizada = 0 AND cancelado = 0
            ORDER BY data_hora_login ASC -- Opcional: ordena por data de login mais antiga
        ''').fetchall()

        # Converte os resultados (Row objects) para uma lista de dicionários para retornar como JSON
        registros_list = [dict(row) for row in registros_separacao]
        print(f"DEBUG: /api/registros/em-separacao - Registros encontrados: {len(registros_list)}")

    return jsonify(registros_list)


# --- Rota API para registros 'no_show' aguardando associação (original) ---
@app.route('/api/noshow/aguardando-associacao', methods=['GET'])
def api_noshow_aguardando_associacao():
    """Retorna registros da tabela 'no_show' aguardando associação em JSON."""
    print("DEBUG: /api/noshow/aguardando-associacao - Rota acessada.")
    with get_db_connection() as conn:
        # Busca registros na tabela 'no_show' que estão 'aguardando associação':
        # não tem gaiola/estacao associada, não está em separacao (0), finalizado (0),
        # cancelado (0) ou transferido (transferred_to_registro_id IS NULL).
        registros_no_show_aguardando = conn.execute('''
            SELECT id, nome, matricula, rota, tipo_entrega, cidade_entrega, data_hora_login,
                   gaiola, estacao, cpf, rua, transferred_to_registro_id
            FROM no_show
            WHERE gaiola IS NULL
              AND estacao IS NULL
              AND em_separacao = 0
              AND finalizada = 0
              AND cancelado = 0
              AND transferred_to_registro_id IS NULL
            ORDER BY data_hora_login ASC -- Opcional: ordena por data de login mais antiga
        ''').fetchall()

        # Converte os resultados (Row objects) para uma lista de dicionários para retornar como JSON
        no_show_list = [dict(row) for row in registros_no_show_aguardando]
        print(f"DEBUG: /api/noshow/aguardando-associacao - Registros encontrados: {len(no_show_list)}")

    return jsonify(no_show_list)

# --- Rota API para retornar TODOS os registros 'no_show' (para depuração) ---
@app.route('/api/noshow/todos', methods=['GET'])
def api_noshow_todos():
    """Retorna TODOS os registros da tabela 'no_show' em JSON (para depuração/verificação)."""
    print("DEBUG: /api/noshow/todos - Rota acessada.")
    with get_db_connection() as conn:
        # Busca TODOS os registros na tabela 'no_show'
        registros_no_show = conn.execute('''
            SELECT id, nome, matricula, rota, tipo_entrega, cidade_entrega, data_hora_login,
                   gaiola, estacao, cpf, rua, em_separacao, finalizada, cancelado, transferred_to_registro_id
            FROM no_show
            ORDER BY data_hora_login DESC -- Opcional: ordena por data de login mais recente
        ''').fetchall()

        # Converte os resultados (Row objects) para uma lista de dicionários para retornar como JSON
        no_show_list = [dict(row) for row in registros_no_show]
        print(f"DEBUG: /api/noshow/todos - Registros encontrados: {len(no_show_list)}")

    return jsonify(no_show_list)

# --- Rota API para retornar registros 'no_show' pendentes (MODIFICADA) ---
@app.route('/api/noshow/pendentes', methods=['GET'])
def api_noshow_pendentes():
    """
    Retorna registros da tabela 'no_show' que estão pendentes de associação inicial:
    em_separacao = 0 e hora_finalizacao IS NULL, não finalizado, cancelado ou transferido.
    """
    print("DEBUG: /api/noshow/pendentes - Rota acessada.")
    with get_db_connection() as conn:
        # Busca registros na tabela 'no_show' que estão pendentes de associação inicial:
        # em_separacao = 0, hora_finalizacao IS NULL, finalizada = 0, cancelado = 0, transferred_to_registro_id IS NULL.
        registros_no_show_pendentes = conn.execute('''
            SELECT id, nome, matricula, rota, tipo_entrega, cidade_entrega, data_hora_login,
                   gaiola, estacao, cpf, rua, em_separacao, finalizada, cancelado, transferred_to_registro_id
            FROM no_show
            WHERE em_separacao = 0
              AND hora_finalizacao IS NULL
              AND finalizada = 0
              AND cancelado = 0
              AND transferred_to_registro_id IS NULL
            ORDER BY data_hora_login ASC -- Opcional: ordena por data de login mais antiga
        ''').fetchall()

        # Converte os resultados (Row objects) para uma lista de dicionários para retornar como JSON
        no_show_list = [dict(row) for row in registros_no_show_pendentes]
        print(f"DEBUG: /api/noshow/pendentes - Registros encontrados: {len(no_show_list)}")

    return jsonify(no_show_list)

# ... (seu código Flask existente da parte 1 e parte 2 antes desta rota)

# ... (seu código Flask existente da parte 1 e parte 2)

# ... (seu código Flask existente antes desta rota)

@app.route('/api/no_show_aguardando_motorista', methods=['GET'])
def get_no_show_aguardando_motorista_api():
    """
    Retorna registros da tabela no_show com status que resultaria no rótulo
    'Aguardando Motorista' na página de listagem (o caso 'else'),
    no formato JSON. Inclui apenas ID, Rota e Rua.
    """
    print("DEBUG: /api/no_show_aguardando_motorista - Rota API acessada.")
    records = [] # Inicializa records como lista vazia antes do try
    try:
        with get_db_connection() as conn:
            print("DEBUG: Conexão com banco de dados estabelecida.")
            # Query ajustada para corresponder APENAS à lógica do rótulo 'Aguardando Motorista'
            # na página de listagem (o bloco '{% else %}') - REMOVE O FILTRO DE RUA AQUI
            cursor = conn.execute('''
                SELECT id, rota, rua
                FROM no_show
                WHERE finalizada = 0
                  AND cancelado = 0
                  AND em_separacao != 1
                  AND em_separacao != 2
                  AND em_separacao != 4
                -- O filtro de rua será feito no JavaScript
            ''')
            records = cursor.fetchall()
            print(f"DEBUG: Resultado fetchall() tipo: {type(records)}") # Log tipo do resultado da query
            print(f"DEBUG: Resultado fetchall() conteúdo: {records}") # Log conteúdo do resultado da query

        # Converter os resultados (sqlite3.Row) para uma lista de dicionários serializáveis
        # Esta linha só será executada se fetchall() não lançar exceção e records não for None
        records_list = [dict(row) for row in records]
        print(f"DEBUG: /api/no_show_aguardando_motorista - Registros encontrados (status Aguardando Motorista, qualquer rua): {len(records_list)}")
        print(f"DEBUG: Lista para jsonify: {records_list}") # Log a lista ANTES de converter para JSON

        return jsonify(records_list)

    except Exception as e:
        print(f"DEBUG: Erro na rota /api/no_show_aguardando_motorista: {e}")
        # Retorna um erro no formato JSON
        return jsonify({'error': 'Erro ao buscar dados no-show', 'message': str(e)}), 500

# ... (o restante do seu código Flask após esta rota)

# --- ROTA AJUSTADA PARA BUSCAR NOTÍCIAS DA CNN BRASIL ---
@app.route('/api/get_news_headlines', methods=['GET'])
def get_news_headlines():
    # URL do feed RSS da CNN Brasil
    # Verificado em 2025-05-15, mas URLs de feed podem mudar.
    # Se parar de funcionar, pode ser necessário buscar a nova URL do feed RSS da CNN Brasil.
    cnn_brasil_feed_url = 'https://www.cnnbrasil.com.br/feed/'

    all_headlines = []

    # --- Buscar notícias da CNN Brasil (usando RSS) ---
    try:
        print(f"DEBUG Flask: Buscando feed da CNN Brasil em: {cnn_brasil_feed_url}")
        feed = feedparser.parse(cnn_brasil_feed_url)

        if feed.entries:
            print(f"DEBUG Flask: Feed da CNN Brasil encontrado com {len(feed.entries)} entradas.")
            # Limita o número de manchetes da CNN Brasil (ex: as 5 mais recentes)
            for entry in feed.entries[:5]: # Pega as 5 primeiras manchetes
                # Pode adicionar formatação ou limpar o título se necessário
                headline = entry.title
                # Exemplo: remover HTML básico se houver (feedparser geralmente limpa)
                # from bs4 import BeautifulSoup
                # headline = BeautifulSoup(headline, 'html.parser').get_text()

                all_headlines.append(f"CNN Brasil: {headline}") # Adiciona prefixo

        else:
            all_headlines.append("CNN Brasil: Não foi possível carregar manchetes do feed.")
            print("DEBUG Flask: Feed da CNN Brasil não retornou entradas.")

    except Exception as e:
        print(f"DEBUG Flask: Erro ao buscar feed da CNN Brasil: {e}")
        all_headlines.append("CNN Brasil: Erro ao carregar notícias.")

    # --- Seção para outras fontes (como Shopee) ---
    # Mantenha ou remova esta seção dependendo se você quer incluir outras fontes aqui.
    # Se você remover, o letreiro superior só mostrará a CNN Brasil.
    # Se você quiser adicionar outras fontes, implemente a busca aqui e adicione
    # as manchetes à lista `all_headlines`.
    # ... (Seu código para buscar outras fontes, se houver) ...


    # Adiciona uma mensagem padrão caso nenhuma manchete tenha sido carregada com sucesso
    if not all_headlines or all(msg.startswith("CNN Brasil: Erro") for msg in all_headlines):
         all_headlines = ["Erro ao carregar notícias da CNN Brasil ou fontes indisponíveis."]
         print("DEBUG Flask: Nenhuma manchete válida da CNN Brasil coletada, retornando mensagem de erro/fallback.")


    # Retorna as manchetes em formato JSON
    return jsonify({"headlines": all_headlines})
# --- FIM DA ROTA AJUSTADA ---

if __name__ == '__main__':
    # Inicializa o banco de dados ao iniciar o aplicativo
    init_db()
    app.run(debug=True)
