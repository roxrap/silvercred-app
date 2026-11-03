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
            return False

        # Abrir la planilla (puedes ajustar el nombre o usar ID si prefieres)
        # Nota: Asegúrate de que el bot/cuenta de servicio tenga permisos de Editor en la planilla.
        sheet_url = st.secrets.get("SHEET_URL", "")
        if sheet_url:
            sheet = client.open_by_url(sheet_url).sheet1
        else:
            # Fallback buscando por nombre si estuviera configurado
            sheet = client.open("Silvercred_Auditoria").sheet1

        from datetime import datetime, timedelta, timezone
        zona_arg = timezone(timedelta(hours=-3))
        fecha_hora = datetime.now(zona_arg).strftime("%d/%m/%Y %H:%M:%S")
        modelo_y_tiempo = f"{modelo} ({tiempo}s)"

        # --- PARSING INTELIGENTE DE LA RESPUESTA DE LA IA ---
        # Extraer dictamen (APROBADO, CONDICIONADO, RECHAZADO)
        dictamen = "REVISAR"
        if "DICTAMEN: APROBADO" in resultado_ia.upper():
            dictamen = "APROBADO"
        elif "DICTAMEN: CONDICIONADO" in resultado_ia.upper():
            dictamen = "CONDICIONADO"
        elif "DICTAMEN: RECHAZADO" in resultado_ia.upper():
            dictamen = "RECHAZADO"

        # Extracción de campos clave del dictamen para las 17 columnas
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
            fecha_hora,                  # A: Fecha y Hora
            nombre_cliente,              # B: Cliente
            tipo_operacion,              # C: Tipo Operación
            modelo_y_tiempo,             # D: Modelo IA y Tiempo
            dictamen,                    # E: Resultado Dictamen (APROBADO/CONDICIONADO/RECHAZADO)
            neto,                        # F: Ingreso Neto Comprobado
            situacion_lab,               # G: Situación Laboral
            antiguedad,                  # H: Antigüedad Laboral
            cuota_max,                   # I: Cuota Máxima (30% Neto)
            capital_max,                 # J: Capital Máximo
            bcra,                        # K: BCRA
            score,                       # L: Score Veraz
            credixsa,                    # M: Reporte Credixsa
            antecedentes,                # N: Antecedentes Negativos
            consultas,                   # O: Consultas últimos 3 meses
            fundamento,                  # P: Fundamento Técnico
            "Procesado OK"               # Q: Observaciones
        ]

        # Escribir secuencialmente en la siguiente fila libre
        sheet.append_row(fila_datos)
        return True

    except Exception as e:
        print(f"Error al registrar en Google Sheets: {e}")
        return False
