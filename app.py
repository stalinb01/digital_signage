"""
Digital Signage Application
Flask Backend con gestión de pantallas y generación de presentaciones HTML

Estructura de carpetas requerida:
digital_signage/
├── app.py (este archivo)
├── templates/
│   ├── index.html
│   └── screen_template.html
├── static/
│   ├── uploads/
│   └── css/
└── data/
    ├── screens/
    │   ├── pantalla1/
    │   ├── pantalla2/
    │   ├── pantalla3/
    │   ├── pantalla4/
    │   └── pantalla5/
    └── config/

Instalación:
pip install flask

Uso:
python app.py
Abrir navegador en: http://localhost:5000
"""
"""
Digital Signage Application - Versión Modularizada
Flask Backend con templates separados
"""

from flask import Flask, render_template, request, jsonify, url_for, session, redirect
from functools import wraps
import os
import json
import hashlib
from datetime import datetime
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

# Cargar variables de entorno
load_dotenv(verbose=True)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWD')

app.config['UPLOAD_FOLDER'] = os.getenv('UP_FOLDER')
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENG'))
app.config['ALLOWED_EXTENSIONS'] = set(os.getenv('ALLOWED_EXT').split(','))
app.config['ALLOWED_VIDEO_EXTENSIONS'] = set(os.getenv('ALLOWED_VIDEO_EXT').split(','))

# Crear estructura de carpetas
RAW_FOLDER = os.getenv('FOLDERS_ESTRUC')
FOLDERS = [folder.strip() for folder in RAW_FOLDER.split(',')]

for folder in FOLDERS:
    os.makedirs(folder, exist_ok=True)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def allowed_video(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_VIDEO_EXTENSIONS']

def generate_hash_id():
    """Generar ID único usando hash"""
    timestamp = datetime.now().isoformat()
    random_str = os.urandom(16).hex()
    return hashlib.md5(f"{timestamp}{random_str}".encode()).hexdigest()[:12]

def load_screen_config(screen_id):
    """Cargar configuración de una pantalla"""
    config_path = f'data/config/pantalla{screen_id}.json'
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'screen_id': screen_id, 'slides': []}

def save_screen_config(screen_id, config):
    """Guardar configuración de una pantalla"""
    config_path = f'data/config/pantalla{screen_id}.json'
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

def generate_screen_html(screen_id):
    """
    Generar HTML de presentación para una pantalla usando templates
    MODULARIZADO: Usa Jinja2 templates en lugar de strings concatenados
    """
    config = load_screen_config(screen_id)
    slides = config.get('slides', [])
    
    # Extraer datos de la marquesina
    marquee_enabled = config.get('marquee_enabled', False)
    marquee_text = config.get('marquee_text', "")
    
    # Renderizar el template usando Jinja2
    html_content = render_template(
        'screen_base.html',
        screen_id=screen_id,
        slides_json=json.dumps(slides, ensure_ascii=False),
        marquee_enabled=marquee_enabled,
        marquee_text=marquee_text
    )
    
    # Guardar el HTML generado
    output_path = f'data/screens/pantalla{screen_id}/index.html'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return output_path

# ===== RUTAS DE AUTENTICACIÓN =====

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            return "Contraseña incorrecta", 401
    return '''
        <form method="post" style="text-align:center; margin-top:100px; font-family:sans-serif;">
            <h2>Panel de Control - Acceso</h2>
            <input type="password" name="password" placeholder="Contraseña" style="padding:10px;">
            <button type="submit" style="padding:10px;">Entrar</button>
        </form>
    '''

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

# ===== RUTAS PRINCIPALES =====

@app.route('/')
@login_required
def index():
    """Página principal de administración"""
    return render_template('index.html')

@app.route('/api/screens')
@login_required
def get_screens():
    """Obtener lista de pantallas configuradas"""
    screens = []
    for i in range(1, 6):
        config = load_screen_config(i)
        screens.append({
            'id': i,
            'name': f'Pantalla {i}',
            'slides_count': len(config.get('slides', [])),
            'has_content': len(config.get('slides', [])) > 0
        })
    return jsonify(screens)

@app.route('/api/screen/<int:screen_id>')
@login_required
def get_screen(screen_id):
    """Obtener configuración de una pantalla"""
    if screen_id < 1 or screen_id > 5:
        return jsonify({'error': 'ID de pantalla inválido'}), 400
    
    config = load_screen_config(screen_id)
    return jsonify(config)

@app.route('/api/screen/<int:screen_id>', methods=['POST'])
@login_required
def save_screen(screen_id):
    """Guardar configuración de una pantalla"""
    if screen_id < 1 or screen_id > 5:
        return jsonify({'error': 'ID de pantalla inválido'}), 400
    
    data = request.json
    save_screen_config(screen_id, data)
    return jsonify({'success': True, 'message': 'Configuración guardada'})

@app.route('/api/upload', methods=['POST'])
@login_required
def upload_file():
    """Subir imagen o video"""
    if 'file' not in request.files:
        return jsonify({'error': 'No se envió ningún archivo'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Nombre de archivo vacío'}), 400
    
    file_type = None
    if file and allowed_file(file.filename):
        file_type = 'image'
    elif file and allowed_video(file.filename):
        file_type = 'video'
    else:
        return jsonify({'error': 'Tipo de archivo no permitido'}), 400
    
    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)
    
    url = url_for('static', filename=f'uploads/{filename}')
    return jsonify({
        'success': True,
        'url': url,
        'filename': filename,
        'type': file_type
    })

@app.route('/api/generate/<int:screen_id>', methods=['POST'])
@login_required
def generate_screen(screen_id):
    """Generar HTML de presentación"""
    if screen_id < 1 or screen_id > 5:
        return jsonify({'error': 'ID de pantalla inválido'}), 400
    
    try:
        output_path = generate_screen_html(screen_id)
        return jsonify({
            'success': True,
            'message': f'Presentación generada exitosamente',
            'url': f'/pantalla{screen_id}',
            'path': output_path
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/pantalla<int:screen_id>')
def show_screen(screen_id):
    """Mostrar pantalla generada (acceso público sin login)"""
    if screen_id < 1 or screen_id > 5:
        return "Pantalla no encontrada", 404
    
    html_path = f'data/screens/pantalla{screen_id}/index.html'
    if not os.path.exists(html_path):
        return f"La pantalla {screen_id} aún no ha sido generada. Por favor, genera la presentación primero.", 404
    
    with open(html_path, 'r', encoding='utf-8') as f:
        return f.read()

if __name__ == '__main__':
    print("=" * 60)
    print("🖥️  DIGITAL SIGNAGE APPLICATION - MODULAR")
    print("=" * 60)
    print(f"📱 Panel de administración: http://localhost:5000")
    print(f"🎬 Pantallas disponibles:")
    for i in range(1, 6):
        print(f"   • Pantalla {i}: http://localhost:5000/pantalla{i}")
    print("=" * 60)
    print("\n✅ Servidor iniciado. Presiona CTRL+C para detener.\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)