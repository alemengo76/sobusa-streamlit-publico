"""Feature engineering v3 (sobusa-fe-3.0): conjunto de entrenamiento sin fuga temporal.

Uso, después de reglas_comunes:

    from conjunto_entrenamiento import construir_conjunto, diccionario_variables, VARIABLES
    X = construir_conjunto(P, cal, dias, hor)
    entrenamiento = X[X.habilitada_supervisada & X.particion.eq("entrenamiento")]

SUPUESTO DE DISPONIBILIDAD (se declara y se hace cumplir en el código):
    Todo lo ocurrido el día D está disponible desde las 00:00 del día D+1.
    Una variable calculada para un origen t solo usa ventanas que terminan, a más tardar,
    a la medianoche del día de t. Las pruebas lo verifican perturbando el día de t.

Por qué la oferta entra con rezago: los despachos se registran con una mediana de 11 a 15
minutos antes de la salida (0,1 % se conoce con 120 min de anticipación), así que las salidas
de la ventana [t, t+H) no se conocen en t. Se usan las salidas de la misma ventana ayer y
hace una semana.
"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from dateutil.easter import easter

from reglas_comunes import etiqueta_operativa

VERSION = "sobusa-fe-3.1"
REZAGOS_DIAS = (1, 7, 14, 21)
CORTES = {"validacion_desde": "2025-01-01", "prueba_desde": "2025-07-01"}

# Periodos de vacaciones escolares APROXIMADOS (calendario A, Atlántico). La Semana Santa se
# calcula exacta; el resto debe reemplazarse con el calendario oficial de cada año.
VACACIONES = {
    "mitad_anio": ("06-15", "07-15"),
    "fin_anio": ("12-01", "01-25"),     # cruza de año: diciembre de un año a enero del siguiente
}

CALENDARIO = ["hora", "minuto", "dia_semana_iso", "mes", "es_fin_semana",
              "hora_sin", "hora_cos", "semana_sin", "semana_cos", "mes_sin", "mes_cos"]
CONTEXTO = ["id_ruta", "horizonte_min", "tipo_dia", "marca_calendario",
            "es_vispera_festivo", "es_post_festivo", "vacaciones_escolares"]
HISTORIA = [f"y_rezago_{d}d" for d in REZAGOS_DIAS] + ["y_media_4_semanas", "y_n_4_semanas"]
OFERTA = ["salidas_rezago_1d", "salidas_rezago_7d", "pax_por_viaje_rezago_7d"]
NIVEL = ["nivel_diario_28d", "nivel_diario_7d"]
VARIABLES = CONTEXTO + CALENDARIO + HISTORIA + OFERTA + NIVEL
CATEGORICAS = ["id_ruta", "tipo_dia", "marca_calendario"]


# ---------------------------------------------------------------------------
# Calendario
# ---------------------------------------------------------------------------
def marcas_dia(cal: pd.DataFrame, vacaciones: dict = VACACIONES) -> pd.DataFrame:
    """Víspera y día posterior a festivo, y vacaciones escolares, por fecha."""
    c = cal[["fecha", "festivo", "marca_calendario", "tipo_dia"]].copy().sort_values("fecha")
    es_fest = c.festivo.notna()
    fest = set(c.fecha[es_fest])
    c["es_vispera_festivo"] = (c.fecha + pd.Timedelta(days=1)).isin(fest) & ~es_fest
    c["es_post_festivo"] = (c.fecha - pd.Timedelta(days=1)).isin(fest) & ~es_fest

    vac = pd.Series(False, index=c.index)
    for a in range(c.fecha.dt.year.min() - 1, c.fecha.dt.year.max() + 1):
        e = pd.Timestamp(easter(a))
        vac |= c.fecha.between(e - pd.Timedelta(days=7), e)                       # Semana Santa
        oct12 = pd.Timestamp(a, 10, 12)
        lunes = oct12 + pd.Timedelta(days=(7 - oct12.dayofweek) % 7)            # festivo de la Raza
        vac |= c.fecha.between(lunes, lunes + pd.Timedelta(days=6))              # receso de octubre
        for nombre, (ini, fin) in vacaciones.items():
            i = pd.Timestamp(f"{a}-{ini}")
            f = pd.Timestamp(f"{a + 1 if fin < ini else a}-{fin}")
            vac |= c.fecha.between(i, f)
    c["vacaciones_escolares"] = vac
    return c[["fecha", "es_vispera_festivo", "es_post_festivo", "vacaciones_escolares"]]


def variables_calendario(origen: pd.Series) -> pd.DataFrame:
    t = pd.DatetimeIndex(origen)
    x = pd.DataFrame(index=origen.index)
    x["hora"], x["minuto"] = t.hour, t.minute
    x["dia_semana_iso"], x["mes"] = t.dayofweek + 1, t.month
    x["es_fin_semana"] = (t.dayofweek >= 5).astype(int)
    ang = 2 * np.pi * (t.hour * 60 + t.minute) / 1440
    x["hora_sin"], x["hora_cos"] = np.sin(ang), np.cos(ang)
    ang = 2 * np.pi * t.dayofweek / 7
    x["semana_sin"], x["semana_cos"] = np.sin(ang), np.cos(ang)
    ang = 2 * np.pi * (t.month - 1) / 12
    x["mes_sin"], x["mes_cos"] = np.sin(ang), np.cos(ang)
    return x


# ---------------------------------------------------------------------------
# Historia, oferta y nivel (todas con rezago seguro)
# ---------------------------------------------------------------------------
def _rezago_seguro(valores: pd.Series, claves: pd.DataFrame, dias: int) -> np.ndarray:
    """Valor de la misma (ruta, H) en origen - dias, solo si esa ventana terminó antes de la
    medianoche del día del origen. valores está indexado por (id_ruta, horizonte_min, origen)."""
    o = claves.origen - pd.Timedelta(days=dias)
    fin = o + pd.to_timedelta(claves.horizonte_min, unit="min")
    idx = pd.MultiIndex.from_arrays([claves.id_ruta, claves.horizonte_min, o])
    v = valores.reindex(idx).to_numpy(dtype="float64", copy=True)
    v[(fin > claves.origen.dt.normalize()).to_numpy()] = np.nan
    return v


def salidas_por_ventana(P: pd.DataFrame, origenes: pd.DataFrame, dias: pd.DataFrame,
                        paso: int = 15) -> pd.Series:
    """Salidas elegibles en [t, t+H) para cada (ruta, H, origen). Es la oferta REAL de la ventana:
    no se conoce en t, solo se usa a través de rezagos.

    Dentro de los días con datos, una franja sin salidas aporta 0. Fuera del periodo con datos
    o en días sin datos, el valor queda NA: no se sabe cuántas salidas hubo.
    """
    x = P.loc[P.elegible].assign(franja=lambda d: d.salida_programada.dt.floor(f"{paso}min"))
    g = x.groupby(["id_ruta", "franja"]).size()
    out = []
    for (r, H), o in origenes.groupby(["id_ruta", "horizonte_min"]):
        d = dias.loc[dias.id_ruta.eq(r)]
        con_datos = set(d.fecha[d.clase_dia.ne("sin_datos")])
        idx = pd.date_range(d.fecha.min(), d.fecha.max() + pd.Timedelta(days=1), freq=f"{paso}min", inclusive="left")
        s = (g.loc[r] if r in g.index.get_level_values(0) else pd.Series(dtype=float)).reindex(idx, fill_value=0)
        s = s.astype("float64").where(idx.normalize().isin(con_datos))
        k = int(H) // paso
        adelante = s[::-1].rolling(k, min_periods=k).sum()[::-1]
        out.append(pd.Series(adelante.to_numpy(), index=pd.MultiIndex.from_arrays(
            [np.repeat(r, len(idx)), np.repeat(H, len(idx)), idx], names=["id_ruta", "horizonte_min", "origen"])))
    return pd.concat(out)


def nivel_diario(dias: pd.DataFrame) -> pd.DataFrame:
    """Mediana de pasajeros por día en los 28 y 7 días ANTERIORES (sin incluir el día).

    Solo excluye días sin datos o de baja calidad, que se deciden con información del propio día.
    No excluye los anómalos: su detección compara con la media del año entero (incluye el futuro)
    y usarla aquí sería fuga. La mediana amortigua esos días.
    """
    d = dias[["id_ruta", "fecha", "pax", "clase_dia"]].sort_values(["id_ruta", "fecha"]).copy()
    d["pax_ok"] = d.pax.where(~d.clase_dia.isin(["sin_datos", "baja_calidad"]))
    g = d.groupby("id_ruta").pax_ok
    d["nivel_diario_28d"] = g.transform(lambda s: s.shift(1).rolling(28, min_periods=14).median())
    d["nivel_diario_7d"] = g.transform(lambda s: s.shift(1).rolling(7, min_periods=4).median())
    return d[["id_ruta", "fecha", "nivel_diario_28d", "nivel_diario_7d"]]


# ---------------------------------------------------------------------------
# Particiones
# ---------------------------------------------------------------------------
def particionar(origen: pd.Series, horizonte: pd.Series, cortes: dict = CORTES) -> pd.DataFrame:
    v, p = pd.Timestamp(cortes["validacion_desde"]), pd.Timestamp(cortes["prueba_desde"])
    """Cortes cronológicos. Se purga la fila cuya ventana [t, t+H) termina después del inicio
    del bloque siguiente (terminar justo en el corte es válido)."""
    fin = origen + pd.to_timedelta(horizonte, unit="min")
    part = pd.Series(np.select([origen < v, origen < p], ["entrenamiento", "validacion"], default="prueba"),
                     index=origen.index)
    purga = (part.eq("entrenamiento") & (fin > v)) | (part.eq("validacion") & (fin > p))
    return pd.DataFrame({"particion": part, "purga_por_ventana": purga})


# ---------------------------------------------------------------------------
# Conjunto completo
# ---------------------------------------------------------------------------
def construir_conjunto(P: pd.DataFrame, cal: pd.DataFrame, dias: pd.DataFrame, hor: pd.DataFrame,
                       cortes: dict = CORTES, vacaciones: dict = VACACIONES) -> pd.DataFrame:
    """Una fila por (ruta, origen operativo de día completo, horizonte).

    Las filas salen de la etiqueta operativa (días completos, franjas operativas). Los rezagos salen
    de una segunda etiqueta que (1) incluye los días anómalos, porque qué días son anómalos se decide
    con la media del año completo y dejar que eso decida qué rezago existe sería usar el futuro, y
    (2) cubre todas las franjas del día, porque fuera del horario la oferta es 0, no un faltante.
    """
    Y = etiqueta_operativa(P, cal, dias, hor)
    # Etiqueta para rezagos (v3.1): todas las franjas de los días completos, no solo las operativas
    # del tipo de día. Fuera del horario, una franja sin salidas suma 0: es un dato, no un faltante.
    # Sin esto, el lunes 04:30 no encontraba rezago en el domingo 04:30 (franja no operativa).
    dias_hist = dias.assign(clase_dia=dias.clase_dia.replace({"anomalo": "completo"}))
    Y_hist = etiqueta_operativa(P, cal, dias_hist, hor.assign(operativa=True))
    X = Y[["id_ruta", "origen", "horizonte_min", "tipo_dia", "y_pasajeros", "estado_etiqueta"]].copy()
    X = X.sort_values(["id_ruta", "horizonte_min", "origen"]).reset_index(drop=True)
    X["fecha"] = X.origen.dt.normalize()

    X = X.merge(cal[["fecha", "marca_calendario"]], on="fecha", how="left")
    X = X.merge(marcas_dia(cal, vacaciones), on="fecha", how="left")
    X = pd.concat([X, variables_calendario(X.origen)], axis=1)

    yv = Y_hist.set_index(["id_ruta", "horizonte_min", "origen"]).y_pasajeros
    for d in REZAGOS_DIAS:
        X[f"y_rezago_{d}d"] = _rezago_seguro(yv, X, d)
    sem = np.column_stack([_rezago_seguro(yv, X, d) for d in (7, 14, 21, 28)])
    X["y_n_4_semanas"] = np.isfinite(sem).sum(axis=1)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)   # filas sin ninguna semana: queda NA
        X["y_media_4_semanas"] = np.where(X.y_n_4_semanas >= 2, np.nanmean(sem, axis=1), np.nan)

    sal = salidas_por_ventana(P, X[["id_ruta", "horizonte_min", "origen"]], dias)
    X["salidas_rezago_1d"] = _rezago_seguro(sal, X, 1)
    X["salidas_rezago_7d"] = _rezago_seguro(sal, X, 7)
    X["pax_por_viaje_rezago_7d"] = np.where(X.salidas_rezago_7d > 0, X.y_rezago_7d / X.salidas_rezago_7d, np.nan)

    X = X.merge(nivel_diario(dias), on=["id_ruta", "fecha"], how="left")
    X = pd.concat([X, particionar(X.origen, X.horizonte_min, cortes)], axis=1)
    X["etiqueta_completa"] = X.estado_etiqueta.eq("completa")
    X["habilitada_supervisada"] = X.etiqueta_completa & ~X.purga_por_ventana
    X["feature_version"] = VERSION
    for c in ["es_vispera_festivo", "es_post_festivo", "vacaciones_escolares"]:
        X[c] = X[c].fillna(False).astype(int)
    return X


def diccionario_variables() -> pd.DataFrame:
    """Contrato de variables: fórmula, disponibilidad en t y riesgo de fuga."""
    filas = []
    def fila(n, fam, formula, disp, riesgo="bajo"):
        filas.append({"variable": n, "familia": fam, "formula": formula, "disponible_en_t": disp,
                      "riesgo_fuga": riesgo, "feature_version": VERSION})
    for n in CALENDARIO:
        fila(n, "calendario", f"derivada de origen t ({n})", "siempre: calendario civil")
    fila("id_ruta", "contexto", "ruta del origen", "siempre")
    fila("horizonte_min", "contexto", "H en minutos (30, 60, 120)", "siempre")
    fila("tipo_dia", "contexto", "laboral / sabado / dom_festivo (festivos oficiales, Ley Emiliani)", "siempre")
    fila("marca_calendario", "contexto", "carnaval_lun_mar > festivo_profundo > festivo_comun > sabado_santo > fin_de_anio > normal", "siempre")
    fila("es_vispera_festivo", "contexto", "el día siguiente es festivo", "siempre")
    fila("es_post_festivo", "contexto", "el día anterior fue festivo", "siempre")
    fila("vacaciones_escolares", "contexto", "Semana Santa, receso de octubre (exactos) y mitad/fin de año (aproximados)", "siempre", "bajo; fechas aproximadas")
    for d in REZAGOS_DIAS:
        fila(f"y_rezago_{d}d", "historia", f"etiqueta de la misma ruta y H en t - {d} días", "solo si esa ventana terminó antes de las 00:00 del día de t")
    fila("y_media_4_semanas", "historia", "media de la etiqueta en t-7, t-14, t-21 y t-28 días (mínimo 2)", "ídem")
    fila("y_n_4_semanas", "historia", "cuántas de esas 4 semanas tienen etiqueta", "ídem")
    fila("salidas_rezago_1d", "oferta", "salidas elegibles en [t, t+H) de ayer", "ídem", "bajo; la oferta del mismo día NO se usa")
    fila("salidas_rezago_7d", "oferta", "salidas elegibles en [t, t+H) de hace 7 días", "ídem")
    fila("pax_por_viaje_rezago_7d", "oferta", "y_rezago_7d / salidas_rezago_7d", "ídem")
    fila("nivel_diario_28d", "nivel", "mediana de pasajeros por día en los 28 días anteriores, sin días de baja calidad (mínimo 14)", "desde las 00:00 del día de t")
    fila("nivel_diario_7d", "nivel", "ídem con 7 días (mínimo 4)", "desde las 00:00 del día de t")
    return pd.DataFrame(filas)
