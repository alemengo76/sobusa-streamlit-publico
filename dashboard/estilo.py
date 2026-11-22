"""Identidad visual del tablero, tomada de la maqueta v2 (maqueta_sobusa_tablero_v2.html).

Se reproducen la paleta, la tipografía, la barra lateral verde, las tarjetas con encabezado (punto,
título, subtítulo y fuente), los indicadores, las píldoras, los chips de estado con forma (no solo
color), las listas, la conclusión de una decisión y los pasos del cálculo.

Todo texto que viene de la API pasa por ``html.escape`` antes de entrar en un fragmento HTML.
Este módulo no importa Streamlit: devuelve cadenas, así que se prueba sin interfaz.
"""
from __future__ import annotations

import html
import math
from collections.abc import Iterable, Sequence

# Paleta de la maqueta (variables :root)
VERDE, VERDE2, VT2, MENTA = "#0E7C4A", "#16A060", "#9ED3B4", "#E4F2E9"
NAV, NAVACT, NAVTXT = "#104B46", "#0A3531", "#D3E3E0"
FONDO, TINTA, SEC, TER, LIN, LIN2 = "#F5F6F4", "#101814", "#66706A", "#8C948F", "#E3E5E0", "#EEF0EC"
ACERO, AT2, ACEROF = "#3A6F8C", "#A9C3D2", "#EAF1F5"
AMBAR, AMBART, AMBARF = "#C98A0B", "#7A5200", "#FBF0D9"
CORAL, CORALT, CORALF, CO2 = "#D04A35", "#9B3324", "#F9E3DE", "#EFA697"
GRIS = "#C9CEC9"

def _svg(cuerpo: str) -> str:
    """Icono de trazo (estilo Lucide) como data-URI para usarlo de máscara en CSS."""
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
           "stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>" + cuerpo + "</svg>")
    return 'url("data:image/svg+xml;utf8,' + svg.replace("#", "%23").replace('"', "'") + '")'


# Un icono por sección, en el orden de SECCIONES del tablero.
_ICONOS = (
    ("<rect x='3' y='3' width='7' height='9' rx='1.5'/><rect x='14' y='3' width='7' height='5' rx='1.5'/>"
     "<rect x='14' y='12' width='7' height='9' rx='1.5'/><rect x='3' y='16' width='7' height='5' rx='1.5'/>"),
    "<path d='M3 3v18h18'/><path d='m7 15 4-4 3 3 5-6'/>",
    "<path d='M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9'/><path d='M10.3 21a1.94 1.94 0 0 0 3.4 0'/>",
    "<path d='M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z'/><path d='m9 12 2 2 4-4'/>",
    "<circle cx='12' cy='12' r='9'/><circle cx='12' cy='12' r='5'/><circle cx='12' cy='12' r='1'/>",
    "<path d='M12 2 2 7l10 5 10-5-10-5z'/><path d='m2 17 10 5 10-5'/><path d='m2 12 10 5 10-5'/>",
)
ICONOS_NAV = "\n".join(
    f'[data-testid="stSidebar"] [role="radiogroup"] > label:nth-child({i}),'
    f'[data-testid="stSidebar"] [role="radiogroup"] > :nth-child({i}) label{{{{--ico:{_svg(c)}}}}}'
    for i, c in enumerate(_ICONOS, start=1)).replace("{{", "{").replace("}}", "}")
ICONO_VACIO = _svg("<circle cx='12' cy='12' r='9'/><path d='M8 12h8'/>")


CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap');
:root{{--ico-vacio:{ICONO_VACIO};--verde:{VERDE};--verde2:{VERDE2};--vt2:{VT2};--menta:{MENTA};--nav:{NAV};--navact:{NAVACT};
--navtxt:{NAVTXT};--fondo:{FONDO};--tinta:{TINTA};--sec:{SEC};--ter:{TER};--lin:{LIN};--lin2:{LIN2};
--acero:{ACERO};--acerof:{ACEROF};--ambar:{AMBAR};--ambart:{AMBART};--ambarf:{AMBARF};--coral:{CORAL};
--coralt:{CORALT};--coralf:{CORALF};
--sans:'Geist','IBM Plex Sans',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
--mono:'Geist Mono','IBM Plex Mono',ui-monospace,'SF Mono',Menlo,Consolas,monospace;
--sombra:0 1px 2px rgba(16,24,20,.04),0 4px 14px -6px rgba(16,24,20,.08);
--sombra2:0 1px 2px rgba(16,24,20,.06),0 10px 28px -10px rgba(16,24,20,.16);
--r:14px}}
html,body,[data-testid="stAppViewContainer"]{{color:var(--tinta);font-family:var(--sans);
  font-variant-numeric:tabular-nums;-webkit-font-smoothing:antialiased}}
[data-testid="stAppViewContainer"]{{background:
  radial-gradient(1200px 500px at 85% -120px,rgba(22,160,96,.07),transparent 60%),var(--fondo)}}
[data-testid="stMain"] p,[data-testid="stMain"] li,[data-testid="stMain"] label,
[data-testid="stMain"] input,[data-testid="stMain"] textarea{{font-family:var(--sans)}}
[data-testid="stIconMaterial"],.material-symbols-rounded,[translate="no"][class*="material"]{{
  font-family:"Material Symbols Rounded"!important}}
/* sin el «Deploy» ni la franja de color de Streamlit: no es parte del producto */
[data-testid="stHeader"]{{background:transparent;height:0}}
[data-testid="stDecoration"],[data-testid="stAppDeployButton"],.stAppDeployButton,
[data-testid="stToolbarActions"],[data-testid="stStatusWidget"]{{display:none!important}}
[data-testid="stMainBlockContainer"],.block-container{{padding-top:2.2rem!important;padding-bottom:3rem!important;
  max-width:1440px}}
[data-testid="stMain"] label,[data-testid="stMain"] [data-testid="stWidgetLabel"] p{{color:var(--sec)!important;
  font:600 11.5px var(--sans)!important;letter-spacing:.02em}}
[data-testid="stMain"] .stCheckbox p,[data-testid="stMain"] [role="radiogroup"] p{{color:var(--tinta)!important}}

/* ---------------- barra lateral */
[data-testid="stSidebar"]{{background:linear-gradient(180deg,#125650 0%,{NAV} 38%,#0B3934 100%);
  border-right:0;box-shadow:inset -1px 0 0 rgba(255,255,255,.04)}}
[data-testid="stSidebar"] *{{color:var(--navtxt)}}
[data-testid="stSidebar"] [role="radiogroup"]{{gap:3px}}
[data-testid="stSidebar"] [role="radiogroup"] label{{padding:10px 14px;border-radius:10px;margin:0;width:100%;
  font-weight:500;display:flex;align-items:center;gap:11px;transition:background .15s,color .15s;cursor:pointer}}
[data-testid="stSidebar"] [role="radiogroup"] label:hover{{background:rgba(255,255,255,.06)}}
[data-testid="stSidebar"] [role="radiogroup"] label::before{{content:"";flex:none;width:18px;height:18px;
  background:currentColor;opacity:.75;-webkit-mask:var(--ico) center/contain no-repeat;mask:var(--ico) center/contain no-repeat}}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked){{background:rgba(255,255,255,.11);
  box-shadow:inset 3px 0 0 #7CD3A6,0 1px 0 rgba(255,255,255,.04)}}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked)::before{{opacity:1;background:#7CD3A6}}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) *{{color:#fff;font-weight:600}}
[data-testid="stSidebar"] [role="radiogroup"] label > div:not(:has(p)){{display:none!important}}
{ICONOS_NAV}
[data-testid="stSidebar"] .stButton button{{width:100%;background:rgba(255,255,255,.06);
  border:1px solid rgba(255,255,255,.16);border-radius:10px;font-weight:600}}
[data-testid="stSidebar"] .stButton button:hover{{background:rgba(255,255,255,.12);border-color:#7CD3A6}}
[data-testid="stSidebar"] .stCheckbox p{{font-size:12.5px}}
[data-testid="stSidebar"] hr{{border-color:rgba(255,255,255,.08)}}

/* ---------------- tarjetas */
[data-testid="stVerticalBlockBorderWrapper"]{{background:#fff;border-radius:var(--r)!important;
  border:1px solid var(--lin)!important;box-shadow:var(--sombra);transition:box-shadow .2s}}
[data-testid="stVerticalBlockBorderWrapper"]:hover{{box-shadow:var(--sombra2)}}
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlockBorderWrapper"]{{box-shadow:none}}

/* ---------------- campos */
[data-testid="stMain"] [data-baseweb="select"] > div,[data-testid="stMain"] [data-baseweb="input"],
[data-testid="stMain"] [data-baseweb="base-input"],[data-testid="stMain"] [data-baseweb="textarea"]{{
  background:#fff!important;border:1px solid #D9DDD6!important;border-radius:10px!important;
  transition:border-color .15s,box-shadow .15s}}
[data-testid="stMain"] [data-baseweb="select"] > div:hover,[data-testid="stMain"] [data-baseweb="input"]:hover{{
  border-color:#B9C1B9!important}}
[data-testid="stMain"] [data-baseweb="select"] > div:focus-within,[data-testid="stMain"] [data-baseweb="input"]:focus-within,
[data-testid="stMain"] [data-baseweb="textarea"]:focus-within{{border-color:var(--verde2)!important;
  box-shadow:0 0 0 3px rgba(22,160,96,.15)!important}}
[data-testid="stMain"] input,[data-testid="stMain"] textarea,[data-testid="stMain"] [data-baseweb="select"] *{{
  color:var(--tinta)!important;background:transparent!important}}
[data-testid="stMain"] [data-testid="stNumberInput"] button{{background:#F3F4F1!important;border:0!important}}

/* ---------------- botones */
[data-testid="stMain"] .stButton button,[data-testid="stMain"] .stDownloadButton button,
[data-testid="stMain"] .stFormSubmitButton button{{border-radius:10px;font-weight:600;min-height:40px;
  background:#fff;color:var(--tinta);border:1px solid #D9DDD6;box-shadow:0 1px 1px rgba(16,24,20,.04);
  transition:all .15s}}
[data-testid="stMain"] .stButton button p,[data-testid="stMain"] .stDownloadButton button p{{color:inherit!important;
  font-weight:600}}
[data-testid="stMain"] .stButton button:hover,[data-testid="stMain"] .stDownloadButton button:hover{{
  border-color:var(--verde2);color:var(--verde);background:#F7FBF8}}
[data-testid="stMain"] .stButton button:disabled{{opacity:.55}}
.stButton button[kind="primary"],.stFormSubmitButton button[kind="primary"]{{
  background:linear-gradient(180deg,#14935A,var(--verde))!important;border-color:var(--verde)!important;
  color:#fff!important;box-shadow:0 1px 2px rgba(14,124,74,.3),inset 0 1px 0 rgba(255,255,255,.15)!important}}
.stButton button[kind="primary"]:hover{{filter:brightness(1.06)}}

/* ---------------- selectores horizontales como control segmentado */
[data-testid="stMain"] .stRadio [role="radiogroup"]{{display:inline-flex;flex-wrap:wrap;gap:2px;padding:3px;
  background:#EBEEE9;border-radius:11px;border:1px solid #E1E5DF}}
[data-testid="stMain"] .stRadio [role="radiogroup"] label{{margin:0!important;padding:6px 14px;border-radius:8px;
  cursor:pointer;transition:background .15s}}
[data-testid="stMain"] .stRadio [role="radiogroup"] label > div:not(:has(p)){{display:none!important}}
[data-testid="stMain"] .stRadio [role="radiogroup"] label p{{font:500 13px var(--sans)!important;color:var(--sec)!important}}
[data-testid="stMain"] .stRadio [role="radiogroup"] label:hover p{{color:var(--tinta)!important}}
[data-testid="stMain"] .stRadio [role="radiogroup"] label:has(input:checked){{background:#fff;
  box-shadow:0 1px 2px rgba(16,24,20,.1),0 0 0 1px rgba(16,24,20,.04)}}
[data-testid="stMain"] .stRadio [role="radiogroup"] label:has(input:checked) p{{color:var(--tinta)!important;font-weight:600!important}}

/* ---------------- avisos, desplegables, tablas */
[data-testid="stMain"] [data-testid="stAlert"]{{border-radius:12px}}
[data-testid="stMain"] [data-testid="stAlert"] > div{{border-radius:12px;border:1px solid rgba(16,24,20,.06)}}
[data-testid="stMain"] [data-testid="stExpander"] details{{background:#FAFBF9;border:1px solid var(--lin)!important;
  border-radius:12px!important}}
[data-testid="stMain"] [data-testid="stExpander"] summary p{{font-weight:600!important;color:var(--tinta)!important}}
[data-testid="stMain"] [data-testid="stExpander"] summary:hover p{{color:var(--verde)!important}}
[data-testid="stMain"] [data-testid="stDataFrame"]{{border:1px solid var(--lin);border-radius:12px;overflow:hidden}}
[data-testid="stMain"] [data-testid="stCaptionContainer"]{{color:var(--ter)}}
.stTabs [aria-selected="true"]{{color:var(--verde)}}

/* ---------------- logo y pie de la barra lateral */
.sb-logo{{display:grid;place-items:center;padding:14px 0 18px}}
.sb-logo .iso{{width:48px;height:48px;border-radius:14px;display:grid;place-items:center;margin:0 auto;
  background:linear-gradient(145deg,#3CC47A,#1E8C50);
  box-shadow:0 6px 18px -4px rgba(47,179,107,.55),inset 0 1px 0 rgba(255,255,255,.25)}}
.sb-logo .nom{{color:#fff!important;font:700 12px var(--sans);letter-spacing:.22em;margin-top:10px;text-align:center}}
.sb-logo .lema{{color:#8FB2AC!important;font:500 10.5px var(--sans);text-align:center;margin-top:2px;letter-spacing:.02em}}
.sb-pie{{font-size:11px;color:#8FB2AC!important;line-height:1.6;padding:14px 2px 0;margin-top:10px;
  border-top:1px solid rgba(255,255,255,.08)}}
.sb-pie b{{color:#E3EEEB!important}}
.aviso-sb{{background:#FFF7E1;border:1px solid #EFDDAE;color:var(--ambart);font:600 11px var(--sans);
  padding:5px 12px;border-radius:6px;margin-bottom:8px}}

/* ---------------- cabecera de página */
.cabecera{{display:flex;align-items:flex-end;gap:16px;flex-wrap:wrap;margin:0 0 18px}}
.cabecera .tit{{min-width:0}}
.cabecera .ante{{font:600 11px var(--sans);letter-spacing:.12em;text-transform:uppercase;color:var(--verde2);
  margin-bottom:4px}}
.cabecera h1{{margin:0;font:650 28px/1.15 var(--sans)!important;letter-spacing:-.025em;padding:0!important;
  color:var(--tinta)}}
.cabecera .bajada{{color:var(--sec);font-size:13.5px;margin-top:6px}}
.pildoras{{display:flex;gap:8px;flex-wrap:wrap;margin-left:auto}}
.pil{{display:inline-flex;align-items:center;gap:8px;height:32px;padding:0 13px;border:1px solid var(--lin);
  border-radius:999px;background:rgba(255,255,255,.85);backdrop-filter:blur(6px);font-size:12.5px;white-space:nowrap;
  box-shadow:0 1px 2px rgba(16,24,20,.04)}}
.pil .k{{color:var(--sec)}} .pil b{{font-weight:600}}
.punto{{width:8px;height:8px;border-radius:50%;background:#2FB36B;display:inline-block;
  box-shadow:0 0 0 3px rgba(47,179,107,.18);animation:latido 2.4s ease-in-out infinite}}
.punto.mal{{background:var(--coral);box-shadow:0 0 0 3px rgba(208,74,53,.18)}}
.punto.gris{{background:{GRIS};box-shadow:none;animation:none}}
@keyframes latido{{0%,100%{{box-shadow:0 0 0 3px rgba(47,179,107,.18)}}50%{{box-shadow:0 0 0 5px rgba(47,179,107,.06)}}}}

/* ---------------- encabezado de tarjeta */
.ch{{display:flex;align-items:center;gap:9px;min-height:30px;margin-bottom:6px}}
.ch .p{{width:4px;height:16px;border-radius:2px;background:var(--verde2);flex:none}}
.ch .p.c{{background:var(--coral)}} .ch .p.g{{background:{GRIS}}}
.ch h3{{margin:0!important;padding:0!important;font:650 14.5px var(--sans)!important;white-space:nowrap;
  letter-spacing:-.01em;color:var(--tinta)}}
.ch .sub{{color:var(--ter);font-size:12.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}}
.ch .fte{{margin-left:auto;font:500 10.5px var(--mono);color:var(--acero);white-space:nowrap;
  background:var(--acerof);padding:2px 7px;border-radius:6px}}

/* ---------------- indicadores */
.kpis{{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(0,1fr);gap:0}}
.kpi{{padding:8px 18px 6px;min-width:0;position:relative}}
.kpi + .kpi{{border-left:1px solid var(--lin2)}}
.kpi .l{{font:600 12px var(--sans);color:var(--sec);display:flex;align-items:center;gap:6px;letter-spacing:.01em}}
.kpi .v{{display:flex;align-items:baseline;gap:7px;margin-top:8px;flex-wrap:wrap}}
.kpi .v b{{font:650 34px/1 var(--sans);letter-spacing:-.035em;color:var(--tinta)}}
.kpi .v span{{color:var(--ter);font-size:12.5px}}
.kpi .ctx{{font-size:12px;color:var(--sec);margin-top:8px;line-height:1.45}}
.kpi .fte{{font:500 10px/1.6 var(--mono);color:var(--acero);margin-top:6px;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis}}
.kpi.mal .v b{{color:var(--coralt)}} .kpi.sd .v b{{color:#AEB5AF;font-size:22px;font-weight:500;letter-spacing:-.01em}}
.kpi.mal .l:before{{content:"";border-left:4.5px solid transparent;border-right:4.5px solid transparent;
  border-bottom:8px solid var(--coral)}}

/* ---------------- listas */
.lista{{list-style:none;margin:0;padding:0}}
.lista li{{display:flex;align-items:center;gap:10px;min-height:40px;padding:7px 2px;border-top:1px solid var(--lin2);
  font-size:13.5px}}
.lista li:first-child{{border-top:0}}
.lista .p{{width:7px;height:7px;border-radius:50%;background:var(--verde2);flex:none}}
.lista b{{font-weight:600;white-space:nowrap;min-width:0;overflow:hidden;text-overflow:ellipsis}}
.lista .val{{color:var(--sec);min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.lista .der{{margin-left:auto;font:600 13px var(--sans);white-space:nowrap;flex:none;color:var(--tinta)}}
.leg{{display:flex;flex-wrap:wrap;gap:8px;margin:6px 0 2px}}
.lp{{display:inline-flex;align-items:center;gap:8px;height:28px;padding:0 12px;border:1px solid var(--lin);
  border-radius:999px;font-size:12px;background:#fff}}
.lp i{{width:9px;height:9px;border-radius:3px;display:inline-block}}
.lp .n{{color:var(--sec);font-family:var(--mono);font-size:11px}}

/* ---------------- chips y formas */
.chip{{display:inline-flex;align-items:center;gap:5px;font:600 11px var(--sans);padding:3px 9px;
  border-radius:999px;white-space:nowrap;box-shadow:inset 0 0 0 1px rgba(16,24,20,.05)}}
.chip.ok{{background:var(--menta);color:var(--verde)}} .chip.nv{{background:var(--coralf);color:var(--coralt)}}
.chip.av{{background:var(--ambarf);color:var(--ambart)}} .chip.ac{{background:var(--acerof);color:#2C5670}}
.chip.gr{{background:#F0F1EC;color:#4D5550}}
.cua{{width:7px;height:7px;background:currentColor;border-radius:1px;display:inline-block}}
.tri{{width:0;height:0;border-left:4.5px solid transparent;border-right:4.5px solid transparent;
  border-bottom:8px solid currentColor;display:inline-block}}
.cir{{width:8px;height:8px;border:2px solid currentColor;border-radius:50%;display:inline-block}}
.rom{{width:7px;height:7px;background:currentColor;transform:rotate(45deg);display:inline-block}}

/* ---------------- bloques de contenido */
.conclusion{{display:flex;gap:12px;align-items:flex-start;padding:14px 16px;border-radius:12px;
  font:600 14px/1.45 var(--sans);margin-bottom:12px;border:1px solid transparent}}
.conclusion > span{{margin-top:6px;flex:none}}
.conclusion.nv{{background:var(--coralf);color:var(--coralt);border-color:#F1CFC7}}
.conclusion.ok{{background:var(--menta);color:#0B5E38;border-color:#CDE7D7}}
.conclusion.av{{background:var(--ambarf);color:var(--ambart);border-color:#F0DFB8}}
.datos{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}}
.datos > div{{padding:10px 0;border-top:1px solid var(--lin2);display:flex;justify-content:space-between;gap:10px;
  font-size:13px}}
.datos > div:nth-child(-n+2){{border-top:0}}
.datos > div:nth-child(odd){{padding-right:16px}}
.datos > div:nth-child(even){{padding-left:16px;border-left:1px solid var(--lin2)}}
.datos .l{{color:var(--sec)}} .datos .v{{font-weight:600;text-align:right;min-width:0;overflow-wrap:anywhere}}
.datos .v.sd{{color:#AEB5AF;font-weight:500}}
.pasos{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr))}}
.pasos > div{{padding:12px 14px 10px;border-left:1px solid var(--lin2);min-width:0}}
.pasos > div:nth-child(4n+1){{border-left:0}} .pasos > div:nth-child(n+5){{border-top:1px solid var(--lin2)}}
.pasos .n{{font:700 10.5px var(--mono);color:var(--verde);background:var(--menta);border-radius:999px;
  width:24px;height:24px;display:grid;place-items:center;margin-bottom:8px;box-shadow:inset 0 0 0 1px #CDE7D7}}
.pasos b{{display:block;font-size:12px;margin-bottom:4px;color:var(--sec);font-weight:600}}
.pasos .f{{font:650 15px var(--sans);letter-spacing:-.01em}}
.pasos small{{display:block;color:var(--sec);font-size:11px;margin-top:4px;line-height:1.4}}
.pasos .mal .f{{color:var(--coralt)}}
.zona{{display:flex;align-items:center;gap:10px;margin:14px 0 10px;font:650 11px var(--sans);
  letter-spacing:.1em;text-transform:uppercase;color:var(--sec)}}
.zona:after{{content:"";flex:1;height:1px;background:linear-gradient(90deg,var(--lin),transparent)}}
.vacio{{border:1px dashed #D3D8D1;border-radius:12px;padding:22px 16px 18px;color:var(--sec);text-align:center;
  background:repeating-linear-gradient(135deg,#FBFBFA 0 10px,#F7F8F6 10px 20px);font-size:13.5px;line-height:1.5}}
.vacio:before{{content:"";display:block;width:26px;height:26px;margin:0 auto 8px;background:#B9C1BA;
  -webkit-mask:var(--ico-vacio) center/contain no-repeat;mask:var(--ico-vacio) center/contain no-repeat}}
.nota{{font-size:11.5px;color:var(--ter)}} .mono{{font-family:var(--mono)}}
.escritura{{display:inline-flex;align-items:center;gap:6px;font:600 11px var(--sans);color:var(--ambart);
  border:1px solid #EBD6A6;border-radius:999px;padding:3px 10px;background:#FFF9EB}}
.escritura:before{{content:"";width:6px;height:6px;border-radius:50%;background:var(--ambar)}}
</style>
"""

ICONO_BUS = ('<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="#fff" stroke-width="2" '
             'stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="4" width="14" height="13" rx="3"/>'
             '<path d="M5 11h14"/><path d="M8.5 20v-3M15.5 20v-3"/></svg>')

SIN_DATO = "Sin dato"


def e(valor) -> str:
    """Escapa cualquier valor para HTML (None -> «Sin dato»)."""
    return html.escape(SIN_DATO if valor is None else str(valor), quote=True)


# Caracteres que Markdown de Streamlit interpreta (enlaces, imágenes, énfasis, HTML, LaTeX con $, tablas).
# No se escapa el guion: los correlation_id y los UUID lo usan y no forma sintaxis dentro de una línea.
_MARKDOWN = str.maketrans({c: "\\" + c for c in "\\`*_[]<>!$|~#{}"})


def md(valor) -> str:
    """Texto plano para st.error/st.warning/st.info/st.caption, que interpretan Markdown: un texto de la
    API no puede convertirse en enlace, imagen, énfasis ni fórmula. None -> «Sin dato»."""
    return (SIN_DATO if valor is None else str(valor)).translate(_MARKDOWN)


def es_faltante(valor) -> bool:
    if valor is None or type(valor).__name__ in ("NAType", "NaTType"):
        return True
    try:
        return isinstance(valor, float) and math.isnan(valor)
    except TypeError:
        return False


def num(valor, dec: int = 0, sufijo: str = "") -> str:
    """Número con formato es-CO (miles con punto, decimales con coma). Nunca convierte None en 0."""
    if es_faltante(valor):
        return SIN_DATO
    try:
        x = float(valor)
    except (TypeError, ValueError):
        return str(valor)
    if math.isinf(x):
        return SIN_DATO
    texto = f"{x:,.{dec}f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return texto + sufijo


def pct(valor, dec: int = 2) -> str:
    """Proporción (0,1385) como porcentaje («13,85 %»)."""
    if es_faltante(valor):
        return SIN_DATO
    try:
        return num(float(valor) * 100, dec, " %")
    except (TypeError, ValueError):
        return SIN_DATO


def corto(identificador, n: int = 4) -> str:
    """«e3f1…7a02» para mostrar ids largos sin perder la referencia (el id completo va en title)."""
    if not identificador:
        return SIN_DATO
    s = str(identificador)
    return s if len(s) <= 2 * n + 1 else f"{s[:n]}…{s[-n:]}"


# ------------------------------------------------------------------ fragmentos

def logo_lateral() -> str:
    return (f'<div class="sb-logo"><div><div class="iso">{ICONO_BUS}</div>'
            '<div class="nom">SOBUSA</div><div class="lema">Frecuencias de despacho</div></div></div>')


def pie_lateral(consultado: str | None = None) -> str:
    c = f'Datos consultados a las <b>{e(consultado)}</b><br>' if consultado else ""
    return (f'<div class="sb-pie">{c}Rutas 2 · 16 · 21 — Barranquilla<br>'
            'Prototipo · Data Challenge 2026</div>')


def pildora(clave: str | None, valor, *, punto: str | None = None, mono: bool = False) -> str:
    p = f'<span class="punto {e(punto)}"></span>' if punto is not None else ""
    k = f'<span class="k">{e(clave)}</span>' if clave else ""
    estilo = ' class="mono" style="font-weight:500"' if mono else ""
    return f'<span class="pil">{p}{k}<b{estilo}>{e(valor)}</b></span>'


def cabecera(titulo: str, pildoras: Iterable[str], *, antetitulo: str | None = None,
             bajada: str | None = None) -> str:
    a = f'<div class="ante">{e(antetitulo)}</div>' if antetitulo else ""
    b = f'<div class="bajada">{e(bajada)}</div>' if bajada else ""
    return (f'<div class="cabecera"><div class="tit">{a}<h1>{e(titulo)}</h1>{b}</div>'
            f'<div class="pildoras">{"".join(pildoras)}</div></div>')


def franja_pildoras(pildoras: Iterable[str]) -> str:
    """Fila de píldoras de contexto (día, ejecuciones, datos hasta)."""
    return f'<div class="pildoras" style="margin:6px 0 10px">{"".join(pildoras)}</div>'


def encabezado(titulo: str, sub: str | None = None, fuente: str | None = None, punto: str = "") -> str:
    s = f'<span class="sub">{e(sub)}</span>' if sub else ""
    f = f'<span class="fte">{e(fuente)}</span>' if fuente else ""
    return f'<div class="ch"><span class="p {e(punto)}"></span><h3>{e(titulo)}</h3>{s}{f}</div>'


def kpis(items: Sequence[dict]) -> str:
    """items: dicts con l (etiqueta), v (valor ya formateado), u, ctx, fte, mal (bool)."""
    partes = []
    for k in items:
        sd = k.get("v") in (None, SIN_DATO)
        clase = "mal" if k.get("mal") else ("sd" if sd else "")
        partes.append(
            f'<div class="kpi {clase}"><div class="l">{e(k.get("l"))}</div>'
            f'<div class="v"><b>{e(k.get("v"))}</b><span>{e(k.get("u", ""))}</span></div>'
            + (f'<div class="ctx">{e(k["ctx"])}</div>' if k.get("ctx") else "")
            + (f'<div class="fte">{e(k["fte"])}</div>' if k.get("fte") else "") + "</div>")
    return f'<div class="kpis">{"".join(partes)}</div>'


FORMAS = {"ok": "cua", "nv": "tri", "av": "cir", "gr": "rom", "ac": "cua"}


def chip(texto, clase: str = "gr", forma: str | None = None) -> str:
    f = forma if forma is not None else FORMAS.get(clase, "")
    icono = f'<span class="{f}"></span>' if f else ""
    return f'<span class="chip {e(clase)}">{icono}{e(texto)}</span>'


def chip_viable(es_viable) -> str:
    if es_viable is True:
        return chip("Viable", "ok")
    if es_viable is False:
        return chip("No viable", "nv")
    return chip(SIN_DATO, "gr")


def chip_severidad(sev) -> str:
    return {"alta": chip("Alta", "nv"), "media": chip("Media", "av"),
            "baja": chip("Baja", "gr")}.get(sev, chip(sev, "gr", ""))


def chip_estado_alerta(est) -> str:
    clase = "ac" if est == "abierta" else ("gr" if est in ("cerrada", "descartada") else "ok")
    return chip(est, clase, "")


def chip_estado_modelo(est) -> str:
    return {"activo": chip("activo", "ok"), "candidato": chip("candidato", "ac"),
            "rechazado": chip("rechazado", "nv"), "retirado": chip("retirado", "gr")}.get(est, chip(est, "gr", ""))


def lista(items: Sequence[tuple]) -> str:
    """items: (titulo, valor, derecha, color_punto|None)."""
    filas = []
    for titulo, valor, der, color in items:
        p = f'<span class="p" style="background:{e(color)}"></span>' if color else '<span class="p"></span>'
        filas.append(f'<li>{p}<b>{e(titulo)}</b><span class="val" title="{e(valor)}">{e(valor)}</span>'
                     + (f'<span class="der">{e(der)}</span>' if der not in (None, "") else "") + "</li>")
    return f'<ul class="lista">{"".join(filas)}</ul>'


def leyenda(items: Sequence[tuple]) -> str:
    """items: (nombre, color, numero|None)."""
    return '<div class="leg">' + "".join(
        f'<span class="lp"><i style="background:{e(c)}"></i>{e(n)}'
        + (f'<span class="n">{e(v)}</span>' if v is not None else "") + "</span>"
        for n, c, v in items) + "</div>"


def conclusion(texto: str, clase: str) -> str:
    icono = {"ok": "cua", "nv": "tri", "av": "cir"}.get(clase, "cua")
    return f'<div class="conclusion {e(clase)}"><span class="{icono}"></span><div>{e(texto)}</div></div>'


def datos(pares: Sequence[tuple]) -> str:
    """pares: (etiqueta, valor) — el valor None se muestra «Sin dato» en gris."""
    celdas = []
    for etiqueta, valor in pares:
        sd = valor in (None, SIN_DATO)
        celdas.append(f'<div><span class="l">{e(etiqueta)}</span>'
                      f'<span class="v{" sd" if sd else ""}">{e(valor)}</span></div>')
    return f'<div class="datos">{"".join(celdas)}</div>'


def pasos(items: Sequence[tuple]) -> str:
    """items: (titulo, valor, nota, mal)."""
    return '<div class="pasos">' + "".join(
        f'<div class="{"mal" if mal else ""}"><span class="n">{i}</span><b>{e(t)}</b>'
        f'<div class="f">{e(v)}</div><small>{e(n)}</small></div>'
        for i, (t, v, n, mal) in enumerate(items, start=1)) + "</div>"


def zona(texto: str) -> str:
    return f'<div class="zona">{e(texto)}</div>'


OCULTAR_FUENTES = "<style>.fte{display:none!important}</style>"


def fecha_larga(d) -> str:
    """«viernes 20 de noviembre de 2026» sin depender del locale del sistema."""
    dias = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
    meses = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
             "octubre", "noviembre", "diciembre")
    return f"{dias[d.weekday()]} {d.day} de {meses[d.month - 1]} de {d.year}"


def vacio(texto: str) -> str:
    return f'<div class="vacio">{e(texto)}</div>'


def nota(texto: str) -> str:
    return f'<div class="nota">{e(texto)}</div>'


def marca_escritura(texto: str = "Acción que escribe") -> str:
    return f'<span class="escritura">{e(texto)}</span>'
