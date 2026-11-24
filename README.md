# SMA de abastecimiento de medicamentos · Red de hospitales públicos

Sistema multiagente que reproduce la **Situación 1**: un brote respiratorio en
el Hospital A provoca riesgo de desabastecimiento de un antibiótico. Los
agentes detectan, pronostican, coordinan un traslado desde otro hospital y
completan la compra al proveedor alterno, mientras el Supervisor registra todo.

El diagrama de secuencia **se genera desde la traza real** de la ejecución, no
está dibujado a mano.

## Qué demuestra

- Percepción distribuida: cada agente lee solo lo que le corresponde.
- Comunicación **FIPA-ACL**: `INFORM`, `REQUEST`, `AGREE`, `FAILURE`,
  `QUERY-REF`, `QUERY-IF`, con `conversation-id` y protocolo.
- Coordinación bajo incertidumbre: traslado + compra con presupuesto limitado.
- Negociación implícita: el Coordinador prioriza y elige proveedor.
- Supervisión: registro de eventos, disponibilidad y reporte de cierre.
- Reproducibilidad: semilla fija, misma traza en cada ejecución.

## Arquitectura

| Concepto MAS-ML | Implementación |
|---|---|
| Environment | `RedHospitalaria` (`sma/model.py`), entorno compartido |
| Organization | `SistemaAbastecimiento`: los cinco roles del escenario |
| Role | Monitor de Inventario, Pronosticador, Coordinador, Comprador, Supervisor |
| Agent | Clases que heredan de `mesa.Agent` (`sma/agents/`) |
| Object | `Lote`, `OrdenCompra`, `Proveedor` (`sma/domain/models.py`) |
| Relaciones | Control del Supervisor, dependencia de Compras respecto al Coordinador, propiedad de objetos del dominio |

**Stack:** Mesa 3.5.3 (framework de simulación multiagente: modelo, agentes,
activación y semilla) + una capa FIPA-ACL propia (`sma/acl.py`, `sma/bus.py`),
porque Mesa no implementa el estándar de comunicación.

El bus entrega los mensajes al inicio de la ronda siguiente. Eso hace
determinista el orden de las conversaciones y reproduce las rondas del
diagrama de secuencia (11 rondas para el flujo completo).

## Ejecutar en local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python -m sma.run          # traza, métricas y verificación por consola
pytest                     # pruebas del escenario y ramas alternativas
streamlit run app.py       # panel web
```

El comando `python -m sma.run` genera además:

- `out/s1_traza.json` — todos los eventos y mensajes.
- `out/s1_secuencia.mmd` — diagrama Mermaid listo para el informe.

## Panel web

El panel permite:

- Ejecutar el escenario con un clic.
- Ver la traza por rondas y fases (A/B, C, D, E).
- Consultar las 16 verificaciones del flujo.
- Ver el diagrama de secuencia generado y descargarlo.
- Activar ramas alternativas: presupuesto insuficiente, Compras no puede
  gestionar, agente caído.

## Cómo probarlo paso a paso

Todo desde PowerShell, en la carpeta del proyecto.

```powershell
# 1. Entorno (fuera de OneDrive para evitar bloqueos de sincronización)
python -m venv C:\Users\123cr\.venvs\sma-red-hospitales
$py = "C:\Users\123cr\.venvs\sma-red-hospitales\Scripts\python.exe"

# 2. Dependencias
& $py -m pip install -r requirements.txt

# 3. Pruebas automáticas -> debe decir "6 passed"
& $py -m pytest

# 4. Escenario por consola -> debe mostrar 16 líneas [OK]
& $py -m sma.run

# 5. Panel web -> abre http://localhost:8501
& $py -m streamlit run app.py
```

Qué mirar:

- En `python -m sma.run`, la sección **Métricas** debe dar cobertura `1.0`,
  orden `confirmada` y presupuesto restante positivo.
- En el panel, pestaña **Verificación**: 16/16 en verde.
- Pestaña **Diagrama de secuencia**: se dibuja desde la traza. Descárgalo en
  `.mmd` para el informe.
- Barra lateral: activa **Forzar presupuesto insuficiente** o **Compras no puede
  gestionar la compra** y pulsa **Re-ejecutar**. Verás el `FAILURE`
  correspondiente y ninguna orden generada.

## Despliegue gratuito (Streamlit Community Cloud)

1. Sube el repo a GitHub como `sma-red-hospitales`.
2. Entra en <https://share.streamlit.io> → **New app**.
3. Repositorio `sma-red-hospitales`, rama `main`, archivo `app.py`.
4. En **Advanced settings** elige **Python 3.12** (Mesa exige ≥3.12;
   `runtime.txt` lo deja fijado).
5. **Deploy**. Obtienes una URL pública sin coste.

La app se suspende por inactividad y despierta al visitarla; ábrela un par de
minutos antes de la demo.

## Estructura

```
config/s1.yaml          catálogo abierto de medicamentos, hospitales, proveedores
sma/acl.py              mensajes y performativas FIPA-ACL
sma/bus.py              bus en proceso con entrega por rondas
sma/trace.py            traza + exportación a Mermaid
sma/domain/models.py    Lote, OrdenCompra, Proveedor, Hospital
sma/model.py            RedHospitalaria (entorno Mesa)
sma/agents/             los cinco agentes
sma/scenario/s1.py      verificación paso a paso del escenario
sma/run.py              ejecución y CLI
app.py                  panel Streamlit
tests/                  pruebas
```

## Configuración

El catálogo **no está limitado a cinco medicamentos**: añade una entrada en
`config/s1.yaml` (medicamento, inventario por hospital y precios de proveedor)
y aparece en todo el sistema. Los umbrales se derivan de `stock_seguridad_dias`
y del consumo diario; el excedente descuenta el stock de seguridad y un colchón
logístico de dos días.

## Alcance y limitaciones

- La compra termina en orden **confirmada**; no se simula la entrega física.
- El reinicio de agentes (`solicitarReinicio`) queda fuera: pertenece a la
  Situación 2. El Supervisor sí notifica fallos.
- El transporte ACL es en proceso. Sustituirlo por XMPP no requiere tocar a los
  agentes, solo el adaptador del bus.
- No se usa ningún LLM ni servicio externo: sin claves y sin coste.
