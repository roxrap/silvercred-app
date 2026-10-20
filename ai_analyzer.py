import os
import time
from google import genai
from prompts import obtener_prompt_credito

def analizar_credito_con_fallback(api_key, files_dict, tipo_operacion, nombre_cliente):
    local_client = genai.Client(api_key=api_key)
    modelos = ['gemini-3.8-flash']
    inicio = time.time()
    ultimo_error = ""
    
    for modelo in modelos:
        max_intentos = 2
        for intento in range(max_intentos):
            uploaded_files = []
            try:
                for tipo, path in files_dict.items():
                    if path and os.path.exists(path):
                        g_file = local_client.files.upload(file=path)
                        uploaded_files.append(g_file)
                
                prompt = obtener_prompt_credito(tipo_operacion, nombre_cliente)
                
                response = local_client.models.generate_content(
                    model=modelo,
                    contents=uploaded_files + [prompt]
                )
                duracion = round(time.time() - inicio, 1)
                return response.text, modelo, duracion
            
            except Exception as e:
                ultimo_error = str(e)
                if "503" in str(e) and intento < max_intentos - 1:
                    time.sleep(2)
                    continue
                else:
                    break
                    
    duracion = round(time.time() - inicio, 1)
    return f"Error crítico con Gemini: {ultimo_error}", "Error", duracion
