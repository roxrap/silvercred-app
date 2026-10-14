import os
import pandas as pd
from google import genai
from google.oauth2 import service_account
from googleapiclient.discovery import build
import streamlit as st

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="Silvercred - Sistema de Evaluación Crediticia",
    page_icon="logo.png" if os.path.exists("logo.png") else "💳",
    layout="wide",
)

# --- INICIALIZACIÓN DE SERVICIOS CON SECRETS ---
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
client = genai.Client(api_key=GEMINI_API_KEY)


@st.cache_resource
def init_google_services():
  try:
    credentials_dict = dict(st.secrets["gcp_service_account"])
    gcp_creds = service_account.Credentials.from_service_account_info(
        credentials_dict,
        scopes=[
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets",
        ],
    )
    service = build("drive", "v3", credentials=gcp_creds)
    return service
  except Exception as e:
    st.error(f"Error al conectar con Google Drive mediante secretos: {e}")
    return None


drive_service = init_google_services()

# --- CUERPO PRINCIPAL DE LA APLICACIÓN ---
st.title("💳 Silvercred - Sistema de Evaluación Crediticia")
st.write(
    "Bienvenido al panel de gerencia. Sube la documentación y procesa las"
    " solicitudes de crédito."
)

if drive_service:
  st.success("Conectado exitosamente con Google Drive y servicios en la nube.")
else:
  st.warning(
      "La aplicación no pudo inicializar el servicio de Google Drive. Revisa"
      " los Secrets."
  )
