import os
import time
from google import genai
from prompts import obtener_prompt_credito

def analizar_credito_con_fallback(api_key, files_dict, tipo_operacion, nombre_cliente):
    local_client = genai.Client(api_key=api_key)
    # Usamos gemini-2.5-flash que es ultrarrápido para lectura de documentos
    modelos_a_probar = ['gemini-2.5-flash', 'gemini-3.8-flash']
    inicio = time.time()
    
    for modelo in modelos_a_probar:
        uploaded_files = []
        try:
            for tipo, path in files_dict.items():
                if path and os.path.exists(path):
                    g_file = local_client.files.upload(file=path)
                    uploaded_files.append(g_file)
            
            prompt = obtener_prompt_credito(tipo_operacion, nombre_cliente)
            
            inicio_modelo = time.time()
            response = local_client.models.generate_content(
                model=modelo,
                contents=uploaded_files + [prompt]
            )
            duracion = round(time.time() - inicio_modelo, 1)
            
            if response and response.text:
                return response.text, modelo, duracion
                
        except Exception as e:
            continue
            
    duracion = round(time.time() - inicio, 1)
    return "⚠️ **No se pudo completar el análisis:** Ocurrió un inconveniente al procesar la documentación adjunta.", "Error", duracion
