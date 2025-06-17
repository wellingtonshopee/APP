# forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField, SelectMultipleField
from wtforms.validators import DataRequired, Email, EqualTo, ValidationError, Length, Optional
from wtforms.widgets import ListWidget, CheckboxInput

# Importe apenas as classes de modelo necessárias para os formulários
from models import User, Permissao, Etapa, SituacaoPedido, Login # Certifique-se de que todas as classes usadas em formulários estão aqui

# --- Campos Personalizados ---

# Campo customizado para múltiplas checkboxes (útil para as páginas de acesso de permissões)
class MultiCheckboxField(SelectMultipleField):
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()

# --- Classes de Formulário ---

class SistemaLoginForm(FlaskForm):
    """Formulário para login de usuários."""
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Senha', validators=[DataRequired()])
    remember = BooleanField('Lembrar-me')
    submit = SubmitField('Entrar')

class CadastroUsuarioForm(FlaskForm):
    """Formulário para o registro de novos usuários."""
    username = StringField('Nome de Usuário', validators=[DataRequired(), Length(min=2, max=64, message="O nome de usuário deve ter entre 2 e 64 caracteres.")])
    email = StringField('Email', validators=[DataRequired(), Email(message="Email inválido.")])
    password = PasswordField('Senha', validators=[DataRequired(), Length(min=6, message="A senha deve ter pelo menos 6 caracteres.")])
    confirm_password = PasswordField('Confirme a Senha', validators=[DataRequired(), EqualTo('password', message='As senhas devem ser iguais!')])
    matricula = StringField('Matrícula', validators=[DataRequired(), Length(max=20, message="A matrícula não pode exceder 20 caracteres.")])
    nome_completo = StringField('Nome Completo', validators=[DataRequired(), Length(max=100, message="O nome completo não pode exceder 100 caracteres.")])
    is_admin = BooleanField('É Administrador?')
    
    # === CORREÇÃO AQUI: MUDAR coerce=int PARA coerce=str ===
    paginas_acesso = MultiCheckboxField('Acesso às Páginas', coerce=str) 
    
    submit = SubmitField('Cadastrar Usuário')

    # Validadores personalizados para verificar se email/matricula/username já existem no DB
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first() 
        if user:
            raise ValidationError('Este nome de usuário já está em uso. Por favor, escolha outro.')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Este email já está cadastrado. Por favor, escolha outro.')

    def validate_matricula(self, matricula):
        user = User.query.filter_by(matricula=matricula.data).first()
        if user:
            raise ValidationError('Esta matrícula já está em uso. Por favor, escolha outra.')


class EditarUsuarioForm(FlaskForm):
    """Formulário para edição de usuários existentes."""
    username = StringField('Nome de Usuário', validators=[DataRequired(), Length(min=2, max=64, message="O nome de usuário deve ter entre 2 e 64 caracteres.")])
    email = StringField('Email', validators=[DataRequired(), Email(message="Email inválido.")])
    
    # Campos de senha tornados OPCIONAIS para edição.
    # A validação 'EqualTo' só é ativada se 'password' for preenchido.
    password = PasswordField(
        'Nova Senha (deixe em branco para não alterar)', 
        validators=[Optional(), Length(min=6, message='A senha deve ter pelo menos 6 caracteres se alterada.')]
    )
    confirm_password = PasswordField(
        'Confirme a Nova Senha', 
        validators=[Optional(), EqualTo('password', message='As senhas devem ser iguais!')]
    )

    matricula = StringField('Matrícula', validators=[Optional(), Length(max=20, message="A matrícula não pode exceder 20 caracteres.")])
    nome_completo = StringField('Nome Completo', validators=[Optional(), Length(max=100, message="O nome completo não pode exceder 100 caracteres.")])
    ativo = BooleanField('Usuário Ativo?')
    is_admin = BooleanField('É Administrador?')
    
    # === CORREÇÃO AQUI: MUDAR coerce=int PARA coerce=str ===
    paginas_acesso = MultiCheckboxField('Acesso às Páginas', coerce=str) 
    
    submit = SubmitField('Atualizar Usuário')

    # Construtor para passar valores originais para validação de unicidade
    def __init__(self, original_username=None, original_email=None, original_matricula=None, *args, **kwargs):
        super(EditarUsuarioForm, self).__init__(*args, **kwargs)
        self.original_username = original_username
        self.original_email = original_email
        self.original_matricula = original_matricula

    # Validadores personalizados para garantir unicidade ao editar (ignorando o próprio usuário)
    def validate_username(self, username):
        if username.data != self.original_username:
            user = User.query.filter_by(username=username.data).first()
            if user:
                raise ValidationError('Este nome de usuário já está em uso. Por favor, escolha outro.')

    def validate_email(self, email):
        if email.data != self.original_email:
            user = User.query.filter_by(email=email.data).first()
            if user:
                raise ValidationError('Este email já está registrado. Por favor, use outro.')

    def validate_matricula(self, matricula):
        if matricula.data != self.original_matricula:
            user = User.query.filter_by(matricula=matricula.data).first()
            if user:
                raise ValidationError('Esta matrícula já está em uso. Por favor, escolha outra.')


class NovaSenhaForm(FlaskForm):
    """Formulário para redefinição de senha."""
    password = PasswordField('Nova Senha', validators=[DataRequired(), Length(min=6, message="A senha deve ter pelo menos 6 caracteres.")])
    confirm_password = PasswordField('Confirmar Nova Senha', validators=[DataRequired(), EqualTo('password', message='As senhas devem ser iguais!')])
    submit = SubmitField('Definir Nova Senha')

# --- Outros Formulários (Exemplos, ajuste conforme o seu projeto) ---

class RegistroForm(FlaskForm):
    """Formulário para registrar entradas de registro."""
    nome = StringField('Nome', validators=[DataRequired()])
    matricula = StringField('Matrícula', validators=[DataRequired()])
    rota = StringField('Rota', validators=[DataRequired()])
    tipo_entrega = StringField('Tipo de Entrega', validators=[DataRequired()])
    cidade_entrega = StringField('Cidade de Entrega', validators=[DataRequired()])
    rua = StringField('Rua', validators=[DataRequired()])
    estacao = StringField('Estação', validators=[DataRequired()])
    tipo_veiculo = StringField('Tipo de Veículo')
    gaiola = StringField('Gaiola', validators=[Optional()])
    quantidade_pacotes = StringField('Quantidade de Pacotes', validators=[Optional()]) # Pode ser IntField
    data_de_entrega = StringField('Data de Entrega (DD/MM/AAAA)', validators=[Optional()]) # Pode ser DateField
    submit = SubmitField('Salvar Registro')

class NoShowForm(FlaskForm):
    """Formulário para registrar no-shows."""
    nome = StringField('Nome', validators=[DataRequired()])
    matricula = StringField('Matrícula', validators=[DataRequired()])
    gaiola = StringField('Gaiola', validators=[DataRequired()])
    tipo_entrega = StringField('Tipo de Entrega', validators=[DataRequired()])
    rua = StringField('Rua', validators=[DataRequired()])
    estacao = StringField('Estação', validators=[DataRequired()])
    submit = SubmitField('Registrar No-Show')

class TransferirNoShowForm(FlaskForm):
    """Formulário para transferir um no-show para um registro."""
    nome_motorista = StringField('Nome do Motorista Recebedor', validators=[DataRequired()])
    matricula_motorista = StringField('Matrícula do Motorista Recebedor', validators=[DataRequired()])
    cidade_entrega = StringField('Cidade de Entrega do Recebedor', validators=[DataRequired()])
    tipo_veiculo = StringField('Tipo de Veículo do Recebedor', validators=[DataRequired()])
    submit = SubmitField('Transferir No-Show')

class EditarRegistroForm(FlaskForm):
    """Formulário para editar um registro existente."""
    nome = StringField('Nome', validators=[DataRequired()])
    matricula = StringField('Matrícula', validators=[DataRequired()])
    rota = StringField('Rota', validators=[DataRequired()])
    tipo_entrega = StringField('Tipo de Entrega', validators=[DataRequired()])
    cidade_entrega = StringField('Cidade de Entrega', validators=[DataRequired()])
    rua = StringField('Rua', validators=[DataRequired()])
    estacao = StringField('Estação', validators=[DataRequired()])
    tipo_veiculo = StringField('Tipo de Veículo')
    gaiola = StringField('Gaiola', validators=[Optional()])
    quantidade_pacotes = StringField('Quantidade de Pacotes', validators=[Optional()])
    data_de_entrega = StringField('Data de Entrega (DD/MM/AAAA)', validators=[Optional()])
    
    # Supondo que você tenha campos para Etapa e Situação do Pedido
    etapa_id = SelectMultipleField('Etapa', coerce=int, validators=[Optional()])
    situacao_pedido_id = SelectMultipleField('Situação do Pedido', coerce=int, validators=[Optional()])
    
    submit = SubmitField('Atualizar Registro')

    def __init__(self, *args, **kwargs):
        super(EditarRegistroForm, self).__init__(*args, **kwargs)
        # Popule as choices para Etapa e SituacaoPedido dinamicamente
        self.etapa_id.choices = [(e.id, e.nome_etapa) for e in Etapa.query.order_by(Etapa.nome_etapa).all()]
        self.situacao_pedido_id.choices = [(s.id, s.nome_situacao) for s in SituacaoPedido.query.order_by(SituacaoPedido.nome_situacao).all()]

class EditarNoShowForm(FlaskForm):
    """Formulário para editar um no-show existente."""
    nome = StringField('Nome', validators=[DataRequired()])
    matricula = StringField('Matrícula', validators=[DataRequired()])
    gaiola = StringField('Gaiola', validators=[DataRequired()])
    tipo_entrega = StringField('Tipo de Entrega', validators=[DataRequired()])
    rua = StringField('Rua', validators=[DataRequired()])
    estacao = StringField('Estação', validators=[DataRequired()])
    submit = SubmitField('Atualizar No-Show')

class LoginCadastroForm(FlaskForm): # Assumi que este seria para o formulário de login original, antes de SistemaLoginForm
    """Formulário genérico para login e cadastro (se você o usar)."""
    nome = StringField('Nome', validators=[DataRequired()])
    matricula = StringField('Matrícula', validators=[DataRequired()])
    tipo_veiculo = StringField('Tipo de Veículo', validators=[Optional()])
    submit = SubmitField('Salvar Login')
