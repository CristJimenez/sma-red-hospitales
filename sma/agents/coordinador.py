"""Agente Coordinador: arquitectura basada en utilidad.

Integra el riesgo del Inventario y la proyección del Pronóstico, prioriza,
planifica (traslado y/o compra), ejecuta las acciones sobre el entorno y
verifica que se confirmen. La decisión vive en ``sma.decision`` como función
pura; este agente solo la aplica y habla FIPA-ACL.
"""

from __future__ import annotations

from typing import Any

from ..acl import (
    AGREE,
    FAILURE,
    FIPA_QUERY,
    FIPA_QUERY_IF,
    FIPA_REQUEST,
    INFORM,
    QUERY_IF,
    QUERY_REF,
    REQUEST,
)
from ..decision import Donante, Oferta, planificar
from .base import AgenteBase


class AgenteCoordinador(AgenteBase):
    nombre = "coordinador"

    def __init__(self, modelo: Any) -> None:
        super().__init__(modelo)
        self.riesgo: dict[str, Any] | None = None
        self.proyeccion: dict[str, Any] | None = None
        self.excedentes: dict[str, Any] | None = None
        self.oferta: dict[str, Any] | None = None
        self.orden: dict[str, Any] | None = None
        self.cola: list[dict[str, Any]] = []
        self.atendidos: list[dict[str, Any]] = []
        self.resultados: list[str] = []
        self.abastecidos: set[str] = set()
        self.consultado = False
        self.decidido = False
        self.compra_alterna_solicitada = False
        self.esperando_emergencia = False
        self.motivo_escalado = ""
        self.traslado_total = 0
        self.faltante = 0
        self.demanda = 0
        self.cantidad_compra = 0

    # ------------------------------------------------------------------
    def procesar(self, mensajes: list[Any]) -> None:
        for mensaje in mensajes:
            if mensaje.performativa == INFORM:
                self._procesar_inform(mensaje)
            elif mensaje.performativa == AGREE:
                self.accion("recibirAgree", {"conversation_id": mensaje.conversation_id})
            elif mensaje.performativa == FAILURE:
                self._manejar_failure(mensaje)

        if self.riesgo and self.proyeccion and not self.consultado:
            self._consultar_excedentes()

    # ------------------------------------------------------------------
    def _procesar_inform(self, mensaje: Any) -> None:
        contenido = mensaje.contenido
        tipo = contenido.get("tipo")
        if tipo == "riesgo_desabastecimiento":
            self._registrar_riesgo(contenido)
        elif tipo == "demanda_proyectada":
            self.proyeccion = contenido
        elif tipo == "excedentes":
            if contenido.get("modo") == "emergencia":
                self.excedentes = contenido
                self._aplicar_emergencia()
            else:
                self.excedentes = contenido
                self._decidir()
        elif tipo == "retraso_proveedor":
            self.oferta = contenido
            self._pedir_compra_alterna()
        elif tipo == "oferta_proveedor":
            self.oferta = contenido
            self._pedir_compra_directa()
        elif tipo == "orden_generada":
            self.orden = contenido.get("orden")
            self._solicitar_confirmacion()
        elif tipo == "orden_confirmada":
            self._cerrar(contenido)
        elif tipo == "fallo_detectado":
            self.accion("registrarFallo", contenido)

    # ------------------------------------------------------------------
    # Riesgos en cola
    # ------------------------------------------------------------------
    def _registrar_riesgo(self, riesgo: dict[str, Any]) -> None:
        clave = (riesgo.get("hospital"), riesgo.get("medicamento"))
        actual = self.riesgo
        if actual and (actual.get("hospital"), actual.get("medicamento")) == clave:
            return
        if any((r.get("hospital"), r.get("medicamento")) == clave for r in self.cola):
            return
        if actual is None:
            self.riesgo = riesgo
            return
        self.cola.append(riesgo)
        self._ordenar_cola()

    def _ordenar_cola(self) -> None:
        if self.model.config.opciones.prioridad_riesgos == "orden_deteccion":
            return
        self.cola.sort(key=lambda r: float(r.get("dias_hasta_agotamiento", 999)))

    def _siguiente_riesgo(self) -> bool:
        if not self.cola:
            return False
        self.riesgo = self.cola.pop(0)
        self.excedentes = None
        self.oferta = None
        self.orden = None
        self.consultado = False
        self.decidido = False
        self.compra_alterna_solicitada = False
        self.esperando_emergencia = False
        self.motivo_escalado = ""
        self.traslado_total = 0
        self.faltante = 0
        self.demanda = 0
        self.cantidad_compra = 0
        self.accion("priorizarRiesgo", self.riesgo)
        return True

    # ------------------------------------------------------------------
    def _consultar_excedentes(self) -> None:
        self.consultado = True
        self.demanda = self._demanda_para(self.riesgo or {})
        self.accion(
            "analizarEventos",
            {
                "riesgo": self.riesgo,
                "demanda_proyectada": self.demanda,
                "riesgos_en_cola": len(self.cola),
            },
        )
        self.enviar(
            QUERY_REF,
            "inventario",
            {
                "consulta": "excedentes",
                "medicamento": self.riesgo["medicamento"],
                "hospital": self.riesgo["hospital"],
                "excluir": self._hospitales_en_riesgo(),
            },
            protocolo=FIPA_QUERY,
            conversation_id="excedentes-1",
            reply_with="q-excedentes-1",
        )

    def _hospitales_en_riesgo(self) -> list[str]:
        """Un hospital con riesgo no puede ser donante: primero se cubre a sí mismo."""
        hospitales = []
        for riesgo in [self.riesgo, *self.cola]:
            if not riesgo:
                continue
            hospital = riesgo.get("hospital")
            if hospital and hospital not in hospitales:
                hospitales.append(hospital)
        for hospital in self.abastecidos:
            if hospital not in hospitales:
                hospitales.append(hospital)
        return hospitales

    def _demanda_para(self, riesgo: dict[str, Any]) -> int:
        hospital_id = riesgo.get("hospital", "")
        med = riesgo.get("medicamento", "")
        proyeccion = self.proyeccion or {}
        if (
            proyeccion.get("hospital") == hospital_id
            and proyeccion.get("medicamento") == med
        ):
            return int(proyeccion.get("demanda_proyectada", 0))

        hospital = self.model.config.hospitales.get(hospital_id)
        if hospital is None:
            return int(proyeccion.get("demanda_proyectada", 0))
        factor = self.model.factor_brote(hospital_id, med)
        consumo = hospital.consumo_efectivo(med, factor)
        return int(round(consumo * self.model.config.horizonte_pronostico_dias))

    # ------------------------------------------------------------------
    # Decisión
    # ------------------------------------------------------------------
    def _decidir(self) -> None:
        if self.decidido or self.riesgo is None:
            return
        self.decidido = True

        med = self.riesgo["medicamento"]
        hospital_id = self.riesgo["hospital"]
        hospital = self.model.config.hospitales[hospital_id]
        medicamento = self.model.config.medicamentos[med]
        stock = hospital.stock(med)
        factor = self.model.factor_brote(hospital_id, med)
        consumo = hospital.consumo_efectivo(med, factor)
        necesidad = max(0, self.demanda - stock)
        presupuesto = self.model.presupuesto_restante
        opciones = self.model.config.opciones

        donantes = [
            Donante(
                hospital_id=donante_id,
                cantidad=int(datos["cantidad"]),
                vence_en_dias=int(datos.get("lote_vence_en_dias", 365)),
                cadena_frio_ok=bool(datos.get("cadena_frio_ok", True)),
            )
            for donante_id, datos in (self.excedentes or {}).get("excedentes", {}).items()
        ]
        ofertas = [
            Oferta(
                proveedor_id=proveedor.id,
                precio_unitario=proveedor.precio(med),
                plazo_dias=proveedor.plazo_efectivo(),
                disponible=proveedor.precio(med) > 0,
            )
            for proveedor in self.model.config.proveedores.values()
        ]

        plan = planificar(
            necesidad=necesidad,
            stock=stock,
            consumo=consumo,
            donantes=donantes,
            ofertas=ofertas,
            presupuesto=presupuesto,
            requiere_frio=medicamento.cadena_frio,
            transporte_refrigerado=opciones.transporte_refrigerado,
            tiempo_traslado_dias=self.model.config.tiempo_traslado_dias,
            politica=opciones.politica_presupuesto,
            permitir_emergencia=opciones.traslado_emergencia,
        )

        movido = 0
        for traslado in plan.traslados:
            movido += self.model.trasladar(
                traslado["hospital"], hospital_id, med, int(traslado["cantidad"])
            )

        self.traslado_total = movido
        self.faltante = max(0, necesidad - movido)
        if movido > 0:
            self.abastecidos.add(hospital_id)
        self.model.demanda_proyectada = self.demanda

        compra = plan.compra
        decision = {
            "tipo": "decision",
            "hospital": hospital_id,
            "medicamento": med,
            "demanda_proyectada": self.demanda,
            "stock_actual": stock,
            "necesidad": necesidad,
            "donantes": [t["hospital"] for t in plan.traslados],
            "traslado": movido,
            "faltante": self.faltante,
            "accion": plan.accion,
            "motivo": plan.motivo,
            "descartes": plan.descartes,
            "compra_prevista": {
                "proveedor": compra.proveedor_id,
                "cantidad": compra.cantidad,
                "coste": compra.coste,
                "motivo": compra.motivo,
            }
            if compra
            else None,
            "riesgo_residual": self.faltante,
        }
        self.model.decision = decision
        self.model.decisiones.append(decision)
        self.accion("decidirTrasladoOCompra", decision)
        self.enviar(INFORM, "supervisor", decision)

        if plan.accion == "ninguna":
            self._finalizar_riesgo("sin_necesidad", "sin_riesgo")
            return

        if self.faltante <= 0:
            self._finalizar_riesgo("cobertura_por_traslado", "exito")
            return

        if compra and compra.motivo in ("ok", "parcial"):
            self.cantidad_compra = min(int(compra.cantidad), self.faltante)
            self._solicitar_compra()
            return

        self._intentar_emergencia(plan.motivo)

    # ------------------------------------------------------------------
    def _solicitar_compra(self) -> None:
        med = self.riesgo["medicamento"]
        self.enviar(
            REQUEST,
            "compras",
            {
                "tipo": "comprar",
                "medicamento": med,
                "cantidad": self.cantidad_compra,
                "hospital": self.riesgo["hospital"],
                "dias_cobertura": round(self._dias_cobertura(), 2),
                "presupuesto_autorizado": round(self.model.presupuesto_restante, 2),
            },
            protocolo=FIPA_REQUEST,
            conversation_id="compra-1",
            reply_with="req-compra-1",
        )
        self.accion(
            "enviarRequest",
            {"destinatario": "compras", "cantidad": self.cantidad_compra},
        )

    def _dias_cobertura(self) -> float:
        med = self.riesgo["medicamento"]
        hospital = self.model.config.hospitales[self.riesgo["hospital"]]
        factor = self.model.factor_brote(hospital.id, med)
        consumo = hospital.consumo_efectivo(med, factor)
        if consumo <= 0:
            return float("inf")
        return hospital.stock(med) / consumo

    # ------------------------------------------------------------------
    # Compra al proveedor alterno / directo
    # ------------------------------------------------------------------
    def _pedir_compra_alterna(self) -> None:
        if self.compra_alterna_solicitada or self.oferta is None:
            return
        self.compra_alterna_solicitada = True

        oferta = self.oferta.get("oferta", {})
        proveedor = oferta.get("proveedor", "P2")
        precio = float(oferta.get("precio_unitario", 0.0))
        cantidad = int(self.oferta.get("cantidad_solicitada", self.faltante))
        coste = cantidad * precio

        if coste <= self.model.presupuesto_restante + 1e-9:
            self._request_proveedor(proveedor, cantidad, "compra-2")
        else:
            self.enviar(
                INFORM,
                "supervisor",
                {"tipo": "fallo_presupuesto", "coste": round(coste, 2)},
            )
            self._intentar_emergencia("presupuesto_insuficiente")

    def _pedir_compra_directa(self) -> None:
        if self.compra_alterna_solicitada or self.oferta is None:
            return
        self.compra_alterna_solicitada = True

        oferta = self.oferta.get("oferta", {})
        proveedor = oferta.get("proveedor", "P1")
        precio = float(oferta.get("precio_unitario", 0.0))
        cantidad = int(self.oferta.get("cantidad_solicitada", self.faltante))
        coste = cantidad * precio

        if coste <= self.model.presupuesto_restante + 1e-9:
            self._request_proveedor(proveedor, cantidad, "compra-1b")
        else:
            self.enviar(
                INFORM,
                "supervisor",
                {"tipo": "fallo_presupuesto", "coste": round(coste, 2)},
            )
            self._intentar_emergencia("presupuesto_insuficiente")

    def _request_proveedor(self, proveedor: str, cantidad: int, conversation: str) -> None:
        self.cantidad_compra = cantidad
        self.enviar(
            REQUEST,
            "compras",
            {
                "tipo": "comprar_a_proveedor",
                "proveedor": proveedor,
                "medicamento": self.riesgo["medicamento"],
                "cantidad": cantidad,
                "presupuesto_autorizado": round(self.model.presupuesto_restante, 2),
            },
            protocolo=FIPA_REQUEST,
            conversation_id=conversation,
            reply_with=f"req-{conversation}",
        )
        self.accion(
            "enviarRequest",
            {
                "destinatario": "compras",
                "proveedor": proveedor,
                "cantidad": cantidad,
            },
        )

    # ------------------------------------------------------------------
    # Replanificación de emergencia
    # ------------------------------------------------------------------
    def _intentar_emergencia(self, motivo: str) -> None:
        self.motivo_escalado = motivo
        if not self.model.config.opciones.traslado_emergencia:
            self._escalar(motivo)
            return
        self.esperando_emergencia = True
        self.enviar(
            QUERY_REF,
            "inventario",
            {
                "consulta": "excedentes_emergencia",
                "medicamento": self.riesgo["medicamento"],
                "hospital": self.riesgo["hospital"],
                "excluir": self._hospitales_en_riesgo(),
            },
            protocolo=FIPA_QUERY,
            conversation_id="emergencia-1",
            reply_with="q-emergencia-1",
        )
        self.accion("replanificar", {"motivo": motivo, "consulta": "emergencia"})

    def _aplicar_emergencia(self) -> None:
        if self.riesgo is None:
            return
        self.esperando_emergencia = False
        med = self.riesgo["medicamento"]
        hospital_id = self.riesgo["hospital"]

        donantes = [
            Donante(
                hospital_id=donante_id,
                cantidad=int(datos["cantidad"]),
                vence_en_dias=int(datos.get("lote_vence_en_dias", 365)),
                cadena_frio_ok=bool(datos.get("cadena_frio_ok", True)),
            )
            for donante_id, datos in (self.excedentes or {}).get("excedentes", {}).items()
        ]

        movido = 0
        restante = self.faltante
        for donante in sorted(donantes, key=lambda d: (-d.cantidad, d.vence_en_dias)):
            if restante <= 0:
                break
            cantidad = min(donante.cantidad, restante)
            hecho = self.model.trasladar(donante.hospital_id, hospital_id, med, cantidad)
            movido += hecho
            restante -= hecho

        self.traslado_total += movido
        if movido > 0:
            self.abastecidos.add(hospital_id)
        self.faltante = max(0, self.faltante - movido)
        self.model.replanificaciones += 1
        self.model.riesgo_residual = self.faltante

        if self.faltante <= 0:
            accion = "traslado_emergencia"
            resultado = "exito"
        elif self.traslado_total > 0:
            accion = "traslado_parcial"
            resultado = "parcial"
        else:
            accion = "escalar"
            resultado = "fallo"

        if self.model.decision is not None:
            self.model.decision["accion"] = accion
            self.model.decision["traslado"] = self.traslado_total
            self.model.decision["faltante"] = self.faltante
            self.model.decision["riesgo_residual"] = self.faltante
            self.model.decision["replanificacion"] = {
                "motivo": self.motivo_escalado,
                "traslado_extra": movido,
            }
            self.model.decisiones[-1] = self.model.decision

        self.enviar(
            INFORM,
            "supervisor",
            {
                "tipo": "replanificacion",
                "motivo": self.motivo_escalado,
                "traslado_extra": movido,
                "riesgo_residual": self.faltante,
            },
        )
        self.accion(
            "verificarAcciones",
            {"accion": accion, "riesgo_residual": self.faltante},
        )
        self._finalizar_riesgo(accion, resultado)

    def _escalar(self, motivo: str) -> None:
        self.model.riesgo_residual = self.faltante
        self.enviar(
            INFORM,
            "supervisor",
            {
                "tipo": "escalado",
                "motivo": motivo,
                "hospital": (self.riesgo or {}).get("hospital"),
                "medicamento": (self.riesgo or {}).get("medicamento"),
                "riesgo_residual": self.faltante,
            },
        )
        self.accion("escalar", {"motivo": motivo, "riesgo_residual": self.faltante})
        self._finalizar_riesgo(motivo, "parcial" if self.traslado_total else "fallo")

    # ------------------------------------------------------------------
    # Cierre
    # ------------------------------------------------------------------
    def _solicitar_confirmacion(self) -> None:
        if not self.orden:
            return
        self.enviar(
            QUERY_IF,
            "compras",
            {"consulta": "orden_confirmada", "orden": self.orden.get("orden")},
            protocolo=FIPA_QUERY_IF,
            conversation_id="confirmacion-1",
            reply_with="q-confirmacion-1",
        )
        self.accion("solicitarConfirmacion", {"orden": self.orden.get("orden")})

    def _cerrar(self, contenido: dict[str, Any]) -> None:
        if self.orden is None:
            return
        self.accion(
            "verificarAcciones",
            {"orden": contenido.get("orden"), "confirmada": contenido.get("confirmada")},
        )
        residual = max(0, self.faltante - self.cantidad_compra)
        self.model.riesgo_residual = residual
        if self.model.decision is not None:
            self.model.decision["riesgo_residual"] = residual
            self.model.decisiones[-1] = self.model.decision
        resultado = "parcial" if residual > 0 else "exito"
        self._finalizar_riesgo("orden_confirmada", resultado, contenido.get("orden"))

    def _finalizar_riesgo(
        self, motivo: str, resultado: str, orden: Any = None
    ) -> None:
        self.atendidos.append(
            {
                "hospital": (self.riesgo or {}).get("hospital"),
                "medicamento": (self.riesgo or {}).get("medicamento"),
                "motivo": motivo,
                "resultado": resultado,
            }
        )
        self.resultados.append(resultado)

        if self._siguiente_riesgo():
            return

        self.model.cierre = True
        self.model.resultado = resultado
        self.enviar(
            INFORM,
            "supervisor",
            {
                "tipo": "cierre",
                "orden": orden,
                "motivo": motivo,
                "resultado": resultado,
                "riesgos_atendidos": len(self.atendidos),
            },
        )

    def _manejar_failure(self, mensaje: Any) -> None:
        motivo = mensaje.contenido.get("motivo", "desconocido")
        self.model.replanificaciones += 1
        self.accion("reevaluar", {"motivo": motivo})
        self.enviar(
            INFORM,
            "supervisor",
            {"tipo": "fallo_compra", "motivo": motivo},
        )
        self._intentar_emergencia(motivo)
