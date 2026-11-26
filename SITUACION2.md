# Contexto: Situación 2 del SMA de abastecimiento de medicamentos

## 1. Situación 2: lote próximo a vencer, demanda en competencia y falla del Agente de Pronóstico

### 1.1 Descripción

Un lote de un medicamento está próximo a su fecha de vencimiento en el hospital C, donde la demanda es baja. Al mismo tiempo, los hospitales A y B necesitan ese medicamento y compiten por el lote, porque **un mismo lote no puede asignarse a dos hospitales a la vez**. El Agente de Inventario detecta el riesgo de vencimiento, genera un evento de riesgo y lo informa. El Coordinador consulta al Agente de Pronóstico la demanda proyectada de A y B, pero durante el proceso **el Agente de Pronóstico deja de responder**. El Supervisor detecta el timeout, lo registra, notifica al Coordinador y activa el procedimiento de recuperación. Mientras tanto, el Coordinador no se detiene: usa la última estimación disponible o el historial de consumo, compara la urgencia de A y B, elige el hospital prioritario y pide a Inventario preparar el traslado del lote. Si el traslado se rechaza, reasigna el lote al otro hospital. El Supervisor registra los eventos durante todo el proceso.

La situación demuestra que el sistema debe **resolver una competencia por un recurso escaso** (negociación coordinada por el Coordinador) y **tolerar la falla de un agente** (supervisión y recuperación), sin detener la operación de la red.

### 1.2 Precondiciones

- El hospital C tiene un lote del medicamento próximo a vencer y su demanda es baja.
- Los hospitales A y B necesitan el mismo medicamento y ninguno puede quedar sin atención.
- El lote solo puede asignarse a un hospital a la vez.
- El Agente de Pronóstico tiene una estimación previa y un historial de consumo disponibles.
- El Supervisor está operativo y monitorea el estado y los tiempos de respuesta de los agentes.
- Inventario, Coordinador y Supervisor están operativos al inicio.

### 1.3 Participantes (orden en el diagrama de secuencia, de izquierda a derecha)

1. Red de hospitales públicos (`<<environment>>`)
2. Agente de Inventario (`<<agent>>`)
3. Agente de Pronóstico (`<<agent>>`)
4. Agente Coordinador (`<<agent>>`)
5. Agente Supervisor (`<<agent>>`)
6. Objeto Lote (cantidad, fechaVencimiento)

El Agente de Compras y los proveedores no participan en esta situación. Los hospitales A, B y C no son agentes: forman parte del entorno (Red de hospitales).

### 1.4 Flujo principal, por fases

**Fase A: detección del riesgo de vencimiento (Inventario)**

1. Inventario consulta a la Red de hospitales: `leerRegistros()`.
2. La Red responde (retorno): `stock, fechasCaducidad, consumoDiario`.
3. Inventario ejecuta `compararUmbral()` y detecta el lote de C próximo a vencer con demanda baja.
4. Inventario ejecuta `generarEventoRiesgo()`.
5. Inventario → Coordinador: `INFORM (riesgo_vencimiento lote_C cantidad fecha)`, con `enviarInform()`.
6. Inventario → Supervisor: `INFORM (informe_inventario riesgo_vencimiento hospital_C)`, con `enviarInform()`.
7. Supervisor ejecuta `registrarEvento()`.

**Fase B: consulta de demanda a Pronóstico**

8. Coordinador → Pronóstico: `QUERY-REF (demanda_proyectada hospital_A hospital_B)` (protocolo FIPA-Query).

*Fragmento `alt` (respuesta de Pronóstico)*

- `[Pronóstico responde a tiempo]`:
  - Pronóstico consulta a la Red: historial de consumo.
  - La Red responde (retorno): `historialConsumo, estacionalidad`.
  - Pronóstico ejecuta `calcularProyeccion()`.
  - Pronóstico → Coordinador: `INFORM (demanda_estimada hospital_A hospital_B)`, con `enviarEstimacion()`.
- `else [timeout: Pronóstico deja de responder]`:
  - Supervisor ejecuta `registrarEvento()` (detecta el timeout del Agente de Pronóstico).
  - Supervisor → Coordinador: `INFORM (fallo_detectado agente_pronostico)`, con `notificarFallo()`.
  - Coordinador usa la última estimación o el historial de consumo como sustituto de la proyección.
  - Coordinador → Supervisor: `INFORM (decision uso_ultima_estimacion)`; el Supervisor ejecuta `registrarEvento()`.

**Fragmento `par` (desde aquí, en paralelo): Fase C (traslado) y Fase D (recuperación)**

La Fase D solo ocurre en la rama de timeout y corre sin detener la decisión del Coordinador.

**Fase C: análisis y decisión del Coordinador (rama de traslado)**

9. Coordinador ejecuta `analizarEventos()` e integra el riesgo de vencimiento en C con la demanda de A y B (proyectada o sustituta) para definir la urgencia.
10. Coordinador → Inventario: `QUERY-REF (stock antibiotico hospital_A hospital_B)`.
11. Inventario consulta a la Red: `leerRegistros()`.
12. La Red responde (retorno): stock de A y B.
13. Inventario → Coordinador: `INFORM (stock hospital_A hospital_B)`. Ambos hospitales necesitan el lote y no puede asignarse a los dos.
14. Coordinador ejecuta `decidirTrasladoOCompra()`: compara la urgencia de A y B y elige el hospital prioritario.
15. Coordinador → Supervisor: `INFORM (decision traslado lote_C hospital_prioritario)`; el Supervisor ejecuta `registrarEvento()`.
16. Coordinador → Inventario: `REQUEST (preparar_traslado lote_C hospital_prioritario)`, con `enviarRequest()` (protocolo FIPA-Request).

*Fragmento `alt` (respuesta de Inventario al traslado)*

- `[traslado viable]`:
  - Inventario → Coordinador: `AGREE (ejecutará el traslado)`.
  - Inventario → Red: trasladar el lote de C al hospital prioritario (acción sobre el entorno, no un método de un agente).
  - Inventario → Lote: actualizar cantidad.
  - Inventario → Coordinador: `INFORM (traslado_realizado inventarios_actualizados)`, con `enviarInform()`.
  - Si sobró demanda, el Coordinador envía el otro hospital a lista de espera o a la Situación 1 (compra a proveedor).
- `else [traslado rechazado]`:
  - Inventario → Coordinador: `REFUSE (traslado_inconveniente)`.
  - Coordinador ejecuta `decidirTrasladoOCompra()`: reasigna el lote al otro hospital.
  - Coordinador → Inventario: `REQUEST (preparar_traslado lote_C hospital_alterno)`, con `enviarRequest()`.
  - Inventario → Red: trasladar el lote al nuevo hospital (acción sobre el entorno).
  - Inventario → Lote: actualizar cantidad.
  - Inventario → Coordinador: `INFORM (traslado_reasignado completado)`.

**Fase D: recuperación del Agente de Pronóstico (rama del Supervisor)**

Fragmento `opt`: `[Pronóstico dejó de responder]`.

17. Supervisor → Pronóstico: `REQUEST (solicitar_reinicio_recuperacion)`, con `solicitarReinicio()` (protocolo FIPA-Request).
18. Pronóstico → Supervisor: `AGREE (acepta iniciar reinicio)`.

*Fragmento `alt` (resultado del reinicio)*

- `[reinicio exitoso]`:
  - Pronóstico ejecuta `actualizarModelo()` (corrige el error de predicción).
  - Pronóstico → Supervisor: `INFORM (reinicio_completado modelo_actualizado)`.
  - Supervisor ejecuta `generarReporte()` (reporte del incidente).
- `else [fallo al reiniciar]`:
  - Pronóstico → Supervisor: `FAILURE (error_al_reiniciar)`.
  - Supervisor notifica y escala a intervención manual, con `notificarFallo()`.
  - Supervisor ejecuta `generarReporte()` (reporte del incidente).

**Fase E: cierre**

19. Supervisor ejecuta `registrarEvento()` (cierre) y `generarReporte()`.

> Este listado es solo ordenamiento narrativo. El diagrama de secuencia final **no lleva números** en las flechas; el orden se lee por la posición vertical.

### 1.5 Flujos alternativos y excepciones

| Condición | Resultado |
|---|---|
| Pronóstico deja de responder (timeout) | El Supervisor registra y notifica con `notificarFallo()`; el Coordinador decide con la última estimación o el historial de consumo |
| Inventario rechaza el traslado (`REFUSE`) | El Coordinador reasigna el lote al otro hospital |
| Ambos hospitales rechazan o ninguno puede recibir el lote | El Coordinador prioriza según urgencia, lo informa al Supervisor y escala; el lote en riesgo de vencimiento queda registrado |
| Sobra demanda tras asignar el lote | El otro hospital pasa a lista de espera o a la Situación 1 (traslado más compra) |
| El reinicio de Pronóstico falla (`FAILURE`) | El Supervisor notifica, escala a intervención manual y genera el reporte |
| Otro agente deja de responder | El Supervisor notifica con `notificarFallo()` y puede iniciar un procedimiento de recuperación autorizado |

### 1.6 Postcondiciones

- El lote de C se asigna a un único hospital (A o B), sin doble asignación, y el inventario de ambos hospitales queda actualizado.
- Se evita la pérdida del lote por vencimiento.
- El hospital que no recibió el lote queda en lista de espera o pasa a la Situación 1.
- El Agente de Pronóstico queda recuperado con el modelo actualizado, o el caso queda escalado a intervención manual.
- Todos los eventos, decisiones y el reporte del incidente quedan registrados por el Supervisor.
