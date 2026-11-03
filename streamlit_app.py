import streamlit as st
import os
import tempfile
from services import registrar_auditoria_sheet
from ai_analyzer import analizar_credito_con_fallback
from bcra_api import consultar_bcra_api
from datetime import datetime, timedelta, timezone

# --- CONFIGURACIÓN DE ZONA HORARIA ARGENTINA (UTC-3) ---
zona_arg = timezone(timedelta(hours=-3))
f_argentina = datetime.now(zona_arg)
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
        st.image("logo.png", width="stretch")
    st.markdown("---")
    st.markdown("### 🏢 Sucursales operativas")
    st.markdown("- Santa Fe\n- San Javier")
    st.markdown("---")
    st.info("Módulo Activo: Validación BCRA por API + Análisis IA y Auditoría Sheets")

# --- INICIALIZAR ESTADO DE SESIÓN ---
if "bcra_resultado" not in st.session_state:
    st.session_state.bcra_resultado = None
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
if "cuil_cliente" not in st.session_state:
    st.session_state.cuil_cliente = None

# --- INTERFAZ PRINCIPAL ---
st.title("💳 Silvercred - Sistema de Evaluación Crediticia")
st.markdown("---")
st.subheader("🔍 Paso 1: Central de Deudores BCRA")

# ==========================================
# PASO 1: VALIDACIÓN PREVIA POR API BCRA
# ==========================================
with st.form("form_bcra_previa"):
    col_dni1, col_dni2, col_dni3 = st.columns([2, 1, 1])
    with col_dni1:
        nombre_cliente_input = st.text_input("Apellido y Nombre Completo del Cliente", placeholder="Ej: RAPALI, ROXANA ANALIA", value=st.session_state.nombre_cliente or "")
    with col_dni2:
        cuil_input = st.text_input("CUIL del Cliente (11 dígitos)", placeholder="Ej: 27294758882", value=st.session_state.cuil_cliente or "")
    with col_dni3:
        tipo_op_input = st.selectbox("Tipo de Operación", ["Apertura", "Renovación"], index=0 if st.session_state.tipo_operacion == "Apertura" else 1)
        
    btn_consultar_bcra = st.form_submit_button("Consultar BCRA por API")

if btn_consultar_bcra:
    if not nombre_cliente_input.strip() or not cuil_input.strip():
        st.warning("Por favor, completa el nombre y el CUIL de 11 dígitos para realizar la consulta en el BCRA.")
    else:
        st.session_state.nombre_cliente = nombre_cliente_input.strip().upper()
        st.session_state.cuil_cliente = cuil_input.strip()
        st.session_state.tipo_operacion = tipo_op_input
        
        with st.spinner("Consultando API oficial del Banco Central (BCRA)..."):
            resultado_bcra = consultar_bcra_api(st.session_state.cuil_cliente)
            st.session_state.bcra_resultado = resultado_bcra
            st.session_state.analisis_resultado = None

# Mostrar resultado del BCRA si ya fue consultado
if st.session_state.bcra_resultado:
    res_bcra = st.session_state.bcra_resultado
    
    if not res_bcra.get("valido"):
        st.error(f"❌ {res_bcra.get('mensaje')}")
    else:
        st.info(f"📋 **Titular BCRA:** {res_bcra.get('denominacion')} | **Estado:** {res_bcra.get('mensaje')}")
        

        # Mostrar la tabla limpia con las columnas exactas del reporte BCRA (Usando st.table para evitar errores de carga de componentes)
        items_bcra = res_bcra.get("items_tabla", [])
        if items_bcra:
            st.markdown("##### Detalle Central de Deudores BCRA")
            st.table(items_bcra)
        else:
            st.info("Sin deudas o entidades informantes registradas en el período actual.")


        
        # SI ESTÁ RECHAZADO POR EL BCRA (Ej: Situación 4 o 5)
        if res_bcra.get("rechazado"):
            st.error("🚨 **CRÉDITO RECHAZADO EN INSTANCIA BCRA:** El cliente registra antecedentes en situaciones críticas (Sit 4 o 5). No es necesario cargar más documentación.")
            
            if st.session_state.analisis_resultado is None:
                dictamen_rechazo = f"""1. Datos Identificatorios:
- Apellido y Nombre: {st.session_state.nombre_cliente}
- CUIL: {st.session_state.cuil_cliente}
- Tipo de Operación: {st.session_state.tipo_operacion}

5. Resolución Crediticia:
DICTAMEN: RECHAZADO
Fundamento Técnico: Rechazado de manera directa por la API del BCRA debido a registros en situación crediticia deficiente ({res_bcra.get('mensaje')})."""
                
                with st.spinner("Registrando rechazo en Google Sheets..."):
                    registrar_auditoria_sheet(
                        st.session_state.nombre_cliente,
                        st.session_state.tipo_operacion,
                        "API BCRA",
                        0.1,
                        dictamen_rechazo
                    )
                st.session_state.analisis_resultado = dictamen_rechazo
                st.success("📝 Rechazo registrado correctamente en la auditoría de Google Sheets.")

        # SI ESTÁ APTO PARA CONTINUAR (BCRA OK)
        else:
            st.success("✅ **BCRA Aprobado / Viable:** El cliente se encuentra en condiciones de continuar con el análisis de burós.")
            
            st.markdown("---")
            st.subheader("📂 Paso 2: Carga de Documentación Restante (Recibo, Veraz y Credixsa)")
            
            with st.form("form_legajo_completo"):
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    archivo_recibo = st.file_uploader("1. Recibo de Sueldo (PDF o Imagen)", type=["pdf", "png", "jpg", "jpeg"])
                with col_b:
                    archivo_veraz = st.file_uploader("2. Informe Veraz (PDF)", type=["pdf"])
                with col_c:
                    archivo_credixsa = st.file_uploader("3. Reporte Credixsa (PDF)", type=["pdf"])
                
                submitted_legajo = st.form_submit_button("Procesar Dictamen Integral con Gemini")

            if submitted_legajo:
                if not (archivo_recibo or archivo_veraz or archivo_credixsa):
                    st.warning("Por favor, adjunta al menos la documentación correspondiente para el análisis analítico.")
                else:
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

                        st.write("🧠 Conectando con Gemini para procesamiento analítico optimizado...")
                        
                        res, mod, tiempo = analizar_credito_con_fallback(
                            GEMINI_API_KEY, paths_dict, st.session_state.tipo_operacion, st.session_state.nombre_cliente
                        )
                        
                        st.session_state.analisis_resultado = res
                        st.session_state.modelo_usado = mod
                        st.session_state.tiempo_total = tiempo

                        st.write("📊 Registrando datos estructurados en Google Sheets (17 columnas)...")
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

# Mostrar resultados si ya fueron generados por la IA
if st.session_state.analisis_resultado and not (st.session_state.bcra_resultado and st.session_state.bcra_resultado.get("rechazado")):
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
