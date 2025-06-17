-- init_db.sql

-- Desabilitar a verificação de chave estrangeira temporariamente para permitir a exclusão de tabelas em qualquer ordem
PRAGMA foreign_keys = OFF;

-- Remover tabelas existentes (se houver) para garantir um estado limpo
DROP TABLE IF EXISTS usuario_permissoes;
DROP TABLE IF EXISTS usuario;
DROP TABLE IF EXISTS permissao;
-- Adicione aqui outras tabelas que você queira remover e recriar, por exemplo:
-- DROP TABLE IF EXISTS registro;
-- DROP TABLE IF EXISTS noshow;
-- DROP TABLE IF EXISTS etapa;
-- DROP TABLE IF EXISTS cidade;
-- DROP TABLE IF EXISTS situacaopedido;
-- DROP TABLE IF EXISTS pacoterastreado;
-- DROP TABLE IF EXISTS logatividade;


-- Habilitar a verificação de chave estrangeira novamente
PRAGMA foreign_keys = ON;


-- Criar a tabela 'usuario'
CREATE TABLE usuario (
    id INTEGER NOT NULL,
    username VARCHAR(64) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(128) NOT NULL,
    matricula VARCHAR(20) UNIQUE,
    nome_completo VARCHAR(100),
    is_admin BOOLEAN DEFAULT (0), -- 0 para False, 1 para True
    ativo BOOLEAN DEFAULT (1),   -- 0 para False, 1 para True
    PRIMARY KEY (id)
);

-- Criar a tabela 'permissao'
CREATE TABLE permissao (
    id INTEGER NOT NULL,
    nome_pagina VARCHAR(80) NOT NULL UNIQUE,
    descricao VARCHAR(200),
    PRIMARY KEY (id)
);

-- Criar a tabela de associação 'usuario_permissoes'
CREATE TABLE usuario_permissoes (
    usuario_id INTEGER NOT NULL,
    permissao_id INTEGER NOT NULL,
    PRIMARY KEY (usuario_id, permissao_id),
    FOREIGN KEY (usuario_id) REFERENCES usuario(id),
    FOREIGN KEY (permissao_id) REFERENCES permissao(id)
);

-- Inserir permissões padrão
INSERT INTO permissao (nome_pagina, descricao) VALUES
('painel_gerencial', 'Acesso ao painel principal de entregas.'),
('pacotes_rota', 'Gerenciar pacotes e importações.'),
('dashboard', 'Visualizar o dashboard de métricas.'),
('gerenciar_usuarios', 'Acesso para gerenciar usuários e permissões.');
-- Adicione mais permissões conforme necessário


-- Inserir usuário administrador (senha 'Admin@123' hasheada)
INSERT INTO usuario (username, email, password_hash, matricula, nome_completo, is_admin, ativo) VALUES
('admin', 'admin@sysspx.com', 'scrypt:32768:8:1$y6yVlU4wM6LY9FW1$fe97fad8fcac80119c0f434a0cca35bbe92cacbede98a5150069ffc626c0ad4867099454b163ff659bb758ba255f204d9dc6d8ef3720aaf68d31e08e090cdddb', '0001', 'Administrador Sistema', 1, 1);


-- Inserir usuário comum (senha 'User@123' hasheada)
INSERT INTO usuario (username, email, password_hash, matricula, nome_completo, is_admin, ativo) VALUES
('usuario_comum', 'comum@sysspx.com', 'scrypt:32768:8:1$HKNEyBUyAB7g0hdb$0cf4616c5eae83ef47bd198a4c9cb1e7f01c01caa2873f81be6a73b2209994da3cc73f9820af3ac23036e66c112e694e2f639b4a4890401172c373942ae5aaa4', '0002', 'Usuário Padrão', 0, 1);


-- Associar permissões ao 'usuario_comum'
INSERT INTO usuario_permissoes (usuario_id, permissao_id) VALUES
((SELECT id FROM usuario WHERE username = 'usuario_comum'), (SELECT id FROM permissao WHERE nome_pagina = 'pacotes_rota')),
((SELECT id FROM usuario WHERE username = 'usuario_comum'), (SELECT id FROM permissao WHERE nome_pagina = 'dashboard'));