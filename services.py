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
        
        # Cargar credenciales desde los secretos de Streamlit
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

        # Abrir la planilla por URL desde los secretos o por nombre por defecto
        sheet_url = st.secrets.get("SHEET_URL", "")
        if sheet_url:
            sheet = client.open_by_url(sheet_url).sheet1
        else:
            sheet = client.open("Auditoria_Dictamenes_Silvercred").sheet1

        from datetime import datetime, timedelta, timezone
        zona_arg = timezone(timedelta(hours=-3))
        fecha_hora = datetime.now(zona_arg).strftime("%d/%m/%Y %H:%M:%S")
        modelo_y_tiempo = f"{modelo} ({tiempo}s)"

        # --- PARSING DIRECTO Y SEGURO DE DICTAMEN ---
        dictamen = "REVISAR"
        if "DICTAMEN: APROBADO" in resultado_ia.upper() or "APROBADO" in resultado_ia.upper():
            dictamen = "APROBADO"
        elif "DICTAMEN: CONDICIONADO" in resultado_ia.upper() or "CONDICIONADO" in resultado_ia.upper():
            dictamen = "CONDICIONADO"
        elif "DICTAMEN: RECHAZADO" in resultado_ia.upper() or "RECHAZADO" in resultado_ia.upper():
            dictamen = "RECHAZADO"

        # Extraer campos garantizando que nunca sean nulos
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

        # --- FILA EXACTA DE 17 COLUMNAS (A a la Q) ---
        fila_datos = [
            str(fecha_hora),                  # A: Fecha y Hora
            str(nombre_cliente),              # B: Cliente
            str(tipo_operacion),              # C: Tipo Operación
            str(modelo_y_tiempo),             # D: Modelo IA y Tiempo
            str(dictamen),                    # E: Resultado Dictamen
            str(neto),                        # F: Ingreso Neto Comprobado
            str(situacion_lab),               # G: Situación Laboral
            str(antiguedad),                  # H: Antigüedad Laboral
            str(cuota_max),                   # I: Cuota Máxima (30% Neto)
            str(capital_max),                 # J: Capital Máximo
            str(bcra),                        # K: BCRA
            str(score),                       # L: Score Veraz
            str(credixsa),                    # M: Reporte Credixsa
            str(antecedentes),                # N: Antecedentes Negativos
            str(consultas),                   # O: Consultas últimos 3 meses
            str(fundamento),                  # P: Fundamento Técnico
            "Procesado OK"                    # Q: Observaciones
        ]

        # Forzar la escritura en la hoja usando USER_ENTERED para respetar tipos
        sheet.append_row(fila_datos, value_input_option='USER_ENTERED')
        return True

    except Exception as e:
        st.error(f"⚠️ Error detallado al registrar en Google Sheets: {str(e)}")
        print(f"Error al registrar en Google Sheets: {e}")
        return False
