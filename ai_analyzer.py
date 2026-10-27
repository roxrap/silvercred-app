import os
import time
from google import genai
from prompts import obtener_prompt_credito

def analizar_credito_con_fallback(api_key, files_dict, tipo_operacion, nombre_cliente):
    local_client = genai.Client(api_key=api_key)
    # Usamos gemini-2.5-flash como modelo principal por su velocidad y estabilidad
    modelos_a_probar = ['gemini-2.5-flash', 'gemini-3.8-flash']
    inicio = time.time()
    
    max_intentos = 3
    espera_inicial = 2
    
    for intento in range(max_intentos):
        try:
            contents_list = []
            
            # 1. Subir archivos adjuntos al servidor de Gemini y agregarlos a la lista
            for tipo, path in files_dict.items():
                if path and os.path.exists(path):
                    g_file = local_client.files.upload(file=path)
                    contents_list.append(g_file)
            
            # 2. Obtener el prompt estructurado desde prompts.py
            prompt_texto = obtener_prompt_credito(tipo_operacion, nombre_cliente)
            contents_list.append(prompt_texto)
            
            # 3. Probar con los modelos disponibles
            for modelo in modelos_a_probar:
                try:
                    inicio_modelo = time.time()
                    response = local_client.models.generate_content(
                        model=modelo,
                        contents=contents_list
                    )
                    duracion = round(time.time() - inicio_modelo, 1)
                    
                    if response and response.text:
                        return response.text, modelo, duracion
                except Exception as sub_e:
                    # Si falla un modelo, pasa al siguiente de la lista
                    continue
            
            # Si ningún modelo respondió, lanza excepción para reintentar
            raise Exception("Ninguno de los modelos pudo procesar la solicitud.")
            
        except Exception as e:
            error_str = str(e)
            
            # Reintento automático si es alta demanda (503) u otro error temporal
            if intento < max_intentos - 1:
                tiempo_espera = espera_inicial * (2 ** intento)
                time.sleep(tiempo_espera)
                continue
            else:
                duracion = round(time.time() - inicio, 1)
                
                if "503" in error_str:
                    mensaje_amigable = (
                        "⚠️ **Aviso Operativo (Alta Demanda):**\n\n"
                        "El servicio de inteligencia artificial está experimentando un pico de tráfico temporal. "
                        "Por favor, aguarde unos segundos y vuelva a presionar el botón de procesamiento."
                    )
                else:
                    mensaje_amigable = (
                        f"⚠️ **No se pudo completar el análisis:**\n\n"
                        f"Detalle técnico: {error_str}"
                    )
                
                return mensaje_amigable, "Error", duracion

    duracion = round(time.time() - inicio, 1)
    return "⚠️ **Atención:** El servidor no respondió tras varios intentos automáticos.", "Error", duracion
