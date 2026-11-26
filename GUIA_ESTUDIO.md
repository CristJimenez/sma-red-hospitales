# Guía de estudio · SMA de abastecimiento hospitalario

Documento único para estudiar, exponer y defender el proyecto. Todo lo que
aparece aquí está sacado del código y de la traza real: si cambias una regla,
cambia la guía.

- **Entrega:** 26 de noviembre.
- **Stack:** Python 3.12 + Mesa 3.5.3 + capa FIPA-ACL propia + Streamlit.
- **Demo:** <https://sma-red-hospitales-aawy4zv7fgovymwsyfkx74.streamlit.app/>
- **Repositorio:** `CristJimenez/sma-red-hospitales` (rama `main`).
- **Pruebas:** 66 (3 panel + 6 S1 + 23 S2 + 34 variantes).

---

## 1. Qué es el proyecto en una frase

Una red de tres hospitales públicos se coordina mediante **agentes autónomos que
hablan FIPA-ACL** para evitar que falte un medicamento crítico, resolviendo dos
situaciones distintas: un brote que dispara la demanda (S1) y un lote que caduca
mientras dos hospitales compiten por él, con un agente que falla (S2).

La idea que hay que transmitir: **no es una simulación de stock, es un sistema
multiagente**. El stock es el pretexto; lo que se evalúa es la organización, la
comunicación, la coordinación y la tolerancia a fallos.

---

## 2. Cómo ejecutar (chuleta)

```powershell
# Entorno (fuera de OneDrive a propósito: evita bloqueos de sincronización)
python -m venv C:\Users\123cr\.venvs\sma-red-hospitales
$py = "C:\Users\123cr\.venvs\sma-red-hospitales\Scripts\python.exe"
& $py -m pip install -r requirements.txt

& $py -m pytest                      # 66 pruebas
& $py -m sma.run                     # Situación 1 (16 pasos [OK])
& $py -m sma.run --situacion 2       # Situación 2 (19 pasos [OK])
& $py -m sma.run --listar            # las 13 variantes de S1
& $py -m sma.run --situacion 2 --listar   # las 7 variantes de S2
& $py -m streamlit run app.py        # panel en http://localhost:8501
```

En este equipo el intérprete del venv es:

```powershell
& "C:\Users\123cr\AppData\Local\Temp\opencode\venv-sma\Scripts\python.exe" -m pytest
```

Salidas que genera `sma.run`:

| Archivo | Contenido |
|---|---|
| `out/s1_traza.json` | traza completa de la S1 |
| `out/s1_secuencia.mmd` | diagrama Mermaid de la S1 |
| `out/s2_traza.json` | traza completa de la S2 |
| `out/s2_secuencia.mmd` | diagrama Mermaid de la S2 |

`Diagrama1.drawio` (S1) y `Diagrama2.drawio` (S2) son los dibujos del informe.
La versión generada desde la traza se escribe en `out/s1_secuencia.drawio` con
`python -m sma.diagrama`.

---

## 3. Marco conceptual mínimo (lo que te pueden preguntar de teoría)

### 3.1 Sistema multiagente (SMA)

Un SMA es un conjunto de agentes que:

- **perciben** su entorno de forma parcial,
- **actúan** sobre él,
- **deciden** con información incompleta,
- y **se comunican** para coordinar sus objetivos.

Propiedades que el proyecto demuestra: autonomía, reactividad, proactividad,
cooperación y distribución del control (no hay un cerebro central que lo sepa
todo).

### 3.2 MAS-ML (la metodología)

MAS-ML extiende UML para modelar sistemas multiagente. Sus elementos y su
traducción al proyecto:

| Concepto MAS-ML | En el proyecto | Archivo |
|---|---|---|
| **Environment** | la red de hospitales (hospitales, lotes, proveedores, órdenes) | `sma/model.py`, `sma/model_s2.py` |
| **Organization** | `SistemaAbastecimiento` (S1) / `SistemaLoteCompartido` (S2) | diagramas del informe |
| **Role** | Inventario, Pronóstico, Coordinador, Compras, Supervisor | `sma/agents/` |
| **Agent** | la instancia que desempeña un rol | `sma/agents/*.py` |
| **Object** | `Lote`, `OrdenCompra`, `Proveedor` | `sma/domain/models.py` |
| **Relación de control** | Supervisor → resto (monitorea y reporta) | mensajes `INFORM` al Supervisor |
| **Relación de dependencia** | Coordinador → Inventario / Pronóstico / Compras | `QUERY-REF`, `REQUEST` |
| **Relación de asociación** | hospital ↔ lote | `Hospital.lotes` |

Lo importante para la defensa: **los roles son estables, los agentes que los
desempeñan son instancias**. En la S2 el rol Compras no existe; por eso hay dos
organizaciones distintas, no una con un agente de más.

### 3.3 FIPA-ACL (el estándar de comunicación)

Un mensaje ACL no es un string: es una estructura con performativa, emisor,
receptor, contenido, protocolo y correlación de conversación.

Lo implementado en `sma/acl.py`:

| Campo | Para qué sirve |
|---|---|
| `performativa` | la intención del mensaje (`inform`, `request`, …) |
| `emisor` / `receptor` | quién habla y a quién |
| `contenido` | el payload (dict) |
| `protocolo` | `fipa-request`, `fipa-query`, `fipa-query-if` |
| `conversation_id` | agrupa los mensajes de una misma conversación |
| `reply_with` / `in_reply_to` | correlaciona pregunta y respuesta |

**Performativas usadas** (las 7 del proyecto):

| Performativa | Significado | Ejemplo en el proyecto |
|---|---|---|
| `INFORM` | informar un hecho | Inventario avisa el riesgo |
| `REQUEST` | pedir una acción | Coordinador pide preparar el traslado |
| `AGREE` | aceptar | Inventario acepta el traslado |
| `REFUSE` | rechazar sin poder cumplir | Inventario rechaza el traslado (S2) |
| `FAILURE` | intentó y falló | Pronóstico no puede reiniciarse (S2) |
| `QUERY-REF` | preguntar por un valor | "¿cuál es el stock de A y B?" |
| `QUERY-IF` | preguntar por una verdad | "¿la orden está confirmada?" |

**Protocolos FIPA** que se reconocen: `fipa-request` (REQUEST → AGREE/REFUSE →
INFORM/FAILURE) y `fipa-query` (QUERY-REF → INFORM). El `QUERY-IF` usa
`fipa-query-if`.

### 3.4 Mesa (el framework)

Mesa aporta tres cosas y solo tres:

1. `mesa.Model` con **semilla** (`rng=`), que da reproducibilidad.
2. `mesa.Agent` con **registro automático**: al crear el agente queda en
   `model.agents`.
3. `model.agents.do("step")`: activa a todos los agentes **en orden de
   creación**, una vez por ronda.

Mesa **no** trae FIPA-ACL ni bus de mensajes; por eso hay una capa propia
(`sma/acl.py`, `sma/bus.py`). Esto es una decisión de diseño, no un parche.

### 3.5 Entrega diferida (la decisión que explica todo)

El bus **no entrega en el acto**: un mensaje enviado en la ronda N se entrega al
inicio de la ronda N+1 (`sma/bus.py`).

Consecuencias:

- El orden de las conversaciones es **determinista**.
- Se modela la latencia real de la comunicación.
- Las rondas del diagrama de secuencia **coinciden** con las del código.
- S1 tarda 11 rondas y S2 tarda 9 por la **cadena de dependencias**, no por
  casualidad.

Si alguien propone "entregar inmediato", la respuesta es: se rompe la
correspondencia con el diagrama y el determinismo, y el escenario deja de
parecerse a una conversación real.

---

## 4. Arquitectura del código (mapa para estudiar)

Esta sección es el mapa del repositorio: qué hace cada archivo, en qué orden
leerlo y dónde tocar cuando quieras cambiar algo. Si solo tienes dos horas,
lee **4.1**, **4.4** y **4.6**; con eso puedes defender el flujo completo.

### 4.1 Las cinco capas

```
config/*.yaml            DATOS      hospitales, stock, precios, variantes
sma/domain/models.py     DOMINIO    Hospital, Lote, Proveedor, OrdenCompra
sma/decision*.py         REGLAS     funciones puras: estado → plan
sma/agents/*.py          ROLES      perciben, aplican el plan y hablan FIPA
sma/model*.py + bus.py   ENTORNO    rondas Mesa, entrega diferida, acciones
sma/trace.py             EVIDENCIA  todo queda registrado para el informe
app.py / sma/run.py      INTERFAZ   panel Streamlit y consola
```

Regla de dependencias: **cada capa solo importa hacia abajo**. `decision.py` no
conoce agentes ni mensajes; `trace.py` no conoce el modelo; `domain/models.py`
no importa nada del proyecto. Si aparece un import "hacia arriba", es un error
de diseño, no una optimización.

### 4.2 Ruta de lectura en 9 pasos

No leas los archivos en orden alfabético: se entiende mejor de los datos hacia
la interfaz.

| Paso | Lee | Pregunta que responde | ~Tiempo |
|---|---|---|---|
| 1 | `config/s1.yaml` + `config/variantes.yaml` | ¿con qué datos juega la S1 y qué casos existen? | 15 min |
| 2 | `sma/domain/models.py` | ¿qué es un lote, un umbral, un excedente, un plazo efectivo? | 20 min |
| 3 | `sma/acl.py` + `sma/bus.py` | ¿qué es un mensaje y cuándo se entrega? | 15 min |
| 4 | `sma/model.py` (`__init__`, `step`, `trasladar`, `crear_orden`) | ¿quién activa a los agentes y cómo cambia el entorno? | 20 min |
| 5 | `sma/agents/base.py` + `sma/agents/inventario.py` | ¿cómo es un agente por dentro? | 15 min |
| 6 | `sma/decision.py` + `sma/agents/coordinador.py` | ¿dónde está el "cerebro" de la S1? | 40 min |
| 7 | `sma/agents/compras.py` + `pronostico.py` + `supervisor.py` | ¿quién compra, quién proyecta y quién vigila? | 30 min |
| 8 | `sma/trace.py` + `sma/scenario/s1.py` | ¿cómo se convierte la ejecución en evidencia? | 20 min |
| 9 | `config/s2.yaml` → `model_s2.py` → `decision_s2.py` → `agents/s2/` | ¿qué cambia en la S2? | 60 min |

Total: unas 4 horas. El día de la defensa basta con releer **4.6** y el
**checklist 4.10**.

### 4.3 Archivo por archivo: qué es cada cosa

**Datos** (aquí no hay lógica; cambiar un número cambia la simulación):

| Archivo | Qué contiene |
|---|---|
| `config/s1.yaml` | Escenario S1 completo: semilla, presupuesto, 5 medicamentos, 3 hospitales con inventario y consumo, 2 proveedores, evento de brote y opciones. |
| `config/variantes.yaml` | Las 13 variantes de S1: `overrides` sobre `s1.yaml` + `esperado` (lo que el test debe ver). |
| `config/s2.yaml` | Escenario S2: lote en riesgo, umbral de vencimiento, caída y reinicio del Pronóstico, rechazos de traslado. |
| `config/variantes_s2.yaml` | Las 7 variantes de S2, con la misma estructura. |

**Dominio** — `sma/domain/models.py`:

- `Medicamento`: crítico, cadena de frío, precio de referencia, vida útil.
- `Lote`: cantidad, vencimiento y hospital dueño; `a_dict()` para la traza.
- `Hospital`: `stock()`, `umbral()`, `consumo_efectivo()`,
  `dias_hasta_agotamiento()`, `excedente()`, `lotes_proximos_a_vencer()`,
  `retirar()` y `agregar()`. Aquí viven las fórmulas del informe.
- `Proveedor`: `precio()`, `plazo_efectivo()` = entrega + retraso.
- `OrdenCompra`: `OC-001`, cantidad, proveedor, coste y estado.
- `Evento`, `Opciones`, `Configuracion`: el resto de `s1.yaml` ya tipado.

**Comunicación**:

| Archivo | Qué hay dentro |
|---|---|
| `sma/acl.py` | Constantes `INFORM`, `REQUEST`, `AGREE`, `REFUSE`, `FAILURE`, `QUERY_REF`, `QUERY_IF`; protocolos `fipa-*`; `MensajeACL` con `resumen()` y `a_dict()`. |
| `sma/bus.py` | `enviar()` asigna `seq` y `ronda`, guarda en `pendientes` y registra en la traza; `entregar()` devuelve la lista y la vacía. **Toda la entrega diferida cabe en 33 líneas.** |

**Decisión pura** (sin agentes, sin mensajes, sin reloj):

| Archivo | Qué hay dentro |
|---|---|
| `sma/decision.py` | `Donante`, `Oferta`, `Plan`; `_motivo_descarte()`, `seleccionar_traslado()`, `decidir_accion()`, `elegir_proveedor()`, `planificar()`. Constantes: margen 1 día, vida mínima 2 días, penalización 0.5 €/día. |
| `sma/decision_s2.py` | `Urgencia`, `PlanTraslado`; `demanda_sustituta()`, `calcular_urgencias()`, `elegir_hospital_prioritario()`, `planificar_traslado()`, `hospital_alterno()`. |
| `sma/forecast.py` | `holt()`, `factores_estacionales()`, `mape()`, `proyectar()`. Lo comparten S1 y S2. |

**Entorno y carga**:

| Archivo | Qué hay dentro |
|---|---|
| `sma/model.py` | `RedHospitalaria(mesa.Model)`: crea los 5 agentes (el orden importa), `step()`, `factor_brote()`, `trasladar()`, `crear_orden()`, `gastar()` y `metricas()`. |
| `sma/model_s2.py` | `RedHospitalariaS2`: 4 agentes, `asignar_lote()` (mueve el mismo objeto `Lote`) y `metricas()` de la S2. |
| `sma/config.py` | `cargar_config()`: lee YAML, construye objetos y genera el historial sintético reproducible (`_generar_historial`). `_fusionar()` aplica los overrides. |
| `sma/config_s2.py` | `ConfiguracionS2`, `OpcionesS2` y `cargar_config_s2()`. |
| `sma/variantes.py` | `Variante` (título, descripción, `esperado`, `overrides`), `listar_variantes()`, `cargar_variante()`. |
| `sma/variantes_s2.py` | Lo mismo para la S2. |

**Agentes de la S1** (`sma/agents/`):

| Archivo | Qué hace |
|---|---|
| `base.py` | `AgenteBase`: `step()` vacía el buzón y llama a `procesar()`; `enviar()` crea el `MensajeACL` y lo pasa al bus; `accion()` registra en la traza. |
| `inventario.py` | `_detectar_riesgos()` compara stock con umbral y avisa; `_responder_excedentes()` calcula quién puede ceder y cuánto. |
| `pronostico.py` | `_holt()`, `_factores_estacionales()`, `_mape()` y `_pronosticar_evento()`: proyecta la demanda y reporta el error. |
| `coordinador.py` | El rol más grande: `_procesar_inform()`, `_consultar_excedentes()`, `_decidir()`, `_solicitar_compra()`, `_pedir_compra_alterna()`, `_intentar_emergencia()`, `_escalar()`, `_solicitar_confirmacion()`, `_cerrar()` y `_manejar_failure()`. |
| `compras.py` | `_gestionar_compra()` responde `AGREE`/`FAILURE` y alerta el retraso; `_comprar()` crea la orden y gasta; `_confirmar()` responde al `QUERY-IF`. |
| `supervisor.py` | Registra los `INFORM` de su lista `EVENTOS`, detecta "sin riesgo" y genera el reporte de cierre. |

**Agentes de la S2** (`sma/agents/s2/`):

| Archivo | Qué hace |
|---|---|
| `inventario.py` | `_detectar_vencimiento()`, `_responder_stock()` y `_preparar_traslado()` (acepta o rechaza según `rechazos_traslado`). |
| `pronostico.py` | `_proyectar()`, `_estimar_previa()`, `_responder_demanda()`; si está caído no responde, y `_responder_reinicio()` / `_completar_reinicio()` lo recuperan. |
| `coordinador.py` | `_analizar()` (pide demanda), `_usar_sustituto()` (timeout), `_consultar_stock()`, `_decidir()`, `_solicitar_traslado()`, `_reasignar()` (tras `REFUSE`), `_cerrar()` y `_escalar()`. |
| `supervisor.py` | `_verificar_timeout()` (la condición está aquí), `_procesar_failure()`, `_reporte_incidente()` y `_generar_reporte()`. |

**Evidencia y verificación**:

| Archivo | Qué hace |
|---|---|
| `sma/trace.py` | `Traza`: `registrar_mensaje()`, `registrar_accion()`, `registrar_entorno()`, consultas (`mensajes()`, `buscar()`, `acciones()`, `entorno()`) y `a_mermaid()`. Define participantes y alias de S1 y S2. |
| `sma/scenario/s1.py` | `verificar()`: 16 comprobaciones numeradas del enunciado de la S1. |
| `sma/scenario/s2.py` | `verificar_s2()`: 19 comprobaciones de la S2. |

**Interfaces**:

| Archivo | Qué hace |
|---|---|
| `sma/run.py` | `ejecutar()`, `ejecutar_variante()`, `ejecutar_s2()`, `imprimir_timeline()`, `_guardar()` y el CLI (`--situacion`, `--variante`, `--listar`, `--rondas`, `--salida`). |
| `app.py` | `_importar_sma()` (recarga limpia en Streamlit), `correr_s1()` / `correr_s2()` con caché, tablas y descargas. |
| `sma/diagrama.py` | `items_desde_traza()`, `generar()` y `main()`: escribe `out/s1_secuencia.drawio` desde la traza. No toca `Diagrama1.drawio`. |

**Pruebas**:

| Archivo | Qué demuestra |
|---|---|
| `tests/test_s1.py` | Flujo base, presupuesto insuficiente, Compras caído, determinismo, Mermaid y drawio generado (6). |
| `tests/test_s2.py` | Flujo base, lote único en las 7 variantes, determinismo, `REFUSE`, escalado, Mermaid y decisiones puras (23). |
| `tests/test_variantes.py` | Las 13 variantes de S1 de extremo a extremo, la matriz pura y la inmutabilidad de la traza (34). |
| `tests/test_app.py` | El panel arranca, ejecuta una variante y cambia a S2 (3). |

### 4.4 El ciclo de una ronda, con el código delante

```python
# sma/model.py · RedHospitalaria.step
self.ronda += 1
for mensaje in self.bus.entregar():        # lo enviado en la ronda anterior
    agente = self.por_nombre.get(mensaje.receptor)
    agente.buzon.append(mensaje)           # se reparte a los buzones
self.agents.do("step")                     # uno por uno, en orden de creación

# sma/agents/base.py · AgenteBase.step
self.model.latidos[self.nombre] = self.model.ronda
mensajes, self.buzon = self.buzon, []      # vaciar antes de procesar
self.procesar(mensajes)                    # aquí vive la lógica del rol
```

Consecuencias que hay que poder explicar:

1. **No hay concurrencia real**: los agentes se activan en serie.
2. **La entrega es diferida**: enviar en N significa procesar en N+1.
3. **El orden de creación es el orden de activación**. En S1:
   `inventario → pronostico → coordinador → compras → supervisor`. En S2:
   `inventario → pronostico → coordinador → supervisor`.
4. **`latidos`** guarda la última ronda en que se activó cada agente (hoy solo
   se escribe; es el punto de enganche para monitorización).
5. La simulación para cuando `modelo.cierre` y `supervisor.reporte` existen;
   `max_rondas` es solo un tope de seguridad.

### 4.5 Anatomía de un agente

Todos los agentes hacen como máximo cuatro cosas:

1. **Percibir**: leen su buzón en `procesar(mensajes)`.
2. **Consultar el entorno**: `self.model.config...`, `self.model.ronda` y los
   lotes de los hospitales (solo lectura).
3. **Actuar sobre el entorno**: llaman a métodos del modelo
   (`trasladar`, `crear_orden`, `asignar_lote`).
4. **Comunicar y dejar evidencia**: `self.enviar(...)` y `self.accion(...)`.

Un agente **no** debe tocar las variables de otro agente ni saltarse el bus.
Si dos agentes necesitan hablarse, se manda un `MensajeACL`. Esa disciplina es
lo que hace que la traza sea fiable.

Ejemplo mínimo (`inventario.py`):

```python
if stock <= umbral or dias <= stock_seguridad:
    evento = {"tipo": "riesgo_desabastecimiento", "hospital": ..., ...}
    self.accion("generarEventoRiesgo", evento)   # queda en la traza
    self.enviar(INFORM, "coordinador", evento)   # sale por el bus
```

### 4.6 Un mensaje de punta a punta

Sigamos el primer `INFORM` de la S1 (`riesgo_desabastecimiento`). Es el mejor
ejemplo para explicar el sistema en la defensa:

1. `inventario._detectar_riesgos()` recorre hospitales y medicamentos y
   construye el diccionario del riesgo con las fórmulas de `Hospital`.
2. `AgenteBase.enviar()` crea el `MensajeACL` con emisor, receptor, contenido y
   protocolo.
3. `Bus.enviar()` le asigna `seq` y `ronda`, lo guarda en `pendientes` y llama a
   `traza.registrar_mensaje()`.
4. En la ronda siguiente, `RedHospitalaria.step()` llama a `bus.entregar()` y
   mete el mensaje en el buzón del Coordinador.
5. `coordinador.procesar()` ve un `INFORM` y llama a `_procesar_inform()`.
6. `_procesar_inform()` reconoce `tipo == "riesgo_desabastecimiento"` y llama a
   `_registrar_riesgo()`.
7. Cuando tiene riesgo **y** proyección, `_consultar_excedentes()` envía un
   `QUERY-REF` al Inventario (ronda 2).
8. `inventario._responder_excedentes()` contesta con `INFORM excedentes`
   (ronda 3).
9. Con los excedentes, `coordinador._decidir()` llama a `decision.planificar()`,
   ejecuta `model.trasladar()` y envía `REQUEST` a Compras.
10. Compras responde `AGREE`, alerta el retraso de P1 y el Coordinador pide P2;
    la orden se confirma con `QUERY-IF` → `INFORM`; el Supervisor cierra.

Cada paso deja un evento en `out/s1_traza.json`; el Mermaid y el drawio
generado se construyen recorriendo exactamente esos eventos.

### 4.7 ¿Dónde toco si quiero…?

| Quiero… | Voy a… | Lo comprueba… |
|---|---|---|
| cambiar stock, consumo o precios | `config/s1.yaml` o `config/s2.yaml` | `pytest` y `sma.run` |
| añadir un hospital | `config/s1.yaml → hospitales` (con `inventario` y `consumo_diario`) | no hay que tocar código |
| añadir un medicamento | `medicamentos` + `inventario` + `consumo_diario` | catálogo abierto; aparece en todo el sistema |
| añadir un "y si" | `config/variantes.yaml`: `overrides` + `esperado` | `test_variante_cumple_lo_esperado` |
| cambiar qué proveedor gana | `sma/decision.py → elegir_proveedor()` | `tests/test_variantes.py` |
| cambiar la prioridad de la S2 | `sma/decision_s2.py → elegir_hospital_prioritario()` | `tests/test_s2.py` |
| cambiar el orden de activación | `sma/model.py → __init__` | **revisar todo el escenario**: cambian las rondas |
| añadir o cambiar un mensaje | el agente correspondiente + `sma/scenario/s1.py` | el check numerado falla si desaparece |
| cambiar el diagrama Mermaid | `sma/trace.py → a_mermaid()` | `test_diagrama_mermaid...` |
| añadir una pestaña al panel | `app.py` | `tests/test_app.py` |

### 4.8 Cómo leer una traza sin perderse

La traza es una lista de eventos con tres tipos:

| `tipo` | Campos | Significado |
|---|---|---|
| `mensaje` | `ronda`, `performativa`, `emisor`, `receptor`, `contenido`, `protocolo` | un ACL enviado |
| `accion` | `ronda`, `agente`, `accion`, `detalle` | algo que hizo un agente (auto-llamada) |
| `entorno` | `ronda`, `accion`, `detalle`, `origen`, `destino` | un cambio real en el mundo (traslado, orden) |

Para verla sin abrir el JSON entero:

```powershell
& $py -m sma.run | Select-String "riesgo|REQUEST|AGREE|cierre"
```

O con Python, filtrando solo los mensajes:

```python
import json
eventos = json.load(open("out/s1_traza.json", encoding="utf-8"))["eventos"]
for e in eventos:
    if e["tipo"] == "mensaje":
        print(e["ronda"], e["emisor"], "->", e["receptor"],
              e["performativa"], e["contenido"].get("tipo"))
```

Truco para estudiar: ejecuta la S1 y la S2, abre los dos `.mmd` y compara. En la
S1 verás `COMP`, `P1`, `P2` y `OC`; en la S2 verás `LOTE` y ningún proveedor.
Eso demuestra que son **dos organizaciones distintas**, no la misma con un
agente de más.

### 4.9 Convenciones y trampas del código

- Los identificadores están en español; las constantes FIPA, en mayúsculas.
- El atributo `nombre` de un agente es a la vez la clave del buzón, el `emisor`
  del ACL y la clave de alias de la traza. Cambiarlo rompe los mensajes.
- **No "arregles" la entrega diferida**: es lo que hace determinista el orden y
  explica las rondas del diagrama.
- `AgenteBase.step()` vacía el buzón antes de procesar. Si guardas una
  referencia a la lista, ya no es la del agente.
- La traza copia con `deepcopy`: un mensaje no puede cambiar después de
  enviarse.
- `ronda_inicio` dispara la detección del Inventario y el pronóstico; no
  asumas que siempre es la ronda 1.
- En S2, `asignar_lote()` mueve el **mismo objeto** `Lote` de una lista a otra:
  nunca se copia ni se reparte.
- Los tests no usan mocks: ejecutan el modelo real con semilla fija y comparan
  la traza.

### 4.10 Checklist: ¿ya entiendes el código?

Si fallas una pregunta, vuelve al archivo indicado.

| Pregunta | Respuesta corta | Archivo |
|---|---|---|
| ¿Quién crea a los agentes y en qué orden? | `RedHospitalaria.__init__`; el orden de creación es el de activación | `sma/model.py` |
| ¿Dónde espera un mensaje antes de entregarse? | en `Bus.pendientes`; se entrega al inicio de la ronda siguiente | `sma/bus.py` |
| ¿Por qué el Coordinador decide en la ronda 4? | necesita la proyección (r1→r2) y los excedentes (r2→r3) | `sma/agents/coordinador.py` |
| ¿Qué diferencia hay entre `accion` y `entorno`? | `accion` es una auto-llamada del agente; `entorno` cambia el mundo | `sma/trace.py` |
| ¿Quién elige al proveedor y con qué criterio? | `elegir_proveedor()`: mínimo `precio + 0.5 × plazo` entre los viables | `sma/decision.py` |
| ¿Dónde está la regla de que el lote no se reparte? | `planificar_traslado()` asigna el lote completo a uno solo | `sma/decision_s2.py` |
| ¿Quién detecta el timeout y con qué condición? | el Supervisor, si `ronda > ronda_consulta` y no hubo respuesta | `sma/agents/s2/supervisor.py` |
| ¿Qué pasa si el Pronóstico no dejó estimación? | se usa `media(historial) × horizonte` | `sma/decision_s2.py` |
| ¿Cómo se añade una variante sin tocar Python? | una entrada en el YAML con `overrides` y `esperado` | `config/variantes*.yaml` |
| ¿Qué se genera y qué se dibuja a mano? | Mermaid y `out/s1_secuencia.drawio` se generan; `Diagrama1/2.drawio` son del informe | `sma/trace.py`, `sma/diagrama.py` |
| ¿Qué aporta `scenario/s1.py` frente a un test? | son las mismas comprobaciones que muestra el panel, no solo pytest | `sma/scenario/s1.py` |
| ¿Qué habría que cambiar para usar XMPP? | solo el adaptador del bus; los agentes no cambian | `sma/bus.py` |

---

## 5. Situación 1 · brote respiratorio

### 5.1 Enunciado

En el Hospital A se declara un brote respiratorio que multiplica por **1.6** el
consumo de amoxicilina. El stock no alcanza, la red puede ceder excedentes y,
si no llega, hay que comprar. El presupuesto es limitado y un proveedor está
retrasado.

### 5.2 Datos (config/s1.yaml)

| Dato | Valor |
|---|---|
| Semilla | 7 |
| Presupuesto | 5 000 € |
| Horizonte de pronóstico | 14 días |
| Tiempo de traslado | 1 día |
| Evento | brote en `H_A`, amoxicilina, factor 1.6, ronda 1 |

| Hospital | Stock amox. | Consumo/día | Seguridad | Umbral | Excedente |
|---|---|---|---|---|---|
| H_A | 120 | 30 (×1.6 = 48) | 5 días | 150 | — (en riesgo) |
| H_B | 400 | 8 | 5 días | 40 | **344** |
| H_C | 150 | 4 | 4 días | 16 | **126** |

Fórmulas:

- `umbral = consumo_diario × stock_seguridad_dias`
- `excedente = stock − consumo × (stock_seguridad + 2 días de colchón)`
  - H_B: `400 − 8×(5+2) = 344`
  - H_C: `150 − 4×(4+2) = 126`

| Proveedor | Plazo base | Retraso | Plazo efectivo | Precio amox. |
|---|---|---|---|---|
| P1 (habitual) | 3 días | 9 días | **12 días** | 2.40 € |
| P2 (alterno) | 5 días | 0 | **5 días** | 2.60 € |

### 5.3 Agentes y arquitectura

| Agente | Arquitectura | Qué hace |
|---|---|---|
| **Inventario** | reactiva (reflejo simple) | compara stock con umbral, detecta riesgo y calcula excedentes |
| **Pronóstico** | basada en modelos con aprendizaje | Holt + estacionalidad semanal + factor de brote; reporta MAPE |
| **Coordinador** | basada en utilidad | integra riesgo + proyección, prioriza, planifica y ejecuta |
| **Compras** | basada en objetivos | consulta ofertas, elige proveedor, genera y confirma la orden |
| **Supervisor** | deliberativa | registra eventos, comprueba disponibilidad y genera el reporte |

Por qué cada una: el Inventario solo reacciona a umbrales (no planifica); el
Pronóstico necesita un modelo matemático; el Coordinador compara alternativas y
elige la de mayor utilidad; Compras persigue un objetivo (dejar la orden
confirmada); el Supervisor razona sobre el estado global.

### 5.4 Flujo real (11 rondas, 15 mensajes ACL)

| Ronda | Mensaje | Contenido |
|---|---|---|
| 1 | Inventario → Coordinador | `INFORM riesgo_desabastecimiento` (H_A) |
| 1 | Inventario → Supervisor | `INFORM informe_inventario` |
| 1 | Pronóstico → Coordinador | `INFORM demanda_proyectada = 700` |
| 2 | Coordinador → Inventario | `QUERY-REF excedentes` |
| 3 | Inventario → Coordinador | `INFORM excedentes` (H_B 344, H_C 126) |
| 4 | Coordinador → Supervisor | `INFORM decision` (traslado 470 + compra 110) |
| 4 | Coordinador → Compras | `REQUEST comprar 110` |
| 5 | Compras → Coordinador | `AGREE gestion_compra` |
| 5 | Compras → Coordinador | `INFORM retraso_proveedor` (P1, 9 días) |
| 5 | Compras → Supervisor | `INFORM retraso_proveedor` |
| 6 | Coordinador → Compras | `REQUEST comprar_a_proveedor P2` |
| 7 | Compras → Coordinador | `INFORM orden_generada` (OC-001) |
| 8 | Coordinador → Compras | `QUERY-IF orden_confirmada` |
| 9 | Compras → Coordinador | `INFORM orden_confirmada = true` |
| 10 | Coordinador → Supervisor | `INFORM cierre` |

> Por qué el Coordinador tarda en decidir: en la ronda 2 todavía no tiene la
> proyección (llega en la 1 pero se entrega en la 2) ni los excedentes (se
> piden en la 2 y llegan en la 3). Decide en la 4. **Eso es la entrega
> diferida funcionando.**

### 5.5 La decisión (sma/decision.py)

1. **Necesidad** = `demanda_proyectada − stock` = `700 − 120 = 580`.
2. **Filtrar donantes**. Se descarta un lote si:
   - no tiene cantidad,
   - vence en menos de 2 días,
   - el medicamento exige frío y el donante no lo garantiza,
   - el medicamento exige frío y no hay transporte refrigerado,
   - el traslado llega después del agotamiento (`tiempo_traslado >
     días_hasta_agotamiento + 1`), salvo que se permita emergencia.
3. **Ordenar** los aptos por vencimiento más próximo (FIFO por caducidad).
4. **Repartir** la necesidad: H_B 344 + H_C 126 = 470. Faltan 110.
5. **Elegir proveedor**: viable si llega antes de la cobertura
   (`plazo ≤ cobertura`) y está disponible. Se elige el mínimo de
   `precio + 0.5 × plazo` (penalización por día).
   - Cobertura tras el traslado: `(120 + 470) / 48 = 12.29` días.
   - P1: `2.40 + 0.5×12 = 8.40` · P2: `2.60 + 0.5×5 = 5.10` → **P2**.
6. **Compras** confirma que puede gestionar (`AGREE`), detecta que P1 está
   retrasado y lo informa; el Coordinador pide la compra a P2.
7. **Orden**: `110 × 2.60 = 286 €`. Presupuesto: `5 000 − 286 = 4 714 €`.

Acciones posibles del planificador: `ninguna`, `traslado`, `compra`,
`traslado_y_compra`, `traslado_parcial`, `escalar`.

### 5.6 Resultado base

| Métrica | Valor |
|---|---|
| Demanda proyectada | 700 |
| Traslado recibido | 470 (H_B 344 + H_C 126) |
| Compra | 110 uds a P2 |
| Coste | 286.00 € |
| Presupuesto restante | 4 714.00 € |
| Cobertura | 1.0 |
| Riesgo residual | 0 |
| Resultado | `exito` |
| Rondas / mensajes | 11 / 15 |
| Verificación | 16/16 |

### 5.7 Las 13 variantes de la S1

Cada una es un *override* de `config/s1.yaml` en `config/variantes.yaml`. No se
duplica el escenario: se cambian los datos que provocan el caso.

| Variante | Qué cambia | Resultado |
|---|---|---|
| `base` | — | traslado 470 + compra 110 a P2 |
| `solo_traslado` | H_B con 700 | traslado 580, sin orden |
| `solo_compra` | sin excedentes | compra 460 a P2 |
| `sin_necesidad` | H_A con 800 | `sin_riesgo`, no actúa |
| `excedente_por_vencer` | lote de H_B vence en 1 día | traslado 126 + compra 454 |
| `cadena_frio` | insulina sin transporte refrigerado | compra 108 a P2 |
| `proveedores_retrasados` | P1 +12, P2 +30 días | traslado parcial 494, residual 86 |
| `sin_donantes_ni_proveedores` | sin salida y sin emergencia | `escalar`, residual 460 |
| `presupuesto_insuficiente` | fuerza rechazo por presupuesto | replanifica, residual 86 |
| `compras_no_puede` | Compras responde `FAILURE` | replanifica, residual 86 |
| `proveedor_habitual_ok` | P1 sin retraso | compra a P1 |
| `presupuesto_parcial` | 200 € y política parcial | compra 76, residual 34 |
| `dos_hospitales` | H_B con 40 | dos decisiones y dos órdenes |

---

## 6. Situación 2 · lote por vencer, competencia y fallo

### 6.1 Enunciado

En el Hospital C hay un lote de 200 unidades de amoxicilina que **caduca en 12
días** y C consume muy poco. Los hospitales A y B se quedan cortos y **compiten
por ese mismo lote**: un lote no puede estar en dos hospitales a la vez. Además,
el **Agente de Pronóstico deja de responder** en la ronda 3 y el Supervisor debe
detectarlo, reiniciarlo y decidir qué hacer si no vuelve.

Aquí no hay proveedores ni Compras: el problema es **asignar un recurso escaso**
y **seguir operando con un agente caído**.

### 6.2 Datos (config/s2.yaml)

| Dato | Valor |
|---|---|
| Semilla | 11 |
| Horizonte | 14 días |
| Lote en riesgo | `L-C-001`, H_C, amoxicilina, **200 uds**, vence en 12 días |
| Umbral de vencimiento | 30 días |
| Pronóstico caído | sí, en la ronda 3 |
| Reinicio falla | no (en la base) |
| Rechazos de traslado | 0 (en la base) |

| Hospital | Stock | Consumo/día | Días hasta agotar | Demanda 14 d | Necesidad |
|---|---|---|---|---|---|
| H_A | 60 | 20 | **3.0** | 310 | 250 |
| H_B | 40 | 10 | **4.0** | 155 | 115 |
| H_C | 200 | 2 | 100.0 | — | — |

Por qué hay riesgo: el lote cubre `200 / 2 = 100` días de consumo de C, pero
vence en 12. Se perderían 176 unidades. Condición del código:
`vence_en_dias ≤ umbral` **y** `cobertura_dias > vence_en_dias`.

### 6.3 Agentes

| Agente | Arquitectura | Qué hace |
|---|---|---|
| **Inventario** | reactiva | detecta el lote por vencer, responde stock de A/B, acepta o rechaza el traslado |
| **Pronóstico** | modelos + recuperación | proyecta la demanda de A y B; deja su última estimación; atiende el reinicio |
| **Coordinador** | utilidad | compara urgencias, decide el destino, reasigna si rechazan, cierra |
| **Supervisor** | deliberativa | detecta el timeout, notifica, pide el reinicio, escala y reporta |

No hay Compras ni Proveedores: **el rol no existe en esta organización**.

### 6.4 Fases del enunciado (SITUACION2.md)

| Fase | Qué ocurre |
|---|---|
| **A · Detección** | Inventario lee registros, compara el umbral y genera el evento de riesgo |
| **B · Consulta** | El Coordinador pide la demanda al Pronóstico (QUERY-REF) |
| **C · Decisión** | Timeout, fallback, consulta de stock, prioridad, traslado y cierre |
| **D · Recuperación** | El Supervisor reinicia al Pronóstico (REQUEST → AGREE → INFORM) |
| **E · Supervisión** | Registro de eventos, reporte de incidente y reporte de cierre |

### 6.5 Flujo real (9 rondas, 16 mensajes ACL)

| Ronda | Mensaje | Contenido |
|---|---|---|
| 1 | Inventario → Coordinador | `INFORM riesgo_vencimiento` (`L-C-001`, 200 uds, 12 días) |
| 1 | Inventario → Supervisor | `INFORM informe_inventario` |
| 2 | Coordinador → Pronóstico | `QUERY-REF demanda_proyectada` (A y B) |
| 3 | Supervisor → Coordinador | `INFORM fallo_detectado` (timeout) |
| 3 | Supervisor → Pronóstico | `REQUEST solicitar_reinicio` |
| 4 | Pronóstico → Supervisor | `AGREE reinicio_aceptado` |
| 4 | Coordinador → Supervisor | `INFORM decision` (usa la última estimación) |
| 4 | Coordinador → Inventario | `QUERY-REF stock` (A y B) |
| 5 | Inventario → Coordinador | `INFORM stock` (60/40, 3 y 4 días) |
| 5 | Pronóstico → Supervisor | `INFORM reinicio_completado` |
| 6 | Coordinador → Supervisor | `INFORM decision` (traslado a H_A) |
| 6 | Coordinador → Inventario | `REQUEST preparar_traslado` |
| 7 | Inventario → Coordinador | `AGREE traslado_aceptado` |
| 7 | Inventario → Coordinador | `INFORM traslado_realizado` |
| 8 | Coordinador → Supervisor | `INFORM decision` (lista de espera H_B) |
| 8 | Coordinador → Supervisor | `INFORM cierre` |

Observa el **paralelismo real**: mientras el Supervisor recupera al Pronóstico
(rondas 3–5), el Coordinador **no se detiene**: en la ronda 4 ya está decidiendo
con la última estimación y pidiendo el stock. Eso es lo que representa el
fragmento `par` del diagrama.

### 6.6 El timeout, ronda a ronda

1. **Ronda 2**: el Coordinador envía la consulta y anota
   `consulta_pronostico = {ronda: 2, respondida: False}`.
2. **Ronda 3**: el Pronóstico, por configuración, ya no atiende consultas. El
   Supervisor comprueba `ronda > ronda_consulta` y `respondida == False` →
   declara el timeout, registra el evento, informa al Coordinador y pide el
   reinicio.
3. **Ronda 4**: el Pronóstico acepta (`AGREE`) y queda `reinicio_pendiente`.
4. **Ronda 5**: ejecuta `actualizarModelo` e informa `reinicio_completado`.
5. Si el reinicio falla: responde `FAILURE error_al_reiniciar`; el Supervisor
   notifica, **escala a intervención manual** y genera el reporte del incidente.

El Coordinador nunca espera al Pronóstico para decidir: usa
`ultima_estimacion` y, si no existe, la media del historial de consumo.

### 6.7 Reglas puras (sma/decision_s2.py)

```python
necesidad = max(0, demanda - stock)
dias = stock / consumo
prioridad = min(urgencias, key=lambda u: (u.dias, -u.necesidad, u.hospital))
```

- El lote va **completo** al hospital prioritario (`cantidad = 200`), nunca se
  reparte. Es un invariante del dominio y hay un test que lo comprueba.
- `faltante = max(0, necesidad_prioritario − lote)` = `250 − 200 = 50`.
- **Reasignación**: si Inventario responde `REFUSE`, el Coordinador elige el
  siguiente hospital no intentado. Si no queda ninguno → `escalar`.
- **Demanda sustituta**: última estimación; si no hay, `media(historial) ×
  horizonte`.

### 6.8 Resultado base

| Métrica | Valor |
|---|---|
| Demanda proyectada | H_A 310 · H_B 155 |
| Prioridad | **H_A** (3 días vs 4) |
| Lote asignado | `L-C-001` → **H_A** (200 uds) |
| Faltante del prioritario | 50 uds |
| Lista de espera | **H_B** |
| Riesgo residual | **165** = (250−200) + 115 |
| Stock final | H_A 260 · H_B 40 · H_C 0 |
| Timeout / reinicio | sí / `exitoso` |
| Fuente de la demanda | `ultima_estimacion` |
| Resultado | `exito` |
| Rondas / mensajes | 9 / 16 |
| Verificación | 19/19 |

### 6.9 Las 7 variantes de la S2

| Variante | Qué cambia | Resultado |
|---|---|---|
| `s2_base` | — | lote a H_A, H_B en espera, residual 165 |
| `s2_pronostico_ok` | `pronostico_caido: false` | decide con el modelo, sin timeout |
| `s2_traslado_rechazado` | 1 rechazo | reasigna a H_B, H_A en espera, residual 250 |
| `s2_reinicio_falla` | `reinicio_falla: true` | `FAILURE`, escala, lote igual a H_A |
| `s2_sin_receptor` | 2 rechazos | `escalado`, lote queda en H_C, residual 365 |
| `s2_sin_estimacion` | falla en ronda 1 | usa historial, residual 151 |
| `s2_sin_riesgo` | umbral 5 días | `sin_riesgo`, no hay traslado |

### 6.10 Cómo leer el diagrama de la S2

- **6 participantes**: `RED`, `INV`, `PRO`, `COORD`, `SUP`, `LOTE`.
- **Sin numeración** en las flechas (así lo pide el informe).
- `alt` **Pronóstico responde / timeout**.
- `par` **traslado + recuperación** (dos hilos en la misma ronda).
- `alt` **traslado viable / rechazado**.
- `opt [Pronóstico dejó de responder]` con `alt` **reinicio exitoso / fallo**.

---

## 7. Cómo se garantiza que lo que dices es verdad

### 7.1 La traza es la fuente de verdad

Cada mensaje, acción y cambio de entorno se registra en `Traza` **en el momento
en que ocurre** y se copia (`deepcopy`). Un mensaje no puede cambiar después de
enviarse. El Mermaid se genera recorriendo esos eventos:

```
traza real → a_mermaid() → out/*.mmd
traza real → sma/diagrama.py → out/s1_secuencia.drawio
```

Por eso el `.mmd` y el `.drawio` generado **no pueden divergir** de la
ejecución: se construyen recorriendo los eventos. Los dibujos del informe
(`Diagrama1.drawio` y `Diagrama2.drawio`) son la versión legible de esa misma
secuencia y se revisan contra la traza y las comprobaciones de `sma/scenario/*`.

### 7.2 Verificación paso a paso

- `sma/scenario/s1.py`: 16 comprobaciones (riesgo, informes, proyección,
  consulta, traslado, compra, orden confirmada, reporte, cobertura).
- `sma/scenario/s2.py`: 19 comprobaciones (riesgo, timeout, fallback, reinicio,
  stock, decisión, traslado, lote único, lista de espera, reporte).

Se ejecutan desde el panel y desde la consola (`python -m sma.run`). No son
"tests aparte": son la misma función que usa la app.

### 7.3 Pruebas (66)

| Archivo | Qué cubre | Pruebas |
|---|---|---|
| `tests/test_s1.py` | flujo base, presupuesto, Compras caído, determinismo, Mermaid y drawio | 6 |
| `tests/test_s2.py` | flujo base, lote único en 7 variantes, determinismo, variantes, REFUSE, escalado, Mermaid, decisiones puras | 23 |
| `tests/test_variantes.py` | las 13 variantes de S1 + funciones puras + inmutabilidad de la traza | 34 |
| `tests/test_app.py` | el panel arranca, cambia de variante y cambia a S2 | 3 |

Comando: `pytest` → **66 passed**.

### 7.4 Determinismo

Semilla fija + historial sintético reproducible (`random.Random(f"{semilla}:{hospital}:{medicamento}")`)
+ bus con entrega diferida + sin concurrencia real = **misma traza siempre**.
Hay tests que ejecutan dos veces y comparan métricas y número de eventos.

### 7.5 El invariante del lote (S2)

`RedHospitalariaS2.asignar_lote()`:

1. Comprueba que el lote no esté ya asignado.
2. Lo **quita** de la lista del hospital de origen.
3. Cambia `lote.hospital_id`.
4. Lo **añade** a la lista del destino.

Es el mismo objeto `Lote` que se mueve, no una copia. Test:
`test_el_lote_nunca_se_duplica` recorre las 7 variantes y comprueba que el
origen queda a 0 y que solo un hospital tiene ≥ 200 unidades.

---

## 8. Decisiones de diseño y su justificación

| Decisión | Por qué |
|---|---|
| **Mesa** como framework | es un framework de SMA real, en Python, sin servicios externos ni claves; da modelo, agentes, activación y semilla |
| **FIPA-ACL propia** | Mesa no implementa el estándar; escribirlo demuestra el dominio del protocolo y permite correlacionar conversaciones |
| **Bus en proceso** | cero infraestructura, cero coste, determinista; el transporte es intercambiable (XMPP) sin tocar agentes |
| **Entrega diferida** | modela latencia, hace determinista el orden y explica las rondas del diagrama |
| **Decisión pura** | se prueba la regla sin simular; el agente solo ejecuta y comunica |
| **Variantes declarativas en YAML** | 20 casos sin duplicar escenarios; los tests las parametrizan |
| **Traza como fuente de verdad** | el diagrama del informe sale del código, no de una herramienta de dibujo |
| **Sin LLM** | requisito del enunciado: determinismo, reproducibilidad y coste cero |
| **Streamlit Community Cloud** | despliegue público y gratuito; Python 3.12 por exigencia de Mesa |
| **Dos organizaciones (S1/S2)** | los roles cambian: en S2 no existen Compras ni Proveedores |

---

## 9. Preguntas de defensa (con respuesta corta)

**¿Por qué Mesa y no JADE/SPADE?**
JADE/SPADE son Java/Python con contenedores y servicios; aquí se pedía algo
ejecutable en cualquier sitio, sin instalar nada y sin coste. Mesa da el ciclo de
vida y la semilla; la capa FIPA se implementa encima, que es justo lo que se
quiere demostrar.

**¿Qué aporta Mesa si la comunicación es propia?**
Modelo, registro automático de agentes, activación ordenada por ronda y
reproducibilidad con semilla. Sin Mesa habría que reimplementar el scheduler.

**¿Por qué la entrega es diferida?**
Para que el orden sea determinista y para que las rondas del diagrama coincidan
con las del código. Además modela la latencia real: un agente no puede responder
en el mismo instante en que recibe.

**¿Cómo evitas que dos agentes decidan a la vez?**
La activación es secuencial y en orden fijo (`agents.do("step")`), y los mensajes
se entregan al inicio de la ronda. No hay concurrencia real, así que no hay
condiciones de carrera.

**¿Cómo se calcula la demanda?**
Holt (nivel + tendencia) con estacionalidad semanal, ajustado por el factor de
brote en S1. Se reporta el MAPE como medida de error. El historial es sintético y
reproducible a partir de la semilla.

**¿Qué es el MAPE y para qué lo usas?**
Error porcentual absoluto medio: se entrena con la serie menos los últimos 7 días
y se valida con esos 7. Se reporta en la traza y en la decisión; sirve para saber
cuánto de fiable es la proyección.

**¿Cómo se elige el proveedor?**
Entre las ofertas viables (llegan antes del agotamiento) se minimiza
`precio + 0.5 × plazo`. La penalización evita que un proveedor barato pero lento
gane siempre.

**¿Qué pasa si ningún proveedor llega a tiempo?**
Se intenta un traslado de emergencia (se libera el colchón logístico, se respeta
el stock de seguridad). Si aun así no alcanza, se escala el riesgo residual al
Supervisor y se registra el fallo. Variantes: `proveedores_retrasados`,
`sin_donantes_ni_proveedores`.

**¿Cómo se cubren todos los "y si"?**
Con 13 variantes en S1 y 7 en S2, cada una un override de datos, y tests
parametrizados que comparan lo esperado con lo real. No hay casos "a mano".

**¿Qué diferencia hay entre S1 y S2?**
S1 es un problema de **desabastecimiento** con dos palancas (traslado y compra) y
presupuesto. S2 es un problema de **asignación de un recurso escaso** (un lote
que solo puede ir a un hospital) más **tolerancia a fallos** (un agente deja de
responder). En S2 no existen Compras ni Proveedores.

**¿Por qué el lote va entero a un solo hospital?**
Porque es un objeto del dominio: un lote físico no se puede partir entre dos
almacenes sin trazabilidad. Además, repartirlo no resolvería la urgencia de
ninguno de los dos. Es un invariante comprobado por test.

**¿Qué criterio usa el Coordinador para priorizar?**
Días hasta el agotamiento (menor primero); desempata por necesidad y por
identificador. En la base, H_A se agota en 3 días y H_B en 4 → H_A.

**¿Y el hospital que no recibe el lote?**
Queda en **lista de espera** con su riesgo residual registrado. En el informe se
plantea que pase a la Situación 1 (compra) o se renegocie con otro donante.

**¿Qué pasa si el reinicio del Pronóstico falla?**
El Pronóstico responde `FAILURE`; el Supervisor notifica, escala a intervención
manual y genera el reporte del incidente. La operación **no se detiene**: el
Coordinador ya decidió con la última estimación.

**¿Qué pasa si el Pronóstico falla antes de dejar su estimación?**
Se usa la media del historial de consumo multiplicada por el horizonte
(variante `s2_sin_estimacion`).

**¿Por qué el diagrama no puede estar mal?**
El `.mmd` y `out/s1_secuencia.drawio` se generan desde la traza: si el código
cambia, cambian solos. Los dibujos del informe (`Diagrama1.drawio` y
`Diagrama2.drawio`) se contrastan con esa traza, y las comprobaciones de
`sma/scenario/*` fallan si un paso deja de ocurrir.

**¿Por qué 11 rondas en S1 y 9 en S2?**
Por la cadena de dependencias y la entrega diferida. En S1: riesgo (1) →
consulta (2) → excedentes (3) → decisión (4) → compra (5) → proveedor (6) →
orden (7) → confirmación (8–9) → cierre (10). En S2 el Pronóstico y el
Supervisor trabajan en paralelo, así que la cadena es más corta.

**¿Qué limitaciones tiene?**
El traslado en S2 es inmediato (no se modela el transporte), la compra termina en
orden confirmada (no hay entrega física), el bus es en proceso (no hay red real)
y no se simulan varios medicamentos a la vez en S2. Están en el README.

**¿Se puede escalar a más hospitales o medicamentos?**
Sí: el catálogo es abierto. Añadir un medicamento en `config/s1.yaml` lo hace
aparecer en todo el sistema; añadir un hospital es una entrada más. Las reglas no
dependen del número de hospitales.

**¿Cómo se despliega y cuánto cuesta?**
Streamlit Community Cloud desde GitHub, rama `main`, archivo `app.py`, Python
3.12 (`runtime.txt`). Coste cero. La app se suspende por inactividad y despierta
al visitarla.

---

## 10. Limitaciones y trabajo futuro

1. El traslado del lote en S2 es inmediato: no hay tiempo de transporte ni
   ventana de caducidad durante el viaje.
2. La compra termina en orden **confirmada**: no se modela la recepción física ni
   el consumo posterior.
3. El bus es en proceso. Sustituirlo por XMPP/JADE no requiere tocar agentes,
   solo el adaptador.
4. En S2 se simula un solo medicamento; el catálogo abierto está en S1.
5. El fallo del Pronóstico es un timeout planificado por configuración, no
   aleatorio (a propósito: la demo debe ser reproducible).

---

## 11. Chuleta para la demo (5 minutos)

1. **Abre la app** (despiértala 2–3 min antes) y muestra el selector
   **Situación 1 / Situación 2**.
2. **S1 base**: métricas (470 traslado, 110 compra, 286 €, cobertura 1.0),
   pestaña *Secuencia* (11 rondas), pestaña *Verificación* (16/16).
3. **S1 `solo_traslado`**: mismo escenario, sin compra. Demuestra que la decisión
   es declarativa.
4. **S1 `dos_hospitales`**: dos decisiones y dos órdenes.
5. **S2 base**: lote `L-C-001` → H_A, H_B en espera, timeout sí, reinicio
   exitoso, 9 rondas, 19/19.
6. **S2 `s2_traslado_rechazado`**: aparece `REFUSE` y el lote se reasigna a H_B.
7. **S2 `s2_reinicio_falla`**: `FAILURE`, escalado a intervención manual.
8. **Descarga** el `.mmd` y el `.json` desde la pestaña *Traza*.
9. Cierra con: *"el diagrama del informe no está dibujado: sale de esta traza"*.

Frase para el tribunal: **"el sistema no solo calcula; negocia, se recupera de
un fallo y deja evidencia de cada paso."**

---

## 12. Glosario rápido

| Término | Definición |
|---|---|
| **Agente** | entidad autónoma que percibe, decide y actúa |
| **Entorno** | lo que el agente percibe y modifica (la red de hospitales) |
| **Rol** | responsabilidad abstracta (Inventario, Coordinador…) |
| **Organización** | conjunto de roles y relaciones que cooperan |
| **Objeto** | entidad pasiva del dominio (Lote, OrdenCompra, Proveedor) |
| **Performativa** | intención comunicativa de un mensaje ACL |
| **Protocolo FIPA** | secuencia válida de mensajes para lograr algo |
| **Conversation-id** | identificador que agrupa una conversación |
| **Entrega diferida** | el mensaje se entrega en la ronda siguiente |
| **Traza** | registro ordenado de mensajes, acciones y cambios del entorno |
| **Variante** | override de datos que provoca un caso "y si" |
| **Riesgo residual** | demanda que queda sin cubrir tras la decisión |
| **Lista de espera** | hospital que no recibe el lote y queda pendiente |
| **MAPE** | error porcentual absoluto medio del pronóstico |
| **Invariante** | propiedad que siempre se cumple (el lote no se duplica) |
