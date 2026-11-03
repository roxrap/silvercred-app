import requests

def consultar_bcra_api(identificacion):
    """
    Consulta la API pública del BCRA (Central de Deudores) usando el CUIT/CUIL de 11 dígitos.
    Extrae correctamente el periodo, la entidad, situación, monto real y días de atraso.
    """
    try:
        id_limpia = "".join(filter(str.isdigit, str(identificacion)))
        
        if len(id_limpia) != 11:
            return {
                "valido": False,
                "mensaje": "La API del BCRA exige el CUIL completo de 11 dígitos (ej: 20XXXXXXXXX)."
            }

        url = f"https://api.bcra.gob.ar/centraldedeudores/v1.0/Deudas/{id_limpia}"
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
                    "items_tabla": [],
                    "rechazado": False,
                    "mensaje": "Situación 1 (Sin deudas registradas)"
                }

            peor_situacion = 1
            items_tabla = []
            
            for periodo_obj in periodos:
                # Obtener periodo (ej: "202609" y pasarlo a "09/26")
                raw_periodo = str(periodo_obj.get("periodo", "") or periodo_obj.get("fecha", ""))
                if len(raw_periodo) == 6:
                    anio = raw_periodo[:4]
                    mes = raw_periodo[4:]
                    periodo_formato = f"{mes}/{anio[2:]}"
                else:
                    periodo_formato = raw_periodo

                entidades = periodo_obj.get("entidades", [])
                
                for ent in entidades:
                    entidad_nombre = ent.get("entidad", "Entidad financiera")
                    sit = ent.get("situacion", 1)

                    # Capturar el monto de forma limpia
                    monto = ent.get("monto", None)
                    if monto is None:
                        monto = ent.get("importe", 0)
                        
                    dias_atraso = ent.get("diasAtraso", "N/A")
                    
                    if sit > peor_situacion:
                        peor_situacion = sit
                        
                    # Formatear el monto de manera limpia sin decimales extraños
                    try:
                        monto_num = float(monto)
                        # Si es un número entero grande, lo mostramos con separador de miles limpio
                        monto_str = f"{int(monto_num):,}".replace(",", ".")
                    except:
                        monto_str = str(monto)
                    
                         
                    items_tabla.append({
                        "Denominación del deudor": denominacion,
                        "Entidad": entidad_nombre,
                        "Periodo": periodo_formato,
                        "Situación": sit,
                        "Monto": monto_str,
                        "Días de atraso": dias_atraso
                    })

            rechazado = False
            mensaje_resultado = f"Situación máxima detectada: {peor_situacion}."
            if peor_situacion >= 4:
                rechazado = True
                mensaje_resultado = f"RECHAZADO POR BCRA: Posee antecedentes en Situación {peor_situacion}."

            return {
                "valido": True,
                "denominacion": denominacion,
                "peor_situacion": peor_situacion,
                "items_tabla": items_tabla,
                "rechazado": rechazado,
                "mensaje": mensaje_resultado
            }
            
        elif response.status_code == 400:
            return {
                "valido": False,
                "mensaje": f"El BCRA rechazó el formato ({id_limpia}). Ingrese un CUIL válido de 11 dígitos."
            }
        elif response.status_code == 404:
            return {
                "valido": True,
                "denominacion": "NO REGISTRADO",
                "peor_situacion": 1,
                "items_tabla": [],
                "rechazado": False,
                "mensaje": "Sin registros previos en BCRA."
            }
        else:
            return {
                "valido": False,
                "mensaje": f"Error en la consulta al BCRA (Código HTTP {response.status_code})."
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
