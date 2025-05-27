# routes/noshow_routes.py

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app, session
from models import db, NoShow, Registro # Importe seus modelos e db
from config import STATUS_EM_SEPARACAO, STATUS_REGISTRO_PRINCIPAL, get_data_hora_brasilia
from utils import formatar_texto_title

noshow_bp = Blueprint('noshow_bp', __name__)

@noshow_bp.route('/registro_no_show', methods=['GET'])
def registro_no_show():
    # Lógica de listagem e filtragem de registros NoShow
    # ... (Sua lógica de filtro e paginação para NoShow) ...
    # Exemplo:
    no_shows_query = NoShow.query
    no_shows = no_shows_query.order_by(NoShow.data_hora_login.desc()).all()

    return render_template('seus_templates_noshow.html', no_shows=no_shows)

@noshow_bp.route('/associacao_no_show', methods=['GET'])
def associacao_no_show():
    return render_template('associacao_no_show.html')

@noshow_bp.route('/criar_registro_no_show', methods=['POST'])
def criar_registro_no_show():
    if request.is_json:
        data = request.get_json()
    else:
        data = request.form

    nome = data.get('nome')
    matricula = data.get('matricula')
    tipo_entrega = data.get('tipo_entrega')
    rota = data.get('rota') # gaiola no modelo
    estacao = data.get('estacao')
    rua = data.get('rua')

    # Aplica a formatação title
    nome = formatar_texto_title(nome)
    tipo_entrega = formatar_texto_title(tipo_entrega)
    rota = formatar_texto_title(rota)
    estacao = formatar_texto_title(estacao)
    rua = formatar_texto_title(rua)

    if not all([nome, matricula, tipo_entrega, rota, estacao, rua]):
        return jsonify({'success': False, 'message': 'Todos os campos obrigatórios devem ser preenchidos.'}), 400

    if not (rua.isdigit() and 1 <= int(rua) <= 9):
        return jsonify({'success': False, 'message': 'O campo "Rua" deve ser um dígito de 1 a 9.'}), 400

    try:
        novo_registro = NoShow(
            data_hora_login=get_data_hora_brasilia(),
            nome=nome,
            matricula=matricula,
            gaiola=rota,
            tipo_entrega=tipo_entrega,
            rua=rua,
            estacao=estacao,
            finalizada=0,
            cancelado=0,
            em_separacao=STATUS_EM_SEPARACAO['AGUARDANDO_MOTORISTA'] # Define o status inicial
        )
        db.session.add(novo_registro)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Registro No Show criado com sucesso!'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Erro ao criar registro No Show: {e}")
        return jsonify({'success': False, 'message': f'Erro interno ao criar registro: {str(e)}'}), 500

@noshow_bp.route('/transferir_no_show_para_registro/<int:no_show_id>', methods=['POST'])
def transferir_no_show_para_registro(no_show_id):
    # Sua lógica de transferência de NoShow para Registro
    # (Copie e cole aqui a lógica da rota /transferir_no_show_para_registro do app.py original)
    # Lembre-se de importar o modelo Registro se precisar dele aqui

    # ... (Seu código existente da rota /transferir_no_show_para_registro aqui) ...
    
    data_hora_transferencia = get_data_hora_brasilia()
    try:
        registro_no_show = NoShow.query.filter(
            NoShow.id == no_show_id,
            NoShow.finalizada == 0,
            NoShow.cancelado == 0,
            NoShow.em_separacao != STATUS_EM_SEPARACAO['TRANSFERIDO'],
            NoShow.transferred_to_registro_id.is_(None)
        ).first()

        if not registro_no_show:
            flash('Registro No-Show não encontrado, já finalizado, cancelado ou transferido.', 'error')
            return redirect(url_for('noshow_bp.registro_no_show'))

        registros_correspondentes = Registro.query.filter(
            Registro.rota == registro_no_show.gaiola,
            Registro.tipo_entrega == registro_no_show.tipo_entrega,
            Registro.finalizada == 0,
            Registro.cancelado == 0,
            Registro.status != STATUS_REGISTRO_PRINCIPAL['FINALIZADO'],
            Registro.status != STATUS_REGISTRO_PRINCIPAL['CANCELADO']
        ).order_by(Registro.data_hora_login.asc()).all()

        if not registros_correspondentes:
            flash(f'Nenhum registro ativo correspondente encontrado na fila de carregamento para a Rota "{registro_no_show.gaiola}" e Tipo de Entrega "{registro_no_show.tipo_entrega}". Criando um novo registro principal.', 'warning')
            
            # Criar um novo registro principal se não encontrar um correspondente
            novo_registro_principal = Registro(
                nome=formatar_texto_title(no_show_original.nome),
                matricula=no_show_original.matricula,
                data_hora_login=get_data_hora_brasilia(),
                rota=formatar_texto_title(no_show_original.gaiola),
                tipo_entrega=formatar_texto_title(no_show_original.tipo_entrega),
                cidade_entrega='Não Aplicável',
                rua=formatar_texto_title(no_show_original.rua),
                estacao=formatar_texto_title(no_show_original.estacao),
                status=STATUS_REGISTRO_PRINCIPAL['FINALIZADO'],
                finalizada=1,
                em_separacao=STATUS_EM_SEPARACAO['TRANSFERIDO']
            )
            db.session.add(novo_registro_principal)
            registro_destino = novo_registro_principal
        else:
            registro_destino = registros_correspondentes[0]
            if len(registros_correspondentes) > 1:
                flash(f'Múltiplos registros ativos correspondentes encontrados. Transferindo para o registro mais antigo (ID: {registro_destino.id}).', 'info')

        # Capture original data from registro_destino BEFORE updating it
        registro_no_show.transfer_nome_motorista = registro_destino.nome
        registro_no_show.transfer_matricula_motorista = registro_destino.matricula
        registro_no_show.transfer_cidade_entrega = registro_destino.cidade_entrega
        registro_no_show.transfer_tipo_veiculo = registro_destino.tipo_veiculo if hasattr(registro_destino, 'tipo_veiculo') else None
        registro_no_show.transfer_login_id = registro_destino.login_id if hasattr(registro_destino, 'login_id') else None
        registro_no_show.transfer_gaiola_origem = registro_destino.rota
        registro_no_show.transfer_estacao_origem = registro_destino.estacao
        registro_no_show.transfer_rua_origem = registro_destino.rua
        registro_no_show.transfer_data_hora_login_origem = registro_destino.data_hora_login

        # Transferir dados (atualizar o registro em 'registros')
        registro_destino.rota = formatar_texto_title(registro_no_show.gaiola)
        registro_destino.estacao = formatar_texto_title(registro_no_show.estacao)
        registro_destino.rua = formatar_texto_title(registro_no_show.rua)
        registro_destino.status = STATUS_REGISTRO_PRINCIPAL['FINALIZADO']
        registro_destino.finalizada = 1
        registro_destino.hora_finalizacao = data_hora_transferencia
        registro_destino.em_separacao = STATUS_EM_SEPARACAO['TRANSFERIDO']

        # Marcar o registro no_show como TRANSFERIDO e vincular ao registro de destino
        registro_no_show.finalizada = 1
        registro_no_show.cancelado = 0
        registro_no_show.em_separacao = STATUS_EM_SEPARACAO['TRANSFERIDO']
        registro_no_show.hora_finalizacao = data_hora_transferencia
        registro_no_show.transferred_to_registro_id = registro_destino.id

        db.session.add(registro_destino)
        db.session.add(registro_no_show)
        db.session.commit()

        flash(f'Dados do registro No-Show (ID: {no_show_id}) transferidos com sucesso para o registro de carregamento (ID: {registro_destino.id}). O registro de carregamento foi FINALIZADO. O registro No-Show foi marcado como TRANSFERIDO.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Ocorreu um erro durante a transferência do registro: {str(e)}', 'error')

    return redirect(url_for('noshow_bp.registro_no_show', _anchor=f'no-show-registro-{no_show_id}',
                             data=request.args.get('data'),
                             nome=request.args.get('nome'),
                             matricula=request.args.get('matricula'),
                             rota=request.args.get('rota'),
                             status=request.args.get('status')))

# Outras rotas relacionadas a NoShow, como atualizar_status_no_show, associar_no_show,
# dessociar_no_show, finalizar_carregamento_no_show_id_status_separacao
# (se você mantiver essa) devem ser movidas para este arquivo.