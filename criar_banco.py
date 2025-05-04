import sqlite3

# Conectar ao banco de dados SQLite
def conectar_banco():
    return sqlite3.connect('dados.db')

# Criar tabelas no banco de dados
def criar_tabelas():
    conn = conectar_banco()
    cursor = conn.cursor()

    # Criando a tabela de registros
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            matricula TEXT,
            rota TEXT,
            tipo_entrega TEXT,
            tipo_veiculo TEXT,       -- << ADICIONE ESTA LINHA
            data_hora_login DATETIME,
            gaiola TEXT,
            estacao TEXT,
            cpf TEXT NOT NULL
        )
    ''')

    # Criando a tabela de histórico
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            registro_id INTEGER,
            acao TEXT,
            gaiola TEXT,
            estacao TEXT,
            data_hora DATETIME,
            FOREIGN KEY (registro_id) REFERENCES registros(id)
        )
    ''')

    # Verificando se a coluna 'tipo_veiculo' já existe, e caso contrário, adicionando
    try:
        cursor.execute('ALTER TABLE registros ADD COLUMN tipo_veiculo TEXT')
        print("Coluna 'tipo_veiculo' adicionada com sucesso!")
    except sqlite3.OperationalError:
        print("A coluna 'tipo_veiculo' já existe na tabela 'registros'.")

    # Verificando se a coluna 'cpf' já existe, e caso contrário, adicionando
    try:
        cursor.execute('ALTER TABLE registros ADD COLUMN cpf TEXT NOT NULL')
        print("Coluna 'cpf' adicionada com sucesso!")
    except sqlite3.OperationalError:
        print("A coluna 'cpf' já existe na tabela 'registros'.")

    conn.commit()
    conn.close()

# Executa a criação das tabelas
if __name__ == '__main__':
    criar_tabelas()
    print("Tabelas criadas com sucesso!")
