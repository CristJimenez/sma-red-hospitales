# SMA de abastecimiento de medicamentos · Red de hospitales públicos

Sistema multiagente con **dos situaciones** que se eligen desde el mismo panel:

- **Situación 1:** un brote respiratorio en el Hospital A provoca riesgo de
  desabastecimiento. Los agentes detectan, pronostican, coordinan un traslado
  desde otro hospital y completan la compra al proveedor alterno.
- **Situación 2:** un lote de amoxicilina está por vencer en el Hospital C y los
  hospitales A y B compiten por él. El Agente de Pronóstico deja de responder,
  el Supervisor detecta el timeout y lo reinicia, y el Coordinador decide con la
  última estimación o con el historial de consumo.

Los diagramas de secuencia **salen de la traza real** de cada ejecución. En la
Situación 1, `out/s1_secuencia.mmd` y `out/s1_secuencia.drawio` se generan de los
mismos eventos; el segundo se regenera con `python -m sma.diagrama`. El dibujo
del informe es `Diagrama1.drawio`. En la Situación 2, `out/s2_secuencia.mmd` se
descarga desde el panel y el dibujo del informe es `Diagrama2.drawio`.

## Qué demuestra

- Percepción distribuida: cada agente lee solo lo que le corresponde.
- Comunicación **FIPA-ACL**: `INFORM`, `REQUEST`, `AGREE`, `REFUSE`, `FAILURE`,
  `QUERY-REF`, `QUERY-IF`, con `conversation-id` y protocolo.
- Coordinación bajo incertidumbre: traslado + compra con presupuesto limitado.
- **Competencia por un recurso escaso:** un lote solo puede ir a un hospital;
  el Coordinador compara urgencias y reasigna si el traslado se rechaza.
- **Tolerancia a fallos:** el Supervisor detecta el timeout, notifica, reinicia
  al Pronóstico y escala si el reinicio falla, sin detener la operación.
- Reproducibilidad: semilla fija, misma traza en cada ejecución.

## Matriz de "y si" de la Situación 1

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

## Matriz de "y si" de la Situación 2

Las reglas puras están en `sma/decision_s2.py` y los casos en
`config/variantes_s2.yaml`.

| Variante | Situación | Resultado |
|---|---|---|
| `s2_base` | Timeout del Pronóstico | Se reinicia y el lote va a A |
| `s2_pronostico_ok` | El Pronóstico responde | Decide con la proyección |
| `s2_traslado_rechazado` | Inventario rechaza el traslado | Reasigna el lote a B |
| `s2_reinicio_falla` | El reinicio responde `FAILURE` | Escala a intervención manual |
| `s2_sin_receptor` | A y B rechazan el lote | Escala y el lote queda en C |
| `s2_sin_estimacion` | El Pronóstico cae antes de estimar | Usa el historial de consumo |
| `s2_sin_riesgo` | El lote no está por vencer | No hay traslado ni incidente |

```powershell
python -m sma.run --listar
python -m sma.run --variante solo_traslado
python -m sma.run --situacion 2 --listar
python -m sma.run --situacion 2 --variante s2_pronostico_ok
```

Cada variante se ejecuta en los tests de extremo a extremo y también con las
funciones puras de decisión (`tests/test_variantes.py`, `tests/test_s2.py`).

## Arquitectura

| Concepto MAS-ML | Situación 1 | Situación 2 |
|---|---|---|
| Environment | `RedHospitalaria` (`sma/model.py`) | `RedHospitalariaS2` (`sma/model_s2.py`) |
| Organization | `SistemaAbastecimiento` | `SistemaLoteCompartido` |
| Roles | Inventario, Pronóstico, Coordinador, Compras, Supervisor | Inventario, Pronóstico, Coordinador, Supervisor |
| Object | `Lote`, `OrdenCompra`, `Proveedor` | `Lote` (objeto que cambia de hospital) |
| Relaciones | Control del Supervisor; dependencia de Compras | Control del Supervisor; competencia A/B por el lote |

**Stack:** Mesa 3.5.3 (framework de simulación multiagente: modelo, agentes,
activación y semilla) + una capa FIPA-ACL propia (`sma/acl.py`, `sma/bus.py`),
porque Mesa no implementa el estándar de comunicación.

El bus entrega los mensajes al inicio de la ronda siguiente. Eso hace
determinista el orden de las conversaciones y reproduce las rondas del
diagrama de secuencia: 11 rondas para la Situación 1 y 9 para el flujo base de
la Situación 2.

## Ejecutar en local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python -m sma.run                    # Situación 1 por consola
python -m sma.run --situacion 2      # Situación 2 por consola
python -m sma.diagrama               # regenera out/s1_secuencia.drawio (S1)
pytest                               # pruebas de ambas situaciones
streamlit run app.py                 # panel web con selector
```

`python -m sma.run` genera además:

- `out/s1_traza.json` / `out/s1_secuencia.mmd` — Situación 1.
- `out/s2_traza.json` / `out/s2_secuencia.mmd` — Situación 2.

## Panel web

El panel permite:

- **Cambiar entre Situación 1 y Situación 2** en la barra lateral.
- Elegir cualquiera de las variantes de la situación activa.
- Ver la traza por rondas y fases (A/B, C, D, E).
- Consultar las 16 verificaciones de la S1 y las 19 de la S2.
- Comparar lo esperado con lo real en las variantes.
- Consultar la matriz completa de casos.
- Descargar la traza y el diagrama de secuencia (`.mmd`).

En la Situación 2 el panel muestra el lote asignado, el faltante, el riesgo
residual, si hubo timeout y el resultado del reinicio.

## Cómo probarlo paso a paso

Todo desde PowerShell, en la carpeta del proyecto.

```powershell
# 1. Entorno (fuera de OneDrive para evitar bloqueos de sincronización)
python -m venv C:\Users\123cr\.venvs\sma-red-hospitales
$py = "C:\Users\123cr\.venvs\sma-red-hospitales\Scripts\python.exe"

# 2. Dependencias
& $py -m pip install -r requirements.txt

# 3. Pruebas automáticas -> debe decir "66 passed"
& $py -m pytest

# 4. Situación 1 -> 16 líneas [OK]
& $py -m sma.run

# 4b. Cualquier "y si" de la S1
& $py -m sma.run --variante solo_traslado
& $py -m sma.run --listar

# 5. Situación 2 -> 19 líneas [OK]
& $py -m sma.run --situacion 2

# 5b. Cualquier "y si" de la S2
& $py -m sma.run --situacion 2 --variante s2_traslado_rechazado
& $py -m sma.run --situacion 2 --listar

# 6. Panel web -> abre http://localhost:8501
& $py -m streamlit run app.py
```

Qué mirar:

- En la S1, la sección **Métricas** debe dar cobertura `1.0`, orden
  `confirmada`, traslado `470`, compra `110` y presupuesto restante positivo.
- En la S2 base, el lote `L-C-001` (200 uds) debe quedar asignado a `H_A`,
  `H_B` en lista de espera, timeout detectado y reinicio `exitoso`.
- En el panel, pestaña **Verificación**: 16/16 en S1 y 19/19 en S2.
- Pestaña **Traza**: métricas, decisión del Coordinador y descarga del diagrama
  en `.mmd`. Los dibujos completos son `Diagrama1.drawio` y
  `Diagrama2.drawio`.
- Selector **Situación**: cambia a la S2 y prueba `s2_reinicio_falla` o
  `s2_sin_receptor` para ver el escalado.
- Pestaña **Matriz de casos**: las 13 variantes de S1 o las 7 de S2.

## Despliegue gratuito (Streamlit Community Cloud)

Demo: <https://sma-red-hospitales-aawy4zv7fgovymwsyfkx74.streamlit.app/>

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
config/s1.yaml             catálogo abierto, hospitales y proveedores (S1)
config/variantes.yaml      matriz de "y si" de la S1
config/s2.yaml             hospitales, lote en riesgo y opciones (S2)
config/variantes_s2.yaml   matriz de "y si" de la S2
sma/acl.py                 mensajes y performativas FIPA-ACL
sma/bus.py                 bus en proceso con entrega por rondas
sma/trace.py               traza + exportación a Mermaid (participantes por escenario)
sma/diagrama.py            traza S1 → out/s1_secuencia.drawio
sma/forecast.py            Holt + estacionalidad compartido por S1 y S2
sma/decision.py            planificador puro de la S1
sma/decision_s2.py         urgencia, prioridad y traslado del lote (S2)
sma/variantes.py           carga de variantes de la S1
sma/variantes_s2.py        carga de variantes de la S2
sma/domain/models.py       Lote, OrdenCompra, Proveedor, Hospital
sma/model.py               RedHospitalaria (entorno Mesa de la S1)
sma/model_s2.py            RedHospitalariaS2 (entorno Mesa de la S2)
sma/agents/                los cinco agentes de la S1
sma/agents/s2/             los cuatro agentes de la S2
sma/scenario/s1.py         verificación paso a paso de la S1
sma/scenario/s2.py         verificación paso a paso de la S2
sma/run.py                 ejecución y CLI de ambas situaciones
app.py                     panel Streamlit con selector
tests/                     pruebas
```

## Configuración

El catálogo **no está limitado a cinco medicamentos**: añade una entrada en
`config/s1.yaml` (medicamento, inventario por hospital y precios de proveedor)
y aparece en todo el sistema. Los umbrales se derivan de `stock_seguridad_dias`
y del consumo diario; el excedente descuenta el stock de seguridad y un colchón
logístico de dos días.

La Situación 2 se configura en `config/s2.yaml`: hospitales y consumos, lote en
riesgo (`lote_riesgo`), umbral de vencimiento y opciones (`pronostico_caido`,
`ronda_fallo_pronostico`, `reinicio_falla`, `rechazos_traslado`).

## Alcance y limitaciones

- La compra termina en orden **confirmada**; no se simula la entrega física.
- El traslado del lote en la S2 es inmediato en la misma ronda; no se modela el
  tiempo de transporte entre hospitales.
- El fallo del Pronóstico es un timeout de consulta: el agente conserva su
  última estimación y el Supervisor lo reinicia con el protocolo FIPA-Request.
- Con varios riesgos, el Coordinador de la S1 los atiende en cola por días hasta
  el agotamiento. Un hospital en riesgo o recién abastecido no actúa como donante.
- La emergencia libera el colchón logístico, pero respeta el stock de seguridad.
- El transporte ACL es en proceso. Sustituirlo por XMPP no requiere tocar a los
  agentes, solo el adaptador del bus.
- No se usa ningún LLM ni servicio externo: sin claves y sin coste.
