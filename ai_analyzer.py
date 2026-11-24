import os
import time
from google import genai
from prompts import obtener_prompt_credito


def _extraer_rutas_validas(valor):
    """Normaliza un valor de files_dict (str, list o tuple) a una lista de rutas existentes."""
    if not valor:
        return []
    if isinstance(valor, (list, tuple)):
        return [p for p in valor if isinstance(p, str) and p and os.path.exists(p)]
    if isinstance(valor, str) and os.path.exists(valor):
        return [valor]
    return []


def _etiqueta_tipo_documento(tipo, indice=None, total=1):
    """Genera una etiqueta clara para ayudar al modelo a identificar cada documento."""
    nombres_base = {
        "recibos": "Recibo de sueldo / haber",
        "recibo": "Recibo de sueldo / haber",
        "veraz": "Informe Veraz",
        "credixsa": "Reporte Credixsa",
    }
    base = nombres_base.get(tipo, f"Documento ({tipo})")
    if total > 1 and indice is not None:
        return f"[{base} #{indice} de {total}]"
    return f"[{base}]"


def analizar_credito_con_fallback(api_key, files_dict, tipo_operacion, nombre_cliente):
    local_client = genai.Client(api_key=api_key)
    # Usamos gemini-2.5-flash como modelo principal por su velocidad y estabilidad
    modelos_a_probar = ["gemini-2.5-flash", "gemini-3.8-flash"]
    inicio = time.time()

    max_intentos = 3
    espera_inicial = 2

    for intento in range(max_intentos):
        archivos_gemini_subidos = []
        try:
            contents_list = []

            # 1. Subir archivos adjuntos al servidor de Gemini (soporta 1 o múltiples archivos por clave)
            for tipo, valor in files_dict.items():
                rutas = _extraer_rutas_validas(valor)
                total_rutas = len(rutas)

                for idx, path in enumerate(rutas, start=1):
                    etiqueta = _etiqueta_tipo_documento(tipo, indice=idx, total=total_rutas)
                    g_file = local_client.files.upload(file=path)
                    archivos_gemini_subidos.append(g_file)
                    contents_list.append(etiqueta)
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
                        contents=contents_list,
                    )
                    duracion = round(time.time() - inicio_modelo, 1)

                    if response and response.text:
                        return response.text, modelo, duracion
                except Exception:
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

        finally:
            # Limpia los archivos subidos a la API de Gemini en este intento
            for g_file in archivos_gemini_subidos:
                try:
                    local_client.files.delete(name=g_file.name)
                except Exception:
                    pass

    duracion = round(time.time() - inicio, 1)
    return "⚠️ **Atención:** El servidor no respondió tras varios intentos automáticos.", "Error", duracion
