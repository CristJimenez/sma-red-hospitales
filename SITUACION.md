# Contexto: Situación 1 del SMA de abastecimiento de medicamentos

## 1. Situación 1: riesgo de desabastecimiento por brote respiratorio

### 1.1 Descripción

El hospital A (el de mayor complejidad) recibe un aumento de pacientes con infecciones respiratorias. El consumo de un antibiótico crece más rápido de lo normal y su existencia llegará al umbral mínimo en pocos días. El Agente de Inventario genera un evento de riesgo y lo informa. En paralelo, el Agente de Pronóstico proyecta que el consumo seguirá creciendo. El Coordinador integra ambas fuentes, consulta los excedentes de la red y encuentra que el hospital B (pequeño) tiene excedente, pero no alcanza a cubrir la demanda proyectada. Decide **trasladar parte del excedente y comprar el faltante**. El Agente de Compras consulta a los dos proveedores y descubre que el habitual (Proveedor 1) tiene retraso. El Coordinador le pide comprar al alterno (Proveedor 2) dentro del presupuesto autorizado. El Supervisor registra los eventos durante todo el proceso.

La situación demuestra que el problema no es solo detectar un faltante, sino que agentes especializados **perciban, comuniquen, analicen y coordinen** una respuesta colaborativa en un entorno incierto y cambiante.

### 1.2 Precondiciones

- El stock del antibiótico en el hospital A está cerca del umbral mínimo.
- El hospital B tiene excedente del mismo antibiótico.
- Existe presupuesto autorizado disponible.
- Los dos proveedores están registrados con catálogo y tiempos de entrega.
- Todos los agentes están operativos.

### 1.3 Participantes (orden en el diagrama de secuencia, de izquierda a derecha)

1. Red de hospitales públicos (`<<environment>>`)
2. Agente de Inventario (`<<agent>>`)
3. Agente de Pronóstico (`<<agent>>`)
4. Agente Coordinador (`<<agent>>`)
5. Agente de Compras (`<<agent>>`)
6. Agente Supervisor (`<<agent>>`)
7. Objeto Proveedor 1 (habitual)
8. Objeto Proveedor 2 (alterno)
9. Objeto OrdenCompra

### 1.4 Flujo principal, por fases

**Fase A y B, en paralelo (fragmento `par`)**

*Rama de Inventario*
1. Inventario consulta a la Red de hospitales: `leerRegistros()`.
2. La Red responde (retorno): `stock, fechasCaducidad, consumoDiario`.
3. Inventario ejecuta `compararUmbral()`.
4. Inventario ejecuta `generarEventoRiesgo()`.
5. Inventario → Coordinador: `INFORM (riesgo_desabastecimiento antibiotico hospital_A)`, con `enviarInform()`.
6. Inventario → Supervisor: `INFORM (informe_inventario riesgo hospital_A)`, con `enviarInform()`.
7. Supervisor ejecuta `registrarEvento()`.

*Rama de Pronóstico*
8. Pronóstico consulta a la Red: historial de consumo.
9. La Red responde (retorno): `historialConsumo, estacionalidad`.
10. Pronóstico ejecuta `calcularProyeccion()`.
11. Pronóstico → Coordinador: `INFORM (demanda_proyectada antibiotico hospital_A creciente)`, con `enviarEstimacion()`.

**Fase C: análisis y decisión del Coordinador**

12. Coordinador ejecuta `analizarEventos()` e integra inventario actual y demanda esperada para definir la urgencia.
13. Coordinador → Inventario: `QUERY-REF (excedentes antibiotico red)` (protocolo FIPA-Query).
14. Inventario consulta a la Red: `leerRegistros()`.
15. La Red responde (retorno): stock de la red.
16. Inventario → Coordinador: `INFORM (excedente hospital_B cantidad X)`. El excedente no cubre la demanda proyectada.
17. Coordinador ejecuta `decidirTrasladoOCompra()`: traslado parcial más compra del faltante.
18. Coordinador → Red: trasladar excedente de B a A (acción sobre el entorno, no un método de un agente).
19. Coordinador → Supervisor: `INFORM (decision traslado y compra)`.
20. Supervisor ejecuta `registrarEvento()`.

**Fase D: compra (protocolo FIPA-Request)**

21. Coordinador → Compras: `REQUEST (comprar antibiotico cantidad_faltante presupuesto_autorizado)`, con `enviarRequest()`.

*Fragmento `alt` (respuesta de Compras)*
- `[acepta gestionar la compra]`: Compras → Coordinador `AGREE`.
- `else [no puede gestionarla]`: Compras → Coordinador `FAILURE (no_puedo_gestionar compra)`. El flujo termina en esta rama.

22. Compras → Proveedor 1: `consultarProveedor(antibiotico)`.
23. Proveedor 1 responde (retorno): `retraso, plazo_incumplido`.
24. Compras → Proveedor 2: `consultarProveedor(antibiotico)`.
25. Proveedor 2 responde (retorno): `disponibilidad, precio, tiempoEntrega`.
26. Compras ejecuta `compararOfertas()`.
27. Compras → Coordinador: `INFORM (retraso proveedor_1; oferta proveedor_2)`, con `alertarRetraso()`.
28. Compras → Supervisor: `INFORM (retraso proveedor_1)`, con `enviarInform()`; el Supervisor ejecuta `registrarEvento()`.
29. Coordinador → Compras: `REQUEST (comprar a proveedor_2 dentro del presupuesto)`, con `enviarRequest()`.

*Fragmento `alt` (presupuesto)*
- `[oferta dentro del presupuesto]`:
  - Compras ejecuta `generarOrdenCompra()`.
  - Compras → OrdenCompra: crear orden (`cantidad, fecha, estado`).
  - Compras → Proveedor 2: enviar la orden de compra.
  - Proveedor 2 responde (retorno): confirmación de recepción.
  - Compras → Coordinador: `INFORM (orden_generada proveedor_2 estado=generada)`, con `enviarInform()`.
- `else [oferta supera el presupuesto]`:
  - Compras → Coordinador: `FAILURE (presupuesto_insuficiente)`.

**Fase E: confirmación y cierre**

30. Coordinador → Compras: `QUERY-IF (orden_confirmada proveedor_2)`, con `solicitarConfirmacion()`.
31. Compras → Coordinador: `INFORM (orden_confirmada true)`, con `enviarInform()`. El estado de la OrdenCompra pasa de *generada* a *confirmada*.
32. Supervisor ejecuta `registrarEvento()` (cierre) y `generarReporte()`.

*Fragmento `opt`:* `[agente no responde o pedido retrasado]`: Supervisor → Coordinador `INFORM (fallo_detectado)`, con `notificarFallo()`. El reinicio de agentes (`solicitarReinicio()`) se reserva para la Situación 2.

> Este listado es solo ordenamiento narrativo. El diagrama de secuencia final **no lleva números** en las flechas; el orden se lee por la posición vertical.

### 1.5 Flujos alternativos y excepciones

| Condición | Resultado |
|---|---|
| Compras no puede gestionar la compra | `FAILURE`; el Coordinador reevalúa (más traslado desde otros hospitales o escalar urgencia) |
| Ningún proveedor cumple el plazo | El Coordinador prioriza traslado de emergencia; el Supervisor registra |
| La oferta supera el presupuesto | `FAILURE (presupuesto_insuficiente)`; no se genera la orden |
| Un agente deja de responder o el pedido se retrasa | El Supervisor notifica con `notificarFallo()` y puede iniciar un procedimiento de recuperación autorizado |

### 1.6 Postcondiciones

- El hospital A queda abastecido mediante traslado más compra.
- Existe una `OrdenCompra` con cantidad, fecha y estado (generada, luego confirmada).
- Todos los eventos y decisiones quedan registrados por el Supervisor.
