import os
import time
from google import genai
from prompts import obtener_prompt_credito

def analizar_credito_con_fallback(api_key, files_dict, tipo_operacion, nombre_cliente):
    local_client = genai.Client(api_key=api_key)
    modelo = 'gemini-3.8-flash'
    inicio = time.time()
    
    max_intentos = 4
    espera_inicial = 2
    
    for intento in range(max_intentos):
        uploaded_files = []
        try:
            for tipo, path in files_dict.items():
                if path and os.path.exists(path):
                    g_file = local_client.files.upload(file=path)
                    uploaded_files.append(g_file)
            
            # Obtiene el prompt estructurado desde prompts.py
            prompt = obtener_prompt_credito(tipo_operacion, nombre_cliente)
            
            response = local_client.models.generate_content(
                model=modelo,
                contents=uploaded_files + [prompt]
            )
            
            duracion = round(time.time() - inicio, 1)
            return response.text, modelo, duracion
            
        except Exception as e:
            error_str = str(e)
            
            # Reintento automático silencioso si es alta demanda (503)
            if "503" in error_str and intento < max_intentos - 1:
                tiempo_espera = espera_inicial * (2 ** intento)
                time.sleep(tiempo_espera)
                continue
            else:
                # Traducción amigable de errores para el operador
                duracion = round(time.time() - inicio, 1)
                
                if "503" in error_str:
                    mensaje_amigable = (
                        "⚠️ **Aviso Operativo (Alta Demanda):**\n\n"
                        "El servicio de inteligencia artificial está experimentando un pico de tráfico temporal. "
                        "Por favor, aguarde unos segundos y vuelva a presionar el botón de procesamiento."
                    )
                elif "404" in error_str:
                    mensaje_amigable = (
                        "❌ **Error de Configuración:**\n\n"
                        "El modelo de análisis configurado no se encuentra disponible. "
                        "Comuníquese con el back-office o soporte técnico."
                    )
                else:
                    mensaje_amigable = (
                        "⚠️ **No se pudo completar el análisis:**\n\n"
                        "Ocurrió un inconveniente al procesar la documentación adjunta. "
                        "Verifique que los archivos (recibo, veraz, credixsa) sean legibles e intente nuevamente."
                    )
                
                return mensaje_amigable, "Error", duracion

    duracion = round(time.time() - inicio, 1)
    return "⚠️ **Atención:** El servidor no respondió tras varios intentos automáticos. Intente nuevamente en un momento.", "Error", duracion
