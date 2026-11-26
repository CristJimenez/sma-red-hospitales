# AGENTS.md

## Proyecto

SMA de abastecimiento hospitalario con dos situaciones: S1 (brote respiratorio,
traslado + compra) y S2 (lote por vencer, competencia A/B, timeout y reinicio
del Pronóstico). Python + Mesa 3.5.3 + capa FIPA-ACL propia. Entrega académica:
26 nov.

## Comandos

```powershell
& "C:\Users\123cr\AppData\Local\Temp\opencode\venv-sma\Scripts\python.exe" -m sma.run
& "C:\Users\123cr\AppData\Local\Temp\opencode\venv-sma\Scripts\python.exe" -m sma.run --situacion 2
& "C:\Users\123cr\AppData\Local\Temp\opencode\venv-sma\Scripts\python.exe" -m sma.diagrama
& "C:\Users\123cr\AppData\Local\Temp\opencode\venv-sma\Scripts\python.exe" -m pytest
& "C:\Users\123cr\AppData\Local\Temp\opencode\venv-sma\Scripts\python.exe" -m streamlit run app.py
```

El venv vive fuera de OneDrive a propósito. Para recrearlo:
`python -m venv <ruta>` + `pip install -r requirements.txt`.

## Arquitectura (lo no obvio)

- **Mesa 3.5.3**: `mesa.Model.__init__(rng=...)`, no `seed=` (deprecado).
  Los agentes heredan de `mesa.Agent` y se registran solos; `model.agents.do("step")`
  los activa en orden de creación. S1: inventario → pronóstico → coordinador →
  compras → supervisor. S2: inventario → pronóstico → coordinador → supervisor.
  No reordenar sin revisar el escenario.
- **Entrega diferida**: el bus entrega al inicio de la ronda siguiente. Un
  mensaje enviado en la ronda N se procesa en N+1. El escenario depende de ello
  (11 rondas en S1, 9 en S2 base). No "arreglarlo" para entrega inmediata.
- **La traza es la fuente de verdad**: `sma/trace.py` genera el Mermaid desde
  los eventos reales. `Traza(participantes, alias, autonumerar)` permite los
  participantes de cada situación (S2 no numera las flechas).
- **Verificación**: `sma/scenario/s1.py` (16 pasos) y `sma/scenario/s2.py`
  (19 pasos). `app.py` y los tests consumen esas funciones.
- **Decisión pura**: `sma/decision.py` (S1) y `sma/decision_s2.py` (S2) no
  conocen agentes ni mensajes. Si cambia una regla, se prueba ahí sin simular.
- **Variantes**: `config/variantes.yaml` y `config/variantes_s2.yaml` son
  overrides de `config/s1.yaml` y `config/s2.yaml`. Los tests parametrizan
  todas; no añadir casos por código.
- **Pronóstico compartido**: `sma/forecast.py` (Holt + estacionalidad) lo usan
  las dos situaciones.
- **Configuración**: `config/s1.yaml` y `config/s2.yaml`, catálogo abierto.

## Trampas del entorno

- Windows + PowerShell 5.1: sin `&&`; usar `;`. Forzar UTF-8
  (`chcp 65001`, `$env:PYTHONIOENCODING="utf-8"`).
- Streamlit Cloud debe usar **Python 3.12** (`runtime.txt`); Mesa exige ≥3.12.
- Sin claves de API ni LLM: no introducir servicios externos.

## No romper

- `pytest` debe quedar en verde (66 pruebas: flujos base, matrices de variantes,
  determinismo, decisiones puras, Mermaid y panel de ambas situaciones).
- La semilla fija debe producir siempre la misma traza.
- La traza se copia al registrarse: un mensaje no puede cambiar después de
  enviarse (afecta al diagrama y al informe).
- En S2, el lote se mueve como un único objeto: nunca puede quedar en dos
  hospitales a la vez.
