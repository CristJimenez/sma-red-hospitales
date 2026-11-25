# SMA de abastecimiento de medicamentos · Red de hospitales públicos

Sistema multiagente que reproduce la **Situación 1**: un brote respiratorio en
el Hospital A provoca riesgo de desabastecimiento de un antibiótico. Los
agentes detectan, pronostican, coordinan un traslado desde otro hospital y
completan la compra al proveedor alterno, mientras el Supervisor registra todo.

El diagrama de secuencia **se genera desde la traza real** de la ejecución, no
está dibujado a mano. `out/s1_secuencia.mmd` y `Diagrama.drawio` salen de los
mismos eventos; el segundo se regenera con `python -m sma.diagrama`.

## Qué demuestra

- Percepción distribuida: cada agente lee solo lo que le corresponde.
- Comunicación **FIPA-ACL**: `INFORM`, `REQUEST`, `AGREE`, `FAILURE`,
  `QUERY-REF`, `QUERY-IF`, con `conversation-id` y protocolo.
- Coordinación bajo incertidumbre: traslado + compra con presupuesto limitado.
- Negociación implícita: el Coordinador prioriza y elige proveedor.
- Supervisión: registro de eventos, disponibilidad y reporte de cierre.
- Reproducibilidad: semilla fija, misma traza en cada ejecución.

## Matriz de "y si"

La decisión del Coordinador vive en `sma/decision.py` como función pura y cada
caso es una variante declarativa en `config/variantes.yaml`. No se duplica el
escenario: solo se cambian los datos que provocan el caso.

| Variante | Situación | Decisión |
|---|---|---|
| `base` | Excedente parcial | Traslado + compra al alterno |
| `solo_traslado` | El excedente cubre todo | Solo traslado, sin orden |
| `solo_compra` | Sin excedente en la red | Solo compra |
| `sin_necesidad` | El stock cubre la demanda | Ninguna acción |
| `excedente_por_vencer` | Lote del donante caduca | Se descarta y se compra |
| `cadena_frio` | Frío sin transporte refrigerado | No se traslada; se compra |
| `proveedores_retrasados` | Ningún proveedor llega a tiempo | Traslado máximo + emergencia + escalado |
| `sin_donantes_ni_proveedores` | Sin salida | Escalado del riesgo |
| `presupuesto_insuficiente` | La compra no cabe | Replanifica y escala el residual |
| `compras_no_puede` | Compras rechaza | Replanifica con traslado de emergencia |
| `proveedor_habitual_ok` | El habitual cumple plazo | Compra al Proveedor 1 |
| `presupuesto_parcial` | Presupuesto corto | Compra parcial y residual |
| `dos_hospitales` | Dos hospitales compiten | Prioriza por agotamiento; dos órdenes |

```powershell
python -m sma.run --listar
python -m sma.run --variante solo_traslado
```

Cada variante se ejecuta en los tests de extremo a extremo y también con las
funciones puras de decisión (`tests/test_variantes.py`).

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
python -m sma.diagrama     # regenera Diagrama.drawio desde la traza
pytest                     # pruebas del escenario y ramas alternativas
streamlit run app.py       # panel web
```

El comando `python -m sma.run` genera además:

- `out/s1_traza.json` — todos los eventos y mensajes.
- `out/s1_secuencia.mmd` — diagrama Mermaid listo para el informe.

## Panel web

El panel permite:

- Elegir cualquiera de las variantes del escenario.
- Ver la traza por rondas y fases (A/B, C, D, E).
- Consultar las 16 verificaciones del flujo base.
- Comparar lo esperado con lo real en las variantes.
- Consultar la matriz completa de casos.
- Descargar la traza y el diagrama de secuencia (`.mmd`).

## Cómo probarlo paso a paso

Todo desde PowerShell, en la carpeta del proyecto.

```powershell
# 1. Entorno (fuera de OneDrive para evitar bloqueos de sincronización)
python -m venv C:\Users\123cr\.venvs\sma-red-hospitales
$py = "C:\Users\123cr\.venvs\sma-red-hospitales\Scripts\python.exe"

# 2. Dependencias
& $py -m pip install -r requirements.txt

# 3. Pruebas automáticas -> debe decir "41 passed"
& $py -m pytest

# 4. Escenario por consola -> debe mostrar 16 líneas [OK]
& $py -m sma.run

# 4b. Cualquier "y si"
& $py -m sma.run --variante solo_traslado
& $py -m sma.run --listar

# 5. Panel web -> abre http://localhost:8501
& $py -m streamlit run app.py
```

Qué mirar:

- En `python -m sma.run`, la sección **Métricas** debe dar cobertura `1.0`,
  orden `confirmada`, traslado `470`, compra `110` y presupuesto restante
  positivo.
- En el panel, pestaña **Verificación**: 16/16 en verde.
- Pestaña **Traza**: métricas, decisión del Coordinador y descarga del diagrama
  en `.mmd` para el informe. El dibujo completo está en `Diagrama.drawio`.
- Selector **Variante**: elige `proveedores_retrasados` o `presupuesto_parcial`
  y mira cómo cambia la decisión, el riesgo residual y la traza.
- Pestaña **Matriz de casos**: las 13 variantes con su decisión esperada.

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
config/variantes.yaml   matriz de "y si" como overrides del escenario base
sma/acl.py              mensajes y performativas FIPA-ACL
sma/bus.py              bus en proceso con entrega por rondas
sma/trace.py            traza + exportación a Mermaid
sma/diagrama.py         exportación de la traza a draw.io (Diagrama.drawio)
sma/decision.py         planificador puro: traslado, compra, escalado
sma/variantes.py        carga de variantes declarativas
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
- Con varios riesgos, el Coordinador los atiende en cola por días hasta el
  agotamiento. Un hospital en riesgo o recién abastecido no actúa como donante.
- La emergencia libera el colchón logístico, pero respeta el stock de seguridad.
- El transporte ACL es en proceso. Sustituirlo por XMPP no requiere tocar a los
  agentes, solo el adaptador del bus.
- No se usa ningún LLM ni servicio externo: sin claves y sin coste.
