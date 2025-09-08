from flask import Flask, render_template, request, jsonify, session
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import uuid
import json
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

def get_db_connection():
    """Establece conexión con la base de datos MySQL"""
    try:
        connection = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DATABASE,
            port=Config.MYSQL_PORT
        )
        return connection
    except Error as e:
        print(f"Error conectando a MySQL: {e}")
        return None

def init_database():
    """Inicializa la base de datos si no existe"""
    try:
        connection = mysql.connector.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            port=Config.MYSQL_PORT
        )
        
        cursor = connection.cursor()
        
        # Crear base de datos si no existe
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.MYSQL_DATABASE}")
        cursor.execute(f"USE {Config.MYSQL_DATABASE}")
        
        # Crear tablas
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_message TEXT NOT NULL,
                bot_response TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                session_id VARCHAR(255) NOT NULL UNIQUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                session_id VARCHAR(255) NOT NULL,
                message_type ENUM('user', 'bot') NOT NULL,
                message_text TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        connection.commit()
        cursor.close()
        connection.close()
        print("Base de datos inicializada correctamente")
        
    except Error as e:
        print(f"Error inicializando base de datos: {e}")

def save_message(session_id, message_type, message_text):
    """Guarda un mensaje en la base de datos"""
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO messages (session_id, message_type, message_text) VALUES (%s, %s, %s)",
                (session_id, message_type, message_text)
            )
            connection.commit()
            cursor.close()
            connection.close()
            return True
        except Error as e:
            print(f"Error guardando mensaje: {e}")
            return False
    return False

def get_chat_history(session_id):
    """Obtiene el historial de chat de una sesión"""
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(
                "SELECT message_type, message_text, timestamp FROM messages WHERE session_id = %s ORDER BY timestamp ASC",
                (session_id,)
            )
            messages = cursor.fetchall()
            cursor.close()
            connection.close()
            return messages
        except Error as e:
            print(f"Error obteniendo historial: {e}")
            return []
    return []

def process_message(user_message):
    """Procesa el mensaje del usuario y genera una respuesta"""
    # Lógica simple del chatbot - puedes expandir esto
    user_message_lower = user_message.lower()
    
    if 'hola' in user_message_lower:
        return "¡Hola! ¿En qué puedo ayudarte hoy?"
    elif 'cómo estás' in user_message_lower:
        return "¡Estoy funcionando perfectamente! ¿Y tú?"
    elif 'adiós' in user_message_lower or 'chao' in user_message_lower:
        return "¡Hasta luego! Fue un gusto ayudarte."
    elif 'nombre' in user_message_lower:
        return "Soy un chatbot creado con Flask y MySQL."
    elif 'ayuda' in user_message_lower:
        return "Puedo responder preguntas simples. Intenta saludarme o preguntar cómo estoy."
    else:
        return "No estoy seguro de cómo responder eso. ¿Puedes intentar con otra pregunta?"

@app.route('/')
def index():
    """Página principal del chatbot"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        
        # Guardar nueva sesión en la base de datos
        connection = get_db_connection()
        if connection:
            try:
                cursor = connection.cursor()
                cursor.execute(
                    "INSERT INTO chat_sessions (session_id) VALUES (%s)",
                    (session['session_id'],)
                )
                connection.commit()
                cursor.close()
                connection.close()
            except Error as e:
                print(f"Error guardando sesión: {e}")
    
    return render_template('index.html')

@app.route('/send_message', methods=['POST'])
def send_message():
    """Endpoint para enviar mensajes al chatbot"""
    user_message = request.json.get('message', '').strip()
    
    if not user_message:
        return jsonify({'error': 'Mensaje vacío'}), 400
    
    # Guardar mensaje del usuario
    save_message(session['session_id'], 'user', user_message)
    
    # Procesar mensaje y generar respuesta
    bot_response = process_message(user_message)
    
    # Guardar respuesta del bot
    save_message(session['session_id'], 'bot', bot_response)
    
    # También guardar en la tabla de conversaciones
    connection = get_db_connection()
    if connection:
        try:
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO conversations (user_message, bot_response) VALUES (%s, %s)",
                (user_message, bot_response)
            )
            connection.commit()
            cursor.close()
            connection.close()
        except Error as e:
            print(f"Error guardando conversación: {e}")
    
    return jsonify({'response': bot_response})

@app.route('/chat_history')
def chat_history():
    """Endpoint para obtener el historial del chat"""
    if 'session_id' not in session:
        return jsonify({'messages': []})
    
    messages = get_chat_history(session['session_id'])
    return jsonify({'messages': messages})

@app.route('/clear_chat', methods=['POST'])
def clear_chat():
    """Endpoint para limpiar el chat"""
    if 'session_id' in session:
        # Crear nueva sesión
        old_session = session['session_id']
        session['session_id'] = str(uuid.uuid4())
        
        # Guardar nueva sesión
        connection = get_db_connection()
        if connection:
            try:
                cursor = connection.cursor()
                cursor.execute(
                    "INSERT INTO chat_sessions (session_id) VALUES (%s)",
                    (session['session_id'],)
                )
                connection.commit()
                cursor.close()
                connection.close()
            except Error as e:
                print(f"Error creando nueva sesión: {e}")
    
    return jsonify({'status': 'success'})

if __name__ == '__main__':
    # Inicializar base de datos al iniciar la aplicación
    init_database()
    app.run(debug=True, host='0.0.0.0', port=5000)