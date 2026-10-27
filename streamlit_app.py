import streamlit as st
import os
import tempfile
from datetime import datetime, timedelta
from services import obtener_o_crear_carpeta_cliente, subir_bytes_a_drive, registrar_auditoria_sheet
from ai_analyzer import analizar_credito_con_fallback

# Hora ajustada para Argentina (UTC-3)
f_argentina = datetime.utcnow() - timedelta(hours=3)
fecha_hora_actual = f_argentina.strftime("%d/%m/%Y %H:%M:%S")

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Silvercred - Sistema de Evaluación Crediticia",
    page_icon="logo.png" if os.path.exists("logo.png") else "💳",
    layout="wide"
)

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")

# --- BARRA LATERAL ---
with st.sidebar:
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    st.markdown("---")
    st.markdown("### 🏢 Sucursales operativas")
    st.markdown("- Santa Fe\n- San Javier")
    st.markdown("---")
    st.info("Módulo Activo: Análisis Crediticio con Auditoría Sheets y Drive")

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
st.markdown("Ingresa los datos del cliente, sube la documentación (PDF o imágenes para el recibo) y el sistema procesará el dictamen de riesgo y registrará todo en su carpeta de Google Drive.")

with st.form("form_cliente"):
    col_1, col_2 = st.columns(2)
    with col_1:
        nombre_cliente_input = st.text_input("Apellido y Nombre Completo del Cliente", placeholder="Ej: QUIROGA, MARISA ALEJANDRA")
    with col_2:
        tipo_op_input = st.selectbox("Tipo de Operación", ["Apertura", "Renovación"])
        
    st.markdown("### 📂 Documentación Requerida")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        archivo_recibo = st.file_uploader("1. Recibo de Sueldo (PDF o Imagen)", type=["pdf", "png", "jpg", "jpeg"])
    with col_b:
        archivo_veraz = st.file_uploader("2. Informe Veraz (PDF)", type=["pdf"])
    with col_c:
        archivo_credixsa = st.file_uploader("3. Reporte Credixsa (PDF)", type=["pdf"])
    
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
            st.write("📥 Leyendo archivos adjuntos...")
            
            # Procesar Recibo
            b_recibo, n_recibo = None, None
            if archivo_recibo:
                b_recibo = archivo_recibo.getvalue()
                n_recibo = archivo_recibo.name
                suffix = os.path.splitext(n_recibo)[1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(b_recibo)
                    paths_dict['recibo'] = tmp.name

            # Procesar Veraz
            b_veraz, n_veraz = None, None
            if archivo_veraz:
                b_veraz = archivo_veraz.getvalue()
                n_veraz = archivo_veraz.name
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(b_veraz)
                    paths_dict['veraz'] = tmp.name

            # Procesar Credixsa
            b_credixsa, n_credixsa = None, None
            if archivo_credixsa:
                b_credixsa = archivo_credixsa.getvalue()
                n_credixsa = archivo_credixsa.name
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(b_credixsa)
                    paths_dict['credixsa'] = tmp.name

            st.write("🧠 Conectando con Gemini 3.8-flash para análisis analítico...")
            st.session_state.analisis_resultado, st.session_state.modelo_usado, st.session_state.tiempo_total = analizar_credito_con_fallback(
                GEMINI_API_KEY, paths_dict, st.session_state.tipo_operacion, st.session_state.nombre_cliente
            )
            
            st.write("📁 Buscando o creando la carpeta individual del cliente en Google Drive...")
            id_carpeta_cliente = obtener_o_crear_carpeta_cliente(st.session_state.nombre_cliente)
            
            if id_carpeta_cliente:
                st.write("📤 Guardando archivos originales en la carpeta de Drive del cliente...")
                
                if b_recibo and n_recibo:
                    st.write(f"   ↳ Subiendo recibo: {n_recibo}")
                    subir_bytes_a_drive(b_recibo, n_recibo, id_carpeta_cliente)
                
                if b_veraz and n_veraz:
                    st.write(f"   ↳ Subiendo informe Veraz: {n_veraz}")
                    subir_bytes_a_drive(b_veraz, n_veraz, id_carpeta_cliente)
                
                if b_credixsa and n_credixsa:
                    st.write(f"   ↳ Subiendo reporte Credixsa: {n_credixsa}")
                    subir_bytes_a_drive(b_credixsa, n_credixsa, id_carpeta_cliente)
                
                st.write("📊 Registrando planilla de auditoría en Google Sheets...")
                registrar_auditoria_sheet(
                    st.session_state.nombre_cliente,
                    st.session_state.tipo_operacion,
                    st.session_state.modelo_usado,
                    st.session_state.tiempo_total,
                    st.session_state.analisis_resultado,
                    "Procesado y guardado correctamente",
                    id_carpeta_cliente
                )
            
            for p in paths_dict.values():
                if os.path.exists(p):
                    try:
                        os.unlink(p)
                    except:
                        pass
            status.update(label="✅ ¡Proceso, análisis, guardado en Drive y auditoría completados con éxito!", state="complete", expanded=False)

# Mostrar resultados si ya fueron generados
if st.session_state.analisis_resultado:
    st.success("¡Operación finalizada y registrada en Google Drive!")
    
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
