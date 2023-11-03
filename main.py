from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_session import Session
import fitz  
import openai
from flask_cors import CORS
import sqlite3


app = Flask(__name__)
CORS(app)

# Defina uma chave secreta para a sessão (substitua 'sua_chave_secreta' por uma chave segura)
app.secret_key = 'sua_chave_secreta'
login_manager = LoginManager()
login_manager.login_view = "login"  # Define a rota para o login
login_manager.init_app(app)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = 5  # Define o tempo em segundos (por exemplo, 5 segundos)
Session(app)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Define o limite de tamanho de arquivo (aqui, 16 MB)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Define o tempo limite de solicitação (aqui, sem tempo limite)

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    # Consulta o banco de dados para carregar o usuário com base no ID
    conn = sqlite3.connect('sessoes_usuarios.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM usuarios WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return User(user[0])
    return None
def mychat(prompt):
    openai.api_key = "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"
    completion = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[
    {"role": "system", "content": "You are a helpful PDF Reader and a Chatbot"},
    {"role": "user", "content": prompt}
  ]
)
    print(completion)
    return completion.choices[0].message.content

@app.route('/')
def homepage():
    return render_template('hometext.html')

@app.route('/register', methods=['POST'])
def register():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']

        # Verifica se o nome de usuário ou e-mail já existem no banco de dados
        conn = sqlite3.connect('sessoes_usuarios.db')
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM usuarios WHERE nome = ? OR email = ?", (nome, email))
        existing_user = cursor.fetchone()

        if existing_user:
            # O nome de usuário ou e-mail já existe
            flash('Nome de usuário ou e-mail já está em uso. Escolha outro.', 'danger')
            conn.close()
        else:
            # Nome de usuário e e-mail são únicos, crie um novo registro no banco de dados
            senha_hash = generate_password_hash(senha)  # Criptografa a senha
            cursor.execute("INSERT INTO usuarios (nome, email, senha) VALUES (?, ?, ?)", (nome, email, senha_hash))
            conn.commit()
            conn.close()

            flash('Registrado com sucesso!', 'success')
            return redirect(url_for('homepage'))

    return render_template('homepage.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nome_de_usuario = request.form['nome_de_usuario']
        senha = request.form['senha']

        conn = sqlite3.connect('sessoes_usuarios.db')
        cursor = conn.cursor()

        # Consulta o banco de dados para encontrar o usuário com o nome de usuário fornecido
        cursor.execute("SELECT id, nome, email, senha FROM usuarios WHERE nome = ?", (nome_de_usuario,))
        usuario = cursor.fetchone()
        conn.close()

        if usuario:
            # O usuário foi encontrado, verifica a senha
            if check_password_hash(usuario[3], senha):  # O terceiro elemento é a senha criptografada
                # Autenticação bem-sucedida, cria uma sessão para o usuário
                login_user(User(usuario[0]))
                flash('Login bem-sucedido!', 'success')
                return redirect(url_for('chatbot_page'))
            else:
                flash('Credenciais inválidas, tente novamente.',
                      'danger')  # Esta mensagem é exibida em caso de senha incorreta.
        # Se o usuário não for encontrado ou as credenciais estiverem incorretas
        flash('Credenciais inválidas, tente novamente.', 'danger')

    return render_template('homepage.html')

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('Você saiu com sucesso!', 'success')
    return redirect(url_for('homepage'))

@app.route('/chatbot')
def chatbot_page():
    conn = sqlite3.connect('sessoes_usuarios.db')
    cursor = conn.cursor()
    cursor.execute("SELECT nome_sessao FROM sessoes")
    sessoes = cursor.fetchall()
    conn.close()
    return render_template('chatbot.html', sessoes=sessoes)

@app.route('/upload', methods=['POST', 'GET'])
def upload_file():
    pdf_text = ""
    error_message = ""

    if request.method == 'POST':
        file = request.files['file']

        if file:
            pdf_text = convert_pdf_from_memory(file)
        else:
            error_message = "Nenhum arquivo enviado"

    return jsonify(pdf_text=pdf_text, error_message=error_message)


@app.route('/respond', methods=['GET'])
def chatbot():
    try:
        pergunta = request.args.get('pergunta')
        resposta = mychat(pergunta)

    except Exception as e:
        resposta = 'Ops! Ocorreu um erro e não pude retornar a pergunta: {}'.format(e)

    return jsonify(resposta=resposta)

def convert_pdf_from_memory(pdf_file):
    # Abra o arquivo PDF diretamente da memória
    pdf_bytes = pdf_file.read()
    pdf_document = fitz.open("pdf", pdf_bytes)

    pdf_text = ""
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        pdf_text += page.get_text()

    return pdf_text

if __name__ == '__main__':
    app.run(debug=True)


