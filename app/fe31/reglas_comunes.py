"""Reglas comunes de calidad y etiqueta para las rutas 2, 16 y 21 (versión vigente en REGLAS["version"]).

Un solo módulo que aplican las tres rutas por igual, para reemplazar los criterios
distintos de cada notebook. Orden de uso:

    cal   = calendario(P.salida_programada.min(), P.salida_programada.max())
    P, Q  = aplicar_cuarentena(P)            # Q: tabla de cuarentena (una fila por viaje y regla)
    dias  = clasificar_dias(P, cal)          # completo / anomalo / baja_calidad / sin_datos
    hor   = horario_operacion(P, cal, dias)  # franjas operativas por ruta y tipo de día
    Y     = etiqueta_operativa(P, cal, dias, hor)
    cob   = cobertura(Y)

Columnas requeridas en P (nombres del notebook de feature engineering):
    id_ruta, id_programacion, salida_programada, inicio_registrado, fin_registrado,
    finalizado, cancelada, pasajeros_original, bajadas_original

Principios:
- Nada se borra ni se imputa. Las reglas solo agregan columnas y una tabla de cuarentena.
- Los umbrales viven en REGLAS (versionado). En el prototipo se cargan desde la tabla de
  umbrales de ai_frecuencias; aquí son el valor por defecto.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
from dateutil.easter import easter

REGLAS = {
    "version": "comun-1.5",
    "pasajeros_max": 500,          # por viaje; más que esto -> cuarentena del viaje
    "bajadas_max": 500,            # solo afecta análisis de bajadas
    "duracion_max_min": 1440,      # más de 24 h -> cierre tardío: cuarentena para la etiqueta
    "duracion_ciclo_min": 60,      # rango válido solo para calcular el ciclo
    "duracion_ciclo_max": 480,
    "inicio_antes_salida_dias": 1, # inicio/fin fuera de [salida-1 día, salida+2 días] -> incoherente
    "fin_despues_salida_dias": 2,
    "anomalia_k_desv": 3.0,        # caída mayor a k desviaciones frente a su referencia
    "baja_calidad_pct_faltantes": 0.05,  # >5 % de elegibles SIN CONTEO en el día...
    "baja_calidad_min_viajes": 3,        # ...y al menos 3 viajes (la cuarentena no cuenta aquí)
    "horario_pct_dias": 0.50,      # inicio y fin del servicio: franjas con salidas en >=50 % de los días
    "resolucion_min": 15,
    "horizontes_min": (30, 60, 120),
}

COLUMNAS_P = ["id_ruta", "id_programacion", "salida_programada", "inicio_registrado",
              "fin_registrado", "finalizado", "cancelada", "pasajeros_original",
              "bajadas_original"]


# ---------------------------------------------------------------------------
# 1. Calendario: festivos de Colombia (Ley 51 de 1983), Carnaval y marcas de la ruta 16
# ---------------------------------------------------------------------------
def _lunes_siguiente(d: date) -> date:
    """Ley Emiliani: el festivo pasa al lunes siguiente si no cae en lunes."""
    return d + timedelta(days=(7 - d.weekday()) % 7)


def festivos_colombia(anio: int) -> dict[date, str]:
    e = easter(anio)
    fijos = {date(anio, 1, 1): "Año Nuevo", date(anio, 5, 1): "Día del Trabajo",
             date(anio, 7, 20): "Independencia", date(anio, 8, 7): "Batalla de Boyacá",
             date(anio, 12, 8): "Inmaculada Concepción", date(anio, 12, 25): "Navidad"}
    trasladables = {(1, 6): "Reyes Magos", (3, 19): "San José", (6, 29): "San Pedro y San Pablo",
                    (8, 15): "Asunción", (10, 12): "Día de la Raza", (11, 1): "Todos los Santos",
                    (11, 11): "Independencia de Cartagena"}
    pares = list(fijos.items())
    pares += [(_lunes_siguiente(date(anio, m, d)), n) for (m, d), n in trasladables.items()]
    pares += [(e - timedelta(days=3), "Jueves Santo"), (e - timedelta(days=2), "Viernes Santo"),
              (e + timedelta(days=43), "Ascensión"), (e + timedelta(days=64), "Corpus Christi"),
              (e + timedelta(days=71), "Sagrado Corazón")]
    out: dict[date, str] = {}
    for d, n in pares:   # dos festivos pueden caer el mismo lunes (30-jun-2025): se unen los nombres
        out[d] = f"{out[d]} / {n}" if d in out else n
    return out


def calendario(desde, hasta) -> pd.DataFrame:
    """Una fila por fecha con tipo_dia y marca_calendario (prioridad de la ruta 16)."""
    fechas = pd.date_range(pd.Timestamp(desde).normalize(), pd.Timestamp(hasta).normalize(), freq="D")
    anios = range(fechas.min().year, fechas.max().year + 1)
    fest = {pd.Timestamp(d): n for a in anios for d, n in festivos_colombia(a).items()}
    pascua = {a: pd.Timestamp(easter(a)) for a in anios}

    c = pd.DataFrame({"fecha": fechas})
    c["anio"] = c.fecha.dt.year
    c["dia_semana_iso"] = c.fecha.dt.dayofweek + 1
    c["festivo"] = c.fecha.map(fest)
    es_fest = c.festivo.notna()
    e = c.anio.map(pascua)
    dif = (c.fecha - e).dt.days
    es_carnaval = dif.isin([-48, -47])          # lunes y martes de Carnaval
    es_sab_santo = dif.eq(-1)
    md = c.fecha.dt.month * 100 + c.fecha.dt.day
    es_fin_anio = (md >= 1224) | (md <= 102)    # 24-dic a 2-ene
    profundo = es_fest & (c.festivo.isin(["Año Nuevo", "Navidad", "Viernes Santo"]))

    c["marca_calendario"] = np.select(
        [es_carnaval, profundo, es_fest, es_sab_santo, es_fin_anio],
        ["carnaval_lun_mar", "festivo_profundo", "festivo_comun", "sabado_santo", "fin_de_anio"],
        default="normal")
    c["tipo_dia"] = np.select([es_fest | c.dia_semana_iso.eq(7), c.dia_semana_iso.eq(6)],
                              ["dom_festivo", "sabado"], default="laboral")
    return c


# ---------------------------------------------------------------------------
# 2. Cuarentena por viaje
# ---------------------------------------------------------------------------
def aplicar_cuarentena(P: pd.DataFrame, reglas: dict = REGLAS) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Agrega columnas de elegibilidad y cuarentena; devuelve (P, tabla_cuarentena)."""
    faltan = set(COLUMNAS_P) - set(P.columns)
    if faltan:
        raise ValueError(f"Faltan columnas en P: {sorted(faltan)}")
    if P.duplicated(["id_ruta", "id_programacion"]).any():
        raise ValueError("Llave (id_ruta, id_programacion) repetida")
    R = reglas
    P = P.copy()
    sal, ini, fin = P.salida_programada, P.inicio_registrado, P.fin_registrado
    dur = (fin - ini).dt.total_seconds() / 60
    pax, baj = P.pasajeros_original, P.bajadas_original

    lim_inf = sal - pd.Timedelta(days=R["inicio_antes_salida_dias"])
    lim_sup = sal + pd.Timedelta(days=R["fin_despues_salida_dias"])
    fuera = lambda s: s.notna() & ((s < lim_inf) | (s > lim_sup))

    reglas_viaje = {   # afectan la etiqueta de pasajeros
        "pasajeros_extremo": pax > R["pasajeros_max"],
        "duracion_negativa": dur < 0,
        "inicio_incoherente": fuera(ini),          # registro mal asignado (p. ej. inicio en 2014)
    }
    reglas_bajadas = {"bajadas_extremo": baj > R["bajadas_max"]}   # solo análisis de bajadas
    # Cierre tardío (fin registrado horas o días después). comun-1.2 lo pasó a solo marca; se revirtió
    # en comun-1.3 porque estos viajes llevan una mediana de 30-54 % de los pasajeros de un viaje normal
    # de la misma ruta, hora y día: el conteo no es confiable. Va a cuarentena para etiqueta y ciclo.
    reglas_ciclo = {
        "duracion_mayor_24h": dur > R["duracion_max_min"],
        "fin_tardio": fuera(fin) & ~fuera(ini),
    }
    afecta = {**{k: "etiqueta" for k in reglas_viaje}, **{k: "bajadas" for k in reglas_bajadas},
              **{k: "etiqueta" for k in reglas_ciclo}}

    filas = []
    for nombre, m in {**reglas_viaje, **reglas_bajadas, **reglas_ciclo}.items():
        m = m.fillna(False).astype(bool)
        valor = {"pasajeros_extremo": pax, "bajadas_extremo": baj}.get(nombre, dur)
        filas.append(pd.DataFrame({"id_ruta": P.id_ruta[m], "id_programacion": P.id_programacion[m],
                                   "regla": nombre, "valor": valor[m].astype("float64"),
                                   "afecta": afecta[nombre],
                                   "version_reglas": R["version"]}))
    Q = pd.concat(filas, ignore_index=True)

    clave = P.id_ruta.astype(str) + "|" + P.id_programacion.astype(str)
    clave_q = Q.id_ruta.astype(str) + "|" + Q.id_programacion.astype(str)
    P["cuarentena_etiqueta"] = clave.isin(clave_q[Q.afecta.eq("etiqueta")])
    P["cuarentena_bajadas"] = clave.isin(clave_q[Q.afecta.eq("bajadas")])
    P["elegible"] = (P.finalizado.eq("S") & P.cancelada.eq("N")).fillna(False)
    conteo_ok = pax.notna() & np.isfinite(pax.astype("float64")) & (pax >= 0)
    P["pax_valido"] = P.elegible & conteo_ok.fillna(False) & ~P.cuarentena_etiqueta
    P["pax_bloquea"] = P.elegible & ~P.pax_valido          # elegible sin conteo usable
    P["marca_cierre_tardio"] = clave.isin(clave_q[Q.regla.isin(list(reglas_ciclo))])
    P["apto_ciclo"] = P.elegible & dur.between(R["duracion_ciclo_min"], R["duracion_ciclo_max"]) & ~P.marca_cierre_tardio
    P["marca_duracion_larga"] = P.elegible & dur.between(R["duracion_ciclo_max"], R["duracion_max_min"],
                                                         inclusive="right")
    P["version_reglas"] = R["version"]
    return P, Q


# ---------------------------------------------------------------------------
# 3. Clasificación de días por ruta
# ---------------------------------------------------------------------------
def clasificar_dias(P: pd.DataFrame, cal: pd.DataFrame, reglas: dict = REGLAS) -> pd.DataFrame:
    """Clase por (ruta, fecha): sin_datos > baja_calidad > anomalo > completo.

    Baja calidad (comun-1.1) = más del 5 % de los elegibles sin conteo y al menos 3 viajes.
    Los viajes en cuarentena no cuentan aquí: ya dejan NA las ventanas que los contienen.

    Anómalo = día con marca 'normal' cuya demanda cae más de k desviaciones frente a la
    media de los días normales del mismo año y día de la semana (método de la ruta 16).
    """
    R = reglas
    x = P.loc[P.elegible].assign(fecha=lambda d: d.salida_programada.dt.normalize(),
                                  pax_ok=lambda d: d.pasajeros_original.where(d.pax_valido, 0.0),
                                  sin_conteo=lambda d: d.pax_bloquea & ~d.cuarentena_etiqueta)
    d = x.groupby(["id_ruta", "fecha"]).agg(
        n_elegibles=("elegible", "size"), n_bloquea=("pax_bloquea", "sum"),
        n_sin_conteo=("sin_conteo", "sum"), pax=("pax_ok", "sum"))
    d = d.reset_index()
    rutas = P.id_ruta.unique()
    malla = pd.MultiIndex.from_product([rutas, cal.fecha], names=["id_ruta", "fecha"]).to_frame(index=False)
    d = malla.merge(d, on=["id_ruta", "fecha"], how="left").merge(cal, on="fecha", how="left")
    cols = ["n_elegibles", "n_bloquea", "n_sin_conteo"]
    d[cols] = d[cols].fillna(0).astype(int)

    d["pct_bloquea"] = np.where(d.n_elegibles > 0, d.n_bloquea / d.n_elegibles.clip(lower=1), np.nan)
    d["pct_sin_conteo"] = np.where(d.n_elegibles > 0, d.n_sin_conteo / d.n_elegibles.clip(lower=1), np.nan)
    normal = d.marca_calendario.eq("normal") & d.n_elegibles.gt(0)
    # Demanda ajustada: escala el total por los viajes sin conteo usable, para que "faltan datos"
    # no se confunda con "bajó la demanda". Solo se usa para detectar anomalías.
    validos = (d.n_elegibles - d.n_bloquea).clip(lower=1)
    d["pax_ajustado"] = np.where(d.n_elegibles > 0, d.pax * d.n_elegibles / validos, np.nan)
    ref = d[normal].groupby(["id_ruta", "anio", "dia_semana_iso"]).pax_ajustado.mean().rename("pax_referencia")
    d = d.merge(ref.reset_index(), on=["id_ruta", "anio", "dia_semana_iso"], how="left")
    d["efecto"] = d.pax_ajustado / d.pax_referencia - 1
    sd = d[normal].groupby("id_ruta").efecto.std().rename("sd_efecto")
    d = d.merge(sd.reset_index(), on="id_ruta", how="left")

    sin = d.n_elegibles.eq(0)
    # comun-1.1: solo conteos faltantes (falla de medición). La cuarentena ya bloquea sus ventanas.
    baja = ~sin & d.pct_sin_conteo.gt(R["baja_calidad_pct_faltantes"]) & d.n_sin_conteo.ge(R["baja_calidad_min_viajes"])
    anom = ~sin & ~baja & d.marca_calendario.eq("normal") & (d.efecto < -R["anomalia_k_desv"] * d.sd_efecto)
    d["clase_dia"] = np.select([sin, baja, anom], ["sin_datos", "baja_calidad", "anomalo"], default="completo")
    d["version_reglas"] = R["version"]
    return d


# ---------------------------------------------------------------------------
# 4. Horario de operación
# ---------------------------------------------------------------------------
def horario_operacion(P: pd.DataFrame, cal: pd.DataFrame, dias: pd.DataFrame,
                      reglas: dict = REGLAS) -> pd.DataFrame:
    """Horario de operación por (ruta, tipo_dia, hhmm), como tramo continuo (comun-1.4).

    El servicio empieza en la primera franja de 15 min con salidas en >= pct de los días completos y
    termina en la última. comun-1.5 baja pct de 0,80 a 0,50: al final del día la ruta 21 sale cada
    25-30 min y ninguna franja llegaba al 80 %, así que el domingo el servicio "terminaba" a las 17:30. Todas las franjas intermedias son operativas: si en una no salió bus, la
    oferta fue 0. Con la regla franja por franja (hasta comun-1.3), una ruta con salidas cada ~20 min
    perdía franjas de pleno servicio (ruta 21 domingo: 22 de 51), porque un bus no cae en cada franja.
    """
    R = reglas
    ok = dias.loc[dias.clase_dia.eq("completo"), ["id_ruta", "fecha", "tipo_dia"]]
    x = P.loc[P.elegible, ["id_ruta", "salida_programada"]].assign(
        fecha=lambda d: d.salida_programada.dt.normalize(),
        hhmm=lambda d: d.salida_programada.dt.floor(f"{R['resolucion_min']}min").dt.strftime("%H:%M"))
    x = x.merge(ok, on=["id_ruta", "fecha"])
    n_dias = ok.groupby(["id_ruta", "tipo_dia"]).fecha.nunique().rename("dias_totales")
    usados = x.groupby(["id_ruta", "tipo_dia", "hhmm"]).fecha.nunique().rename("dias_con_salida")
    franjas = pd.date_range("2000-01-01", periods=1440 // R["resolucion_min"],
                            freq=f"{R['resolucion_min']}min").strftime("%H:%M")
    malla = pd.MultiIndex.from_product([n_dias.index.get_level_values(0).unique(),
                                        ["laboral", "sabado", "dom_festivo"], franjas],
                                       names=["id_ruta", "tipo_dia", "hhmm"]).to_frame(index=False)
    h = malla.merge(usados.reset_index(), how="left").merge(n_dias.reset_index(), how="left")
    h["dias_con_salida"] = h.dias_con_salida.fillna(0).astype(int)
    h["pct_dias"] = h.dias_con_salida / h.dias_totales
    h["supera_umbral"] = h.pct_dias.ge(R["horario_pct_dias"]).fillna(False)
    limites = (h.loc[h.supera_umbral].groupby(["id_ruta", "tipo_dia"]).hhmm.agg(["min", "max"])
                .rename(columns={"min": "inicio_servicio", "max": "fin_servicio"}).reset_index())
    h = h.merge(limites, on=["id_ruta", "tipo_dia"], how="left")
    h["operativa"] = (h.hhmm >= h.inicio_servicio) & (h.hhmm <= h.fin_servicio)
    h["version_reglas"] = R["version"]
    return h


# ---------------------------------------------------------------------------
# 5. Etiqueta operativa [t, t+H)
# ---------------------------------------------------------------------------
def etiqueta_operativa(P: pd.DataFrame, cal: pd.DataFrame, dias: pd.DataFrame, hor: pd.DataFrame,
                       reglas: dict = REGLAS) -> pd.DataFrame:
    """Pasajeros de salidas elegibles en [t, t+H), solo para orígenes en franja operativa de día completo.

    Cambios frente a sobusa-fe-2.0:
    - Dentro del horario de operación, una franja sin salidas aporta 0 (no hay oferta), no bloquea.
    - La ventana queda NA (sin imputar) si contiene un viaje elegible sin conteo válido o en cuarentena.
    - Solo se evalúan orígenes operativos: la noche sin servicio no cuenta como faltante.
    """
    R = reglas
    paso = R["resolucion_min"]
    x = P.loc[P.elegible].assign(franja=lambda d: d.salida_programada.dt.floor(f"{paso}min"))
    x["pax_ok"] = x.pasajeros_original.where(x.pax_valido, 0.0)
    g = x.groupby(["id_ruta", "franja"]).agg(pax=("pax_ok", "sum"), n_elig=("elegible", "size"),
                                             n_bloq=("pax_bloquea", "sum"))
    completos = dias.loc[dias.clase_dia.eq("completo"), ["id_ruta", "fecha", "tipo_dia"]]
    operativas = hor.loc[hor.operativa, ["id_ruta", "tipo_dia", "hhmm"]]
    salida = []
    for ruta in P.id_ruta.unique():
        idx = pd.date_range(cal.fecha.min(), cal.fecha.max() + pd.Timedelta(days=1),
                            freq=f"{paso}min", inclusive="left")
        s = g.loc[ruta].reindex(idx, fill_value=0) if ruta in g.index.get_level_values(0) \
            else pd.DataFrame(0, index=idx, columns=["pax", "n_elig", "n_bloq"])
        base = pd.DataFrame({"id_ruta": ruta, "origen": idx})
        base["fecha"] = base.origen.dt.normalize()
        base["hhmm"] = base.origen.dt.strftime("%H:%M")
        base = base.merge(completos, on=["id_ruta", "fecha"]).merge(operativas, on=["id_ruta", "tipo_dia", "hhmm"])
        pos = idx.get_indexer(base.origen)
        for H in R["horizontes_min"]:
            k = H // paso
            adelante = lambda col: s[col][::-1].rolling(k, min_periods=k).sum()[::-1].to_numpy()
            pax, ne, nb = adelante("pax")[pos], adelante("n_elig")[pos], adelante("n_bloq")[pos]
            estado = np.select([np.isnan(pax), nb > 0], ["fuera_malla", "bloqueada_conteo"], default="completa")
            salida.append(base[["id_ruta", "origen", "tipo_dia"]].assign(
                horizonte_min=H, y_pasajeros=np.where(estado == "completa", pax, np.nan),
                n_elegibles_ventana=ne, n_bloqueantes_ventana=nb, estado_etiqueta=estado,
                version_reglas=R["version"]))
    return pd.concat(salida, ignore_index=True)


def cobertura(Y: pd.DataFrame) -> pd.DataFrame:
    """% de ventanas completas sobre orígenes operativos de días completos, por ruta y horizonte."""
    c = Y.groupby(["id_ruta", "horizonte_min"]).agg(
        origenes_operativos=("estado_etiqueta", "size"),
        completas=("estado_etiqueta", lambda s: int(s.eq("completa").sum())))
    c["cobertura_pct"] = 100 * c.completas / c.origenes_operativos
    return c.reset_index()
