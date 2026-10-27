import time
from google import genai
from google.genai import types

def analizar_credito_con_fallback(api_key, paths_dict, tipo_operacion, nombre_cliente):
    inicio = time.time()
    
    if not api_key:
        return "Error: Falta configurar la API Key de Gemini en los secrets.", "Ninguno", 0

    client = genai.Client(api_key=api_key)
    
    # Prompt directrices estrictas y simplificadas para las sucursales
    prompt_sistema = f"""
    Actúa como un analista de riesgo crediticio senior de la financiera Silvercred (sucursales Santa Fe y San Javier). 
    Tu objetivo es emitir un dictamen de riesgo **estrictamente conciso, al pie, sin palabras complicadas ni explicaciones de cálculos**, para que el operador humano lo interprete en segundos sin dudas.

    REGLAS DE NEGOCIO OBLIGATORIAS:
    1. DATOS IDENTIFICATORIOS: 
       - Apellido y Nombre del cliente.
       - Mostrar ÚNICAMENTE el DNI (ej: DNI: 29851777), NO incluir CUIL.
       - Tipo de Operación ({tipo_operacion}).
    
    2. SITUACIÓN LABORAL Y CAPITAL MÁXIMO:
       - Clasificar estrictamente la situación laboral en una de estas categorías: Empleado privado, Empleado provincial, Empleado municipal, Empleada doméstica, Jubilado provincial, Jubilado municipal o Jubilado nacional.
       - CAPITAL MÁXIMO A OTORGAR: Se calcula tomando como base el sueldo neto, redondeando por debajo en bloques de 50.000. Es 1 sueldo neto para Empleado privado. Es 50% sueldo neto para Empleado municipal, Empleada doméstica, Jubilado provincial, Jubilado municipal o Jubilado nacional. Es 75% del sueldo neto para Jubilado provincial. No alucines montos desligados del ingreso.
    
    3. EVALUACIÓN DE INGRESOS Y CUOTA:
       - Informar el Ingreso Neto Comprobado y la Antigüedad Laboral.
       - Cuota Máxima / Límite de Cuota Sugerido: Se rige EXCLUSIVAMENTE por la relación cuota-ingreso (el 30% exacto del sueldo neto). NO deducir ni alterar este límite por compromisos mensuales inferidos u otras deudas.

    4. CALIFICACIÓN EN CENTRALES DE RIESGO (VERAZ, BCRA, CREDIXSA):
       - SCORE VERAZ: A partir de 350 puntos en adelante, el score se considera APROBADO (no rechaza por score si es mayor a 350). NO menciones campos técnicos como "Predictor R6" o similares.
       - MOROSIDAD Y LIBRE DE DEUDA: Si las situaciones 2 o 3 en BCRA o Credixsa tienen más de 6 meses de antigüedad o figuran como "Morosidad no vigente", NO se debe solicitar libre de deuda. Solo se exige libre de deuda si hay morosidad VIGENTE y reciente (menor a 6 meses). Si las situaciones 4 o 5 en BCRA, Veraz o Credixsa tienen MENOS de 6 meses de antigüedad ES RECHAZADO. Si las situaciones 4 o 5 en BCRA, Veraz o Credixsa tienen MÁS de 6 meses de antigüedad CONDICIONADO --> debe presentar libre deuda.
       - CERO ALUCINACIONES: Lee estrictamente lo que dicen los archivos adjuntos. Si una deuda (ej. Telecom, AMX) no figura explícitamente en el Veraz aportado, NO la inventes ni la menciones.
       - CONSULTAS EN BUREAUX: Informar la cantidad de consultas realizadas en los **últimos 3 meses** (no en 60 meses).

    5. FORMATO DE SALIDA (ESTRICTAMENTE CONCISO):
       - Datos Identificatorios:
       - Evaluación de Ingresos: (Incluir Neto, Situación Laboral, Antigüedad, Cuota Máxima 30% y Capital Máximo).
       - Calificación en Centrales de Riesgo: (BCRA, Score Equifax, Reporte Credixsa semáforo, Antecedentes reales, Consultas últimos 3 meses).
       - Resolución Crediticia: DICTAMEN: [APROBADO / CONDICIONADO / RECHAZADO]
       - Fundamento Técnico: (Breve, directo, sin rodeos, máximo 2 o 3 líneas explicativas).

    Analiza la documentación adjunta (Recibo de sueldo, Veraz, Credixsa) para el cliente {nombre_cliente}.
    """

    contents = [prompt_sistema]
    
    # Adjuntar archivos físicos a la llamada de Gemini si existen
    for key, path in paths_dict.items():
        if os.path.exists(path):
            try:
                uploaded_file = client.files.upload(file=path)
                contents.append(uploaded_file)
            except Exception as e:
                print(f"Error subiendo archivo temporal {key}: {e}")

    modelos_a_probar = ["gemini-2.5-flash", "gemini-3.8-flash", "gemini-2.5-pro"]
    
    for modelo in modelos_a_probar:
        try:
            inicio_modelo = time.time()
            response = client.models.generate_content(
                model=modelo,
                contents=contents
            )
            tiempo_total = round(time.time() - inicio_modelo, 1)
            if response and response.text:
                return response.text, modelo, tiempo_total
        except Exception as e:
            continue
            
    # Fallback definitivo si fallan los modelos
    tiempo_total = round(time.time() - inicio, 1)
    return "Error crítico: No se pudo procesar el análisis con ningún modelo de Gemini.", "Ninguno", tiempo_total
