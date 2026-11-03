import requests

def consultar_bcra_api(identificacion):
    """
    Consulta la API pública y oficial del BCRA (Central de Deudores) usando el CUIT/CUIL o DNI.
    Retorna un diccionario con el análisis de la situación crediticia.
    """
    try:
        # Limpiar la entrada para dejar solo números
        id_limpia = "".join(filter(str.isdigit, str(identificacion)))
        if not id_limpia or len(id_limpia) < 7:
            return {
                "valido": False,
                "mensaje": "Identificación (DNI/CUIT) no válida para consultar en el BCRA."
            }

        url = f"https://api.bcra.gob.ar/centraldedeudores/v1.0/Deudas/{id_limpia}"
        
        # Realizar la petición GET con un timeout de 8 segundos
        response = requests.get(url, timeout=8)
        
        if response.status_code == 200:
            data = response.json()
            resultado = data.get("results", {})
            denominacion = resultado.get("denominacion", "CLIENTE")
            periodos = resultado.get("periodos", [])
            
            if not periodos:
                return {
                    "valido": True,
                    "denominacion": denominacion,
                    "peor_situacion": 1,
                    "detalle": "Sin antecedentes de deuda registrados en el BCRA.",
                    "rechazado": False
                }

            # Analizar las deudas y situaciones reportadas
            peor_situacion = 1
            detalle_deudas = []
            
            for periodo in periodos:
                fecha = periodo.get("fecha", "")
                entidades = periodo.get("entidades", [])
                for ent in entidades:
                    entidad_nombre = ent.get("entidad", "Entidad financiera")
                    sit = ent.get("situacion", 1)
                    monto = ent.get("importe", 0)
                    
                    if sit > peor_situacion:
                        peor_situacion = sit
                        
                    detalle_deudas.append(f"{entidad_nombre} (Sit {sit}: ${monto:,}) - Período {fecha}")

            # Regla de corte: Si tiene Situación 4 o 5 (considerando histórico reciente)
            rechazado = False
            mensaje_resultado = f"Situación máxima detectada: {peor_situacion}."
            
            if peor_situacion >= 4:
                rechazado = True
                mensaje_resultado = f"RECHAZADO POR BCRA: Posee antecedentes en Situación {peor_situacion}."

            return {
                "valido": True,
                "denominacion": denominacion,
                "peor_situacion": peor_situacion,
                "detalle": " | ".join(detalle_deudas[:5]), # Tomar un resumen de las principales
                "rechazado": rechazado,
                "mensaje": mensaje_resultado
            }
            
        elif response.status_code == 404:
            return {
                "valido": True,
                "denominacion": "NO REGISTRADO",
                "peor_situacion": 1,
                "detalle": "El DNI/CUIT no arroja registros en la base del BCRA.",
                "rechazado": False,
                "mensaje": "Sin registros previos en BCRA."
            }
        else:
            return {
                "valido": False,
                "mensaje": f"Error en la consulta al BCRA (Código {response.status_code})."
            }

    except requests.exceptions.Timeout:
        return {
            "valido": False,
            "mensaje": "La consulta al BCRA demoró demasiado (Timeout). Intente nuevamente."
        }
    except Exception as e:
        return {
            "valido": False,
            "mensaje": f"Excepción técnica al consultar BCRA: {str(e)}"
        }
