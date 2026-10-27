import streamlit as st
import re
import os
import io
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

ID_CARPETA_CLIENTES = "1JJpum6qCPLz8-EbzahCpBZ2TaNbedxZ7"

@st.cache_resource
def init_google_services():
    try:
        if "gcp_service_account" not in st.secrets:
            return None, None
            
        credentials_dict = dict(st.secrets["gcp_service_account"])
        gcp_creds = service_account.Credentials.from_service_account_info(
            credentials_dict,
            scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/drive.file']
        )
        sheets_service = build('sheets', 'v4', credentials=gcp_creds)
        drive_service = build('drive', 'v3', credentials=gcp_creds)
        return drive_service, sheets_service
    except Exception as e:
        st.error(f"Error inicializando servicios de Google: {e}")
        return None, None

drive_service, sheets_service = init_google_services()

def obtener_o_crear_carpeta_cliente(nombre_cliente):
    if not drive_service:
        st.error("El servicio de Google Drive no está inicializado.")
        return None
    try:
        nombre_carpeta = nombre_cliente.strip().upper()
        query = f"name = '{nombre_carpeta}' and '{ID_CARPETA_CLIENTES}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = results.get('files', [])
        
        if files:
            return files[0]['id']
        else:
            folder_metadata = {
                'name': nombre_carpeta,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [ID_CARPETA_CLIENTES]
            }
            folder = drive_service.files().create(body=folder_metadata, fields='id').execute()
            return folder.get('id')
    except Exception as e:
        st.error(f"Error creando carpeta de cliente en Drive: {e}")
        return None

def subir_bytes_a_drive(file_bytes, original_name, id_carpeta_destino):
    if not drive_service or not file_bytes:
        return None
    try:
        file_metadata = {
            'name': original_name,
            'parents': [id_carpeta_destino]
        }
        fh = io.BytesIO(file_bytes)
        media = MediaIoBaseUpload(fh, mimetype='application/octet-stream', resumable=False)
        
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        return file.get('id')
    except Exception as e:
        st.error(f"Error al subir el archivo {original_name}: {e}")
        return None

def obtener_o_crear_planilla_auditoria(id_carpeta_destino):
    if not drive_service or not sheets_service:
        return None
    try:
        nombre_planilla = "Auditoria_Dictamenes_Silvercred"
        query = f"name = '{nombre_planilla}' and '{id_carpeta_destino}' in parents and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"
        results = drive_service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        files = results.get('files', [])
        
        if files:
            return files[0]['id']
        else:
            spreadsheet_body = {
                'properties': {'title': nombre_planilla}
            }
            spreadsheet = sheets_service.spreadsheets().create(body=spreadsheet_body, fields='spreadsheetId').execute()
            spreadsheet_id = spreadsheet.get('spreadsheetId')
            
            try:
                drive_service.files().update(
                    fileId=spreadsheet_id,
                    addParents=id_carpeta_destino,
                    removeParents='root',
                    fields='id, parents'
                ).execute()
            except Exception:
                pass
            
            header_values = [[
                'Fecha y Hora', 'Cliente', 'Tipo Operación', 'Modelo IA y Tiempo', 'Resultado Dictamen',
                'Ingreso Neto Comprobado', 'Situación Laboral', 'Antigüedad Laboral', 'Cuota Máxima (30% Neto)', 'Monto Máximo Disponible',
                'BCRA', 'Score Equifax', 'Reporte Credixsa', 'Antecedentes Negativos', 'Evolución de Deuda',
                'Compromiso Mensual Inferido', 'Margen Disponible Cuota', 'Alertas Técnicas', 'Fundamento Técnico', 'Límite de Cuota Sugerido', 'Estado Archivos'
            ]]
            sheets_service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range='A1',
                valueInputOption='RAW',
                body={'values': header_values}
            ).execute()
            return spreadsheet_id
    except Exception as e:
        return None

def extraer_campo_texto(texto, patron):
    match = re.search(patron, texto, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "N/D"

def registrar_auditoria_sheet(cliente, tipo_op, modelo, tiempo, dictamen_texto, estado_archivos, id_carpeta_cliente):
    try:
        spreadsheet_id = obtener_o_crear_planilla_auditoria(id_carpeta_cliente)
        if not spreadsheet_id:
            return False
            
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
        cuota_max = extraer_campo_texto(dictamen_texto, r"Cuota Máxima disponible.*?:\s*(.*)")
        monto_max = extraer_campo_texto(dictamen_texto, r"Monto máximo disponible:\s*(.*)")
        bcra = extraer_campo_texto(dictamen_texto, r"BCRA:\s*(.*)")
        equifax = extraer_campo_texto(dictamen_texto, r"Score Equifax:\s*(.*)")
        credixsa = extraer_campo_texto(dictamen_texto, r"Reporte Credixsa:\s*(.*)")
        antecedentes = extraer_campo_texto(dictamen_texto, r"Antecedentes Negativos:\s*(.*)")
        evolucion = extraer_campo_texto(dictamen_texto, r"Evolución de Deuda:\s*(.*)")
        compromiso = extraer_campo_texto(dictamen_texto, r"Compromiso Mensual Inferido:\s*(.*)")
        margen = extraer_campo_texto(dictamen_texto, r"Margen Disponible Cuota Mensual:\s*(.*)")
        alertas = extraer_campo_texto(dictamen_texto, r"Alertas Técnicas:\s*(.*?)(?=\n\n|\n5\.|\Z)")
        fundamento = extraer_campo_texto(dictamen_texto, r"Fundamento Técnico:\s*(.*?)(?=\n-|\nLímite|\Z)")
        limite_sugerido = extraer_campo_texto(dictamen_texto, r"Límite de Cuota Sugerido:\s*(.*)")

        row_body = {
            'values': [[
                fecha_hora, cliente, tipo_op, modelo_y_tiempo, resultado,
                ingreso_neto, sit_laboral, antiguedad, cuota_max, monto_max,
                bcra, equifax, credixsa, antecedentes, evolucion,
                compromiso, margen, alertas.replace('\n', ' | '), fundamento.replace('\n', ' '), limite_sugerido, estado_archivos
            ]]
        }
        sheets_service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range='A:U',
            valueInputOption='USER_ENTERED',
            body=row_body
        ).execute()
        return True
    except Exception as e:
        return False
