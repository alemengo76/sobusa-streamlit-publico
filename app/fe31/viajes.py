"""Viajes de progvehiculos en el formato P del feature engineering. Un solo camino para todos.

La ingesta, el entrenamiento y la predicción pasan por a_formato_fe(), así los tres ven los
mismos viajes con la misma limpieza:
  - la del ETL (celda 35): fechas a hora local sin zona, finalizado/cancelada sin espacios y en
    mayúsculas (regenerar_viajes_etl.py hace exactamente esto);
  - los nombres y tipos de la celda 3 del cuaderno de FE (id_ruta como texto, pasajeros float).
"""
from __future__ import annotations

import pandas as pd

ZONA = "America/Bogota"
RUTAS = (2, 16, 21)
# Columnas de progvehiculos que se leen y se guardan en ai_frecuencias.viaje_fuente
COLUMNAS_FUENTE = ["idprogramacion", "idruta", "fechasalida", "fechainicio", "fechafin",
                   "finalizado", "cancelada", "numeropasajeros", "numerobajadas"]
RENOMBRE = {"idruta": "id_ruta", "idprogramacion": "id_programacion",
            "fechasalida": "salida_programada", "fechainicio": "inicio_registrado",
            "fechafin": "fin_registrado", "numeropasajeros": "pasajeros_original",
            "numerobajadas": "bajadas_original"}


def _fecha_local(s: pd.Series) -> pd.Series:
    if not pd.api.types.is_datetime64_any_dtype(s):
        s = pd.to_datetime(s, errors="coerce", format="ISO8601")
    if getattr(s.dt, "tz", None) is not None:
        s = s.dt.tz_convert(ZONA).dt.tz_localize(None)
    return s.astype("datetime64[ns]")


def limpiar_fuente(df: pd.DataFrame) -> pd.DataFrame:
    """Limpieza del ETL sobre columnas con nombres de progvehiculos. No borra filas ni imputa."""
    d = df.copy()
    for c in ("fechasalida", "fechainicio", "fechafin"):
        if c in d:
            d[c] = _fecha_local(d[c])
    for c in ("finalizado", "cancelada"):
        if c in d:
            d[c] = d[c].astype("string").str.strip().str.upper().astype(object)
            d[c] = d[c].where(d[c].notna(), None)
    for c in ("numeropasajeros", "numerobajadas"):
        if c in d:
            d[c] = pd.to_numeric(d[c], errors="coerce").astype("float64")
        else:
            d[c] = float("nan")
    return d


def a_formato_fe(df: pd.DataFrame) -> pd.DataFrame:
    """progvehiculos (nombres originales) -> P de reglas_comunes (mismo índice que la entrada)."""
    d = limpiar_fuente(df)
    P = d[COLUMNAS_FUENTE].rename(columns=RENOMBRE)
    P["id_ruta"] = P.id_ruta.astype(int).astype(str)
    return P
