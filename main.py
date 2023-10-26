from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session
from werkzeug.security import check_password_hash, generate_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_session import Session
import fitz  
import openai
from flask_cors import CORS
import sqlite3
import json
from datetime import datetime

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
    response = openai.Completion.create(
        model="text-davinci-003",
        prompt=prompt,
        max_tokens=2048,
        temperature=0.10,
        top_p=0,
    )
    return response.choices[0].text

@app.route('/')
def homepage():
    return render_template('homepage.html')

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

    return render_template('chatbot.html', pdf_text=pdf_text, error_message=error_message)


@app.route('/respond', methods=['GET'])
def chatbot():
    try:
        pergunta = request.args.get('pergunta')
        usuario_id = 1
        nome_sessao = "Sessao_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        data_hora = "2023-10-25 14:30:00"

        conn = sqlite3.connect('sessoes_usuarios.db')
        cursor = conn.cursor()

        # Recupera as mensagens da sessão atual (ou cria uma nova sessão)
        cursor.execute("SELECT id, mensagens FROM sessoes WHERE usuario_id = ? AND nome_sessao = ?",
                       (usuario_id, nome_sessao))
        registro = cursor.fetchone()

        if registro:
            # A sessão já existe, adiciona a pergunta e a resposta à sessão
            sessao_id, mensagens_json = registro
            mensagens = json.loads(mensagens_json)
        else:
            # A sessão não existe, cria uma nova sessão
            cursor.execute("INSERT INTO sessoes (usuario_id, nome_sessao, data_hora, mensagens) VALUES (?, ?, ?, ?)",
                           (usuario_id, nome_sessao, data_hora, "[]"))
            conn.commit()
            sessao_id = cursor.lastrowid
            mensagens = []

        # Adiciona a pergunta atual à sessão
        mensagens.append({"tipo": "pergunta", "texto": pergunta})

        # Concatena as mensagens para enviar ao modelo
        mensagens_concatenadas = "\n\n".join([msg["texto"] for msg in mensagens])

        resposta = mychat(mensagens_concatenadas)

        # Adiciona a resposta à sessão
        mensagens.append({"tipo": "resposta", "texto": resposta})

        # Atualiza a sessão no banco de dados com todas as mensagens
        cursor.execute("UPDATE sessoes SET mensagens = ? WHERE id = ?", (json.dumps(mensagens), sessao_id))
        conn.commit()
        conn.close()

    except Exception as e:
        resposta = 'Ops! Ocorreu um erro e não pude retornar a pergunta: {}'.format(e)

    return jsonify(resposta=resposta)

@app.route('/get_session', methods=['GET'])
def get_session():
    nome_sessao = request.args.get('nome_sessao')
    usuario_id = 1  # Substitue pelo ID do usuário real

    # Recupera a sessão do banco de dados
    conn = sqlite3.connect('sessoes_usuarios.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM sessoes WHERE usuario_id = ? AND nome_sessao = ?",
        (usuario_id, nome_sessao)
    )
    sessao = cursor.fetchone()

    # Se a sessão existe, retorna as mensagens
    if sessao:
        cursor.execute(
            "SELECT tipo, texto FROM mensagens WHERE sessao_id = ?",
            (sessao[0],)
        )
        mensagens = cursor.fetchall()

        sessao_completa = {
            "nome_sessao": sessao[3],
            "mensagens": [{"tipo": msg[0], "texto": msg[1]} for msg in mensagens]
        }
        return jsonify(sessao=sessao_completa)
    # Se a sessão não existe, cria uma sessão vazia
    nova_sessao = {"nome_sessao": nome_sessao, "mensagens": []}
    return jsonify(sessao=nova_sessao)

@app.route('/get_sessions')
def get_sessions():
    conn = sqlite3.connect('sessoes_usuarios.db')
    cursor = conn.cursor()
    cursor.execute("SELECT nome_sessao FROM sessoes")
    sessoes = [sessao[0] for sessao in cursor.fetchall()]
    conn.close()
    return jsonify(sessoes=sessoes)

def convert_pdf_to_text(pdf_file_path):
    pdf_document = fitz.open(pdf_file_path)
    pdf_text = ""
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        pdf_text += page.get_text()
    return pdf_text
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


