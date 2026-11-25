# AGENTS.md

## Proyecto

SMA de abastecimiento hospitalario (Situación 1: brote respiratorio). Python +
Mesa 3.5.3 + capa FIPA-ACL propia. Entrega académica: 26 nov.

## Comandos

```powershell
& "C:\Users\123cr\AppData\Local\Temp\opencode\venv-sma\Scripts\python.exe" -m sma.run
& "C:\Users\123cr\AppData\Local\Temp\opencode\venv-sma\Scripts\python.exe" -m sma.diagrama
& "C:\Users\123cr\AppData\Local\Temp\opencode\venv-sma\Scripts\python.exe" -m pytest
& "C:\Users\123cr\AppData\Local\Temp\opencode\venv-sma\Scripts\python.exe" -m streamlit run app.py
```

El venv vive fuera de OneDrive a propósito. Para recrearlo:
`python -m venv <ruta>` + `pip install -r requirements.txt`.

## Arquitectura (lo no obvio)

- **Mesa 3.5.3**: `mesa.Model.__init__(rng=...)`, no `seed=` (deprecado).
  Los agentes heredan de `mesa.Agent` y se registran solos; `model.agents.do("step")`
  los activa en orden de creación (inventario → pronóstico → coordinador →
  compras → supervisor). No reordenar sin revisar el escenario.
- **Entrega diferida**: el bus entrega al inicio de la ronda siguiente. Un
  mensaje enviado en la ronda N se procesa en N+1. El escenario depende de ello
  (11 rondas). No "arreglarlo" para entrega inmediata.
- **La traza es la fuente de verdad**: `sma/trace.py` genera el Mermaid desde
  los eventos reales. No mantener un diagrama aparte.
- **Verificación**: `sma/scenario/s1.py` contiene los 16 pasos comprobables.
  `app.py` y los tests consumen la misma función `verificar()`.
- **Decisión pura**: `sma/decision.py` no conoce agentes ni mensajes. Si cambia
  una regla, se prueba ahí sin simular rondas.
- **Variantes**: `config/variantes.yaml` son overrides de `config/s1.yaml`.
  `tests/test_variantes.py` parametriza todas; no añadir casos por código.
- **Configuración**: `config/s1.yaml`, catálogo abierto (N medicamentos).

## Trampas del entorno

- Windows + PowerShell 5.1: sin `&&`; usar `;`. Forzar UTF-8
  (`chcp 65001`, `$env:PYTHONIOENCODING="utf-8"`).
- Streamlit Cloud debe usar **Python 3.12** (`runtime.txt`); Mesa exige ≥3.12.
- Sin claves de API ni LLM: no introducir servicios externos.

## No romper

- `pytest` debe quedar en verde (41 pruebas: flujo base, matriz de variantes,
  determinismo, decisiones puras, Mermaid y panel).
- La semilla fija debe producir siempre la misma traza.
- La traza se copia al registrarse: un mensaje no puede cambiar después de
  enviarse (afecta al diagrama y al informe).
