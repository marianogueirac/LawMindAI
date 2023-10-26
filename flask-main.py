import openai
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import sqlite3
import json
from datetime import datetime

app = Flask(__name__)
CORS(app)

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
def chatbot_page():
    conn = sqlite3.connect('sessoes_usuarios.db')
    cursor = conn.cursor()
    cursor.execute("SELECT nome_sessao FROM sessoes")
    sessoes = cursor.fetchall()
    conn.close()
    return render_template('chatbot.html', sessoes=sessoes)


@app.route('/respond', methods=['GET'])
def chatbot():
    try:
        pergunta = request.args.get('pergunta')
        usuario_id = 1
        nome_sessao = "Sessao_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        data_hora = "2023-10-25 14:30:00"

        conn = sqlite3.connect('sessoes_usuarios.db')
        cursor = conn.cursor()

        # Recupere as mensagens da sessão atual (ou crie uma nova sessão)
        cursor.execute("SELECT id, mensagens FROM sessoes WHERE usuario_id = ? AND nome_sessao = ?",
                       (usuario_id, nome_sessao))
        registro = cursor.fetchone()

        if registro:
            # A sessão já existe, adicione a pergunta e a resposta à sessão
            sessao_id, mensagens_json = registro
            mensagens = json.loads(mensagens_json)
        else:
            # A sessão não existe, crie uma nova sessão
            cursor.execute("INSERT INTO sessoes (usuario_id, nome_sessao, data_hora, mensagens) VALUES (?, ?, ?, ?)",
                           (usuario_id, nome_sessao, data_hora, "[]"))
            conn.commit()
            sessao_id = cursor.lastrowid
            mensagens = []

        # Adicione a pergunta atual à sessão
        mensagens.append({"tipo": "pergunta", "texto": pergunta})

        # Concatene as mensagens para enviar ao modelo
        mensagens_concatenadas = "\n\n".join([msg["texto"] for msg in mensagens])

        resposta = mychat(mensagens_concatenadas)

        # Adicione a resposta à sessão
        mensagens.append({"tipo": "resposta", "texto": resposta})

        # Atualize a sessão no banco de dados com todas as mensagens
        cursor.execute("UPDATE sessoes SET mensagens = ? WHERE id = ?", (json.dumps(mensagens), sessao_id))
        conn.commit()
        conn.close()

    except Exception as e:
        resposta = 'Ops! Ocorreu um erro e não pude retornar a pergunta: {}'.format(e)

    return jsonify(resposta=resposta)

@app.route('/get_session', methods=['GET'])
def get_session():
    nome_sessao = request.args.get('nome_sessao')
    usuario_id = 1  # Substitua pelo ID do usuário real

    # Recupere a sessão do banco de dados
    conn = sqlite3.connect('sessoes_usuarios.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM sessoes WHERE usuario_id = ? AND nome_sessao = ?",
        (usuario_id, nome_sessao)
    )
    sessao = cursor.fetchone()

    # Se a sessão existe, retorne as mensagens
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

    # Se a sessão não existe, crie uma sessão vazia
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

if __name__ == '__main__':
    app.run(debug=True)