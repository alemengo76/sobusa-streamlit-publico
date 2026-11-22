"""Motor de recomendación de frecuencias (especificación v1.5, con factor de carga).

Fórmulas:
    demanda_hora    = demanda_pred * 60 / horizonte_min          (subidas por hora)
    carga_max_hora  = demanda_hora * factor_carga_max            (carga a bordo máxima)
    cap_efectiva    = capacidad_nominal * ocupacion_objetivo
    buses_hora      = ceil(carga_max_hora / cap_efectiva)
    headway         = 60 / buses_hora
    vehiculos       = ceil(ciclo / headway)

Por qué el factor de carga: numeropasajeros es el total de subidas de un viaje de
ida y vuelta de ~4 h. La capacidad limita cuánta gente va a bordo AL MISMO TIEMPO.
Sin el factor, la fórmula sobreestima los buses unas 2 a 3 veces.
"""
from dataclasses import dataclass
import math

import pandas as pd

from app.ml import contrato


class ParametroInvalido(ValueError):
    pass


@dataclass(frozen=True)
class ParametrosRuta:
    idruta: int
    capacidad_nominal: float
    ocupacion_objetivo: float
    ciclo_min: float
    factor_carga_max: float
    capacidad_fuente: str = "derivado_plazas"
    flota_tope: int | None = None
    headway_minimo_min: float = 1.0
    buses_hora_minimo: int = 1
    parametros_version: str = "param_v1"

    def validar(self):
        if self.capacidad_nominal is None or self.capacidad_nominal <= 0:
            raise ParametroInvalido(
                f"Ruta {self.idruta}: la capacidad debe ser > 0 (recibido {self.capacidad_nominal})")
        if not 0.65 <= self.ocupacion_objetivo <= 0.85:
            raise ParametroInvalido(
                f"Ruta {self.idruta}: la ocupación objetivo debe estar entre 0,65 y 0,85")
        if self.ciclo_min <= 0:
            raise ParametroInvalido(f"Ruta {self.idruta}: el ciclo debe ser > 0")
        if not 0 < self.factor_carga_max <= 1:
            raise ParametroInvalido(f"Ruta {self.idruta}: el factor de carga debe estar en (0, 1]")
        return self


def recomendar_fila(demanda_pred: float, horizonte_min: int, p: ParametrosRuta,
                    buses_hora_actual: float | None = None) -> dict:
    p.validar()
    demanda_hora = demanda_pred * 60 / horizonte_min
    carga = demanda_hora * p.factor_carga_max
    cap_ef = p.capacidad_nominal * p.ocupacion_objetivo
    buses = max(p.buses_hora_minimo, math.ceil(round(carga / cap_ef, 9)))
    headway = 60 / buses
    vehiculos = math.ceil(round(p.ciclo_min / headway, 9))

    motivos = []
    if headway < p.headway_minimo_min:
        motivos.append(f"headway de {headway:.2f} min, menor al mínimo operable de "
                       f"{p.headway_minimo_min:.1f} min")
    if p.flota_tope is not None and vehiculos > p.flota_tope:
        motivos.append(f"requiere {vehiculos} vehículos y el tope de flota es {p.flota_tope}")
    viable = not motivos

    headway_actual = 60 / buses_hora_actual if buses_hora_actual else None
    return {
        "demanda_hora": round(demanda_hora, 2),
        "factor_carga_max": p.factor_carga_max,
        "carga_max_estimada_hora": round(carga, 2),
        "capacidad_nominal": p.capacidad_nominal,
        "capacidad_fuente": p.capacidad_fuente,
        "ocupacion_objetivo": p.ocupacion_objetivo,
        "capacidad_efectiva": round(cap_ef, 2),
        "buses_hora_recomendado": buses if viable else None,
        "headway_recomendado_min": round(headway, 2) if viable else None,
        "ciclo_min": p.ciclo_min,
        "vehiculos_requeridos": vehiculos,
        "flota_tope": p.flota_tope,
        "buses_hora_actual": buses_hora_actual,
        "headway_actual_min": round(headway_actual, 2) if headway_actual else None,
        "delta_buses_hora": (buses - buses_hora_actual)
        if (viable and buses_hora_actual is not None) else None,
        "es_viable": viable,
        "motivo_no_viable": "; ".join(motivos) if motivos else None,
        "parametros_version": p.parametros_version,
    }


def recomendar(predicciones: pd.DataFrame, parametros,
               frecuencia_actual: pd.DataFrame | None = None,
               base_demanda: str = "puntual") -> pd.DataFrame:
    """predicciones: contrato de prediction. frecuencia_actual (opcional):
    idruta, franja_inicio, buses_hora_actual (salidas observadas por hora, RF-008).

    parametros: TablaParametros (por ruta y tipo de día) o {idruta: ParametrosRuta} (= 'todos').
    Cada franja usa los parámetros de su ruta y del tipo de día de su fecha (E03); si esa
    combinación no existe, los de 'todos'. parametros_version queda como 'version:tipo_dia'
    para saber qué fila se usó."""
    from app.optimizacion.parametros import TablaParametros, tipo_dia_parametros

    if base_demanda not in ("puntual", "superior"):
        raise ValueError("base_demanda debe ser 'puntual' o 'superior'")
    tabla = TablaParametros.desde(parametros)
    col = "demanda_pred" if base_demanda == "puntual" else "limite_superior"
    pred = predicciones.copy()
    if frecuencia_actual is not None:
        pred = pred.merge(frecuencia_actual, on=["idruta", "franja_inicio"], how="left")
    else:
        pred["buses_hora_actual"] = None
    if "tipo_dia" not in pred.columns:
        pred["tipo_dia"] = tipo_dia_parametros(pred.franja_inicio).to_numpy()

    filas = []
    for r in pred.itertuples(index=False):
        p, tipo_usado = tabla.para(r.idruta, r.tipo_dia)
        actual = getattr(r, "buses_hora_actual", None)
        actual = None if actual is None or pd.isna(actual) else float(actual)
        fila = recomendar_fila(getattr(r, col), r.horizonte_min, p, actual)
        fila["parametros_version"] = f"{p.parametros_version}:{tipo_usado}"
        filas.append({"prediction_id": getattr(r, "prediction_id", None),
                      "idruta": r.idruta, "sentido": r.sentido, "segmento_id": r.segmento_id,
                      "franja_inicio": r.franja_inicio, "horizonte_min": r.horizonte_min,
                      "base_demanda": base_demanda, **fila})
    out = pd.DataFrame(filas, columns=contrato.COLUMNAS_RECOMENDACION)
    return contrato.validar_recomendaciones(out)


def frecuencia_observada(salidas: pd.DataFrame) -> pd.DataFrame:
    """Buses por hora observados (RF-008) a partir de progvehiculos.

    salidas: idruta, fechasalida (de viajes no cancelados). Devuelve, para cada franja
    de 15 min, las salidas en la hora que empieza en esa franja."""
    s = salidas.copy()
    s["franja_inicio"] = pd.to_datetime(s.fechasalida).dt.floor("15min")
    conteo = s.groupby(["idruta", "franja_inicio"]).size().rename("salidas")
    partes = []
    for idruta, g in conteo.groupby(level=0):
        g = g.droplevel(0)
        malla = pd.date_range(g.index.min(), g.index.max(), freq="15min")
        g = g.reindex(malla, fill_value=0)
        hora = sum(g.shift(-k, fill_value=0) for k in range(4))
        partes.append(pd.DataFrame({"idruta": idruta, "franja_inicio": malla,
                                    "buses_hora_actual": hora.to_numpy()}))
    return pd.concat(partes, ignore_index=True)
