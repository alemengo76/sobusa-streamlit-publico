"""Feature engineering FE 3.1 con reglas comun-1.5: la MISMA referencia para entrenar y predecir.

reglas_comunes.py y conjunto_entrenamiento.py son copias EXACTAS de fe_v4_comun15 (no se
editan aquí). Sus huellas están en HUELLAS y tests/unit/test_fe31.py las verifica: si alguien
actualiza el FE, debe copiar los dos archivos de nuevo y actualizar las huellas, a propósito.

conjunto_entrenamiento.py hace `from reglas_comunes import ...` (import de primer nivel, como en
el cuaderno). Para no editarlo, se registra este mismo módulo bajo ese nombre antes de importarlo:
así existe un solo objeto reglas_comunes y un solo REGLAS.
"""
import importlib
import sys

rc = importlib.import_module("app.fe31.reglas_comunes")
sys.modules.setdefault("reglas_comunes", rc)
ce = importlib.import_module("app.fe31.conjunto_entrenamiento")

REGLAS_VERSION = rc.REGLAS["version"]          # comun-1.5
FEATURE_VERSION = ce.VERSION                   # sobusa-fe-3.1

HUELLAS = {
    "reglas_comunes.py": "4ede9d0a6ccac2eb5b00befca8bdd29059c946342335ba66bb931bb5d9eb090d",
    "conjunto_entrenamiento.py": "fb7a0ce103c70adf08ce15902c35012cb5df8420e990bc315d0239ee5a12df5d",
}

# tipo_dia del FE -> tipo_dia de ai_frecuencias.parametro_operativo (CHECK de la tabla)
TIPO_DIA_PARAMETROS = {"laboral": "laboral", "sabado": "sabado", "dom_festivo": "domingo_festivo"}
