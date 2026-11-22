"""Reglas de calidad de la ingesta = reglas comun-1.5 del feature engineering (E02).

Antes la ingesta tenía reglas propias (calidad_v1: CAL-001..004) y el FE usaba comun-1.5, así
que el modelo se entrenaba con un criterio y la API predecía con otro. Ahora este módulo no
define reglas: llama a reglas_comunes.aplicar_cuarentena (copia exacta, ver app/fe31) y solo
traduce su resultado a la tabla data_quality_error. Los umbrales viven en reglas_comunes.REGLAS.

Qué va a data_quality_error (una fila por viaje y regla, con lote, causa y valor):
  - cada regla de comun-1.5 que marcó el viaje (pasajeros_extremo, duracion_negativa,
    inicio_incoherente, duracion_mayor_24h, fin_tardio, bajadas_extremo);
  - pasajeros_sin_conteo: viaje elegible sin conteo usable (nulo, negativo o no finito). En
    comun-1.5 es la marca pax_bloquea; se registra para que los nulos queden consultables.
No se imputa nada y no se modifican los originales (especificación v1.5).
"""
import pandas as pd

from app.fe31 import REGLAS_VERSION, rc
from app.fe31.viajes import a_formato_fe

DESCRIPCION = {
    "pasajeros_extremo": f"más de {rc.REGLAS['pasajeros_max']} pasajeros en un viaje",
    "duracion_negativa": "el fin registrado es anterior al inicio",
    "inicio_incoherente": "inicio fuera de [salida - 1 día, salida + 2 días]",
    "duracion_mayor_24h": "duración del viaje mayor a 24 h (cierre tardío)",
    "fin_tardio": "fin registrado más de 2 días después de la salida",
    "bajadas_extremo": f"más de {rc.REGLAS['bajadas_max']} bajadas (solo afecta bajadas)",
    "pasajeros_sin_conteo": "viaje elegible sin conteo de pasajeros usable (nulo, negativo o no finito)",
}
COLUMNAS_CUARENTENA = ["lote", "idprogramacion", "idruta", "regla", "causa", "valor"]


def marcar(p: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aplica comun-1.5. Devuelve (P con las marcas, tabla Q de reglas_comunes)."""
    if p.duplicated("idprogramacion").any():
        p = p.drop_duplicates("idprogramacion", keep="last")
    return rc.aplicar_cuarentena(a_formato_fe(p))


def evaluar_programaciones(p: pd.DataFrame, lote: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """p: columnas de progvehiculos (idprogramacion, idruta, fechasalida, fechainicio, fechafin,
    finalizado, cancelada, numeropasajeros y, si existe, numerobajadas).

    Devuelve (validas, cuarentena):
      validas: viajes con conteo usable para la etiqueta (marca pax_valido de comun-1.5),
               con sus columnas originales;
      cuarentena: lote, idprogramacion, idruta, regla, causa, valor."""
    p = p.drop_duplicates("idprogramacion", keep="last")
    P, Q = marcar(p)
    sin_conteo = P.pax_bloquea & ~P.cuarentena_etiqueta
    extra = pd.DataFrame({"id_ruta": P.id_ruta[sin_conteo], "id_programacion": P.id_programacion[sin_conteo],
                          "regla": "pasajeros_sin_conteo",
                          "valor": P.pasajeros_original[sin_conteo]})
    filas = pd.concat([Q[["id_ruta", "id_programacion", "regla", "valor"]], extra], ignore_index=True)
    cuarentena = pd.DataFrame({
        "lote": lote,
        "idprogramacion": filas.id_programacion.astype("int64"),
        "idruta": filas.id_ruta.astype(int),
        "regla": filas.regla,
        "causa": filas.regla.map(DESCRIPCION),
        # dtype=object: con pandas 3 una lista de textos y None se vuelve columna de texto con NaN,
        # y ese NaN llegaba a la base como el TEXTO 'NaN'. Un faltante debe quedar como NULL.
        "valor": pd.Series([None if pd.isna(v) else f"{v:g}" for v in filas.valor], dtype=object),
    }, columns=COLUMNAS_CUARENTENA)
    validas = p.loc[P.index[P.pax_valido.to_numpy()]]
    return validas, cuarentena


def elegibles(p: pd.DataFrame) -> pd.Series:
    """Misma definición de viaje elegible que comun-1.5 (finalizado S y no cancelado)."""
    P = a_formato_fe(p)
    return (P.finalizado.eq("S") & P.cancelada.eq("N")).fillna(False).astype(bool)
