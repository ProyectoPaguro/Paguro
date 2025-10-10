from __future__ import annotations

import os
import io
from datetime import datetime, date, time as dtime  # ya lo dejaste así en el paso 1

def rango_hoy():
    hoy = date.today()
    inicio = datetime.combine(hoy, dtime.min)   # 00:00:00 de hoy
    fin    = datetime.combine(hoy, dtime.max)   # 23:59:59.999999 de hoy
    return inicio, fin
   # <— time de datetime con alias
import time as epoch_time                             # <— módulo time con alias
from pathlib import Path

from flask import (
    Flask, render_template, request, redirect, url_for,
    send_file, flash, abort
)
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    UserMixin, LoginManager, login_user, login_required,
    logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import func, text, or_



# Export
from openpyxl import Workbook
from openpyxl.utils import get_column_letter



# -----------------------------------------------------------------------------
# Config básica
# -----------------------------------------------------------------------------
# app.py


import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__, instance_relative_config=True)

from zoneinfo import ZoneInfo
from datetime import timezone, time as dtime, datetime
# --- Zona horaria local (por variable de entorno LOCAL_TZ o Bogotá por defecto)
LOCAL_TZ_NAME = os.environ.get("LOCAL_TZ", "America/Bogota")
LOCAL_TZ = ZoneInfo(LOCAL_TZ_NAME)
UTC = ZoneInfo("UTC")

def to_local(dt):
    """Convierte un datetime guardado en UTC (naive) a hora local."""
    if not dt:
        return None
    # Tus fechas en DB son naive creadas con datetime.utcnow() => trátalas como UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(LOCAL_TZ)

def fmt_local(dt, fmt="%Y-%m-%d %H:%M"):
    x = to_local(dt)
    return x.strftime(fmt) if x else ""

@app.template_filter("localdt")
def localdt_filter(dt, fmt="%Y-%m-%d %H:%M"):
    return fmt_local(dt, fmt)

# --- Bodegas disponibles (puedes editarlas o leerlas de una variable de entorno) ---
BODEGAS_FIJAS = [b.strip() for b in os.getenv("BODEGAS", "Tocancipa,Bogotá Prado,Casa Balsa,Ferias").split(",") if b.strip()]

def listar_bodegas():
    """Devuelve bodegas conocidas: fijas + las que existan en BD."""
    otras = [b[0] for b in db.session.query(Producto.bodega).distinct().all() if b[0]]
    # orden simple y sin duplicados
    vistas = []
    for b in BODEGAS_FIJAS + otras:
        if b and b not in vistas:
            vistas.append(b)
    return vistas

from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo(os.getenv("LOCAL_TZ", "America/Bogota"))  # cámbiala si necesitas
UTC = ZoneInfo("UTC")

def hoy_local_a_utc_bounds():
    """Devuelve (inicio_utc_naive, fin_utc_naive) del día local actual."""
    ahora_local = datetime.now(LOCAL_TZ)
    ini_local = datetime.combine(ahora_local.date(), dtime.min, tzinfo=LOCAL_TZ)
    fin_local = datetime.combine(ahora_local.date(), dtime.max, tzinfo=LOCAL_TZ)
    ini_utc = ini_local.astimezone(UTC).replace(tzinfo=None)  # naive UTC para SQLite
    fin_utc = fin_local.astimezone(UTC).replace(tzinfo=None)
    return ini_utc, fin_utc
# --- SECRET KEY (antes de cualquier uso de session/flash/login_manager) ---
_env_secret = os.environ.get("SECRET_KEY")
if not _env_secret:
    try:
        _env_secret = os.urandom(24).hex()
    except Exception:
        _env_secret = "dev-secret-key-change-me"

app.config["SECRET_KEY"] = _env_secret
app.secret_key = _env_secret

# DEBUG (puedes dejarlo por ahora; verifica en Logs de Render que salga True)
print(">>> SECRET_KEY set? ->", bool(app.config.get("SECRET_KEY")))

# --- Base de datos (DEBE ir antes de  ---
# Usamos el disco persistente de Render en /var/data si existe,
# y si no, caemos a instance/database.db (local).
DATA_DIR = os.environ.get("DATA_DIR", "/var/data")

if os.path.isdir(DATA_DIR) and os.access(DATA_DIR, os.W_OK):
    os.makedirs(DATA_DIR, exist_ok=True)
    db_path = os.path.join(DATA_DIR, "database.db")
else:
    os.makedirs(app.instance_path, exist_ok=True)
    db_path = os.path.join(app.instance_path, "database.db")

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + db_path
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

print(">>> DB file:", db_path)

db = SQLAlchemy(app)

# crea tablas si no existen


# -----------------------------------------------------------------------------
# Modelos
# -----------------------------------------------------------------------------
class Insumo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    unidad = db.Column(db.String(50), nullable=False)
    cantidad_actual = db.Column(db.Float, default=0)
    bodega = db.Column(db.String(100), nullable=False)


class Movimiento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)  # Entrada / Salida
    cantidad = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    insumo_id = db.Column(db.Integer, db.ForeignKey('insumo.id'))
    insumo = db.relationship('Insumo', backref=db.backref('movimientos', lazy=True))


class Usuario(UserMixin, db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email  = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    rol = db.Column(db.String(20), nullable=False, default='operario')  # admin | operario


class Producto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(120), nullable=False)
    acabado = db.Column(db.String(120), nullable=False)
    cantidad_actual = db.Column(db.Float, default=0)
    bodega = db.Column(db.String(120), nullable=False)


class ProdMovimiento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)
    cantidad = db.Column(db.Float, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    bodega = db.Column(db.String(120))  # <— añade esto y te evitas el UPDATE manual
    producto_id = db.Column(db.Integer, db.ForeignKey('producto.id'))
    producto = db.relationship('Producto', backref=db.backref('movimientos', lazy=True))



class Tarea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)      # 'fundir' | 'pulir'
    producto = db.Column(db.String(200), nullable=False)
    acabado = db.Column(db.String(120), nullable=False)
    imagen = db.Column(db.String(255))                   # ruta relativa a /static
    fecha = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Estado unificado
    completada = db.Column(db.Boolean, default=False, nullable=False)
    completada_en = db.Column(db.DateTime)
    completada_por_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'))
    completada_por = db.relationship('Usuario', foreign_keys=[completada_por_id])


# -----------------------------------------------------------------------------
# Login
# -----------------------------------------------------------------------------
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))



# Crear tablas y asegurar columna 'rol'
with app.app_context():
    db.create_all()
    try:
        cols = db.session.execute(text("PRAGMA table_info(prod_movimiento);")).fetchall()
        colnames = [c[1] for c in cols]
        if 'bodega' not in colnames:
            db.session.execute(text("ALTER TABLE prod_movimiento ADD COLUMN bodega VARCHAR(120);"))
            db.session.commit()
    except Exception as e:
        print("Aviso 'bodega en prod_movimiento':", e)
    try:
        cols = db.session.execute(text("PRAGMA table_info(usuarios);")).fetchall()
        colnames = [c[1] for c in cols]
        if 'rol' not in colnames:
            db.session.execute(
                text("ALTER TABLE usuarios ADD COLUMN rol VARCHAR(20) NOT NULL DEFAULT 'operario';")
            )
            db.session.commit()
    except Exception as e:
        print("Aviso 'rol':", e)

# -----------------------------------------------------------------------------
# Utilidades
# -----------------------------------------------------------------------------
def require_roles(*roles):
    def deco(fn):
        from functools import wraps
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            if current_user.rol not in roles:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return deco

# --- Desactivar guardado de imagen por completo ---
def _save_task_image(file_storage):
    """La carga de imagen está deshabilitada. Siempre devolver None."""
    return None


@app.route('/favicon.ico')
def favicon():
    return ('', 204)

# -----------------------------------------------------------------------------
# Dashboard
# -----------------------------------------------------------------------------
@app.route('/')
@login_required
def dashboard():
    total_insumos = Insumo.query.count()
    total_productos = Producto.query.count()

    # HOY en hora local (convertido a UTC para comparar en DB)
    ini_hoy_utc, fin_hoy_utc = hoy_local_a_utc_bounds()

    # movimientos de insumos HOY (local)
    movs_hoy = (Movimiento.query
                .filter(Movimiento.fecha >= ini_hoy_utc,
                        Movimiento.fecha <= fin_hoy_utc)
                .count())

    UMBRAL = 5
    bajos = Insumo.query.filter(Insumo.cantidad_actual < UMBRAL).count()

    # PENDIENTES: SIEMPRE visibles (sin fecha)
    tareas_fundir_pend = (Tarea.query
        .filter(Tarea.tipo=='fundir', Tarea.completada.is_(False))
        .order_by(Tarea.id.desc()).all())

    tareas_pulir_pend = (Tarea.query
        .filter(Tarea.tipo=='pulir', Tarea.completada.is_(False))
        .order_by(Tarea.id.desc()).all())

    # COMPLETADAS HOY (en hora local, usando completada_en)
    tareas_fundir_comp = (Tarea.query
        .filter(Tarea.tipo=='fundir', Tarea.completada.is_(True))
        .filter(Tarea.completada_en >= ini_hoy_utc,
                Tarea.completada_en <= fin_hoy_utc)
        .order_by(Tarea.completada_en.desc().nullslast()).all())

    tareas_pulir_comp = (Tarea.query
        .filter(Tarea.tipo=='pulir', Tarea.completada.is_(True))
        .filter(Tarea.completada_en >= ini_hoy_utc,
                Tarea.completada_en <= fin_hoy_utc)
        .order_by(Tarea.completada_en.desc().nullslast()).all())

    return render_template(
        'dashboard.html',
        total_insumos=total_insumos,
        total_productos=total_productos,
        movs_hoy=movs_hoy,
        bajos=bajos,
        umbral=UMBRAL,
        tareas_fundir_pend=tareas_fundir_pend,
        tareas_fundir_comp=tareas_fundir_comp,
        tareas_pulir_pend=tareas_pulir_pend,
        tareas_pulir_comp=tareas_pulir_comp
    )


# -----------------------------------------------------------------------------
# Tareas
# -----------------------------------------------------------------------------
@app.post("/tareas/agregar")
@login_required
@require_roles("admin")
def tareas_agregar():
    tipo = (request.form.get("tipo") or "").strip().lower()  # 'fundir' | 'pulir'
    producto = (request.form.get("producto") or "").strip()
    acabado = (request.form.get("acabado") or "").strip()
    if not tipo or not producto or not acabado:
        flash("Faltan datos para crear la tarea.", "warning")
        return redirect(url_for("dashboard"))

    imagen_rel = None
    if tipo == "fundir":
        imagen_rel = _save_task_image(request.files.get("imagen"))

    t = Tarea(
        tipo=tipo,
        producto=producto,
        acabado=acabado,
        imagen=imagen_rel,
        fecha=datetime.utcnow(),
        completada=False,
    )
    db.session.add(t)
    db.session.commit()
    flash("Tarea añadida ✅", "success")
    return redirect(url_for("dashboard"))

# --- Inyectar la ruta actual en todos los templates ---
@app.context_processor
def inject_active_path():
    from flask import request
    p = getattr(request, "path", "")
    return {"active_path": p, "ap": p}

@app.post("/tareas/<int:tarea_id>/completar")
@login_required
def tareas_completar(tarea_id):
    t = Tarea.query.get_or_404(tarea_id)
    if not t.completada:
        t.completada = True
        t.completada_en = datetime.utcnow()
        t.completada_por_id = current_user.id
        db.session.commit()
        flash("Tarea completada ✔️", "success")
    return redirect(url_for("dashboard"))

@app.post("/tareas/<int:tarea_id>/reabrir")
@login_required
@require_roles("admin")
def tareas_reabrir(tarea_id):
    t = Tarea.query.get_or_404(tarea_id)
    if t.completada:
        t.completada = False
        t.completada_en = None
        t.completada_por_id = None
        db.session.commit()
        flash("Tarea reabierta ↩️", "info")
    return redirect(url_for("dashboard"))

@app.post("/tareas/<int:tarea_id>/eliminar")
@login_required
@require_roles("admin")
def tareas_eliminar(tarea_id):
    t = Tarea.query.get_or_404(tarea_id)
    if t.imagen:
        try:
            os.remove(os.path.join(app.static_folder, t.imagen))
        except Exception:
            pass
    db.session.delete(t)
    db.session.commit()
    flash("Tarea eliminada 🗑️", "warning")
    return redirect(url_for("dashboard"))

@app.get('/tareas/historial')
@login_required
def historial_tareas():
    tipo = (request.args.get('tipo') or '').lower()            # 'fundir' | 'pulir' | ''
    estado = (request.args.get('estado') or '').lower()        # 'pendiente' | 'completada' | ''
    desde = request.args.get('desde')                          # yyyy-mm-dd
    hasta = request.args.get('hasta')

    q = Tarea.query

    if tipo in ('fundir', 'pulir'):
        q = q.filter(Tarea.tipo == tipo)

    if estado in ('pendiente', 'completada'):
        q = q.filter(Tarea.completada.is_(estado == 'completada'))

    if desde:
        try:
            d = datetime.strptime(desde, "%Y-%m-%d")
            q = q.filter(Tarea.fecha >= d)
        except ValueError:
            flash('Fecha "desde" inválida', 'danger')

    if hasta:
        try:
            h = datetime.strptime(hasta, "%Y-%m-%d")
            h = h.replace(hour=23, minute=59, second=59)
            q = q.filter(Tarea.fecha <= h)
        except ValueError:
            flash('Fecha "hasta" inválida', 'danger')

    tareas = q.order_by(Tarea.fecha.desc(), Tarea.id.desc()).all()
    return render_template('historial_tareas.html',
                           tareas=tareas,
                           sel_tipo=tipo, sel_estado=estado,
                           sel_desde=desde or '', sel_hasta=hasta or '')

# -----------------------------------------------------------------------------
# Insumos
# -----------------------------------------------------------------------------
@app.route('/inventario', endpoint='inventario')
@login_required
def inventario():
    insumos = Insumo.query.order_by(Insumo.nombre.asc()).all()
    nombres = [i.nombre for i in insumos]
    cantidades = [i.cantidad_actual for i in insumos]
    return render_template('inventario.html', insumos=insumos,
                           nombres=nombres, cantidades=cantidades)

@app.route('/insumos', methods=['GET', 'POST'], endpoint='insumos_create')
@login_required
@require_roles('admin')
def insumos_create():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        unidad = request.form.get('unidad')
        cantidad = request.form.get('cantidad')
        bodega = request.form.get('bodega')

        if not (nombre and unidad and cantidad and bodega):
            flash('Faltan datos', 'danger')
            return render_template('insumos.html')

        nuevo = Insumo(
            nombre=nombre.strip(),
            unidad=unidad.strip(),
            cantidad_actual=float(cantidad),
            bodega=bodega.strip()
        )
        db.session.add(nuevo)
        db.session.commit()
        flash('Insumo creado ✅', 'success')
        return redirect(url_for('inventario'))
    return render_template('insumos.html')

@app.route('/insumos/<int:insumo_id>/editar', methods=['GET', 'POST'])
@login_required
@require_roles('admin')
def editar_insumo(insumo_id):
    ins = Insumo.query.get_or_404(insumo_id)
    if request.method == 'POST':
        ins.nombre = request.form.get('nombre', ins.nombre).strip()
        ins.unidad = request.form.get('unidad', ins.unidad).strip()
        ins.bodega = request.form.get('bodega', ins.bodega).strip()
        if request.form.get('cantidad_actual') not in (None, ''):
            ins.cantidad_actual = float(request.form.get('cantidad_actual'))
        db.session.commit()
        flash('Insumo actualizado ✅', 'success')
        return redirect(url_for('inventario'))
    return render_template('editar_insumo.html', insumo=ins)

@app.route('/insumos/<int:insumo_id>/eliminar', methods=['POST'])
@login_required
@require_roles('admin')
def eliminar_insumo(insumo_id):
    ins = Insumo.query.get_or_404(insumo_id)
    Movimiento.query.filter_by(insumo_id=ins.id).delete()
    db.session.delete(ins)
    db.session.commit()
    flash('Insumo eliminado 🗑️', 'warning')
    return redirect(url_for('inventario'))

@app.route('/movimiento', methods=['GET', 'POST'])
@login_required
def movimiento_insumo():

    insumos = Insumo.query.order_by(Insumo.nombre.asc()).all()
    if request.method == 'POST':
        tipo = request.form.get('tipo')
        cantidad = float(request.form.get('cantidad'))
        insumo_id = int(request.form.get('insumo'))
        insumo = Insumo.query.get(insumo_id)

        if not insumo:
            flash('Insumo no encontrado', 'danger')
            return render_template('movimiento.html', insumos=insumos)

        if tipo == 'Entrada':
            insumo.cantidad_actual += cantidad
        elif tipo == 'Salida':
            if insumo.cantidad_actual >= cantidad:
                insumo.cantidad_actual -= cantidad
            else:
                flash('No hay suficiente stock', 'danger')
                return render_template('movimiento.html', insumos=insumos)
        else:
            flash('Tipo inválido', 'danger')
            return render_template('movimiento.html', insumos=insumos)

        mov = Movimiento(tipo=tipo, cantidad=cantidad, insumo=insumo)
        db.session.add(mov)
        db.session.commit()
        flash('Movimiento registrado ✅', 'success')
        return redirect(url_for('inventario'))
    return render_template('movimiento.html', insumos=insumos)

@app.route('/historial')
@login_required
def historial_insumos():
    insumo_id = request.args.get('insumo_id', type=int)
    tipo = request.args.get('tipo')
    desde = request.args.get('desde')
    hasta = request.args.get('hasta')

    q = db.session.query(Movimiento, Insumo).join(Insumo, Movimiento.insumo_id == Insumo.id)

    if insumo_id:
        q = q.filter(Movimiento.insumo_id == insumo_id)
    if tipo in ('Entrada', 'Salida'):
        q = q.filter(Movimiento.tipo == tipo)
    if desde:
        try:
            d = datetime.strptime(desde, "%Y-%m-%d")
            q = q.filter(Movimiento.fecha >= d)
        except ValueError:
            flash('Fecha "desde" inválida', 'danger')
    if hasta:
        try:
            h = datetime.strptime(hasta, "%Y-%m-%d")
            h = h.replace(hour=23, minute=59, second=59)
            q = q.filter(Movimiento.fecha <= h)
        except ValueError:
            flash('Fecha "hasta" inválida', 'danger')

    movs = q.order_by(Movimiento.fecha.desc()).all()
    insumos = Insumo.query.order_by(Insumo.nombre.asc()).all()

    return render_template('historial.html', movs=movs, insumos=insumos,
                           sel_insumo_id=insumo_id or '',
                           sel_tipo=tipo or '',
                           sel_desde=desde or '',
                           sel_hasta=hasta or '')

# -----------------------------------------------------------------------------
# Usuarios
# -----------------------------------------------------------------------------
@app.route('/usuarios')
@login_required
@require_roles('admin')
def usuarios():
    usuarios = Usuario.query.order_by(Usuario.nombre.asc()).all()
    return render_template('usuarios.html', usuarios=usuarios)

@app.route('/usuarios/<int:user_id>/rol', methods=['POST'])
@login_required
@require_roles('admin')
def usuarios_cambiar_rol(user_id):
    nuevo_rol = request.form.get('rol')
    if nuevo_rol not in ['admin', 'operario']:
        flash('Rol inválido', 'danger')
        return redirect(url_for('usuarios'))
    u = Usuario.query.get_or_404(user_id)
    u.rol = nuevo_rol
    db.session.commit()
    flash('Rol actualizado ✅', 'success')
    return redirect(url_for('usuarios'))

# -----------------------------------------------------------------------------
# Exportaciones Insumos
# -----------------------------------------------------------------------------
@app.route('/export/inventario.xlsx')
@login_required
@require_roles('admin')
def export_inventario():
    insumos = Insumo.query.order_by(Insumo.nombre.asc()).all()
    wb = Workbook()
    ws = wb.active
    ws.title = "Inventario"
    headers = ["Nombre", "Unidad", "Cantidad actual", "Bodega"]
    ws.append(headers)
    for i in insumos:
        ws.append([i.nombre, i.unidad, i.cantidad_actual, i.bodega])
    for col in range(1, len(headers)+1):
        ws.column_dimensions[get_column_letter(col)].width = 18
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True,
                     download_name='inventario.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# --- Exportaciones Insumos (deja SOLO esto) ---
@app.route('/export/movimientos.xlsx')
@login_required
@require_roles('admin')
def export_movs_insumos():
    movs = (db.session.query(Movimiento, Insumo)
            .join(Insumo, Movimiento.insumo_id == Insumo.id)
            .order_by(Movimiento.fecha.desc())
            .all())
    wb = Workbook()
    ws = wb.active
    ws.title = "Movimientos"
    headers = ["Fecha", "Insumo", "Tipo", "Cantidad", "Unidad", "Bodega"]
    ws.append(headers)
    for m, i in movs:
        ws.append([fmt_local(m.fecha, "%Y-%m-%d %H:%M"), i.nombre, m.tipo, m.cantidad, i.unidad, i.bodega])
    for col in range(1, len(headers)+1):
        ws.column_dimensions[get_column_letter(col)].width = 18
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True,
                     download_name='movimientos.xlsx',
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

# -----------------------------------------------------------------------------
# Producción
# -----------------------------------------------------------------------------
# app.py

@app.route('/produccion', endpoint='produccion')
@login_required
def produccion():
    q = (request.args.get('q') or '').strip()

    query = Producto.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Producto.nombre.ilike(like),
                Producto.acabado.ilike(like),
                Producto.bodega.ilike(like),
            )
        )

    productos = query.order_by(Producto.nombre.asc()).all()
    return render_template('produccion.html', productos=productos, q=q)

# Alias para compatibilidad con código viejo que llama 'produccion_view'
app.add_url_rule(
    '/produccion',
    endpoint='produccion_view',
    view_func=app.view_functions['produccion']   # o simplemente: view_func=produccion
)


# --------- crear_producto ----------
@app.route('/productos', methods=['GET', 'POST'], endpoint='crear_producto')
@login_required
@require_roles('admin')
def crear_producto():
    if request.method == 'POST':
        nombre = (request.form.get('nombre') or '').strip()
        acabado = (request.form.get('acabado') or '').strip()
        cantidad_str = (request.form.get('cantidad') or '').strip()
        bodega = (request.form.get('bodega') or '').strip()

        if not nombre or not acabado or not cantidad_str or not bodega:
            flash('Faltan datos.', 'danger')
            return render_template('producto_nuevo.html',
                                   nombre=nombre, acabado=acabado,
                                   cantidad=cantidad_str, bodega=bodega)

        cantidad_str = cantidad_str.replace(',', '.')
        try:
            cantidad = float(cantidad_str)
        except ValueError:
            flash('Cantidad inválida.', 'danger')
            return render_template('producto_nuevo.html',
                                   nombre=nombre, acabado=acabado,
                                   cantidad=cantidad_str, bodega=bodega)

        p = Producto(nombre=nombre, acabado=acabado, cantidad_actual=cantidad, bodega=bodega)
        db.session.add(p)
        db.session.commit()
        flash('Producto creado ✅', 'success')
        return go_produccion()

    return render_template('producto_nuevo.html')


# --------- producto_editar ----------
@app.route('/productos/<int:producto_id>/editar', methods=['GET', 'POST'])
@login_required
@require_roles('admin')
def producto_editar(producto_id):
    p = Producto.query.get_or_404(producto_id)
    if request.method == 'POST':
        p.nombre  = request.form.get('nombre',  p.nombre).strip()
        p.acabado = request.form.get('acabado', p.acabado).strip()
        p.bodega  = request.form.get('bodega',  p.bodega).strip()
        if request.form.get('cantidad_actual') not in (None, ''):
            p.cantidad_actual = float(request.form.get('cantidad_actual'))

        db.session.commit()
        flash('Producto actualizado ✅', 'success')
        return go_produccion()

    return render_template('editar_producto.html', producto=p)


# --------- producto_eliminar ----------
@app.route('/productos/<int:producto_id>/eliminar', methods=['POST'])
@login_required
@require_roles('admin')
def producto_eliminar(producto_id):
    p = Producto.query.get_or_404(producto_id)
    ProdMovimiento.query.filter_by(producto_id=p.id).delete()
    db.session.delete(p)
    db.session.commit()
    flash('Producto eliminado 🗑️', 'warning')
    return go_produccion()


# --------- movimiento_produccion ----------
@app.route('/movimiento-produccion', methods=['GET', 'POST'])
@login_required
def movimiento_produccion():
    productos = Producto.query.order_by(Producto.nombre.asc()).all()
    bodegas = listar_bodegas()

    if request.method == 'POST':
        tipo = (request.form.get('tipo') or '').strip()           # Entrada | Salida | Transferencia
        cantidad = float(request.form.get('cantidad') or 0)
        producto_id = int(request.form.get('producto') or 0)
        p = Producto.query.get(producto_id)

        if not p:
            flash('Producto no encontrado', 'danger')
            return render_template('movimiento_produccion.html', productos=productos, bodegas=bodegas)

        if cantidad <= 0:
            flash('Cantidad inválida', 'danger')
            return render_template('movimiento_produccion.html', productos=productos, bodegas=bodegas)

        # --- Transferencia entre bodegas ---
        if tipo == 'Transferencia':
            destino = (request.form.get('bodega_destino') or '').strip()
            if not destino:
                flash('Selecciona la bodega destino.', 'warning')
                return render_template('movimiento_produccion.html', productos=productos, bodegas=bodegas)
            if destino == p.bodega:
                flash('El destino debe ser diferente al origen.', 'warning')
                return render_template('movimiento_produccion.html', productos=productos, bodegas=bodegas)
            if p.cantidad_actual < cantidad:
                flash('No hay suficiente stock en la bodega de origen.', 'danger')
                return render_template('movimiento_produccion.html', productos=productos, bodegas=bodegas)

            # 1) Descuenta en origen (p)
            p.cantidad_actual -= cantidad
            db.session.add(ProdMovimiento(tipo='Salida', cantidad=cantidad, producto=p, fecha=datetime.utcnow()))
            # Vamos a guardar la bodega en el movimiento
            db.session.flush()  # tener id si fuera necesario
            db.session.execute(text("UPDATE prod_movimiento SET bodega=:b WHERE id=:id")).params(
                b=p.bodega, id=p.movimientos[-1].id
            )

            # 2) Suma en destino (mismo nombre+acabado, otra bodega)
            dest = Producto.query.filter_by(nombre=p.nombre, acabado=p.acabado, bodega=destino).first()
            if not dest:
                dest = Producto(nombre=p.nombre, acabado=p.acabado, cantidad_actual=0, bodega=destino)
                db.session.add(dest)
                db.session.flush()

            dest.cantidad_actual += cantidad
            db.session.add(ProdMovimiento(tipo='Entrada', cantidad=cantidad, producto=dest, fecha=datetime.utcnow()))
            db.session.flush()
            db.session.execute(text("UPDATE prod_movimiento SET bodega=:b WHERE id=:id")).params(
                b=destino, id=dest.movimientos[-1].id
            )

            db.session.commit()
            flash(f'Transferencia realizada: {cantidad} de "{p.nombre}" ({p.acabado}) de {p.bodega} → {destino}', 'success')
            return redirect(url_for('produccion'))

        # --- Entrada / Salida simples (misma lógica que ya tenías) ---
        if tipo == 'Entrada':
            p.cantidad_actual += cantidad
        elif tipo == 'Salida':
            if p.cantidad_actual < cantidad:
                flash('No hay suficiente stock del producto', 'danger')
                return render_template('movimiento_produccion.html', productos=productos, bodegas=bodegas)
            p.cantidad_actual -= cantidad
        else:
            flash('Tipo inválido', 'danger')
            return render_template('movimiento_produccion.html', productos=productos, bodegas=bodegas)

        mov = ProdMovimiento(tipo=tipo, cantidad=cantidad, producto=p, fecha=datetime.utcnow())
        db.session.add(mov)
        db.session.flush()
        db.session.execute(text("UPDATE prod_movimiento SET bodega=:b WHERE id=:id")).params(
            b=p.bodega, id=mov.id
        )

        db.session.commit()
        flash('Movimiento registrado ✅', 'success')
        return redirect(url_for('produccion'))

    return render_template('movimiento_produccion.html', productos=productos, bodegas=bodegas)



@app.route('/historial-produccion')
@login_required
def historial_produccion():
    producto_id = request.args.get('producto_id', type=int)
    tipo = request.args.get('tipo')
    desde = request.args.get('desde')
    hasta = request.args.get('hasta')

    q = db.session.query(ProdMovimiento, Producto).join(Producto, ProdMovimiento.producto_id == Producto.id)

    if producto_id:
        q = q.filter(ProdMovimiento.producto_id == producto_id)
    if tipo in ('Entrada', 'Salida'):
        q = q.filter(ProdMovimiento.tipo == tipo)
    if desde:
        try:
            d = datetime.strptime(desde, "%Y-%m-%d")
            q = q.filter(ProdMovimiento.fecha >= d)
        except ValueError:
            flash('Fecha "desde" inválida', 'danger')
    if hasta:
        try:
            h = datetime.strptime(hasta, "%Y-%m-%d")
            h = h.replace(hour=23, minute=59, second=59)
            q = q.filter(ProdMovimiento.fecha <= h)
        except ValueError:
            flash('Fecha "hasta" inválida', 'danger')

    movs = q.order_by(ProdMovimiento.fecha.desc()).all()
    productos = Producto.query.order_by(Producto.nombre.asc()).all()

    return render_template('historial_produccion.html', movs=movs, productos=productos,
                           sel_producto_id=producto_id or '',
                           sel_tipo=tipo or '',
                           sel_desde=desde or '',
                           sel_hasta=hasta or '')
# --- Compatibilidad con nombres antiguos de endpoints ---
# Si alguna vista/plantilla aún llama url_for('produccion_view'), etc.,
# mapeamos esos nombres al endpoint actual.
app.add_url_rule('/produccion',
    endpoint='produccion_view',
    view_func=app.view_functions['produccion']
)

app.add_url_rule( '/movimiento-produccion',
    endpoint='movimiento_produccion_view',
    view_func=app.view_functions['movimiento_produccion']
)

app.add_url_rule(
    '/historial-produccion',
    endpoint='historial_produccion_view',
    view_func=app.view_functions['historial_produccion']
)
from flask import redirect, url_for

def go_produccion():
    try:
        return redirect(url_for('produccion'))          # nuevo
    except Exception:
        try:
            return redirect(url_for('produccion_view')) # alias
        except Exception:
            return redirect('/produccion')              # fallback

# -----------------------------------------------------------------------------
# Página de últimos movimientos (insumos)
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# Página de últimos movimientos (insumos)
# -----------------------------------------------------------------------------
@app.route('/movimientos', endpoint='movimientos')
@login_required
def movimientos():
    movs = (
        db.session.query(Movimiento, Insumo)
        .join(Insumo, Movimiento.insumo_id == Insumo.id)
        .order_by(Movimiento.fecha.desc())
        .limit(200)
        .all()
    )
    return render_template('movimientos_recientes.html', movs=movs)

# -----------------------------------------------------------------------------
# Auth
# -----------------------------------------------------------------------------
@app.route('/registrar', methods=['GET', 'POST'])
def registrar():
    # ¿Ya hay usuarios?
    hay_usuarios = Usuario.query.count() > 0

    if hay_usuarios:
        if not current_user.is_authenticated:
            flash('Inicia sesión para crear usuarios.', 'warning')
            return redirect(url_for('login'))
        if current_user.rol != 'admin':
            flash('⛔ Solo un administrador puede crear usuarios.', 'danger')
            return redirect(url_for('dashboard'))

    if request.method == 'POST':
        nombre = (request.form.get('nombre') or '').strip()
        email  = (request.form.get('email') or '').strip()
        password = (request.form.get('password') or '')

        if not nombre or not email or not password:
            flash('Completa todos los campos.', 'danger')
            return render_template('registrar.html')

        if Usuario.query.filter_by(email=email).first():
            flash('Ese correo ya existe.', 'danger')
            return render_template('registrar.html')

        if not hay_usuarios:
            rol = 'admin'
        else:
            rol_form = (request.form.get('rol') or 'operario').strip().lower()
            rol = 'admin' if rol_form == 'admin' else 'operario'

        nuevo = Usuario(
            nombre=nombre,
            email=email,
            password=generate_password_hash(password),
            rol=rol
        )
        db.session.add(nuevo)
        db.session.commit()

        if not hay_usuarios:
            flash('Primer usuario creado como ADMIN. Inicia sesión.', 'success')
            return redirect(url_for('login'))

        flash('Usuario creado ✅', 'success')
        return redirect(url_for('usuarios'))

    return render_template('registrar.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email') or ''
        password = request.form.get('password') or ''
        u = Usuario.query.filter_by(email=email).first()
        if u and check_password_hash(u.password, password):
            login_user(u)
            flash(f'Bienvenido, {u.nombre} 👋', 'success')
            return redirect(request.args.get('next') or url_for('dashboard'))
        flash('Credenciales incorrectas ❌', 'danger')
        return render_template('login.html'), 401
    return render_template('login.html')

@app.route("/_routes")
def _routes():
    out = []
    for r in app.url_map.iter_rules():
        out.append(f"{r.endpoint:30s} -> {r.rule}")
    return "<pre>" + "\n".join(sorted(out)) + "</pre>"


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# -----------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True)
