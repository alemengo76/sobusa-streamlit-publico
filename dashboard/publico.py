"""Streamlit Community Cloud: interfaz de demostración exclusivamente sintética."""
import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

# Streamlit agrega el directorio de este archivo. Los módulos puros viven en la raíz.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard import demo_publica as demo
from dashboard import estilo as es
from dashboard import exportacion as ex
from dashboard import graficos as gr

os.environ.setdefault("SOBUSA_DEMO_MODE", "1")
st.set_page_config(page_title="SOBUSA · Demo pública", layout="wide")
if os.environ["SOBUSA_DEMO_MODE"] != "1":
    st.error("Este punto de entrada requiere SOBUSA_DEMO_MODE=1.")
    st.stop()

# Usar la misma identidad visual sin cargar fuentes externas.
st.markdown("\n".join(line for line in es.CSS.splitlines() if "@import url" not in line),
            unsafe_allow_html=True)

SECCIONES = ("Resumen", "Demanda y frecuencias", "Alertas", "Calidad de datos",
             "Evaluación (M1)", "Modelos y explicaciones")


@st.cache_resource(show_spinner=False)
def modelos():
    return demo.entrenar()


def descargas(filas, nombre):
    tabla = pd.DataFrame(filas)
    st.dataframe(tabla, width="stretch", hide_index=True)
    csv, xlsx = st.columns(2)
    csv.download_button("Descargar CSV", ex.a_csv(tabla), f"demo_{nombre}.csv",
                        mime="text/csv", key=f"{nombre}_csv")
    xlsx.download_button(
        "Descargar XLSX", ex.a_xlsx(tabla, {"origen": "SOBUSA · datos sintéticos"}),
        f"demo_{nombre}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"{nombre}_xlsx",
    )


with st.sidebar:
    st.markdown(es.logo_lateral(), unsafe_allow_html=True)
    seccion = st.radio("Sección", SECCIONES, index=1)

st.markdown(es.cabecera(seccion, [es.pildora(None, "Demo pública")]), unsafe_allow_html=True)
st.info("Datos y parámetros sintéticos. Los resultados no son pronósticos operativos de SOBUSA.")

if seccion == "Resumen":
    st.write("Selecciona una ruta, una fecha y un horizonte en Demanda y frecuencias. "
             "El modelo calcula abordajes para ventanas que comienzan cada 15 minutos. "
             "Los resultados permanecen en esta sesión.")
elif seccion == "Demanda y frecuencias":
    with st.form("predecir_demo"):
        a, b, c, d = st.columns(4)
        ruta = a.selectbox("Ruta", demo.RUTAS)
        dia = b.date_input("Fecha", date.today(), min_value=date(2020, 1, 1),
                           max_value=date(2100, 12, 31))
        horizonte = c.selectbox("Horizonte (min)", demo.HORIZONTES, index=1)
        oferta = d.number_input("Oferta simulada (buses/h)", min_value=1, max_value=30, value=5)
        calcular = st.form_submit_button("Predecir", type="primary")
    if calcular:
        st.session_state["despacho_demo"] = demo.predecir(modelos(), ruta, dia, horizonte, oferta)
    despacho = st.session_state.get("despacho_demo")
    if despacho:
        st.caption(f"Ruta {despacho.ruta} · {despacho.dia:%d/%m/%Y} · "
                   f"{despacho.horizonte} min · ejecución {despacho.ejecucion}")
        demanda, frecuencia = st.tabs(["Predicciones", "Recomendaciones"])
        with demanda:
            st.vega_lite_chart(gr.demanda(despacho.predicciones, despacho.horizonte),
                               width="stretch", theme=None)
            descargas(despacho.predicciones, "predicciones")
        with frecuencia:
            st.caption("La oferta de referencia y los límites de capacidad y flota son sintéticos.")
            st.vega_lite_chart(gr.frecuencia(despacho.recomendaciones), width="stretch", theme=None)
            descargas(despacho.recomendaciones, "recomendaciones")
elif seccion == "Alertas":
    st.caption("Reglas ALT-001/002/003/004 sobre la última ejecución sintética de la sesión. "
               "ALT-002/003/004 se evalúan a 60 minutos.")
    despacho = st.session_state.get("despacho_demo")
    if despacho is None:
        st.info("Calcula un pronóstico primero.")
    elif despacho.alertas:
        st.caption(f"Ruta {despacho.ruta} · {despacho.dia:%d/%m/%Y} · {despacho.horizonte} min")
        descargas(despacho.alertas, "alertas")
    else:
        st.info("Las reglas aplicables no detectaron alertas en esta ejecución.")
elif seccion == "Calidad de datos":
    st.info("G3 requiere ingestiones y sus eventos. La demostración no consulta registros de calidad.")
elif seccion == "Evaluación (M1)":
    st.info("M1 requiere observaciones reales y evidencia de completitud. La demostración no calcula precisión.")
else:
    st.write(f"**{demo.VERSION}** · regresión por mínimos cuadrados por ruta sobre conteos sintéticos.")
    st.write("Usa hora, picos de mañana y tarde, fin de semana y estacionalidad anual. "
             "El ajuste es reproducible y cada solicitud ejecuta el modelo para la fecha elegida.")
    st.info("TreeSHAP, registro y activación de modelos operativos no están disponibles en esta modalidad.")
