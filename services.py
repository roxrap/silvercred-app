import os
import json
import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
import re

def obtener_cliente_sheets():
    """Conecta a Google Sheets utilizando las credenciales de servicio configuradas en st.secrets."""
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        
        gcp_dict = dict(st.secrets["gcp_service_account"])
        credentials = Credentials.from_service_account_info(gcp_dict, scopes=scope)
        client = gspread.authorize(credentials)
        return client
    except Exception as e:
        print(f"Error al conectar con Google Sheets: {e}")
        return None

def extraer_campo_texto(texto, patron):
    """Extrae un valor del texto de la IA usando expresiones regulares."""
    match = re.search(patron, texto, re.IGNORECASE)
    return match.group(1).strip() if match else "N/D"

def registrar_auditoria_sheet(nombre_cliente, tipo_operacion, modelo, tiempo, resultado_ia):
    """
    Registra una fila de auditoría en Google Sheets siguiendo estrictamente 
    las 17 columnas de la A a la Q.
    """
    try:
        client = obtener_cliente_sheets()
        if not client:
            st.error("⚠️ Error: No se pudo autorizar el cliente de Google Sheets.")
            return False

        sheet_url = st.secrets.get("SHEET_URL", "")
        if sheet_url:
            sheet = client.open_by_url(sheet_url).sheet1
        else:
            sheet = client.open("Auditoria_Dictamenes_Silvercred").sheet1

        from datetime import datetime, timedelta, timezone
        zona_arg = timezone(timedelta(hours=-3))
        fecha_hora = datetime.now(zona_arg).strftime("%d/%m/%Y %H:%M:%S")
        modelo_y_tiempo = f"{modelo} ({tiempo}s)"

        dictamen = "REVISAR"
        if "DICTAMEN: APROBADO" in resultado_ia.upper() or "APROBADO" in resultado_ia.upper():
            dictamen = "APROBADO"
        elif "DICTAMEN: CONDICIONADO" in resultado_ia.upper() or "CONDICIONADO" in resultado_ia.upper():
            dictamen = "CONDICIONADO"
        elif "DICTAMEN: RECHAZADO" in resultado_ia.upper() or "RECHAZADO" in resultado_ia.upper():
            dictamen = "RECHAZADO"

        neto = extraer_campo_texto(resultado_ia, r"Ingreso Neto Comprobado[:\s]*([^\n]+)")
        situacion_lab = extraer_campo_texto(resultado_ia, r"Situación Laboral[:\s]*([^\n]+)")
        antiguedad = extraer_campo_texto(resultado_ia, r"Antigüedad Laboral[:\s]*([^\n]+)")
        cuota_max = extraer_campo_texto(resultado_ia, r"Cuota Máxima.*?[:\s]*([^\n]+)")
        capital_max = extraer_campo_texto(resultado_ia, r"Capital Máximo[:\s]*([^\n]+)")
        bcra = extraer_campo_texto(resultado_ia, r"BCRA[:\s]*([^\n]+)")
        score = extraer_campo_texto(resultado_ia, r"Score.*?[:\s]*([^\n]+)")
        credixsa = extraer_campo_texto(resultado_ia, r"Reporte Credixsa.*?[:\s]*([^\n]+)")
        antecedentes = extraer_campo_texto(resultado_ia, r"Antecedentes.*?[:\s]*([^\n]+)")
        consultas = extraer_campo_texto(resultado_ia, r"Consultas.*?[:\s]*([^\n]+)")
        fundamento = extraer_campo_texto(resultado_ia, r"Fundamento Técnico[:\s]*([^\n]+)")

        fila_datos = [
            str(fecha_hora),                  # A
            str(nombre_cliente),              # B
            str(tipo_operacion),              # C
            str(modelo_y_tiempo),             # D
            str(dictamen),                    # E
            str(neto),                        # F
            str(situacion_lab),               # G
            str(antiguedad),                  # H
            str(cuota_max),                   # I
            str(capital_max),                 # J
            str(bcra),                        # K
            str(score),                       # L
            str(credixsa),                    # M
            str(antecedentes),                # N
            str(consultas),                   # O
            str(fundamento),                  # P
            "Procesado OK"                    # Q
        ]

        sheet.append_row(fila_datos, value_input_option='USER_ENTERED')
        return True

    except Exception as e:
        st.error(f"⚠️ Error detallado al registrar en Google Sheets: {str(e)}")
        print(f"Error al registrar en Google Sheets: {e}")
        return False
