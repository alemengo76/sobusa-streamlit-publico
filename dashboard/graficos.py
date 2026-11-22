"""Gráficas del tablero como especificaciones Vega-Lite (``st.vega_lite_chart``; viene con Streamlit,
sin dependencias nuevas). Reproducen las gráficas de la maqueta v2 con los datos reales de la API.

Las horas se convierten a America/Bogota (UTC-5, sin horario de verano) aquí y se pasan como texto,
para que el navegador no las desplace a su propia zona horaria. Ningún valor faltante se convierte
en 0: las filas sin dato se omiten de la marca correspondiente y se cuentan aparte.
"""
from __future__ import annotations

import math
from datetime import timedelta, timezone
from decimal import Decimal

import pandas as pd

try:                                   # pytest y python -m importan el paquete dashboard
    from dashboard import estilo as es
except ModuleNotFoundError:            # streamlit run agrega dashboard/ a sys.path, no la raíz
    import estilo as es

BOGOTA = timezone(timedelta(hours=-5))
FUENTE = "IBM Plex Sans, system-ui, sans-serif"
CONFIG = {"axis": {"labelColor": es.TER, "titleColor": es.SEC, "gridColor": "#E9ECE7", "gridDash": [2, 4],
                   "domain": False, "ticks": False, "labelPadding": 8, "titlePadding": 10,
                   "labelFont": FUENTE, "titleFont": FUENTE, "labelFontSize": 11, "titleFontSize": 11,
                   "titleFontWeight": 500},
          "axisX": {"grid": False, "domain": True, "domainColor": "#DADFD8"},
          "legend": {"labelFont": FUENTE, "titleFont": FUENTE, "orient": "bottom"},
          "view": {"stroke": None}, "font": FUENTE, "background": "#FFFFFF", "padding": {"top": 14, "left": 4,
                                                                                       "right": 8, "bottom": 4},
          "bar": {"discreteBandSize": {"band": 0.62}}}

# Relleno degradado de la banda de incertidumbre (más intenso arriba, se desvanece hacia abajo).
DEGRADADO = {"gradient": "linear", "x1": 1, "y1": 1, "x2": 1, "y2": 0,
             "stops": [{"offset": 0, "color": "#FFFFFF"}, {"offset": 1, "color": es.VT2}]}


def _f(x):
    """Número JSON o None (nunca NaN/inf, nunca 0 inventado)."""
    if x is None:
        return None
    if isinstance(x, Decimal):
        x = float(x) if x.is_finite() else None
        return x
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else v


def horas_locales(serie) -> pd.Series:
    """ISO con desplazamiento -> Timestamp en hora de Bogotá."""
    t = pd.to_datetime(pd.Series(list(serie)), utc=True, errors="coerce")
    return t.dt.tz_convert(BOGOTA)


def etiqueta_franja(t: pd.Series) -> pd.Series:
    """«HH:MM» si todo es del mismo día; si no, «MM-DD HH:MM»."""
    dias = t.dt.strftime("%Y-%m-%d").nunique()
    return t.dt.strftime("%H:%M" if dias <= 1 else "%m-%d %H:%M")


def demanda(filas: list[dict], horizonte: int | None) -> dict:
    """Predicción (línea) e intervalo (banda) por franja, con pico y valle marcados."""
    df = pd.DataFrame(filas)
    t = horas_locales(df["franja_inicio"])
    datos = pd.DataFrame({"t": t, "franja": etiqueta_franja(t),
                          "pred": [_f(x) for x in df["demanda_pred"]],
                          "inf": [_f(x) for x in df["limite_inferior"]],
                          "sup": [_f(x) for x in df["limite_superior"]]}).sort_values("t")
    datos["orden"] = range(len(datos))
    datos["marca"] = None
    validos = datos.dropna(subset=["pred"])
    if len(validos) >= 3:
        datos.loc[validos["pred"].idxmax(), "marca"] = "Pico"
        datos.loc[validos["pred"].idxmin(), "marca"] = "Valle"
    valores = datos.drop(columns="t").astype(object).where(datos.drop(columns="t").notna(), None)
    valores = valores.to_dict("records")
    titulo_y = f"pasajeros en {horizonte} min" if horizonte else "pasajeros"
    x = {"field": "franja", "type": "ordinal", "sort": {"field": "orden"}, "title": None,
         "axis": {"labelAngle": 0, "labelOverlap": True}}
    tooltip = [{"field": "franja", "title": "Franja"},
               {"field": "pred", "title": "Predicción", "format": ",.2f"},
               {"field": "inf", "title": "Límite inferior", "format": ",.2f"},
               {"field": "sup", "title": "Límite superior", "format": ",.2f"}]
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json", "height": 260, "config": CONFIG,
        "data": {"values": valores},
        "layer": [
            {"mark": {"type": "area", "color": DEGRADADO, "opacity": 0.7, "interpolate": "monotone"},
             "encoding": {"x": x, "y": {"field": "inf", "type": "quantitative", "title": titulo_y},
                          "y2": {"field": "sup"}, "tooltip": tooltip}},
            {"mark": {"type": "line", "color": es.VERDE, "strokeWidth": 2.6, "interpolate": "monotone",
                      "strokeCap": "round"},
             "encoding": {"x": x, "y": {"field": "pred", "type": "quantitative"}, "tooltip": tooltip}},
            {"transform": [{"filter": "datum.marca != null"}],
             "mark": {"type": "point", "filled": True, "fill": "#fff", "stroke": es.VERDE, "strokeWidth": 2,
                      "size": 70},
             "encoding": {"x": x, "y": {"field": "pred", "type": "quantitative"}}},
            {"transform": [{"filter": "datum.marca != null"}],
             "mark": {"type": "text", "dy": -14, "fontWeight": 600, "color": es.TINTA},
             "encoding": {"x": x, "y": {"field": "pred", "type": "quantitative"},
                          "text": {"field": "marca"}}},
        ]}


def frecuencia(filas: list[dict], seleccion: object = None) -> dict:
    """Buses/hora recomendados (barras) frente a la frecuencia actual (escalones). Las franjas no viables
    se marcan en coral a toda la altura: la API no guarda buses/hora para ellas y aquí no se calculan."""
    df = pd.DataFrame(filas)
    t = horas_locales(df["franja_inicio"])
    datos = pd.DataFrame({
        "t": t, "franja": etiqueta_franja(t), "id": df.get("recommendation_id"),
        "rec": [_f(x) for x in df["buses_hora_recomendado"]],
        "act": [_f(x) for x in df.get("buses_hora_actual", pd.Series([None] * len(df)))],
        "viable": [bool(x) if x is not None else None for x in df["es_viable"]],
        "motivo": df.get("motivo_no_viable")}).sort_values("t")
    datos["orden"] = range(len(datos))
    datos["sel"] = datos["id"].astype(object) == seleccion if seleccion is not None else False
    techo = max([v for v in list(datos["rec"]) + list(datos["act"]) if v is not None] or [1]) * 1.15
    datos["techo"] = techo
    registros = datos.drop(columns="t").astype(object).where(datos.drop(columns="t").notna(), None)
    registros = registros.to_dict("records")
    x = {"field": "franja", "type": "ordinal", "sort": {"field": "orden"}, "title": None,
         "axis": {"labelAngle": 0, "labelOverlap": True}}
    tip = [{"field": "franja", "title": "Franja"}, {"field": "act", "title": "Actual (bus/h)"},
           {"field": "rec", "title": "Recomendada (bus/h)"}, {"field": "motivo", "title": "Motivo no viable"}]
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json", "height": 230, "config": CONFIG,
        "data": {"values": registros},
        "layer": [
            {"transform": [{"filter": "datum.viable === false"}],
             "mark": {"type": "bar", "color": es.CO2, "opacity": 0.85, "cornerRadiusTopLeft": 6,
                      "cornerRadiusTopRight": 6},
             "encoding": {"x": x, "y": {"field": "techo", "type": "quantitative", "title": "buses por hora"},
                          "tooltip": tip}},
            {"transform": [{"filter": "datum.viable === true && datum.rec != null"}],
             "mark": {"type": "bar", "cornerRadiusTopLeft": 6, "cornerRadiusTopRight": 6},
             "encoding": {"x": x, "y": {"field": "rec", "type": "quantitative"},
                          "color": {"condition": {"test": "datum.sel", "value": es.VERDE}, "value": es.VT2},
                          "tooltip": tip}},
            {"transform": [{"filter": "datum.act != null"}],
             "mark": {"type": "line", "interpolate": "step-after", "color": es.ACERO, "strokeWidth": 2.4, "strokeDash": [6, 3]},
             "encoding": {"x": x, "y": {"field": "act", "type": "quantitative"}, "tooltip": tip}},
        ]}


def anillo(partes: list[tuple[str, int, str]], centro: str, sub: str) -> dict:
    """Gráfico de anillo con el total en el centro (como «Viabilidad y cambios» y «Alertas por estado»)."""
    valores = [{"nombre": n, "valor": v, "color": c} for n, v, c in partes if v]
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json", "height": 210, "config": CONFIG,
        "layer": [
            {"data": {"values": valores},
             "mark": {"type": "arc", "innerRadius": 62, "outerRadius": 88, "padAngle": 0.025, "cornerRadius": 5},
             "encoding": {"theta": {"field": "valor", "type": "quantitative"},
                          "color": {"field": "nombre", "type": "nominal", "legend": None,
                                    "scale": {"domain": [v["nombre"] for v in valores],
                                              "range": [v["color"] for v in valores]}},
                          "tooltip": [{"field": "nombre", "title": "Grupo"},
                                      {"field": "valor", "title": "Cantidad"}]}},
            {"data": {"values": [{"t": centro}]},
             "mark": {"type": "text", "fontSize": 28, "fontWeight": 700, "dy": -6, "color": es.TINTA},
             "encoding": {"text": {"field": "t"}}},
            {"data": {"values": [{"t": sub}]},
             "mark": {"type": "text", "fontSize": 13, "fontWeight": 600, "dy": 18, "color": es.TINTA},
             "encoding": {"text": {"field": "t"}}},
        ], "view": {"stroke": None}}


def mapa_calor(filas: list[dict], metrica: str, es_porcentaje: bool) -> dict:
    """Ruta × horizonte de una métrica de M1 (un solo modelo). Más oscuro = más error."""
    valores = [{"ruta": f"{f.get('idruta')} · {f.get('nombre_ruta', '')}".strip(" ·"),
                "horizonte": f"{f.get('horizonte_min')} min", "h": f.get("horizonte_min"),
                "valor": _f(f.get(metrica)), "n": f.get("n_validas")} for f in filas]
    presentes = [v["valor"] for v in valores if v["valor"] is not None]
    umbral = (min(presentes) + 0.55 * (max(presentes) - min(presentes))) if presentes else 0
    for v in valores:
        v["oscuro"] = v["valor"] is not None and len(presentes) > 1 and v["valor"] > umbral
    formato = ".2%" if es_porcentaje else ",.1f"
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json", "height": 210, "config": CONFIG,
        "data": {"values": valores},
        "encoding": {"x": {"field": "horizonte", "type": "ordinal", "sort": {"field": "h"}, "title": None,
                           "axis": {"orient": "top", "labelAngle": 0}},
                     "y": {"field": "ruta", "type": "ordinal", "title": None}},
        "layer": [
            {"mark": {"type": "rect", "cornerRadius": 7, "stroke": "#fff", "strokeWidth": 3},
             "encoding": {"color": {"field": "valor", "type": "quantitative", "legend": None,
                                    "scale": {"range": ["#EAF1F5", "#2C5670"]}},
                          "tooltip": [{"field": "ruta", "title": "Ruta"}, {"field": "horizonte", "title": "Horizonte"},
                                      {"field": "valor", "title": metrica.upper(), "format": formato},
                                      {"field": "n", "title": "Observaciones válidas"}]}},
            {"transform": [{"filter": "datum.valor != null"}],
             "mark": {"type": "text", "fontWeight": 700, "fontSize": 13},
             "encoding": {"text": {"field": "valor", "type": "quantitative", "format": formato},
                          "color": {"condition": {"test": "datum.oscuro", "value": "#fff"},
                                    "value": es.TINTA}}},
        ]}


def barras_horizontales(filas: list[dict], campo: str, etiqueta: str, titulo: str, *,
                        divergente: bool = False, formato: str = ",.3f") -> dict:
    """Barras horizontales ordenadas (importancia global, aportes TreeSHAP)."""
    valores = [{"etq": str(f.get(etiqueta)), "valor": _f(f.get(campo))} for f in filas
               if _f(f.get(campo)) is not None]
    color = ({"condition": {"test": "datum.valor < 0", "value": es.ACERO}, "value": es.VERDE}
             if divergente else {"value": es.AT2})
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json", "config": CONFIG,
        "height": {"step": 22}, "data": {"values": valores},
        "encoding": {"y": {"field": "etq", "type": "nominal", "sort": "-x" if not divergente else None,
                           "title": None},
                     "x": {"field": "valor", "type": "quantitative", "title": titulo}},
        "layer": [{"mark": {"type": "bar", "cornerRadiusEnd": 5},
                   "encoding": {"color": color,
                                "tooltip": [{"field": "etq", "title": "Variable"},
                                            {"field": "valor", "title": titulo, "format": formato}]}}],
    }
