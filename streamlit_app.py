import streamlit as st
import os
import tempfile
import time
import re
from datetime import datetime
from google import genai
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Silvercred - Sistema de Evaluación Crediticia",
    page_icon="logo.png" if os.path.exists("logo.png") else "💳",
    layout="wide"
)

# --- INICIALIZACIÓN DE CLIENTE GEMINI Y SERVICIOS GOOGLE (SHEETS) ---
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
client = genai.Client(api_key=GEMINI_API_KEY)
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
        return None, None

drive_service, sheets_service = init_google_services()

# --- FUNCIONES DE PLANILLA DE AUDITORÍA EN CARPETA CLIENTES ---
def obtener_o_crear_planilla_auditoria():
    if not drive_service or not sheets_service:
        return None
    try:
        nombre_planilla = "Auditoria_Dictamenes_Silvercred"
        query = f"name = '{nombre_planilla}' and '{ID_CARPETA_CLIENTES}' in parents and mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"
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
            
            # Mover la planilla recién creada directamente a la carpeta de clientes con permisos
            drive_service.files().update(
                fileId=spreadsheet_id,
                addParents=ID_CARPETA_CLIENTES,
                removeParents='root',
                fields='id, parents'
            ).execute()
            
            header_values = [[
                'Fecha y Hora', 'Cliente', 'Tipo Operación', 'Modelo IA y Tiempo', 'Resultado Dictamen',
                'Ingreso Neto Comprobado', 'Situación Laboral', 'Antigüedad Laboral', 'Cuota Máxima (30% Neto)', 'Monto Máximo Disponible',
                'BCRA', 'Score Equifax', 'Reporte Credixsa', 'Antecedentes Negativos', 'Evolución de Deuda',
                'Compromiso Mensual Inferido', 'Margen Disponible Cuota', 'Alertas Técnicas', 'Fundamento Técnico', 'Límite de Cuota Sugerido', 'Estado Archivos'
            ]]
            sheets_service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range='Sheet1!A1',
                valueInputOption='RAW',
                body={'values': header_values}
            ).execute()
            return spreadsheet_id
    except Exception as e:
        print(f"Error creando planilla en carpeta Clientes: {e}")
        return None

def extraer_campo_texto(texto, patron):
    match = re.search(patron, texto, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return "N/D"

def registrar_auditoria_sheet(cliente, tipo_op, modelo, tiempo, dictamen_texto, estado_archivos):
    try:
        spreadsheet_id = obtener_o_crear_planilla_auditoria()
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
            range='Sheet1!A:U',
            valueInputOption='USER_ENTERED',
            body=row_body
        ).execute()
        return True
    except Exception as e:
        return False

def analizar_credito_con_fallback(files_dict, tipo_operacion, nombre_cliente):
    # Modelo requerido por la API actual para nuevos proyectos
    modelos = ['gemini-3.8-flash', 'gemini-2.0-flash']
    inicio = time.time()
    ultimo_error = ""
    
    for modelo in modelos:
        max_intentos = 2
        for intento in range(max_intentos):
            uploaded_files = []
            try:
                for tipo, path in files_dict.items():
                    if path and os.path.exists(path):
                        g_file = client.files.upload(file=path)
                        uploaded_files.append(g_file)
                
                prompt = f"""
                Eres un analista de riesgos crediticios experto y ejecutivo de Silvercred (sucursales Santa Fe y San Javier). Estás evaluando una solicitud de tipo: {tipo_operacion} para el cliente: {nombre_cliente}.
                
                INSTRUCCIONES Y REGLAS DE NEGOCIO:
                - Considera las normativas vigentes, capacidad de pago, límites específicos para activos/pasivos y matriz de riesgo institucional.
                - Evalúa utilizando únicamente los datos de la documentación provista (Recibo de Sueldo, Informe Veraz, Reporte Credixsa). No exijas requisitos ausentes.
                - Utiliza estrictamente lenguaje técnico, financiero, conciso y gerencial. Omitir decimales en todos los montos monetarios. Evita adjetivos exagerados.
                
                FORMATO OBLIGATORIO DE SALIDA (respetar exactamente los títulos y viñetas):
                
                1. Datos Identificatorios:
                • Apellido y Nombre: {nombre_cliente}
                • CUIL: [CUIL exacto extraído de documentos]
                • Tipo de Operación: {tipo_operacion}
                
                2. Evaluación de Ingresos:
                • Ingreso Neto Comprobado: $ [Monto sin decimales] (Recibo de sueldo [Mes/Año]).
                • Situación Laboral: Relación de dependencia (Empleador: [Nombre del empleador], Rubro/Actividad: [Rubro inferido]).
                • Antigüedad Laboral: [Años y meses] (Fecha de ingreso: [Fecha]).
                • Cuota Máxima disponible (30% Neto): $ [Monto sin decimales] mensuales.
                • Monto máximo disponible: $ [1 sueldo redondeado sin decimales].
                
                3. Calificación en Centrales de Riesgo:
                • BCRA: Situación [X]. Deuda vigente al [Fecha] por $ [Monto sin decimales] ([Entidad]). Historial con cumplimiento normal por [X] meses.
                • Score Equifax: [Puntos] puntos ([Predictor]).
                • Reporte Credixsa: [Semáforo / Estado].
                • Antecedentes Negativos: [Sin observaciones / Detalle].
                • Evolución de Deuda: [Resumen de desendeudamiento].
                
                4. Factores de Riesgo / Endeudamiento Global:
                • Compromiso Mensual Inferido: $ [Monto sin decimales] (Afectación actual del [X]% sobre el haber neto).
                • Margen Disponible Cuota Mensual: $ [Monto sin decimales].
                • Alertas Técnicas:
                  - Consultas en bureaux: [Cantidad exacta de consultas y entidades en el período].
                  - Empleador: Irregularidad empleador en el pago de aportes (si aplica).
                
                5. Resolución Crediticia:
                DICTAMEN: [APROBADO / RECHAZADO / CONDICIONADO]
                Fundamento Técnico: [Explicación corta, ejecutiva y objetiva].
                Límite de Cuota Sugerido: Hasta $ [Monto sin decimales] mensuales.
                """
                
                response = client.models.generate_content(
                    model=modelo,
                    contents=uploaded_files + [prompt]
                )
                duracion = round(time.time() - inicio, 1)
                return response.text, modelo, duracion
            
            except Exception as e:
                ultimo_error = str(e)
                if "404" in str(e):
                    break
                elif "503" in str(e) and intento < max_intentos - 1:
                    time.sleep(2)
                    continue
                else:
                    break
                    
    duracion = round(time.time() - inicio, 1)
    return f"Error crítico con Gemini: {ultimo_error}", "Error", duracion

# --- BARRA LATERAL ---
with st.sidebar:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    st.markdown("---")
    st.markdown("### 🏢 Sucursales operativas")
    st.markdown("- Santa Fe\n- San Javier")
    st.markdown("---")
    st.info("Módulo Activo: Análisis Crediticio con Auditoría Sheets")

# --- INICIALIZAR ESTADO DE SESIÓN ---
if "analisis_resultado" not in st.session_state:
    st.session_state.analisis_resultado = None
if "modelo_usado" not in st.session_state:
    st.session_state.modelo_usado = None
if "tiempo_total" not in st.session_state:
    st.session_state.tiempo_total = None
if "nombre_cliente" not in st.session_state:
    st.session_state.nombre_cliente = None
if "tipo_operacion" not in st.session_state:
    st.session_state.tipo_operacion = None

# --- INTERFAZ PRINCIPAL ---
st.title("💳 Silvercred - Sistema de Evaluación Crediticia")
st.markdown("Ingresa los datos del cliente, sube la documentación y el sistema procesará el dictamen de riesgo y registrará la auditoría en Google Sheets.")

with st.form("form_cliente"):
    col_1, col_2 = st.columns(2)
    with col_1:
        nombre_cliente_input = st.text_input("Apellido y Nombre Completo del Cliente", placeholder="Ej: QUIROGA, MARISA ALEJANDRA")
    with col_2:
        tipo_op_input = st.selectbox("Tipo de Operación", ["Apertura", "Renovación"])
        
    st.markdown("### 📂 Documentación Requerida (Sube los 3 archivos PDF)")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        archivo_recibo = st.file_uploader("1. Recibo de Sueldo", type=["pdf"])
    with col_b:
        archivo_veraz = st.file_uploader("2. Informe Veraz", type=["pdf"])
    with col_c:
        archivo_credixsa = st.file_uploader("3. Reporte Credixsa", type=["pdf"])
    
    submitted = st.form_submit_button("Procesar y Generar Dictamen")

if submitted:
    if not nombre_cliente_input.strip():
        st.warning("Por favor, ingresa el Apellido y Nombre completo del cliente.")
    elif not (archivo_recibo or archivo_veraz or archivo_credixsa):
        st.warning("Por favor, adjunta al menos la documentación correspondiente.")
    else:
        st.session_state.nombre_cliente = nombre_cliente_input.strip().upper()
        st.session_state.tipo_operacion = tipo_op_input
        
        with st.status("🚀 Ejecutando protocolo de análisis crediticio Silvercred...", expanded=True) as status:
            paths_dict = {}
            st.write("📥 Preparando archivos temporales...")
            if archivo_recibo:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(archivo_recibo.getvalue())
                    paths_dict['recibo'] = tmp.name
            if archivo_veraz:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(archivo_veraz.getvalue())
                    paths_dict['veraz'] = tmp.name
            if archivo_credixsa:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(archivo_credixsa.getvalue())
                    paths_dict['credixsa'] = tmp.name

            st.write("🧠 Conectando con Gemini (3.8-flash) para procesamiento analítico...")
            st.session_state.analisis_resultado, st.session_state.modelo_usado, st.session_state.tiempo_total = analizar_credito_con_fallback(
                paths_dict, st.session_state.tipo_operacion, st.session_state.nombre_cliente
            )
            
            st.write("📊 Registrando campos estructurados en Google Sheets dentro de la carpeta 'Clientes'...")
            registrar_auditoria_sheet(
                st.session_state.nombre_cliente,
                st.session_state.tipo_operacion,
                st.session_state.modelo_usado,
                st.session_state.tiempo_total,
                st.session_state.analisis_resultado,
                "Procesado correctamente"
            )
            
            for p in paths_dict.values():
                if os.path.exists(p):
                    try:
                        os.unlink(p)
                    except:
                        pass
            status.update(label="✅ ¡Proceso, análisis y auditoría completados con éxito!", state="complete", expanded=False)

# Mostrar resultados si ya fueron generados
if st.session_state.analisis_resultado:
    st.success("¡Operación finalizada y registrada!")
    
    fecha_hora_actual = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    st.info(f"📊 **Información de Rendimiento e IA:** Modelo utilizado: **{st.session_state.modelo_usado}** | Tiempo: **{st.session_state.tiempo_total} segundos** | Procesado el: **{fecha_hora_actual}**")
    
    st.markdown("---")
    col_tit, col_btn = st.columns([3, 1])
    with col_tit:
        st.subheader(f"🤖 Dictamen Técnico de Riesgo Crediticio ({st.session_state.tipo_operacion})")
    with col_btn:
        st.download_button(
            label="📥 Descargar Dictamen (TXT)",
            data=st.session_state.analisis_resultado,
            file_name=f"Dictamen_{st.session_state.nombre_cliente.replace(', ', '_')}.txt",
            mime="text/plain"
        )
        
    st.markdown(st.session_state.analisis_resultado)
