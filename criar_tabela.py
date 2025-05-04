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
            tipo_veiculo TEXT,
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

    conn.commit()
    conn.close()
    print("Banco de dados e tabelas criadas com sucesso!")

# Executa a criação das tabelas
if __name__ == '__main__':
    criar_tabelas()
