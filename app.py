from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import os, ssl, hashlib, tempfile
import urllib3, requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
old_merge = requests.Session.merge_environment_settings
def merge_environment_settings(self, url, proxies, stream, verify, cert):
    s = old_merge(self, url, proxies, stream, verify, cert)
    s['verify'] = False
    return s
requests.Session.merge_environment_settings = merge_environment_settings
ssl._create_default_https_context = ssl._create_unverified_context

app = Flask(__name__, static_folder='static')
app.config['JSON_SORT_KEYS'] = False
app.json.sort_keys = False
CORS(app)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets","https://www.googleapis.com/auth/drive"]

_creds_env = os.environ.get("GOOGLE_CREDENTIALS_JSON")
if _creds_env:
    _tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    _tmp.write(_creds_env); _tmp.close()
    CREDENCIALES_PATH = _tmp.name
else:
    CREDENCIALES_PATH = "credenciales.json"

# ============================================================
# CONFIGURACIÓN DE LOS 3 EXCEL EN DRIVE (IDs EXACTOS Y CORREGIDOS)
# ============================================================
AREAS_CONFIG = {
    "consulta_externa": {
        "label": "Consulta Externa",
        "sheet_id": "1yZCRyNLQ4TShZEK_HvpVbmJidvcdjqG_JaCr2z4WjDw",
        "worksheet_name": "NUEVO CE"
    },
    "emergencia": {
        "label": "Emergencia",
        "sheet_id": "1CMqxZEotUp8HaX-h35YJLfkWC6zBZIjtxGvT3aJH-wY",
        "worksheet_name": "E"
    },
    "hospitalizacion": {
        "label": "Hospitalización",
        "sheet_id": "1BSMXbCf0zInOwxZ-IXGAKmeguNenTlQBZ0JgUtgehYA", # ID 100% EXACTO 
        "worksheet_name": "H"
    }
}

USERS_SHEET_ID = AREAS_CONFIG["consulta_externa"]["sheet_id"]
USERS_SHEET_TAB  = "USUARIOS_SISTEMA"

# ============================================================
# CRITERIOS — CONSULTA EXTERNA
# ============================================================
CRITERIOS_CE = {
    "FILIACION":{"label":"Filiación","max":4,"items":[
        {"campo":"FILIACIÓN [Número de historia clínica]","nombre":"N° historia clínica","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Nombres y apellidos del paciente]","nombre":"Nombres y apellidos","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Tipo y número de Seguro]","nombre":"Tipo y N° de Seguro","completo":0.25,"incompleto":0,"noExiste":0,"naOk":True},
        {"campo":"FILIACIÓN [Lugar y fecha de nacimiento]","nombre":"Lugar y fecha de nacimiento","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Edad]","nombre":"Edad","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Sexo]","nombre":"Sexo","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Domicilio actual]","nombre":"Domicilio actual","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Lugar de Procedencia]","nombre":"Lugar de Procedencia","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Documento de identificación]","nombre":"Documento de identificación","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Estado Civil]","nombre":"Estado Civil","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Grado de instrucción]","nombre":"Grado de instrucción","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Ocupación]","nombre":"Ocupación","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Religión]","nombre":"Religión","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Teléfono]","nombre":"Teléfono","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Acompañante]","nombre":"Acompañante","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Domicilio y/o teléfono de la persona responsable]","nombre":"Domicilio/tel. responsable","completo":0.25,"incompleto":0,"noExiste":0},
    ]},
    "ANAMNESIS":{"label":"Anamnesis","max":9,"items":[
        {"campo":"ANAMNESIS [Fecha y hora de atención]","nombre":"Fecha y hora de atención","completo":1,"incompleto":0.5,"noExiste":0},
        {"campo":"ANAMNESIS [Motivo de la consulta]","nombre":"Motivo de la consulta","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"ANAMNESIS [Tiempo de enfermedad]","nombre":"Tiempo de enfermedad","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"ANAMNESIS [Relato cronológico]","nombre":"Relato cronológico","completo":3,"incompleto":1.5,"noExiste":0},
        {"campo":"ANAMNESIS [Funciones Biológicas]","nombre":"Funciones Biológicas","completo":1,"incompleto":0.5,"noExiste":0},
        {"campo":"ANAMNESIS [Antecedentes]","nombre":"Antecedentes","completo":2,"incompleto":1,"noExiste":0},
    ]},
    "EXAMEN_CLINICO":{"label":"Examen Clínico","max":9,"items":[
        {"campo":"EXAMEN CLÍNICO [Funciones vitales  T°, FR, FC, PA.]","nombre":"Funciones vitales","completo":2,"incompleto":0.5,"noExiste":0},
        {"campo":"EXAMEN CLÍNICO [Peso, Talla]","nombre":"Peso, Talla","completo":1,"incompleto":0.5,"noExiste":0},
        {"campo":"EXAMEN CLÍNICO [Estado general, estado de hidratación, estado de nutrición, estado de conciencia, piel y anexos.]","nombre":"Estado general","completo":2,"incompleto":1,"noExiste":0},
        {"campo":"EXAMEN CLÍNICO [Examen Clínico Regional]","nombre":"Examen Clínico Regional","completo":4,"incompleto":2,"noExiste":0},
    ]},
    "DIAGNOSTICOS":{"label":"Diagnósticos","max":20,"items":[
        {"campo":"DIAGNÓSTICOS  [Presuntivo coherente]","nombre":"Presuntivo coherente","completo":8,"incompleto":4,"noExiste":0,"naOk":True},
        {"campo":"DIAGNÓSTICOS  [Definitivo coherente]","nombre":"Definitivo coherente","completo":8,"incompleto":4,"noExiste":0,"naOk":True},
        {"campo":"DIAGNÓSTICOS  [Uso del CIE 10]","nombre":"Uso del CIE 10","completo":4,"incompleto":0,"noExiste":0},
    ]},
    "PLAN_TRABAJO":{"label":"Plan de Trabajo","max":24,"items":[
        {"campo":"PLAN DE TRABAJO  [Exámenes de Patología Clínica  pertinentes]","nombre":"Patología Clínica","completo":5,"incompleto":1,"enExceso":2,"noExiste":0,"naOk":True},
        {"campo":"PLAN DE TRABAJO  [Exámenes de Diagnóstico por Imágenes  pertinentes]","nombre":"Diagnóstico por Imágenes","completo":5,"incompleto":1,"enExceso":2,"noExiste":0,"naOk":True},
        {"campo":"PLAN DE TRABAJO  [Interconsultas (a otros servicios dentro del establecimiento de saludpertinentes )]","nombre":"Interconsultas","completo":4,"incompleto":1,"enExceso":2,"noExiste":0,"naOk":True},
        {"campo":"PLAN DE TRABAJO  [Referencias a otros establecimientos de salud.]","nombre":"Referencias","completo":4,"incompleto":0,"noExiste":0,"naOk":True},
        {"campo":"PLAN DE TRABAJO  [Procedimientos diagnósticos y/o terapéuticos pertinentes.]","nombre":"Procedimientos dx/tx","completo":4,"incompleto":1,"enExceso":2,"noExiste":0,"naOk":True},
        {"campo":"PLAN DE TRABAJO  [Fecha de próxima cita.]","nombre":"Fecha próxima cita","completo":2,"incompleto":0,"noExiste":0,"naOk":True},
    ]},
    "TRATAMIENTO":{"label":"Tratamiento","max":17,"items":[
        {"campo":"TRATAMIENTO [Régimen higiénico-dietético y medidas generales concordantes y coherentes.]","nombre":"Régimen higiénico-dietético","completo":4,"incompleto":2,"noExiste":0,"naOk":True},
        {"campo":"TRATAMIENTO [Nombre de medicamentos coherentes y concordante con Denominación Común Internacional (DCI)]","nombre":"Medicamentos (DCI)","completo":4,"incompleto":2,"noExiste":0,"naOk":True},
        {"campo":"TRATAMIENTO [Consigna presentación]","nombre":"Consigna presentación","completo":2,"incompleto":0,"noExiste":0,"naOk":True},
        {"campo":"TRATAMIENTO [Dosis del medicamento]","nombre":"Dosis del medicamento","completo":2,"incompleto":0,"noExiste":0,"naOk":True},
        {"campo":"TRATAMIENTO [Vía de administración]","nombre":"Vía de administración","completo":2,"incompleto":0,"noExiste":0,"naOk":True},
        {"campo":"TRATAMIENTO [Frecuencia del medicamento]","nombre":"Frecuencia medicamento","completo":2,"incompleto":0,"noExiste":0,"naOk":True},
        {"campo":"TRATAMIENTO [Duración del tratamiento]","nombre":"Duración del tratamiento","completo":1,"incompleto":0.5,"noExiste":0,"naOk":True},
    ]},
    "ATRIBUTOS":{"label":"Atributos HC","max":7,"items":[
        {"campo":"ATRIBUTO DE LA HISTORIA CLÍNICA [Se cuenta con Formatos de Atención Integral por etapas de vida ( Primer Nivel de Atención)]","nombre":"Formatos Atención Integral","completo":2,"incompleto":1,"noExiste":0,"naOk":True},
        {"campo":"ATRIBUTO DE LA HISTORIA CLÍNICA [Pulcritud]","nombre":"Pulcritud","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"ATRIBUTO DE LA HISTORIA CLÍNICA [Letra legible]","nombre":"Letra legible","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"ATRIBUTO DE LA HISTORIA CLÍNICA [No uso de abreviaturas]","nombre":"No uso de abreviaturas","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"ATRIBUTO DE LA HISTORIA CLÍNICA [Sello y firma del médico tratante]","nombre":"Sello y firma médico","completo":2,"incompleto":1,"noExiste":0},
    ]},
    "SEGUIMIENTO":{"label":"Seguimiento de Evolución","max":10,"items":[
        {"campo":"ATRIBUTO DE LA HISTORIA CLÍNICA [SEGUIMIENTO DE LA EVOLUCIÓN]","nombre":"Seguimiento de la Evolución","completo":10,"incompleto":5,"noExiste":0,"naOk":True},
    ]},
}

# ============================================================
# CRITERIOS — EMERGENCIA
# ============================================================
CRITERIOS_EME = {
    "FILIACION":{"label":"Filiación","max":8,"items":[
        {"campo":"FILIACIÓN (8 ptos) [Número de historia clínica (0.5 ptos)]","nombre":"N° historia clínica","conforme":0.5,"noConforme":0},
        {"campo":"FILIACIÓN (8 ptos) [Nombres y apellidos del paciente (0.5 ptos)]","nombre":"Nombres y apellidos","conforme":0.5,"noConforme":0},
        {"campo":"FILIACIÓN (8 ptos) [Tipo y Nº Seguro (0.5 ptos)]","nombre":"Tipo y N° Seguro","conforme":0.5,"noConforme":0,"naOk":True},
        {"campo":"FILIACIÓN (8 ptos) [Lugar y fecha de nacimiento (0.5 ptos)]","nombre":"Lugar y fecha nacimiento","conforme":0.5,"noConforme":0,"naOk":True},
        {"campo":"FILIACIÓN (8 ptos) [Edad (0.5 ptos)]","nombre":"Edad","conforme":0.5,"noConforme":0,"naOk":True},
        {"campo":"FILIACIÓN (8 ptos) [Sexo (0.5 ptos)]","nombre":"Sexo","conforme":0.5,"noConforme":0},
        {"campo":"FILIACIÓN (8 ptos) [Domicilio actual (0.5 ptos)]","nombre":"Domicilio actual","conforme":0.5,"noConforme":0,"naOk":True},
        {"campo":"FILIACIÓN (8 ptos) [Lugar de Procedencia (0.5 ptos)]","nombre":"Lugar de Procedencia","conforme":0.5,"noConforme":0,"naOk":True},
        {"campo":"FILIACIÓN (8 ptos) [Documento de identificación (0.5 ptos)]","nombre":"Documento de identificación","conforme":0.5,"noConforme":0,"naOk":True},
        {"campo":"FILIACIÓN (8 ptos) [Estado Civil (0.5 ptos)]","nombre":"Estado Civil","conforme":0.5,"noConforme":0,"naOk":True},
        {"campo":"FILIACIÓN (8 ptos) [Grado de instrucción (0.5 ptos)]","nombre":"Grado de instrucción","conforme":0.5,"noConforme":0,"naOk":True},
        {"campo":"FILIACIÓN (8 ptos) [Ocupación (0.5 ptos)]","nombre":"Ocupación","conforme":0.5,"noConforme":0,"naOk":True},
        {"campo":"FILIACIÓN (8 ptos) [Religión (0.5 ptos)]","nombre":"Religión","conforme":0.5,"noConforme":0,"naOk":True},
        {"campo":"FILIACIÓN (8 ptos) [Teléfono (0.5 ptos)]","nombre":"Teléfono","conforme":0.5,"noConforme":0,"naOk":True},
        {"campo":"FILIACIÓN (8 ptos) [Acompañante (0.5 ptos)]","nombre":"Acompañante","conforme":0.5,"noConforme":0,"naOk":True},
        {"campo":"FILIACIÓN (8 ptos) [Domicilio y/o teléfono de la persona responsable (0.5 ptos)]","nombre":"Domicilio/tel. responsable","conforme":0.5,"noConforme":0,"naOk":True},
    ]},
    "ANAMNESIS":{"label":"Anamnesis","max":13,"items":[
        {"campo":"ANAMNESIS (13 ptos) [Fecha y hora de atención (2 ptos)]","nombre":"Fecha y hora de atención","conforme":2,"noConforme":0},
        {"campo":"ANAMNESIS (13 ptos) [Tiempo de enfermedad (1 pto)]","nombre":"Tiempo de enfermedad","conforme":1,"noConforme":0},
        {"campo":"ANAMNESIS (13 ptos) [Signos y síntomas principales (2 ptos)]","nombre":"Signos y síntomas","conforme":2,"noConforme":0},
        {"campo":"ANAMNESIS (13 ptos) [Desarrollo cronológico de la enfermedad (relato) (5 ptos)]","nombre":"Desarrollo cronológico","conforme":5,"noConforme":0,"naOk":True},
        {"campo":"ANAMNESIS (13 ptos) [Antecedentes (3 ptos)]","nombre":"Antecedentes","conforme":3,"noConforme":0,"naOk":True},
    ]},
    "EXAMEN_CLINICO":{"label":"Examen Clínico","max":10,"items":[
        {"campo":"EXAMEN CLÍNICO (10 ptos) [Funciones vitales Temperatura (T°), Frecuencia respiratoria (FR), Frecuencia cardiaca (FC), Presión arterial (PA), Saturación de oxígeno (Sat O2) en caso lo amerite (2 ptos)]","nombre":"Funciones vitales + SatO2","conforme":2,"noConforme":0},
        {"campo":"EXAMEN CLÍNICO (10 ptos) [Puntaje de Escala de Glasgow (1 pto)]","nombre":"Escala de Glasgow","conforme":1,"noConforme":0,"naOk":True},
        {"campo":"EXAMEN CLÍNICO (10 ptos) [Peso (1 pto)]","nombre":"Peso","conforme":1,"noConforme":0,"naOk":True},
        {"campo":"EXAMEN CLÍNICO (10 ptos) [Estado general, estado de hidratación, estado de nutrición, estado de conciencia, piel y anexos (2 ptos)]","nombre":"Estado general","conforme":2,"noConforme":0},
        {"campo":"EXAMEN CLÍNICO (10 ptos) [Examen clínico regional (4 ptos)]","nombre":"Examen clínico regional","conforme":4,"noConforme":0},
    ]},
    "DIAGNOSTICOS":{"label":"Diagnósticos","max":20,"items":[
        {"campo":"DIAGNÓSTICOS (20 ptos) [Presuntivo coherente (8 ptos)]","nombre":"Presuntivo coherente","conforme":8,"noConforme":0,"naOk":True},
        {"campo":"DIAGNÓSTICOS (20 ptos) [Definitivo coherente (8 ptos)]","nombre":"Definitivo coherente","conforme":8,"noConforme":0,"naOk":True},
        {"campo":"DIAGNÓSTICOS (20 ptos) [Uso del CIE 10 (4 ptos)]","nombre":"Uso del CIE 10","conforme":4,"noConforme":0},
    ]},
    "PLAN_TRABAJO":{"label":"Plan de Trabajo","max":19,"items":[
        {"campo":"PLAN DE TRABAJO (19 ptos) [Exámenes de Patología Clínica pertinentes (4 ptos)]","nombre":"Patología Clínica","conforme":4,"noConforme":0},
        {"campo":"PLAN DE TRABAJO (19 ptos) [Exámenes de Diagnóstico por imágenes pertinentes (4 ptos)]","nombre":"Diagnóstico por Imágenes","conforme":4,"noConforme":0,"naOk":True},
        {"campo":"PLAN DE TRABAJO (19 ptos) [Interconsultas pertinentes (3 ptos)]","nombre":"Interconsultas","conforme":3,"noConforme":0,"naOk":True},
        {"campo":"PLAN DE TRABAJO (19 ptos) [Referencia oportuna (3 ptos)]","nombre":"Referencia oportuna","conforme":3,"noConforme":0,"naOk":True},
        {"campo":"PLAN DE TRABAJO (19 ptos) [Procedimientos diagnósticos y/o terapéuticos pertinentes (3 ptos)]","nombre":"Procedimientos dx/tx","conforme":3,"noConforme":0,"naOk":True},
        {"campo":"PLAN DE TRABAJO (19 ptos) [Exámenes de Laboratorio en Historia Clínica (0.5 ptos)]","nombre":"Lab. en HC","conforme":0.5,"noConforme":0},
        {"campo":"PLAN DE TRABAJO (19 ptos) [Exámenes de Imágenes en Historia Clínica (0.5 ptos)]","nombre":"Imágenes en HC","conforme":0.5,"noConforme":0,"naOk":True},
        {"campo":"PLAN DE TRABAJO (19 ptos) [Respuesta de interconsultas en Historia Clínica (0.5 ptos)]","nombre":"Respuesta interconsultas","conforme":0.5,"noConforme":0,"naOk":True},
        {"campo":"PLAN DE TRABAJO (19 ptos) [Procedimientos en Historia Clínica (0.5 ptos)]","nombre":"Procedimientos en HC","conforme":0.5,"noConforme":0,"naOk":True},
    ]},
    "ALTA":{"label":"Indicaciones de Alta","max":3,"items":[
        {"campo":"ESPECIFICA INDICACIONES DE ALTA (3 ptos) [Condición de egreso del paciente (1 pto)]","nombre":"Condición de egreso","conforme":1,"noConforme":0},
        {"campo":"ESPECIFICA INDICACIONES DE ALTA (3 ptos) [Medicamentos prescritos (1 pto)]","nombre":"Medicamentos prescritos","conforme":1,"noConforme":0,"naOk":True},
        {"campo":"ESPECIFICA INDICACIONES DE ALTA (3 ptos) [Cuidados Generales e indicaciones de reevaluación posterior por consulta externa (1 pto)]","nombre":"Cuidados e indicaciones","conforme":1,"noConforme":0,"naOk":True},
    ]},
    "TRATAMIENTO":{"label":"Tratamiento","max":8,"items":[
        {"campo":"TRATAMIENTO (8 ptos) [Medidas Generales (2 ptos)]","nombre":"Medidas Generales","conforme":2,"noConforme":0,"naOk":True},
        {"campo":"TRATAMIENTO (8 ptos) [Nombre de medicamentos pertinentes con Denominación Común Internacional (DCI) (2 ptos)]","nombre":"Medicamentos (DCI)","conforme":2,"noConforme":0,"naOk":True},
        {"campo":"TRATAMIENTO (8 ptos) [Consigna presentación (1 pto)]","nombre":"Consigna presentación","conforme":1,"noConforme":0,"naOk":True},
        {"campo":"TRATAMIENTO (8 ptos) [Dosis del medicamento (1 pto)]","nombre":"Dosis del medicamento","conforme":1,"noConforme":0,"naOk":True},
        {"campo":"TRATAMIENTO (8 ptos) [Frecuencia del medicamento (1 pto)]","nombre":"Frecuencia medicamento","conforme":1,"noConforme":0,"naOk":True},
        {"campo":"TRATAMIENTO (8 ptos) [Vía de administración (1 pto)]","nombre":"Vía de administración","conforme":1,"noConforme":0,"naOk":True},
    ]},
    "NOTAS_EVOLUCION":{"label":"Notas de Evolución","max":11,"items":[
        {"campo":"NOTAS DE EVOLUCIÓN (11 ptos) [Fecha y hora de evolución (1 pto)]","nombre":"Fecha y hora evolución","conforme":1,"noConforme":0},
        {"campo":"NOTAS DE EVOLUCIÓN (11 ptos) [Nota de Ingreso (1 pto)]","nombre":"Nota de Ingreso","conforme":1,"noConforme":0},
        {"campo":"NOTAS DE EVOLUCIÓN (11 ptos) [Apreciación subjetiva (1 pto)]","nombre":"Apreciación subjetiva","conforme":1,"noConforme":0},
        {"campo":"NOTAS DE EVOLUCIÓN (11 ptos) [Apreciación objetiva (1 pto)]","nombre":"Apreciación objetiva","conforme":1,"noConforme":0},
        {"campo":"NOTAS DE EVOLUCIÓN (11 ptos) [Verificación del tratamiento y dieta (1 pto)]","nombre":"Verificación trat./dieta","conforme":1,"noConforme":0,"naOk":True},
        {"campo":"NOTAS DE EVOLUCIÓN (11 ptos) [Interpretación de exámenes y comentario (2 ptos)]","nombre":"Interpretación exámenes","conforme":2,"noConforme":0},
        {"campo":"NOTAS DE EVOLUCIÓN (11 ptos) [Plan de trabajo (2 ptos)]","nombre":"Plan de trabajo","conforme":2,"noConforme":0},
        {"campo":"NOTAS DE EVOLUCIÓN (11 ptos) [Consigna funciones vitales (1 pto)]","nombre":"Consigna func. vitales","conforme":1,"noConforme":0},
        {"campo":"NOTAS DE EVOLUCIÓN (11 ptos) [Procedimientos realizados (1 pto)]","nombre":"Procedimientos realizados","conforme":1,"noConforme":0,"naOk":True},
    ]},
    "REGISTROS_ENF":{"label":"Registros Obst./Enfermería","max":3,"items":[
        {"campo":"REGISTROS DE OBSTETRICIA Y/O ENFERMERÍA (3 ptos) [Notas de ingreso de obstetricia y/o enfermería (0.5 ptos)]","nombre":"Notas ingreso enf.","conforme":0.5,"noConforme":0,"naOk":True},
        {"campo":"REGISTROS DE OBSTETRICIA Y/O ENFERMERÍA (3 ptos) [Notas obstetricia y/o enfermería (0.5 ptos)]","nombre":"Notas obs./enf.","conforme":0.5,"noConforme":0,"naOk":True},
        {"campo":"REGISTROS DE OBSTETRICIA Y/O ENFERMERÍA (3 ptos) [Hoja de funciones vitales (0.5 ptos)]","nombre":"Hoja func. vitales","conforme":0.5,"noConforme":0,"naOk":True},
        {"campo":"REGISTROS DE OBSTETRICIA Y/O ENFERMERÍA (3 ptos) [Hoja de balance hídrico (0.5 ptos)]","nombre":"Balance hídrico","conforme":0.5,"noConforme":0,"naOk":True},
        {"campo":"REGISTROS DE OBSTETRICIA Y/O ENFERMERÍA (3 ptos) [Kardex (0.5 ptos)]","nombre":"Kardex","conforme":0.5,"noConforme":0,"naOk":True},
        {"campo":"REGISTROS DE OBSTETRICIA Y/O ENFERMERÍA (3 ptos) [Firma y sello del Profesional (0.5 ptos)]","nombre":"Firma/sello profesional","conforme":0.5,"noConforme":0,"naOk":True},
    ]},
    "ATRIBUTOS":{"label":"Atributos de la HC","max":5,"items":[
        {"campo":"ATRIBUTOS DE LA HISTORIA CLÍNICA (5 ptos) [Firma y sello del médico tratante (1 pto)]","nombre":"Firma/sello médico","conforme":1,"noConforme":0},
        {"campo":"ATRIBUTOS DE LA HISTORIA CLÍNICA (5 ptos) [Prioridad de atención (1 pto)]","nombre":"Prioridad de atención","conforme":1,"noConforme":0},
        {"campo":"ATRIBUTOS DE LA HISTORIA CLÍNICA (5 ptos) [Pulcritud (1 pto)]","nombre":"Pulcritud","conforme":1,"noConforme":0},
        {"campo":"ATRIBUTOS DE LA HISTORIA CLÍNICA (5 ptos) [Legibilidad (1 pto)]","nombre":"Legibilidad","conforme":1,"noConforme":0},
        {"campo":"ATRIBUTOS DE LA HISTORIA CLÍNICA (5 ptos) [No uso de abreviaturas (1 pto)]","nombre":"No uso abreviaturas","conforme":1,"noConforme":0},
    ]},
}

# ============================================================
# CRITERIOS — HOSPITALIZACIÓN
# ============================================================
CRITERIOS_HOSP = {
    "FILIACION":{"label":"Filiación","max":4.5,"items":[
        {"campo":"FILIACIÓN [Número de historia clínica]","nombre":"N° historia clínica","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Nombres y apellidos del paciente]","nombre":"Nombres y apellidos","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Tipo y Nº Seguro]","nombre":"Tipo y N° Seguro","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Lugar y fecha de nacimiento]","nombre":"Lugar y fecha nacimiento","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Edad]","nombre":"Edad","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Sexo]","nombre":"Sexo","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Domicilio actual]","nombre":"Domicilio actual","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Lugar de Procedencia]","nombre":"Lugar de Procedencia","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Documento de identificación]","nombre":"Documento de identificación","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Estado Civil]","nombre":"Estado Civil","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Grado de instrucción]","nombre":"Grado de instrucción","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Ocupación]","nombre":"Ocupación","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Religión]","nombre":"Religión","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Teléfono]","nombre":"Teléfono","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Acompañante]","nombre":"Acompañante","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Domicilio y/o teléfono de la persona responsable]","nombre":"Domicilio/tel. responsable","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Fecha de Ingreso]","nombre":"Fecha de Ingreso","completo":0.25,"incompleto":0,"noExiste":0},
        {"campo":"FILIACIÓN [Fecha de elaboración de historia clínica]","nombre":"Fecha elaboración HC","completo":0.25,"incompleto":0,"noExiste":0},
    ]},
    "ENFERMEDAD_ANT":{"label":"Enfermedad y Antecedentes","max":10,"items":[
        {"campo":"ENFERMEDAD Y ANTECEDENTES [Signos y Síntomas principales]","nombre":"Signos y síntomas","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"ENFERMEDAD Y ANTECEDENTES [Tiempo de enfermedad]","nombre":"Tiempo de enfermedad","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"ENFERMEDAD Y ANTECEDENTES [Forma de inicio]","nombre":"Forma de inicio","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"ENFERMEDAD Y ANTECEDENTES [Curso de la enfermedad]","nombre":"Curso de la enfermedad","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"ENFERMEDAD Y ANTECEDENTES [Relato Cronológico de la enfermedad]","nombre":"Relato cronológico","completo":3,"incompleto":1,"noExiste":0},
        {"campo":"ENFERMEDAD Y ANTECEDENTES [Funciones Biológicas]","nombre":"Funciones Biológicas","completo":1,"incompleto":1,"noExiste":0},
        {"campo":"ENFERMEDAD Y ANTECEDENTES [Antecedentes]","nombre":"Antecedentes","completo":2,"incompleto":1,"noExiste":0},
    ]},
    "EXAMEN_CLINICO":{"label":"Examen Clínico","max":7,"items":[
        {"campo":"EXAMEN CLÍNICO [Funciones vitales: Temperatura (Tº), Frecuencia respiratoria (FR), Frecuencia cardiaca (FC), Presión arterial (PA).]","nombre":"Funciones vitales","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"EXAMEN CLÍNICO [Peso ,Talla , IMC]","nombre":"Peso, Talla, IMC","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"EXAMEN CLÍNICO [Estado general, estado de hidratación, estado de nutrición, estado de conciencia, piel y anexos.]","nombre":"Estado general","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"EXAMEN CLÍNICO [Examen Clínico Regional]","nombre":"Examen Clínico Regional","completo":4,"incompleto":2,"noExiste":0},
    ]},
    "DIAGNOSTICOS":{"label":"Diagnósticos","max":20,"items":[
        {"campo":"DIAGNÓSTICOS [Presuntivo coherente y concordante.]","nombre":"Presuntivo coherente","completo":8,"incompleto":4,"noExiste":0,"naOk":True},
        {"campo":"DIAGNÓSTICOS [Definitivo coherente y concordante.]","nombre":"Definitivo coherente","completo":8,"incompleto":4,"noExiste":0,"naOk":True},
        {"campo":"DIAGNÓSTICOS [Uso del CIE 10]","nombre":"Uso del CIE 10","completo":4,"incompleto":2,"noExiste":0},
    ]},
    "PLAN_TRABAJO":{"label":"Plan de Trabajo","max":19,"items":[
        {"campo":"PLAN DE TRABAJO [Exámenes de Patología Clínica pertinentes]","nombre":"Patología Clínica","completo":3,"incompleto":1,"enExceso":2,"noExiste":0,"naOk":True},
        {"campo":"PLAN DE TRABAJO [Exámenes de Diagnóstico por imágenes pertinentes]","nombre":"Diagnóstico por Imágenes","completo":4,"incompleto":1,"enExceso":2,"noExiste":0,"naOk":True},
        {"campo":"PLAN DE TRABAJO [Interconsultas pertinentes]","nombre":"Interconsultas","completo":4,"incompleto":1,"enExceso":2,"noExiste":0,"naOk":True},
        {"campo":"PLAN DE TRABAJO [Referencias Oportunas]","nombre":"Referencias Oportunas","completo":4,"incompleto":0,"noExiste":0,"naOk":True},
        {"campo":"PLAN DE TRABAJO [Procedimientos diagnósticos y/o terapéuticos pertinentes]","nombre":"Procedimientos dx/tx","completo":4,"incompleto":1,"enExceso":2,"noExiste":0,"naOk":True},
    ]},
    "TRATAMIENTO":{"label":"Tratamiento","max":14,"items":[
        {"campo":"TRATAMIENTO [Régimen higiénico-dietético y medidas generales concordantes y coherentes.]","nombre":"Régimen higiénico-dietético","completo":4,"incompleto":2,"noExiste":0},
        {"campo":"TRATAMIENTO [Nombre de medicamentos coherentes y concordantes con Denominación Común Internacional (DCI).]","nombre":"Medicamentos (DCI)","completo":4,"incompleto":2,"noExiste":0},
        {"campo":"TRATAMIENTO [Consigna presentación]","nombre":"Consigna presentación","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"TRATAMIENTO [Dosis del medicamento]","nombre":"Dosis del medicamento","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"TRATAMIENTO [Frecuencia del medicamento]","nombre":"Frecuencia medicamento","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"TRATAMIENTO [Vía de administración]","nombre":"Vía de administración","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"TRATAMIENTO [Cuidados de Enfermería y otros profesionales]","nombre":"Cuidados de Enfermería","completo":2,"incompleto":0,"noExiste":0},
    ]},
    "NOTAS_EVOLUCION":{"label":"Notas de Evolución","max":4,"items":[
        {"campo":"NOTAS DE EVOLUCIÓN [Fecha y hora de evolución]","nombre":"Fecha y hora evolución","completo":0.5,"incompleto":0,"noExiste":0},
        {"campo":"NOTAS DE EVOLUCIÓN [Apreciación subjetiva]","nombre":"Apreciación subjetiva","completo":0.5,"incompleto":0,"noExiste":0},
        {"campo":"NOTAS DE EVOLUCIÓN [Apreciación objetiva]","nombre":"Apreciación objetiva","completo":0.5,"incompleto":0,"noExiste":0},
        {"campo":"NOTAS DE EVOLUCIÓN [Verificación del tratamiento y dieta]","nombre":"Verificación trat./dieta","completo":0.5,"incompleto":0,"noExiste":0,"naOk":True},
        {"campo":"NOTAS DE EVOLUCIÓN [Interpretación de exámenes de apoyo al diagnóstico y comentario]","nombre":"Interpretación exámenes","completo":0.5,"incompleto":0,"noExiste":0},
        {"campo":"NOTAS DE EVOLUCIÓN [Plan diagnóstico]","nombre":"Plan diagnóstico","completo":0.5,"incompleto":0,"noExiste":0,"naOk":True},
        {"campo":"NOTAS DE EVOLUCIÓN [Plan terapéutico]","nombre":"Plan terapéutico","completo":0.5,"incompleto":0,"noExiste":0},
        {"campo":"NOTAS DE EVOLUCIÓN [Firma y sello del médico que evoluciona]","nombre":"Firma/sello médico evolución","completo":0.5,"incompleto":0,"noExiste":0},
    ]},
    "REGISTROS_ENF":{"label":"Registros Enf./Obstetricia","max":6,"items":[
        {"campo":"REGISTROS DE OBSTETRICIA Y/O ENFERMERÍA [Notas de ingreso de enfermería/obstetricia]","nombre":"Notas ingreso enf.","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"REGISTROS DE OBSTETRICIA Y/O ENFERMERÍA [Notas de Evolución de enfermería/obstetricia]","nombre":"Notas evolución enf.","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"REGISTROS DE OBSTETRICIA Y/O ENFERMERÍA [Hoja de Gráfica de Signos vitales]","nombre":"Hoja gráfica signos vitales","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"REGISTROS DE OBSTETRICIA Y/O ENFERMERÍA [Hoja de balance hídrico]","nombre":"Balance hídrico","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"REGISTROS DE OBSTETRICIA Y/O ENFERMERÍA [Kardex]","nombre":"Kardex","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"REGISTROS DE OBSTETRICIA Y/O ENFERMERÍA [Firma y sello del Profesional]","nombre":"Firma/sello profesional","completo":1,"incompleto":0,"noExiste":0},
    ]},
    "ALTA":{"label":"Indicaciones de Alta","max":3,"items":[
        {"campo":"ESPECIFICA INDICACIONES DE ALTA [Informe de Alta]","nombre":"Informe de Alta","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"ESPECIFICA INDICACIONES DE ALTA [Medicamentos prescritos]","nombre":"Medicamentos prescritos","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"ESPECIFICA INDICACIONES DE ALTA [Cuidados generales e indicaciones de reevaluación posterior por consulta externa]","nombre":"Cuidados e indicaciones","completo":1,"incompleto":0,"noExiste":0},
    ]},
    "ATRIBUTOS":{"label":"Atributos de la HC","max":5,"items":[
        {"campo":"ATRIBUTOS DE HISTORIA CLÍNICA [Firma y sello del médico tratante]","nombre":"Firma/sello médico","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"ATRIBUTOS DE HISTORIA CLÍNICA [Orden cronológico de las hojas de la historia clínica]","nombre":"Orden cronológico","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"ATRIBUTOS DE HISTORIA CLÍNICA [Pulcritud]","nombre":"Pulcritud","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"ATRIBUTOS DE HISTORIA CLÍNICA [Legibilidad]","nombre":"Legibilidad","completo":1,"incompleto":0,"noExiste":0},
        {"campo":"ATRIBUTOS DE HISTORIA CLÍNICA [No uso de abreviaturas]","nombre":"No uso de abreviaturas","completo":1,"incompleto":0,"noExiste":0},
    ]},
    "FORMATOS_ESP":{"label":"Formatos Especiales","max":7.5,"items":[
        {"campo":"FORMATOS ESPECIALES [Formato de interconsulta]","nombre":"Formato interconsulta","completo":0.5,"incompleto":0,"noExiste":0,"naOk":True},
        {"campo":"FORMATOS ESPECIALES [Formato de orden de intervención quirúrgica]","nombre":"Orden intervención qx","completo":0.5,"incompleto":0,"noExiste":0,"naOk":True},
        {"campo":"FORMATOS ESPECIALES [Reporte operatorio]","nombre":"Reporte operatorio","completo":0.5,"incompleto":0,"noExiste":0,"naOk":True},
        {"campo":"FORMATOS ESPECIALES [Hoja de evolución pre anestésica]","nombre":"Evolución pre-anestésica","completo":0.5,"incompleto":0,"noExiste":0,"naOk":True},
        {"campo":"FORMATOS ESPECIALES [Lista de verificación de seguridad de la cirugía]","nombre":"Lista verificación cirugía","completo":1,"incompleto":0,"noExiste":0,"naOk":True},
        {"campo":"FORMATOS ESPECIALES [Hoja de anestesia]","nombre":"Hoja de anestesia","completo":0.5,"incompleto":0,"noExiste":0,"naOk":True},
        {"campo":"FORMATOS ESPECIALES [Hoja post anestésica]","nombre":"Hoja post anestésica","completo":0.5,"incompleto":0,"noExiste":0,"naOk":True},
        {"campo":"FORMATOS ESPECIALES [Formatos de patología clínica formato de diagnóstico por imágenes]","nombre":"Patología/imágenes fmt.","completo":0.5,"incompleto":0,"noExiste":0,"naOk":True},
        {"campo":"FORMATOS ESPECIALES [Formato de anatomía patológica]","nombre":"Anatomía patológica","completo":0.5,"incompleto":0,"noExiste":0,"naOk":True},
        {"campo":"FORMATOS ESPECIALES [Formato de consentimiento informado]","nombre":"Consentimiento informado","completo":1,"incompleto":0,"noExiste":0,"naOk":True},
        {"campo":"FORMATOS ESPECIALES [Formato de retiro voluntario]","nombre":"Retiro voluntario","completo":0.5,"incompleto":0,"noExiste":0,"naOk":True},
        {"campo":"FORMATOS ESPECIALES [Epicrisis]","nombre":"Epicrisis","completo":1,"incompleto":0,"noExiste":0,"naOk":True},
    ]},
}

CRITERIOS_POR_AREA = {
    "consulta_externa": CRITERIOS_CE,
    "emergencia":       CRITERIOS_EME,
    "hospitalizacion":  CRITERIOS_HOSP,
}

# ============================================================
# GOOGLE SHEETS
# ============================================================
def get_client():
    creds = Credentials.from_service_account_file(CREDENCIALES_PATH, scopes=SCOPES)
    return gspread.authorize(creds)

def get_dataframe(sheet_id, worksheet_name):
    client = get_client()
    try:
        hoja = client.open_by_key(sheet_id)
    except Exception as e:
        raise Exception("No se pudo acceder al archivo. Verifica que el ID sea correcto y hayas compartido el archivo.")
    try:
        ws = hoja.worksheet(worksheet_name)
    except Exception:
        disp = ", ".join([w.title for w in hoja.worksheets()])
        raise Exception(f"No se encontró la pestaña '{worksheet_name}'. Pestañas existentes: {disp}")
    return pd.DataFrame(ws.get_all_records())

def get_users_sheet():
    client = get_client()
    hoja = client.open_by_key(USERS_SHEET_ID)
    try:
        ws = hoja.worksheet(USERS_SHEET_TAB)
    except Exception:
        ws = hoja.add_worksheet(title=USERS_SHEET_TAB, rows=100, cols=5)
        ws.append_row(["usuario","password_hash","nombre","rol","activo"])
        ws.append_row(["admin", hashlib.sha256("admin123".encode()).hexdigest(), "Administrador","admin","1"])
    return ws

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def calcular_row_ce_hosp(row, criterios):
    total=0; na_total=0; secciones={}
    for sec_key, sec in criterios.items():
        sub=0; na_sec=0; items=[]
        for c in sec["items"]:
            # Obtener valor seguro
            val=""
            for k, v in row.items():
                if str(k).strip() == c["campo"].strip() or c["campo"][:30].lower() in str(k).lower():
                    val = str(v).strip().upper()
                    break
                    
            pts=0; estado="sin_dato"
            if val in ("COMPLETO","C","CONFORME"):   pts=c["completo"]; estado="completo"
            elif val in ("INCOMPLETO","I"):          pts=c.get("incompleto",0); estado="incompleto"
            elif val in ("EN EXCESO","E"):           pts=c.get("enExceso",0); estado="en_exceso"
            elif val in ("NO EXISTE","NE","NO CONFORME"): pts=0; estado="no_existe"
            elif val in ("NO APLICA","NA"):          pts=0; na_sec+=c["completo"]; estado="na"
            
            items.append({"nombre":c["nombre"],"pts":pts,"max":c["completo"],"estado":estado})
            sub+=pts
        na_total+=na_sec; total+=sub
        secciones[sec_key]={"label":sec["label"],"subtotal":sub,"max":sec["max"],"items":items}
    
    max_ap=100-na_total
    pct=round((total/max_ap*100),2) if max_ap>0 else 0
    calif="SATISFACTORIO" if pct>=90 else ("POR MEJORAR" if pct>=75 else "DEFICIENTE")
    return {"puntaje":round(total,2),"max_aplicable":round(max_ap,2),"porcentaje":pct,"calificacion":calif,"secciones":secciones}

def calcular_row_eme(row, criterios):
    total=0; na_total=0; secciones={}
    for sec_key, sec in criterios.items():
        sub=0; na_sec=0; items=[]
        for c in sec["items"]:
            # Obtener valor seguro
            val=""
            for k, v in row.items():
                if str(k).strip() == c["campo"].strip() or c["campo"][:30].lower() in str(k).lower():
                    val = str(v).strip().upper()
                    break
                    
            pts=0; estado="sin_dato"
            if val in ("CONFORME","C","COMPLETO"):              pts=c["conforme"]; estado="completo"
            elif val in ("NO CONFORME","NC","NO EXISTE","NE","INCOMPLETO","I"): pts=0; estado="no_existe"
            elif val in ("NO APLICA","NA"):                      pts=0; na_sec+=c["conforme"]; estado="na"
            
            items.append({"nombre":c["nombre"],"pts":pts,"max":c["conforme"],"estado":estado})
            sub+=pts
        na_total+=na_sec; total+=sub
        secciones[sec_key]={"label":sec["label"],"subtotal":sub,"max":sec["max"],"items":items}
        
    max_ap=100-na_total
    pct=round((total/max_ap*100),2) if max_ap>0 else 0
    calif="SATISFACTORIO" if pct>=90 else ("POR MEJORAR" if pct>=75 else "DEFICIENTE")
    return {"puntaje":round(total,2),"max_aplicable":round(max_ap,2),"porcentaje":pct,"calificacion":calif,"secciones":secciones}

# ==============================================================
# PROCESAR DATOS CON AÑO Y MES SEPARADOS (FILTRO 2024+)
# ==============================================================
def procesar_df(df, area_key, area_label="Área"):
    results = []
    criterios = CRITERIOS_POR_AREA[area_key]
    nombres_meses = {1:"01 - Enero", 2:"02 - Febrero", 3:"03 - Marzo", 4:"04 - Abril", 5:"05 - Mayo", 6:"06 - Junio", 7:"07 - Julio", 8:"08 - Agosto", 9:"09 - Septiembre", 10:"10 - Octubre", 11:"11 - Noviembre", 12:"12 - Diciembre"}
    
    for _, row in df.iterrows():
        r = row.to_dict()
        marca_temporal = str(r.get("Marca temporal", "")).strip()
        
        # 1. Extraer Año de la fecha y APLICAR EL FILTRO (Ignora errores o vacíos)
        try:
            fe = pd.to_datetime(marca_temporal, dayfirst=True)
            if fe.year < 2024:
                continue
            anio_automatico = str(fe.year)
        except Exception:
            continue
            
        # 2. Calcular los puntajes SOLO si pasó el filtro
        calc = calcular_row_eme(r, criterios) if area_key == "emergencia" else calcular_row_ce_hosp(r, criterios)
        
        # 3. Extraer Mes de la columna Auditoria
        mes_raw = ""
        for k, v in r.items():
            if "úmero de Auditoria" in str(k) or "umero de Auditoria" in str(k):
                mes_raw = str(v).strip()
                break
        
        try:
            mes_num = int(float(mes_raw))
            mes_automatico = nombres_meses.get(mes_num, "Sin Mes")
        except Exception:
            mes_automatico = "Sin Mes"

        def campo(keys):
            for k in keys:
                v = str(r.get(k, "")).strip()
                if v and str(v).lower() != "nan": return v
            return "—"
            
        results.append({
            "hc": campo(["NÚMERO DE HISTORIA CLÍNICA","NÚMERO DE LA HISTORIA CLÍNICA","NUMERO DE HISTORIA CLINICA"]),
            "fecha": campo(["FECHA DE AUDITORÍA","FECHA DE AUDITORIA"]),
            "servicio": campo(["SERVICIO AUDITADO:","SERVICIO AUDITADO"]),
            "auditor": campo(["MIEMBROS DEL COMITÉ DE AUDITORIA (que realizan la auditoría)","MIEMBROS DEL COMITÉ DE AUDITORIA","Miembros del Comité de Auditoria que realizan la auditoría"]),
            "anio": anio_automatico,
            "num_auditoria": mes_automatico,
            "diagnostico": campo(["DIAGNÓSTICO DE ALTA","DIAGNÓSTICO","DIAGNOSTICO"]),
            "cie10": campo(["CIE 10 (en mayúsculas, separando diagnósticos con slash, ejemplo: U07.1 / K35.9)"]),
            "area": area_label,
            **calc
        })
        
    results.sort(key=lambda x: (x['anio'], x['num_auditoria']))
    return results

# ============================================================
# RUTAS
# ============================================================
@app.route('/')
def index(): return send_from_directory('static','index.html')

@app.route('/api/login',methods=['POST'])
def login():
    try:
        data=request.json; u=data.get('usuario','').strip(); p=data.get('password','').strip()
        ph=hash_password(p); ws=get_users_sheet(); users=ws.get_all_records()
        for u2 in users:
            if str(u2.get('usuario',''))==u and str(u2.get('password_hash',''))==ph and str(u2.get('activo',''))=='1':
                return jsonify({"ok":True,"nombre":u2.get('nombre',''),"rol":u2.get('rol',''),"usuario":u})
        return jsonify({"ok":False,"msg":"Usuario o contraseña incorrectos"}),401
    except Exception as e: return jsonify({"ok":False,"msg":str(e)}),500

@app.route('/api/usuarios',methods=['GET'])
def get_usuarios():
    try:
        ws=get_users_sheet(); users=ws.get_all_records()
        return jsonify([{"usuario":u['usuario'],"nombre":u['nombre'],"rol":u['rol'],"activo":u['activo']} for u in users])
    except Exception as e: return jsonify({"error":str(e)}),500

@app.route('/api/usuarios',methods=['POST'])
def crear_usuario():
    try:
        data=request.json; ws=get_users_sheet(); ph=hash_password(data['password'])
        ws.append_row([data['usuario'],ph,data['nombre'],data.get('rol','auditor'),'1'])
        return jsonify({"ok":True})
    except Exception as e: return jsonify({"error":str(e)}),500

@app.route('/api/datos',methods=['GET'])
def get_datos():
    ak=request.args.get('area','consulta_externa').lower().strip()
    if ak not in AREAS_CONFIG: return jsonify({"ok":False,"error":f"Área '{ak}' no válida"}),400
    cfg=AREAS_CONFIG[ak]
    try:
        df=get_dataframe(cfg["sheet_id"],cfg["worksheet_name"])
        results=procesar_df(df,ak,area_label=cfg["label"])
        return jsonify({"ok":True,"area":ak,"area_label":cfg["label"],"total":len(results),"registros":results,
            "servicios":sorted({r['servicio'] for r in results if r['servicio']!='—'}),
            "auditores":sorted({r['auditor'] for r in results if r['auditor']!='—'}),
            "anios":sorted({r['anio'] for r in results if r['anio']!='Sin Año'}),
            "meses":sorted({r['num_auditoria'] for r in results if r['num_auditoria']!='Sin Fecha'})})
    except Exception as e: return jsonify({"ok":False,"error":str(e)}),500

@app.route('/api/estadisticas',methods=['POST'])
def get_estadisticas():
    try:
        registros=request.json.get('registros',[])
        if not registros: return jsonify({})
        total=len(registros)
        sat=sum(1 for r in registros if r['calificacion']=='SATISFACTORIO')
        mej=sum(1 for r in registros if r['calificacion']=='POR MEJORAR')
        deft=sum(1 for r in registros if r['calificacion']=='DEFICIENTE')
        prom=round(sum(r['porcentaje'] for r in registros)/total,2)
        secciones_keys=set()
        for r in registros: secciones_keys.update(r.get('secciones',{}).keys())
        secciones_stats={}
        for sk in secciones_keys:
            ss=next((r['secciones'][sk] for r in registros if sk in r.get('secciones',{})),{})
            label=ss.get('label',sk); max_sec=ss.get('max',10)
            items_data={}
            for r in registros:
                for item in r.get('secciones',{}).get(sk,{}).get('items',[]):
                    n=item['nombre']
                    if n not in items_data: items_data[n]={'completo':0,'incompleto':0,'no_existe':0,'en_exceso':0,'na':0,'sin_dato':0}
                    items_data[n][item['estado']]=items_data[n].get(item['estado'],0)+1
            subs=[r.get('secciones',{}).get(sk,{}).get('subtotal',0) for r in registros]
            ps=round(sum(subs)/total,2) if total>0 else 0
            secciones_stats[sk]={"label":label,"max":max_sec,"promedio":ps,"porcentaje":round(ps/max_sec*100,2) if max_sec>0 else 0,"items":items_data}
        servicios={}
        for r in registros:
            s=r['servicio']
            if s not in servicios: servicios[s]={'total':0,'sat':0,'mej':0,'def':0,'pct_sum':0}
            servicios[s]['total']+=1; servicios[s]['pct_sum']+=r['porcentaje']
            if r['calificacion']=='SATISFACTORIO': servicios[s]['sat']+=1
            elif r['calificacion']=='POR MEJORAR': servicios[s]['mej']+=1
            else: servicios[s]['def']+=1
        for s in servicios: servicios[s]['promedio']=round(servicios[s]['pct_sum']/servicios[s]['total'],2)
        return jsonify({"total":total,"satisfactorio":sat,"por_mejorar":mej,"deficiente":deft,"promedio_pct":prom,"secciones":secciones_stats,"por_servicio":servicios})
    except Exception as e: return jsonify({"error":str(e)}),500

if __name__=='__main__':
    port=int(os.environ.get("PORT",5000))
    app.run(host='0.0.0.0',port=port,debug=True)