import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
import urllib3
import os

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ['PYTHONHTTPSVERIFY'] = '0'

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

try:
    print("Paso 1: Conectando credenciales...")
    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file("credenciales.json", scopes=SCOPES)

    print("Paso 2: Autorizando cliente...")
    cliente = gspread.authorize(creds)

    print("Paso 3: Abriendo hoja...")
    hoja = cliente.open("FORMATO DE CONSULTA EXTERNA-INICIAL (Respuestas)")

    print("Paso 4: Leyendo pestaña NUEVO CE...")
    pestaña = hoja.worksheet("NUEVO CE")
    datos = pestaña.get_all_records()
    df = pd.DataFrame(datos)

    print(f"✅ Total de registros: {len(df)}")
    print(df.head())
    df.to_excel("datos_auditoria.xlsx", index=False)
    print("✅ Guardado en datos_auditoria.xlsx")

except Exception as e:
    print(f"❌ ERROR: {e}")