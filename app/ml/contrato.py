"""Contrato de datos entre componentes (prediction y recommendation).

Congelado el 2026-11-02. Cualquier cambio necesita el acuerdo de las tres personas.
Las pruebas validan este contrato para que una ruptura falle en CI y no en la demo.
"""
import hashlib
import math
from decimal import ROUND_HALF_UP, Decimal

import numpy as np
import pandas as pd

HORIZONTES = (30, 60, 120)
RUTAS = (2, 16, 21)
FRANJA_MIN = 15
SENTIDO = "CICLO"      # no hay sentido en los datos de Sobusa (ver DECISIONES.md)
SEGMENTO = "TOTAL"     # los segmentos de Extreme son de prueba (ver DECISIONES.md)

COLUMNAS_PREDICCION = {
    "idruta": "int64",
    "sentido": "object",
    "segmento_id": "object",
    "franja_inicio": "datetime64[ns]",
    "franja_minutos": "int64",
    "horizonte_min": "int64",
    "demanda_pred": "float64",
    "limite_inferior": "float64",
    "limite_superior": "float64",
    "nivel_intervalo": "float64",
    "definicion_tiempo": "object",
    "model_version": "object",
    "feature_version": "object",
    "data_cutoff": "datetime64[ns]",
    "latency_ms": "int64",
}

COLUMNAS_NUMERICAS = ("demanda_pred", "limite_inferior", "limite_superior", "nivel_intervalo")
# Clave única de prediction dentro de una ejecución (migración 0008: + execution_id)
CLAVE_PREDICCION = ["idruta", "sentido", "segmento_id", "franja_inicio", "horizonte_min"]

COLUMNAS_RECOMENDACION = [
    "prediction_id", "idruta", "sentido", "segmento_id", "franja_inicio", "horizonte_min",
    "demanda_hora", "base_demanda", "factor_carga_max", "carga_max_estimada_hora",
    "capacidad_nominal", "capacidad_fuente", "ocupacion_objetivo", "capacidad_efectiva",
    "buses_hora_recomendado", "headway_recomendado_min", "ciclo_min",
    "vehiculos_requeridos", "flota_tope", "buses_hora_actual", "headway_actual_min",
    "delta_buses_hora", "es_viable", "motivo_no_viable", "parametros_version",
]


class ContratoInvalido(ValueError):
    pass


def validar_predicciones(df: pd.DataFrame) -> pd.DataFrame:
    faltan = set(COLUMNAS_PREDICCION) - set(df.columns)
    if faltan:
        raise ContratoInvalido(f"Faltan columnas en prediction: {sorted(faltan)}")
    errores = []
    if not df["idruta"].isin(RUTAS).all():
        errores.append("idruta fuera de (2, 16, 21)")
    if not df["horizonte_min"].isin(HORIZONTES).all():
        errores.append("horizonte_min fuera de (30, 60, 120)")
    if not df["sentido"].eq(SENTIDO).all():
        errores.append(f"sentido debe ser '{SENTIDO}'")
    if (df["demanda_pred"] < 0).any():
        errores.append("demanda_pred negativa")
    if not ((df["limite_inferior"] <= df["demanda_pred"])
            & (df["demanda_pred"] <= df["limite_superior"])).all():
        errores.append("se requiere limite_inferior <= demanda_pred <= limite_superior")
    if df[list(COLUMNAS_PREDICCION)].isna().any().any():
        errores.append("hay nulos en columnas obligatorias")
    numericas = df[list(COLUMNAS_NUMERICAS)].apply(pd.to_numeric, errors="coerce").astype("float64")
    if not np.isfinite(numericas.to_numpy()).all():
        errores.append("hay valores no finitos (NaN o infinito) en demanda, límites o nivel")
    if not pd.to_numeric(df["franja_minutos"], errors="coerce").eq(FRANJA_MIN).all():
        errores.append(f"franja_minutos debe ser {FRANJA_MIN}")
    inicio = pd.to_datetime(df["franja_inicio"])
    if not (inicio.dt.floor(f"{FRANJA_MIN}min") == inicio).all():
        errores.append(f"franja_inicio debe caer en múltiplos de {FRANJA_MIN} minutos, sin segundos")
    # Una ejecución tiene a lo sumo una predicción por ruta, sentido, segmento, franja y horizonte:
    # es la misma clave única de prediction desde la migración 0008 (con execution_id).
    if df.duplicated(CLAVE_PREDICCION).any():
        errores.append("filas duplicadas para la clave única (ruta, sentido, segmento, franja, horizonte)")
    if errores:
        raise ContratoInvalido("; ".join(errores))
    return df


# ------------------------------------------------------------------ huella de un conjunto de predicciones
#
# Identifica el CONTENIDO de lo que una ejecución guarda en prediction (DECISIONES.md, §15). Dos
# ejecuciones con la misma huella guardarían exactamente las mismas filas: la segunda reutiliza las
# de la primera. Si el histórico cambió y eso cambia cualquier valor, la huella cambia.
#
# Normalización (huella-pred/1). La huella se calcula sobre los MISMOS valores que se insertan:
#   - demanda_pred, limite_inferior, limite_superior y nivel_intervalo -> Decimal con 2 decimales
#     (ROUND_HALF_UP, como numeric(10,2) / numeric(3,2)); -0.00 -> 0.00. Se insertan esos Decimal.
#   - franja_inicio y data_cutoff -> hora local de Bogotá sin zona (la de la sesión de la app),
#     ISO hasta los segundos. Bogotá no tiene horario de verano.
#   - enteros -> texto decimal; textos -> tal cual (sin los separadores \x1f ni \n).
#   - nulos, NaN e infinitos -> error (el contrato no los admite).
# No entran prediction_id, execution_id, generated_at ni latency_ms: cambian en cada corrida.
# Si se cambia algo de esta normalización hay que cambiar FORMATO_HUELLA.

FORMATO_HUELLA = "huella-pred/1"
ZONA = "America/Bogota"
COLUMNAS_HUELLA = ("idruta", "sentido", "segmento_id", "franja_inicio", "franja_minutos",
                   "horizonte_min", "demanda_pred", "limite_inferior", "limite_superior",
                   "nivel_intervalo", "definicion_tiempo", "model_id", "model_version",
                   "feature_version", "data_cutoff")
_ENTERAS = ("idruta", "franja_minutos", "horizonte_min", "model_id")
_FECHAS = ("franja_inicio", "data_cutoff")
_TEXTOS = ("sentido", "segmento_id", "definicion_tiempo", "model_version", "feature_version")
_CENTAVO = Decimal("0.01")
_MAXIMO = {"demanda_pred": Decimal("99999999.99"), "limite_inferior": Decimal("99999999.99"),
           "limite_superior": Decimal("99999999.99"), "nivel_intervalo": Decimal("9.99")}
_SEPARADOR = "\x1f"


def _decimal(valor, columna: str) -> Decimal:
    if valor is None or isinstance(valor, bool):
        raise ContratoInvalido(f"{columna}: valor no válido {valor!r}")
    if isinstance(valor, Decimal):
        d = valor
    else:
        try:
            x = float(valor)
        except (TypeError, ValueError) as e:
            raise ContratoInvalido(f"{columna}: valor no numérico {valor!r}") from e
        if not math.isfinite(x):
            raise ContratoInvalido(f"{columna}: valor no finito {valor!r}")
        d = Decimal(repr(x))       # repr: el decimal más corto que representa el float
    if not d.is_finite():
        raise ContratoInvalido(f"{columna}: valor no finito {valor!r}")
    d = d.quantize(_CENTAVO, rounding=ROUND_HALF_UP) + Decimal("0.00")   # + 0.00 convierte -0.00 en 0.00
    if abs(d) > _MAXIMO[columna]:
        raise ContratoInvalido(f"{columna}: {d} no cabe en la columna de la base")
    return d


def _fecha(valor, columna: str) -> pd.Timestamp:
    if valor is None or (not isinstance(valor, str) and pd.isna(valor)):
        raise ContratoInvalido(f"{columna}: fecha nula")
    t = pd.Timestamp(valor)
    if t.tzinfo is not None:
        t = t.tz_convert(ZONA).tz_localize(None)
    if t != t.floor("s"):
        raise ContratoInvalido(f"{columna}: la fecha {t} tiene fracciones de segundo")
    return t


def _entero(valor, columna: str) -> int:
    if valor is None or isinstance(valor, bool) or (not isinstance(valor, str) and pd.isna(valor)):
        raise ContratoInvalido(f"{columna}: entero nulo")
    x = float(valor)
    if not x.is_integer():
        raise ContratoInvalido(f"{columna}: {valor!r} no es entero")
    return int(x)


def _texto(valor, columna: str) -> str:
    if not isinstance(valor, str):
        raise ContratoInvalido(f"{columna}: se esperaba texto y llegó {valor!r}")
    if _SEPARADOR in valor or "\n" in valor:
        raise ContratoInvalido(f"{columna}: el texto contiene un separador de la huella")
    return valor


def normalizar_predicciones(df: pd.DataFrame) -> pd.DataFrame:
    """Copia de df con los valores EXACTOS que se guardan en prediction (y sobre los que se calcula
    la huella). Lanza ContratoInvalido ante nulos, no finitos o valores que no caben en la base."""
    faltan = set(COLUMNAS_HUELLA) - set(df.columns)
    if faltan:
        raise ContratoInvalido(f"Faltan columnas para la huella: {sorted(faltan)}")
    out = df.copy()
    for c in _ENTERAS:
        out[c] = [_entero(v, c) for v in out[c]]
    for c in _FECHAS:
        out[c] = [_fecha(v, c) for v in out[c]]
    for c in _TEXTOS:
        out[c] = [_texto(v, c) for v in out[c]]
    for c in _MAXIMO:
        out[c] = pd.Series([_decimal(v, c) for v in out[c]], index=out.index, dtype=object)
    inf, pred, sup = out.limite_inferior, out.demanda_pred, out.limite_superior
    # El redondeo es monótono, así que esto no debería fallar; se comprueba igual.
    if not all(i <= p <= s for i, p, s in zip(inf, pred, sup, strict=True)):
        raise ContratoInvalido("después de redondear no se cumple limite_inferior <= demanda_pred <= limite_superior")
    if any(p < 0 for p in pred):
        raise ContratoInvalido("demanda_pred negativa")
    for t in out.franja_inicio:
        if t != t.floor(f"{FRANJA_MIN}min"):
            raise ContratoInvalido(f"franja_inicio {t} no cae en múltiplos de {FRANJA_MIN} minutos")
    if out.duplicated(CLAVE_PREDICCION).any():
        raise ContratoInvalido("filas duplicadas para la clave única (ruta, sentido, segmento, franja, horizonte)")
    return out


def _linea(campos) -> str:
    return _SEPARADOR.join(campos)


def huella_predicciones(normalizadas: pd.DataFrame, dia, idrutas, horizontes) -> str:
    """SHA-256 (hex) del contenido de una ejecución de predicción. `normalizadas` debe venir de
    normalizar_predicciones(); `dia`, `idrutas` y `horizontes` son los de la solicitud."""
    if normalizadas.empty:
        raise ContratoInvalido("no hay predicciones para calcular la huella")
    for c in _MAXIMO:
        if not all(isinstance(v, Decimal) for v in normalizadas[c]):
            raise ContratoInvalido("huella_predicciones necesita el resultado de normalizar_predicciones()")
    dia_txt = _fecha(pd.Timestamp(dia).normalize(), "dia").strftime("%Y-%m-%d")
    solicitud = _linea(["solicitud", dia_txt,
                        ",".join(str(_entero(r, "idrutas")) for r in sorted(set(idrutas))),
                        ",".join(str(_entero(h, "horizontes")) for h in sorted(set(horizontes)))])
    filas = []
    for r in normalizadas[list(COLUMNAS_HUELLA)].itertuples(index=False):
        d = r._asdict()
        campos = []
        for c in COLUMNAS_HUELLA:
            v = d[c]
            if c in _FECHAS:
                campos.append(v.strftime("%Y-%m-%dT%H:%M:%S"))
            elif c in _MAXIMO:
                campos.append(format(v, "f"))
            else:
                campos.append(str(v))
        orden = (d["idruta"], d["sentido"], d["segmento_id"], campos[COLUMNAS_HUELLA.index("franja_inicio")],
                 d["horizonte_min"], d["model_id"])
        filas.append((orden, _linea(campos)))
    texto = "\n".join([FORMATO_HUELLA, solicitud] + [linea for _, linea in sorted(filas)])
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def validar_recomendaciones(df: pd.DataFrame) -> pd.DataFrame:
    faltan = set(COLUMNAS_RECOMENDACION) - set(df.columns)
    if faltan:
        raise ContratoInvalido(f"Faltan columnas en recommendation: {sorted(faltan)}")
    sin_motivo = (~df["es_viable"]) & df["motivo_no_viable"].isna()
    if sin_motivo.any():
        raise ContratoInvalido("toda recomendación no viable necesita motivo_no_viable")
    return df
