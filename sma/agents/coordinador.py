"""Agente Coordinador: arquitectura basada en utilidad.

Integra el riesgo del Inventario y la proyección del Pronóstico, prioriza,
decide entre traslado y compra, y verifica que las acciones se ejecuten.
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
        self.consultado = False
        self.decidido = False
        self.compra_alterna_solicitada = False
        self.cerrado = False
        self.traslado_total = 0
        self.faltante = 0
        self.demanda = 0

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
            self.riesgo = contenido
        elif tipo == "demanda_proyectada":
            self.proyeccion = contenido
        elif tipo == "excedentes":
            self.excedentes = contenido
            self._decidir()
        elif tipo == "retraso_proveedor":
            self.oferta = contenido
            self._pedir_compra_alterna()
        elif tipo == "orden_generada":
            self.orden = contenido.get("orden")
            self._solicitar_confirmacion()
        elif tipo == "orden_confirmada":
            self._cerrar(contenido)
        elif tipo == "fallo_detectado":
            self.accion("registrarFallo", contenido)

    # ------------------------------------------------------------------
    def _consultar_excedentes(self) -> None:
        self.consultado = True
        self.demanda = int(self.proyeccion["demanda_proyectada"])
        self.accion(
            "analizarEventos",
            {
                "riesgo": self.riesgo,
                "demanda_proyectada": self.demanda,
            },
        )
        self.enviar(
            QUERY_REF,
            "inventario",
            {
                "consulta": "excedentes",
                "medicamento": self.riesgo["medicamento"],
                "hospital": self.riesgo["hospital"],
            },
            protocolo=FIPA_QUERY,
            conversation_id="excedentes-1",
            reply_with="q-excedentes-1",
        )

    def _decidir(self) -> None:
        if self.decidido:
            return
        self.decidido = True

        med = self.riesgo["medicamento"]
        hospital_id = self.riesgo["hospital"]
        hospital = self.model.config.hospitales[hospital_id]
        stock = hospital.stock(med)
        necesidad = max(0, self.demanda - stock)

        excedentes = (self.excedentes or {}).get("excedentes", {})
        donante_id = None
        traslado = 0
        if excedentes:
            donante_id, datos = max(
                excedentes.items(), key=lambda par: par[1]["cantidad"]
            )
            traslado = min(int(datos["cantidad"]), necesidad)

        movido = 0
        if donante_id and traslado > 0:
            movido = self.model.trasladar(donante_id, hospital_id, med, traslado)

        self.traslado_total = movido
        self.faltante = max(0, necesidad - movido)
        self.model.demanda_proyectada = self.demanda

        decision = {
            "tipo": "decision",
            "hospital": hospital_id,
            "medicamento": med,
            "demanda_proyectada": self.demanda,
            "stock_actual": stock,
            "donante": donante_id,
            "traslado": movido,
            "faltante": self.faltante,
            "accion": "traslado_y_compra" if self.faltante else "traslado",
        }
        self.model.decision = decision
        self.accion("decidirTrasladoOCompra", decision)
        self.enviar(INFORM, "supervisor", decision)

        if self.faltante > 0:
            self.enviar(
                REQUEST,
                "compras",
                {
                    "tipo": "comprar",
                    "medicamento": med,
                    "cantidad": self.faltante,
                    "hospital": hospital_id,
                    "presupuesto_autorizado": round(
                        self.model.presupuesto_restante, 2
                    ),
                },
                protocolo=FIPA_REQUEST,
                conversation_id="compra-1",
                reply_with="req-compra-1",
            )
            self.accion(
                "enviarRequest",
                {"destinatario": "compras", "cantidad": self.faltante},
            )

    def _pedir_compra_alterna(self) -> None:
        if self.compra_alterna_solicitada or self.oferta is None:
            return
        self.compra_alterna_solicitada = True

        oferta = self.oferta.get("oferta", {})
        proveedor = oferta.get("proveedor", "P2")
        precio = float(oferta.get("precio_unitario", 0.0))
        coste = self.faltante * precio

        if coste <= self.model.presupuesto_restante + 1e-9:
            self.enviar(
                REQUEST,
                "compras",
                {
                    "tipo": "comprar_a_proveedor",
                    "proveedor": proveedor,
                    "medicamento": self.riesgo["medicamento"],
                    "cantidad": self.faltante,
                    "presupuesto_autorizado": round(
                        self.model.presupuesto_restante, 2
                    ),
                },
                protocolo=FIPA_REQUEST,
                conversation_id="compra-2",
                reply_with="req-compra-2",
            )
            self.accion(
                "enviarRequest",
                {
                    "destinatario": "compras",
                    "proveedor": proveedor,
                    "cantidad": self.faltante,
                },
            )
        else:
            self.enviar(
                INFORM,
                "supervisor",
                {"tipo": "fallo_presupuesto", "coste": round(coste, 2)},
            )

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
        if self.cerrado:
            return
        self.cerrado = True
        self.model.cierre = True
        self.accion(
            "verificarAcciones",
            {"orden": contenido.get("orden"), "confirmada": contenido.get("confirmada")},
        )
        self.enviar(
            INFORM,
            "supervisor",
            {"tipo": "cierre", "orden": contenido.get("orden")},
        )

    def _manejar_failure(self, mensaje: Any) -> None:
        motivo = mensaje.contenido.get("motivo", "desconocido")
        self.accion("reevaluar", {"motivo": motivo})
        self.enviar(
            INFORM,
            "supervisor",
            {"tipo": "fallo_compra", "motivo": motivo},
        )
