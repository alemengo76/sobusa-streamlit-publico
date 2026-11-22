"""Catálogo ALT-001 a ALT-010 y umbrales por defecto.

Los umbrales vigentes viven en ai_frecuencias.umbral (versionados). Estos valores
solo son la semilla de la migración 0002 y el respaldo en pruebas.
"""

CATALOGO = {
    "ALT-001": {"nombre": "Alta demanda prevista", "severidad": "media",
                "parametro": "factor_sobre_referencia", "valor": 1.30,
                "recomendacion": "Preparar buses de refuerzo para la franja indicada."},
    "ALT-002": {"nombre": "Sobreocupación prevista (>= 90%)", "severidad": "alta",
                "parametro": "ocupacion_maxima", "valor": 0.90,
                "recomendacion": "Aumentar la frecuencia a la recomendada o despachar refuerzo."},
    "ALT-003": {"nombre": "Frecuencia insuficiente", "severidad": "media",
                "parametro": "deficit_buses_hora", "valor": 1.0,
                "recomendacion": "Ajustar la programación a los buses/hora recomendados."},
    "ALT-004": {"nombre": "Frecuencia excesiva (< 30%)", "severidad": "baja",
                "parametro": "ocupacion_minima", "valor": 0.30,
                "recomendacion": "Evaluar reducir salidas en la franja para ahorrar flota."},
    "ALT-005": {"nombre": "Caída anormal de demanda", "severidad": "media",
                "parametro": "caida_relativa", "valor": 0.40,
                "recomendacion": "Verificar novedades viales o fallas de conteo en la ruta."},
    "ALT-006": {"nombre": "Despacho ausente o tardío", "severidad": "alta",
                "parametro": "retraso_maximo_min", "valor": 10.0,
                "recomendacion": "Contactar al despachador y reprogramar la salida."},
    "ALT-007": {"nombre": "Desviación del pronóstico", "severidad": "media",
                "parametro": "error_relativo", "valor": 0.35,
                "recomendacion": "Revisar la franja; si se repite, evaluar reentrenamiento."},
    "ALT-008": {"nombre": "Consolidado anómalo", "severidad": "media",
                "parametro": "diferencia_relativa", "valor": 0.20,
                "recomendacion": "Comparar el consolidado con los viajes y reportar a Extreme."},
    "ALT-009": {"nombre": "Datos incompletos", "severidad": "media",
                "parametro": "cobertura_minima", "valor": 0.90,
                "recomendacion": "Revisar la carga del día y la cuarentena antes de usar los datos."},
    "ALT-010": {"nombre": "Modelo degradado", "severidad": "alta",
                "parametro": "degradacion_wape", "valor": 0.20,
                "recomendacion": "Entrenar un candidato y compararlo contra el modelo activo."},
}

# Las alertas de frecuencia y ocupación (ALT-002, ALT-003, ALT-004) se evalúan solo con las
# recomendaciones de este horizonte. 60 min es el que se usa para decidir despachos (buses por
# hora). Con los tres horizontes, la misma situación salía tres veces: el 10 de diciembre de
# 2025 eran 293 alertas en un día. Las predicciones y recomendaciones de 30 y 120 min se siguen
# calculando y guardando; ALT-001 y las demás alertas no cambian.
HORIZONTE_ALERTAS_FRECUENCIA = 60

ESTADOS = ("abierta", "reconocida", "asignada", "cerrada", "descartada")
TRANSICIONES = {
    "abierta": {"reconocida", "asignada", "cerrada", "descartada"},
    "reconocida": {"asignada", "cerrada", "descartada"},
    "asignada": {"reconocida", "cerrada", "descartada"},
    "cerrada": set(),
    "descartada": set(),
}
