from flask import Flask
from flask import render_template
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from flask_mail import Mail, Message
import json
from flask import jsonify
import os
secret_key = os.urandom(24) 

app = Flask(__name__)

app.secret_key = os.urandom(24)

@app.route('/')
def index():
    return render_template('sitio/index.html')

@app.route('/sobre-mi')
def sobre_mi():
    return render_template('sitio/sobre_mi.html')

@app.route('/portafolio')
def portafolio():
    return render_template('sitio/portafolio.html')

#@app.route('/contacto')
#def contacto():
    #return render_template('sitio/contacto.html')

@app.route('/enlaces')
def enlaces():
    return render_template('sitio/enlaces.html')

@app.route('/mapa')
def mapa():
    return render_template('sitio/mapa.html')

@app.route('/buscar')
def buscar():
    query = request.args.get('q', '')
    return f"Resultados para: {query}"

# Configurar conexión a MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'mi_sitio'

# Looking to send emails in production? Check out our Email API/SMTP product!
app.config['MAIL_SERVER']='sandbox.smtp.mailtrap.io'
app.config['MAIL_PORT'] = 2525
app.config['MAIL_USERNAME'] = 'c9f3f9eb7d9f5c'
app.config['MAIL_PASSWORD'] = 'ddbb522b70fdf8'
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

mysql = MySQL(app)
mail = Mail(app)

# Ruta para el formulario de contacto
@app.route('/contacto', methods=['GET', 'POST'])
def contacto():
    mensaje = None
    exito = None

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        email = request.form.get('email')
        mensaje = request.form.get('message')

        # Verificar si algún campo está vacío
        if not all([nombre, email, mensaje]):
            mensaje = 'Llena los campos.'
            exito = False
        else:
            try:
                cur = mysql.connection.cursor()
                cur.execute("INSERT INTO contactos (nombre, email, mensaje) VALUES (%s, %s, %s)", (nombre, email, mensaje))
                mysql.connection.commit()
                cur.close()

                msg = Message(
                    subject=f"Nuevo mensaje de {nombre}",
                    recipients=["karolinarvizu@gmail.com"],  
                    sender=app.config['MAIL_USERNAME'],
                    body=f"""
                    Nombre: {nombre}
                    Email: {email}
                    Mensaje: {mensaje}
                    """
                )
                
                mail.send(msg)
                mensaje = "¡Mensaje enviado con éxito!"
                exito = True

            except Exception as e:
                app.logger.error(f"Error al enviar correo: {str(e)}")
                mensaje = f"Error al enviar: {str(e)}"
                exito = False

    return render_template('sitio/contacto.html', mensaje=mensaje, exito=exito)

intentos_fallidos = {}

@app.route('/login', methods=['GET', 'POST'])
def login():
    ip_usuario = request.remote_addr  # Captura la IP del usuario

    # Verifica si el usuario ya está bloqueado
    if ip_usuario in intentos_fallidos:
        tiempo_bloqueo, intentos = intentos_fallidos[ip_usuario]

        # Si aún está dentro del tiempo de bloqueo, no permitir el login
        if tiempo_bloqueo is not None and datetime.now() < tiempo_bloqueo:
            flash('Demasiados intentos fallidos. Intenta de nuevo más tarde.', 'danger')
            return redirect(url_for('login'))
        else:
            # Si el tiempo de bloqueo ya pasó, reiniciar el contador
            intentos_fallidos[ip_usuario] = [None, 0]

    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, nombre, password FROM usuarios WHERE email = %s", (email,))
        user = cur.fetchone()  
        
        if user and check_password_hash(user[2], password):  
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            flash('Inicio de sesión exitoso', 'success')
            
            # Si el login fue exitoso, eliminamos los intentos fallidos de la IP
            if ip_usuario in intentos_fallidos:
                del intentos_fallidos[ip_usuario]
                
            return redirect(url_for('index'))
        
        # Si falló el login, incrementar el contador de intentos
        intentos = intentos_fallidos.get(ip_usuario, [None, 0])[1] + 1
        if intentos >= 5:
            tiempo_bloqueo = datetime.now() + timedelta(minutes=5)  
            intentos_fallidos[ip_usuario] = [tiempo_bloqueo, intentos]
            flash('Demasiados intentos fallidos. Intenta de nuevo en 5 minutos.', 'danger')
        else:
            intentos_fallidos[ip_usuario] = [None, intentos]
            flash(f'Credenciales incorrectas. Intento {intentos}/5', 'danger')

        return redirect(url_for('login'))

    return render_template('sitio/login.html')

# Ruta de registro con almacenamiento seguro de contraseñas
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nombre = request.form['nombre']
        email = request.form['email']
        password = request.form['password']
        
        # Hashear la contraseña antes de guardarla en la BD
        hashed_password = generate_password_hash(password)
        
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO usuarios (nombre, email, password) VALUES (%s, %s, %s)", 
                    (nombre, email, hashed_password))
        mysql.connection.commit()
        cur.close()

        flash('Usuario registrado con éxito', 'success')
        return redirect(url_for('login'))

    return render_template('sitio/register.html')

# Ruta de logout segura
@app.route('/logout')
def logout():
    session.clear()  # Elimina todos los datos de sesión
    flash('Has cerrado sesión correctamente', 'success')
    return redirect(url_for('index'))

@app.route('/exportar-usuarios-json')
def exportar_usuarios_json():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, nombre, email FROM usuarios")  # Ajusta los campos según tu base de datos
    usuarios = cur.fetchall()
    cur.close()

    usuarios_lista = [{"id": u[0], "nombre": u[1], "email": u[2]} for u in usuarios]

    ruta_archivo = os.path.join(os.getcwd(), 'usuarios.json')
    with open(ruta_archivo, 'w', encoding='utf-8') as f:
        json.dump(usuarios_lista, f, indent=4, ensure_ascii=False)

    return jsonify({"mensaje": "Archivo usuarios.json generado", "ruta": ruta_archivo})

@app.route('/exportar-contactos-json')
def exportar_contactos_json():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, nombre, email, mensaje FROM contactos")  # Ajusta los campos según tu base de datos
    contactos = cur.fetchall()
    cur.close()

    contactos_lista = [{"id": c[0], "nombre": c[1], "email": c[2], "mensaje": c[3]} for c in contactos]

    ruta_archivo = os.path.join(os.getcwd(), 'contactos.json')
    with open(ruta_archivo, 'w', encoding='utf-8') as f:
        json.dump(contactos_lista, f, indent=4, ensure_ascii=False)

    return jsonify({"mensaje": "Archivo contactos.json generado", "ruta": ruta_archivo})

if __name__ =='__main__':
    app.run(debug=True)