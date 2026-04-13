import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
import urllib3
import os
import ssl

# ====================================================================
# PARCHE PARA SALTAR EL FIREWALL DEL HOSPITAL
# ====================================================================
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ['PYTHONHTTPSVERIFY'] = '0'
ssl._create_default_https_context = ssl._create_unverified_context

AREAS = {
    "consulta_externa": {"sheet": "FORMATO DE CONSULTA EXTERNA-INICIAL (Respuestas)", "tab": "NUEVO CE", "out": "datos_ce.xlsx"},
    "emergencia":       {"sheet": "FORMATO DE EMERGENCIA (Respuestas)", "tab": "E", "out": "datos_emergencia.xlsx"},
    "hospitalizacion":  {"sheet": "FORMATO DE HOSPITALIZACIÓN (Respuestas)", "tab": "H", "out": "datos_hospitalizacion.xlsx"}
}

try:
    print("Paso 1: Conectando credenciales...")
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file("credenciales.json", scopes=SCOPES)

    print("Paso 2: Autorizando cliente...")
    cliente = gspread.authorize(creds)

    for area, config in AREAS.items():
        print(f"\n--- Procesando {area.upper()} ---")
        try:
            print(f"Abriendo hoja: {config['sheet']} ...")
            hoja = cliente.open(config['sheet'])
            
            print(f"Leyendo pestaña: {config['tab']} ...")
            pestaña = hoja.worksheet(config['tab'])
            datos = pestaña.get_all_records()
            df = pd.DataFrame(datos)
            
            print(f"✅ Total de registros: {len(df)}")
            df.to_excel(config['out'], index=False)
            print(f"✅ Copia de seguridad guardada en: {config['out']}")
        except Exception as e:
            print(f"❌ ERROR al procesar {area}: {e}")

except Exception as e:
    print(f"❌ ERROR GENERAL: {e}")