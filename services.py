import streamlit as st
import re
import os
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

# ID de tu planilla de Google Sheets ya creada de forma anticipada
ID_PLANILLA_AUDITORIA = "PEGA_AQUÍ_EL_ID_DE_TU_GOOGLE_SHEET"

@st.cache_resource
def init_google_services():
    try:
        if "gcp_service_account" not in st.secrets:
            return None, None
            
        credentials_dict = dict(st.secrets["gcp_service_account"])
        gcp_creds = service_account.Credentials.from_service_account_info(
            credentials_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        sheets_service = build('sheets', 'v4', credentials=gcp_creds)
        return None, sheets_service
    except Exception as e:
        st.error(f"Error inicializando servicio de Sheets: {e}")
        return None, None

_, sheets_service = init_google_services()

def extraer_campo_texto(texto, patron):
    match = re.search(patron, texto, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "N/D"

def registrar_auditoria_sheet(cliente, tipo_op, modelo, tiempo, dictamen_texto):
    if not sheets_service or ID_PLANILLA_AUDITORIA == "PEGA_AQUÍ_EL_ID_DE_TU_GOOGLE_SHEET":
        return False
    try:
        resultado = "REVISAR"
        if "DICTAMEN: APROBADO" in dictamen_texto.upper() or "APROBADO" in dictamen_texto.upper():
            resultado = "APROBADO"
        elif "DICTAMEN: RECHAZADO" in dictamen_texto.upper() or "RECHAZADO" in dictamen_texto.upper():
            resultado = "RECHAZADO"
        elif "DICTAMEN: CONDICIONADO" in dictamen_texto.upper() or "CONDICIONADO" in dictamen_texto.upper():
            resultado = "CONDICIONADO"
            
        fecha_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        modelo_y_tiempo = f"{modelo} ({tiempo}s)"
        
        ingreso_neto = extraer_campo_texto(dictamen_texto, r"Ingreso Neto Comprobado:\s*(.*)")
        sit_laboral = extraer_campo_texto(dictamen_texto, r"Situación Laboral:\s*(.*)")
        antiguedad = extraer_campo_texto(dictamen_texto, r"Antigüedad Laboral:\s*(.*)")
        cuota_max = extraer_campo_texto(dictamen_texto, r"Cuota Máxima.*?:\s*(.*)")
        monto_max = extraer_campo_texto(dictamen_texto, r"Monto máximo disponible:\s*(.*)")
        bcra = extraer_campo_texto(dictamen_texto, r"BCRA:\s*(.*)")
        equifax = extraer_campo_texto(dictamen_texto, r"Score Equifax:\s*(.*)")
        credixsa = extraer_campo_texto(dictamen_texto, r"Reporte Credixsa:\s*(.*)")
        antecedentes = extraer_campo_texto(dictamen_texto, r"Antecedentes Negativos:\s*(.*)")
        compromiso = extraer_campo_texto(dictamen_texto, r"Compromiso Mensual Inferido:\s*(.*)")
        margen = extraer_campo_texto(dictamen_texto, r"Margen Disponible Cuota Mensual:\s*(.*)")
        limite_sugerido = extraer_campo_texto(dictamen_texto, r"Límite de Cuota Sugerido:\s*(.*)")

        row_body = {
            'values': [[
                fecha_hora, cliente, tipo_op, modelo_y_tiempo, resultado,
                ingreso_neto, sit_laboral, antiguedad, cuota_max, monto_max,
                bcra, equifax, credixsa, antecedentes, compromiso, margen, limite_sugerido
            ]]
        }
        
        # Escribe directamente una línea al final de la planilla existente
        sheets_service.spreadsheets().values().append(
            spreadsheetId=ID_PLANILLA_AUDITORIA,
            range='A:Q',
            valueInputOption='USER_ENTERED',
            body=row_body
        ).execute()
        return True
    except Exception as e:
        st.error(f"Error escribiendo en Google Sheets: {e}")
        return False
