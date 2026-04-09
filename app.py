from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import json
import os
import ssl
import hashlib

# ====================================================================
# PARCHE PARA SALTAR EL FIREWALL DEL HOSPITAL
# ====================================================================
import urllib3
import requests

# 1. Desactivar las advertencias molestas en la consola
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 2. Forzar a la librería 'requests' a ignorar el certificado del hospital
old_merge_environment_settings = requests.Session.merge_environment_settings
def merge_environment_settings(self, url, proxies, stream, verify, cert):
    settings = old_merge_environment_settings(self, url, proxies, stream, verify, cert)
    settings['verify'] = False  # Esto es lo que apaga la verificación SSL
    return settings
requests.Session.merge_environment_settings = merge_environment_settings
# ====================================================================

ssl._create_default_https_context = ssl._create_unverified_context

app = Flask(__name__, static_folder='static')
CORS(app)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

import tempfile

_creds_env = os.environ.get("GOOGLE_CREDENTIALS_JSON")
if _creds_env:
    _tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    _tmp.write(_creds_env)
    _tmp.close()
    CREDENCIALES_PATH = _tmp.name
else:
    CREDENCIALES_PATH = "credenciales.json"
SHEET_NAME = "FORMATO DE CONSULTA EXTERNA-INICIAL (Respuestas)"
WORKSHEET_NAME = "NUEVO CE"
USERS_SHEET = "USUARIOS_SISTEMA"

# ===================== GOOGLE SHEETS =====================
def get_client():
    creds = Credentials.from_service_account_file(CREDENCIALES_PATH, scopes=SCOPES)
    return gspread.authorize(creds)

def get_dataframe():
    client = get_client()
    hoja = client.open(SHEET_NAME)
    ws = hoja.worksheet(WORKSHEET_NAME)
    data = ws.get_all_records()
    return pd.DataFrame(data)

# ===================== USUARIOS =====================
def get_users_sheet():
    client = get_client()
    hoja = client.open(SHEET_NAME)
    try:
        ws = hoja.worksheet(USERS_SHEET)
    except:
        ws = hoja.add_worksheet(title=USERS_SHEET, rows=100, cols=5)
        ws.append_row(["usuario", "password_hash", "nombre", "rol", "activo"])
        # Admin por defecto
        admin_hash = hashlib.sha256("admin123".encode()).hexdigest()
        ws.append_row(["admin", admin_hash, "Administrador", "admin", "1"])
    return ws

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

# ===================== CRITERIOS ANEXO 5 =====================
CRITERIOS = {
    "FILIACION": {
        "label": "Filiación",
        "max": 4,
        "items": [
            {"campo": "FILIACIÓN [Número de historia clínica]", "nombre": "N° historia clínica", "completo": 0.25, "incompleto": 0, "noExiste": 0},
            {"campo": "FILIACIÓN [Nombres y apellidos del paciente]", "nombre": "Nombres y apellidos", "completo": 0.25, "incompleto": 0, "noExiste": 0},
            {"campo": "FILIACIÓN [Tipo y número de Seguro]", "nombre": "Tipo y N° de Seguro", "completo": 0.25, "incompleto": 0, "noExiste": 0, "naOk": True},
            {"campo": "FILIACIÓN [Lugar y fecha de nacimiento]", "nombre": "Lugar y fecha de nacimiento", "completo": 0.25, "incompleto": 0, "noExiste": 0},
            {"campo": "FILIACIÓN [Edad]", "nombre": "Edad", "completo": 0.25, "incompleto": 0, "noExiste": 0},
            {"campo": "FILIACIÓN [Sexo]", "nombre": "Sexo", "completo": 0.25, "incompleto": 0, "noExiste": 0},
            {"campo": "FILIACIÓN [Domicilio actual]", "nombre": "Domicilio actual", "completo": 0.25, "incompleto": 0, "noExiste": 0},
            {"campo": "FILIACIÓN [Lugar de Procedencia]", "nombre": "Lugar de Procedencia", "completo": 0.25, "incompleto": 0, "noExiste": 0},
            {"campo": "FILIACIÓN [Documento de identificación]", "nombre": "Documento de identificación", "completo": 0.25, "incompleto": 0, "noExiste": 0},
            {"campo": "FILIACIÓN [Estado Civil]", "nombre": "Estado Civil", "completo": 0.25, "incompleto": 0, "noExiste": 0},
            {"campo": "FILIACIÓN [Grado de instrucción]", "nombre": "Grado de instrucción", "completo": 0.25, "incompleto": 0, "noExiste": 0},
            {"campo": "FILIACIÓN [Ocupación]", "nombre": "Ocupación", "completo": 0.25, "incompleto": 0, "noExiste": 0},
            {"campo": "FILIACIÓN [Religión]", "nombre": "Religión", "completo": 0.25, "incompleto": 0, "noExiste": 0},
            {"campo": "FILIACIÓN [Teléfono]", "nombre": "Teléfono", "completo": 0.25, "incompleto": 0, "noExiste": 0},
            {"campo": "FILIACIÓN [Acompañante]", "nombre": "Acompañante", "completo": 0.25, "incompleto": 0, "noExiste": 0},
            {"campo": "FILIACIÓN [Domicilio y/o teléfono de la persona responsable]", "nombre": "Domicilio/tel. responsable", "completo": 0.25, "incompleto": 0, "noExiste": 0},
        ]
    },
    "ANAMNESIS": {
        "label": "Anamnesis",
        "max": 9,
        "items": [
            {"campo": "ANAMNESIS [Fecha y hora de atención]", "nombre": "Fecha y hora de atención", "completo": 1, "incompleto": 0.5, "noExiste": 0},
            {"campo": "ANAMNESIS [Motivo de la consulta]", "nombre": "Motivo de la consulta", "completo": 1, "incompleto": 0, "noExiste": 0},
            {"campo": "ANAMNESIS [Tiempo de enfermedad]", "nombre": "Tiempo de enfermedad", "completo": 1, "incompleto": 0, "noExiste": 0},
            {"campo": "ANAMNESIS [Relato cronológico]", "nombre": "Relato cronológico", "completo": 3, "incompleto": 1.5, "noExiste": 0},
            {"campo": "ANAMNESIS [Funciones Biológicas]", "nombre": "Funciones Biológicas", "completo": 1, "incompleto": 0.5, "noExiste": 0},
            {"campo": "ANAMNESIS [Antecedentes]", "nombre": "Antecedentes", "completo": 2, "incompleto": 1, "noExiste": 0},
        ]
    },
    "EXAMEN_CLINICO": {
        "label": "Examen Clínico",
        "max": 9,
        "items": [
            {"campo": "EXAMEN CLÍNICO [Funciones vitales  T°, FR, FC, PA.]", "nombre": "Funciones vitales", "completo": 2, "incompleto": 0.5, "noExiste": 0},
            {"campo": "EXAMEN CLÍNICO [Peso, Talla]", "nombre": "Peso, Talla", "completo": 1, "incompleto": 0.5, "noExiste": 0},
            {"campo": "EXAMEN CLÍNICO [Estado general, estado de hidratación, estado de nutrición, estado de conciencia, piel y anexos.]", "nombre": "Estado general/hidratación", "completo": 2, "incompleto": 1, "noExiste": 0},
            {"campo": "EXAMEN CLÍNICO [Examen Clínico Regional]", "nombre": "Examen Clínico Regional", "completo": 4, "incompleto": 2, "noExiste": 0},
        ]
    },
    "DIAGNOSTICOS": {
        "label": "Diagnósticos",
        "max": 20,
        "items": [
            {"campo": "DIAGNÓSTICOS  [Presuntivo coherente]", "nombre": "Presuntivo coherente", "completo": 8, "incompleto": 4, "noExiste": 0, "naOk": True},
            {"campo": "DIAGNÓSTICOS  [Definitivo coherente]", "nombre": "Definitivo coherente", "completo": 8, "incompleto": 4, "noExiste": 0, "naOk": True},
            {"campo": "DIAGNÓSTICOS  [Uso del CIE 10]", "nombre": "Uso del CIE 10", "completo": 4, "incompleto": 0, "noExiste": 0},
        ]
    },
    "PLAN_TRABAJO": {
        "label": "Plan de Trabajo",
        "max": 24,
        "items": [
            {"campo": "PLAN DE TRABAJO  [Exámenes de Patología Clínica  pertinentes]", "nombre": "Patología Clínica", "completo": 5, "incompleto": 1, "enExceso": 2, "noExiste": 0, "naOk": True},
            {"campo": "PLAN DE TRABAJO  [Exámenes de Diagnóstico por Imágenes  pertinentes]", "nombre": "Diagnóstico por Imágenes", "completo": 5, "incompleto": 1, "enExceso": 2, "noExiste": 0, "naOk": True},
            {"campo": "PLAN DE TRABAJO  [Interconsultas (a otros servicios dentro del establecimiento de saludpertinentes )]", "nombre": "Interconsultas", "completo": 4, "incompleto": 1, "enExceso": 2, "noExiste": 0, "naOk": True},
            {"campo": "PLAN DE TRABAJO  [Referencias a otros establecimientos de salud.]", "nombre": "Referencias", "completo": 4, "incompleto": 0, "noExiste": 0, "naOk": True},
            {"campo": "PLAN DE TRABAJO  [Procedimientos diagnósticos y/o terapéuticos pertinentes.]", "nombre": "Procedimientos diagnósticos", "completo": 4, "incompleto": 1, "enExceso": 2, "noExiste": 0, "naOk": True},
            {"campo": "PLAN DE TRABAJO  [Fecha de próxima cita.]", "nombre": "Fecha de próxima cita", "completo": 2, "incompleto": 0, "noExiste": 0, "naOk": True},
        ]
    },
    "TRATAMIENTO": {
        "label": "Tratamiento",
        "max": 17,
        "items": [
            {"campo": "TRATAMIENTO [Régimen higiénico-dietético y medidas generales concordantes y coherentes.]", "nombre": "Régimen higiénico-dietético", "completo": 4, "incompleto": 2, "noExiste": 0, "naOk": True},
            {"campo": "TRATAMIENTO [Nombre de medicamentos coherentes y concordante con Denominación Común Internacional (DCI)]", "nombre": "Medicamentos (DCI)", "completo": 4, "incompleto": 2, "noExiste": 0, "naOk": True},
            {"campo": "TRATAMIENTO [Consigna presentación]", "nombre": "Consigna presentación", "completo": 2, "incompleto": 0, "noExiste": 0, "naOk": True},
            {"campo": "TRATAMIENTO [Dosis del medicamento]", "nombre": "Dosis del medicamento", "completo": 2, "incompleto": 0, "noExiste": 0, "naOk": True},
            {"campo": "TRATAMIENTO [Vía de administración]", "nombre": "Vía de administración", "completo": 2, "incompleto": 0, "noExiste": 0, "naOk": True},
            {"campo": "TRATAMIENTO [Frecuencia del medicamento]", "nombre": "Frecuencia del medicamento", "completo": 2, "incompleto": 0, "noExiste": 0, "naOk": True},
            {"campo": "TRATAMIENTO [Duración del tratamiento]", "nombre": "Duración del tratamiento", "completo": 1, "incompleto": 0.5, "noExiste": 0, "naOk": True},
        ]
    },
    "ATRIBUTOS": {
        "label": "Atributos HC",
        "max": 7,
        "items": [
            {"campo": "ATRIBUTO DE LA HISTORIA CLÍNICA [Se cuenta con Formatos de Atención Integral por etapas de vida ( Primer Nivel de Atención)]", "nombre": "Formatos Atención Integral", "completo": 2, "incompleto": 1, "noExiste": 0, "naOk": True},
            {"campo": "ATRIBUTO DE LA HISTORIA CLÍNICA [Pulcritud]", "nombre": "Pulcritud", "completo": 1, "incompleto": 0, "noExiste": 0},
            {"campo": "ATRIBUTO DE LA HISTORIA CLÍNICA [Letra legible]", "nombre": "Letra legible", "completo": 1, "incompleto": 0, "noExiste": 0},
            {"campo": "ATRIBUTO DE LA HISTORIA CLÍNICA [No uso de abreviaturas]", "nombre": "No uso de abreviaturas", "completo": 1, "incompleto": 0, "noExiste": 0},
            {"campo": "ATRIBUTO DE LA HISTORIA CLÍNICA [Sello y firma del médico tratante]", "nombre": "Sello y firma médico", "completo": 2, "incompleto": 1, "noExiste": 0},
        ]
    },
    "SEGUIMIENTO": {
        "label": "Seguimiento de Evolución",
        "max": 10,
        "items": [
            {"campo": "ATRIBUTO DE LA HISTORIA CLÍNICA [SEGUIMIENTO DE LA EVOLUCIÓN]", "nombre": "Seguimiento de la Evolución", "completo": 10, "incompleto": 5, "noExiste": 0, "naOk": True},
        ]
    }
}

def get_val(row, campo):
    for k, v in row.items():
        if str(k).strip() == campo.strip():
            return str(v).strip().upper()
    # fuzzy match
    for k, v in row.items():
        if campo[:25].lower() in str(k).lower():
            return str(v).strip().upper()
    return ""

def calcular_row(row):
    total = 0
    na_total = 0
    secciones = {}

    for sec_key, sec in CRITERIOS.items():
        sub = 0
        na_sec = 0
        items = []
        for c in sec["items"]:
            val = get_val(row, c["campo"])
            pts = 0
            estado = "sin_dato"
            if val in ("COMPLETO", "C"):
                pts = c["completo"]; estado = "completo"
            elif val in ("INCOMPLETO", "I"):
                pts = c["incompleto"]; estado = "incompleto"
            elif val in ("EN EXCESO", "E"):
                pts = c.get("enExceso", 0); estado = "en_exceso"
            elif val in ("NO EXISTE", "NE"):
                pts = 0; estado = "no_existe"
            elif val in ("NO APLICA", "NA"):
                pts = 0; na_sec += c["completo"]; estado = "na"
            
            items.append({"nombre": c["nombre"], "pts": pts, "max": c["completo"], "estado": estado})
            sub += pts
        
        na_total += na_sec
        total += sub
        secciones[sec_key] = {"label": sec["label"], "subtotal": sub, "max": sec["max"], "items": items}

    max_aplicable = 100 - na_total
    pct = round((total / max_aplicable * 100), 2) if max_aplicable > 0 else 0
    calif = "SATISFACTORIO" if pct >= 90 else ("POR MEJORAR" if pct >= 75 else "DEFICIENTE")

    return {
        "puntaje": round(total, 2),
        "max_aplicable": round(max_aplicable, 2),
        "porcentaje": pct,
        "calificacion": calif,
        "secciones": secciones
    }

def procesar_df(df):
    results = []
    
    nombres_meses = {
        1: "01 - Enero", 2: "02 - Febrero", 3: "03 - Marzo",
        4: "04 - Abril", 5: "05 - Mayo", 6: "06 - Junio",
        7: "07 - Julio", 8: "08 - Agosto", 9: "09 - Septiembre",
        10: "10 - Octubre", 11: "11 - Noviembre", 12: "12 - Diciembre"
    }
    
    for _, row in df.iterrows():
        r = row.to_dict()
        calc = calcular_row(r)
        
        marca_temporal = str(r.get("Marca temporal", "")).strip()
        
        try:
            fecha_exacta = pd.to_datetime(marca_temporal, dayfirst=True)
            mes_num = fecha_exacta.month
            
            # ==============================================================
            # AHORA EL AÑO Y EL MES VIAJAN POR SEPARADO
            # ==============================================================
            anio_automatico = str(fecha_exacta.year)
            mes_automatico = nombres_meses.get(mes_num, "Sin Mes")
            
        except Exception:
            anio_automatico = "Sin Año"
            mes_automatico = "Sin Fecha"
            
        results.append({
            "hc": str(r.get("NÚMERO DE HISTORIA CLÍNICA", r.get("NUMERO DE HISTORIA CLINICA", "—"))),
            "fecha": str(r.get("FECHA DE AUDITORÍA", r.get("FECHA DE AUDITORIA", "—"))),
            "servicio": str(r.get("SERVICIO AUDITADO", "—")),
            "auditor": str(r.get("Miembros del Comité de Auditoria que realizan la auditoría", "—")),
            "anio": anio_automatico, # NUEVO DATO SEPARADO
            "num_auditoria": mes_automatico, # SOLO EL MES
            "diagnostico": str(r.get("DIAGNÓSTICO", "—")),
            "cie10": str(r.get("CIE 10 (en mayúsculas, separando diagnósticos con slash, ejemplo: U07.1 / K35.9)", "—")),
            **calc
        })
        
    results.sort(key=lambda x: (x['anio'], x['num_auditoria']))
    return results

# ===================== RUTAS =====================
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json
        usuario = data.get('usuario', '').strip()
        password = data.get('password', '').strip()
        pw_hash = hash_password(password)

        ws = get_users_sheet()
        users = ws.get_all_records()
        for u in users:
            if str(u.get('usuario','')) == usuario and str(u.get('password_hash','')) == pw_hash and str(u.get('activo','')) == '1':
                return jsonify({"ok": True, "nombre": u.get('nombre',''), "rol": u.get('rol',''), "usuario": usuario})
        return jsonify({"ok": False, "msg": "Usuario o contraseña incorrectos"}), 401
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500

@app.route('/api/usuarios', methods=['GET'])
def get_usuarios():
    try:
        ws = get_users_sheet()
        users = ws.get_all_records()
        return jsonify([{"usuario": u['usuario'], "nombre": u['nombre'], "rol": u['rol'], "activo": u['activo']} for u in users])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/usuarios', methods=['POST'])
def crear_usuario():
    try:
        data = request.json
        ws = get_users_sheet()
        pw_hash = hash_password(data['password'])
        ws.append_row([data['usuario'], pw_hash, data['nombre'], data.get('rol','auditor'), '1'])
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/datos', methods=['GET'])
def get_datos():
    try:
        # 1. Obtenemos los datos del Excel de Drive
        df = get_dataframe()
        # 2. Los procesamos (calculamos puntos y extraemos año/mes)
        results = procesar_df(df)
        
        # 3. PREPARAMOS LAS LISTAS PARA LOS FILTROS DEL FRONTEND
        # Extraemos solo valores reales, ignorando los indicadores de error o vacíos
        servicios = sorted(list(set(r['servicio'] for r in results if r['servicio'] != '—')))
        auditores = sorted(list(set(r['auditor'] for r in results if r['auditor'] != '—')))
        anios = sorted(list(set(r['anio'] for r in results if r['anio'] != 'Sin Año')))
        meses = sorted(list(set(r['num_auditoria'] for r in results if r['num_auditoria'] != 'Sin Fecha')))

        # 4. Enviamos el paquete completo de datos al Dashboard
        return jsonify({
            "ok": True, 
            "total": len(results), 
            "registros": results, 
            "servicios": servicios, 
            "auditores": auditores,
            "anios": anios, 
            "meses": meses
        })

    except Exception as e:
        # Si algo falla (ej. sin internet), enviamos el error para que no se caiga el sistema
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route('/api/estadisticas', methods=['POST'])
def get_estadisticas():
    try:
        registros = request.json.get('registros', [])
        if not registros:
            return jsonify({})

        total = len(registros)
        sat = sum(1 for r in registros if r['calificacion'] == 'SATISFACTORIO')
        mej = sum(1 for r in registros if r['calificacion'] == 'POR MEJORAR')
        deft = sum(1 for r in registros if r['calificacion'] == 'DEFICIENTE')
        prom = round(sum(r['porcentaje'] for r in registros) / total, 2)

        # Por sección
        secciones_stats = {}
        for sec_key in CRITERIOS.keys():
            label = CRITERIOS[sec_key]['label']
            max_sec = CRITERIOS[sec_key]['max']
            items_data = {}
            for r in registros:
                sec = r.get('secciones', {}).get(sec_key, {})
                for item in sec.get('items', []):
                    n = item['nombre']
                    if n not in items_data:
                        items_data[n] = {'completo': 0, 'incompleto': 0, 'no_existe': 0, 'en_exceso': 0, 'na': 0, 'sin_dato': 0}
                    items_data[n][item['estado']] = items_data[n].get(item['estado'], 0) + 1

            subtotales = [r.get('secciones', {}).get(sec_key, {}).get('subtotal', 0) for r in registros]
            prom_sec = round(sum(subtotales) / total, 2) if total > 0 else 0
            pct_sec = round(prom_sec / max_sec * 100, 2) if max_sec > 0 else 0

            secciones_stats[sec_key] = {
                "label": label,
                "max": max_sec,
                "promedio": prom_sec,
                "porcentaje": pct_sec,
                "items": items_data
            }

        # Por servicio
        servicios = {}
        for r in registros:
            s = r['servicio']
            if s not in servicios:
                servicios[s] = {'total': 0, 'sat': 0, 'mej': 0, 'def': 0, 'pct_sum': 0}
            servicios[s]['total'] += 1
            servicios[s]['pct_sum'] += r['porcentaje']
            if r['calificacion'] == 'SATISFACTORIO': servicios[s]['sat'] += 1
            elif r['calificacion'] == 'POR MEJORAR': servicios[s]['mej'] += 1
            else: servicios[s]['def'] += 1
        for s in servicios:
            servicios[s]['promedio'] = round(servicios[s]['pct_sum'] / servicios[s]['total'], 2)

        return jsonify({
            "total": total, "satisfactorio": sat, "por_mejorar": mej, "deficiente": deft,
            "promedio_pct": prom, "secciones": secciones_stats, "por_servicio": servicios
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)