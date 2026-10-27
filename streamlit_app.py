import streamlit as st
import os
import tempfile
from datetime import datetime, timedelta
from services import registrar_auditoria_sheet
from ai_analyzer import analizar_credito_con_fallback

# Hora ajustada para Argentina (UTC-3)
f_argentina = datetime.now(datetime.UTC) - timedelta(hours=3) if hasattr(datetime, "UTC") else datetime.utcnow() - timedelta(hours=3)
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
        st.image("logo.png", width='stretch')
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
st.markdown("Ingresa los datos del cliente, sube la documentación y el sistema procesará el dictamen de riesgo registrando automáticamente la auditoría en Google Sheets.")

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
            st.write("📥 Preparando archivos temporales...")
            
            if archivo_recibo:
                suffix = os.path.splitext(archivo_recibo.name)[1]
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
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

            st.write("🧠 Conectando con Gemini 3.8-flash para procesamiento analítico...")
            res, mod, tiempo = analizar_credito_con_fallback(
                GEMINI_API_KEY, paths_dict, st.session_state.tipo_operacion, st.session_state.nombre_cliente
            )
            st.session_state.analisis_resultado = res
            st.session_state.modelo_usado = mod
            st.session_state.tiempo_total = tiempo

            st.write("📊 Registrando datos estructurados en Google Sheets...")
            registrar_auditoria_sheet(
                st.session_state.nombre_cliente,
                st.session_state.tipo_operacion,
                st.session_state.modelo_usado,
                st.session_state.tiempo_total,
                st.session_state.analisis_resultado
            )

            for p in paths_dict.values():
                if os.path.exists(p):
                    try:
                        os.unlink(p)
                    except:
                        pass
                        
            status.update(label="✅ ¡Análisis completado y registrado en Sheets con éxito!", state="complete", expanded=False)

# Mostrar resultados si ya fueron generados
if st.session_state.analisis_resultado:
    st.success("¡Operación finalizada y registrada correctamente!")
    
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
