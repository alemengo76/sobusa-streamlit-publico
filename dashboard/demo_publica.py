"""Inferencia y planificación en memoria con datos exclusivamente sintéticos."""
from dataclasses import dataclass
from datetime import date, timedelta, timezone
from uuid import uuid4

if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from app.alertas.motor import alt_001, alt_002_003_004, umbrales_por_defecto
from app.optimizacion.frecuencias import ParametrosRuta, recomendar_fila

RUTAS = (2, 16, 21)
HORIZONTES = (30, 60, 120)
BOGOTA = timezone(timedelta(hours=-5))
SEMILLA = 20261121
VERSION = "regresion-sintetica-v1"
PARAMETROS = {
    ruta: ParametrosRuta(ruta, 44, 0.75, ciclo, 0.55, "sintetica", flota, 4,
                         parametros_version="demo-v1")
    for ruta, ciclo, flota in ((2, 90, 8), (16, 105, 10), (21, 115, 9))
}


def caracteristicas(dia: date, minutos: np.ndarray) -> np.ndarray:
    hora = minutos / 60
    fin_semana = dia.weekday() >= 5
    fase = 2 * np.pi * (dia.timetuple().tm_yday - 1) / 365.25
    manana = np.exp(-((hora - 7.5) / 1.7) ** 2)
    tarde = np.exp(-((hora - 17.5) / 2.1) ** 2)
    return np.column_stack([
        np.ones(len(hora)), manana, tarde,
        np.full(len(hora), fin_semana), manana * fin_semana, tarde * fin_semana,
        np.full(len(hora), np.sin(fase)), np.full(len(hora), np.cos(fase)),
    ])


def entrenar() -> dict[int, np.ndarray]:
    """Ajuste por mínimos cuadrados sobre conteos Poisson generados localmente."""
    rng = np.random.default_rng(SEMILLA)
    origen = date(2024, 1, 1)
    minutos = np.arange(5 * 60, 22 * 60, 15)
    x = np.concatenate([caracteristicas(origen + timedelta(days=i), minutos)
                        for i in range(366)])
    modelos = {}
    for indice, ruta in enumerate(RUTAS):
        media = x @ np.array([13 + 3 * indice, 62 + 5 * indice, 52 + 7 * indice,
                             -4, -23, -19, 3, 2])
        pesos = np.linalg.lstsq(x, rng.poisson(media), rcond=None)[0]
        pesos.setflags(write=False)
        modelos[ruta] = pesos
    return modelos


@dataclass
class Despacho:
    ejecucion: str
    ruta: int
    dia: date
    horizonte: int
    predicciones: list[dict]
    recomendaciones: list[dict]
    alertas: list[dict]


def predecir(modelos: dict[int, np.ndarray], ruta: int, dia: date, horizonte: int,
             oferta: int) -> Despacho:
    if ruta not in RUTAS or horizonte not in HORIZONTES or not 1 <= oferta <= 30:
        raise ValueError("Ruta, horizonte u oferta fuera del rango de la demostración.")

    inicio = pd.Timestamp(dia, tz=BOGOTA)
    minutos = np.arange(5 * 60, 22 * 60, 15)
    x = caracteristicas(dia, minutos)
    pesos = modelos[ruta]
    demanda = (x @ pesos).clip(min=0)
    # Referencia sintética del propio modelo sin el efecto estacional anual.
    normal = (x[:, :6] @ pesos[:6]).clip(min=0)
    pasos = horizonte // 15
    ventana = np.ones(pasos)
    total = np.convolve(demanda, ventana, mode="valid")
    referencia = np.convolve(normal, ventana, mode="valid")

    eid = uuid4().hex
    predicciones = []
    recomendaciones = []
    for i, valor in enumerate(total):
        clave = dict(execution_id=eid, prediction_id=f"{eid}-{i + 1}", idruta=ruta,
                     horizonte_min=horizonte,
                     franja_inicio=(inicio + pd.Timedelta(minutes=int(minutos[i]))).isoformat())
        puntual = round(float(valor), 2)
        predicciones.append(dict(clave, demanda_pred=puntual, model_version=VERSION,
                                  limite_inferior=None, limite_superior=None,
                                  demanda_referencia=float(referencia[i])))
        sugerencia = recomendar_fila(puntual, horizonte, PARAMETROS[ruta], oferta)
        recomendaciones.append(dict(clave, recommendation_id=f"{eid}-r{i + 1}", **sugerencia))

    umbrales = umbrales_por_defecto()
    alertas = alt_001(pd.DataFrame(predicciones), umbrales)
    alertas += alt_002_003_004(pd.DataFrame(recomendaciones), umbrales)
    return Despacho(eid, ruta, dia, horizonte, predicciones, recomendaciones, alertas)


if __name__ == "__main__":
    import runpy

    runpy.run_path(str(Path(__file__).with_name("publico.py")))
