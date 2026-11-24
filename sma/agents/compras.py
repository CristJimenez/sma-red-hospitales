"""Agente de Proveedores y Compras: arquitectura basada en objetivos.

Consulta catálogo y plazos, compara ofertas, genera órdenes dentro del
presupuesto autorizado y hace seguimiento hasta la confirmación.
"""

from __future__ import annotations

from typing import Any

from ..acl import (
    AGREE,
    FAILURE,
    FIPA_REQUEST,
    INFORM,
    QUERY_IF,
    REQUEST,
)
from ..decision import Oferta, elegir_proveedor
from .base import AgenteBase


class AgenteCompras(AgenteBase):
    nombre = "compras"

    def __init__(self, modelo: Any) -> None:
        super().__init__(modelo)
        self.orden: Any = None

    # ------------------------------------------------------------------
    def procesar(self, mensajes: list[Any]) -> None:
        for mensaje in mensajes:
            if mensaje.performativa == REQUEST:
                tipo = mensaje.contenido.get("tipo")
                if tipo == "comprar":
                    self._gestionar_compra(mensaje)
                elif tipo == "comprar_a_proveedor":
                    self._comprar(mensaje)
            elif mensaje.performativa == QUERY_IF:
                self._confirmar(mensaje)

    # ------------------------------------------------------------------
    def _gestionar_compra(self, mensaje: Any) -> None:
        med = mensaje.contenido["medicamento"]
        cantidad = int(mensaje.contenido["cantidad"])
        cobertura = float(mensaje.contenido.get("dias_cobertura", 365))
        config = self.model.config

        if not config.opciones.compras_puede_gestionar:
            self.enviar(
                FAILURE,
                "coordinador",
                {"motivo": "no_puedo_gestionar_compra"},
                conversation_id=mensaje.conversation_id,
                in_reply_to=mensaje.reply_with,
            )
            self.accion("rechazarCompra", {"motivo": "no_puedo_gestionar_compra"})
            return

        ofertas = [
            Oferta(
                proveedor_id=proveedor.id,
                precio_unitario=proveedor.precio(med),
                plazo_dias=proveedor.plazo_efectivo(),
                disponible=proveedor.precio(med) > 0,
            )
            for proveedor in config.proveedores.values()
        ]
        eleccion = elegir_proveedor(
            ofertas,
            cantidad,
            cobertura,
            presupuesto=float("inf"),
            politica="rechazar",
        )

        if eleccion.motivo != "ok":
            self.enviar(
                FAILURE,
                "coordinador",
                {
                    "motivo": "sin_proveedor_viable",
                    "cantidad": cantidad,
                    "dias_cobertura": round(cobertura, 2),
                    "ofertas": [
                        {
                            "proveedor": oferta.proveedor_id,
                            "plazo_dias": oferta.plazo_dias,
                            "precio_unitario": oferta.precio_unitario,
                        }
                        for oferta in ofertas
                    ],
                },
                conversation_id=mensaje.conversation_id,
                in_reply_to=mensaje.reply_with,
            )
            self.accion("rechazarCompra", {"motivo": "sin_proveedor_viable"})
            return

        self.enviar(
            AGREE,
            "coordinador",
            {"tipo": "gestion_compra", "cantidad": cantidad},
            conversation_id=mensaje.conversation_id,
            in_reply_to=mensaje.reply_with,
        )

        for proveedor in config.proveedores.values():
            self.accion(
                "consultarProveedor",
                {
                    "proveedor": proveedor.id,
                    "medicamento": med,
                    "precio": proveedor.precio(med),
                    "tiempo_entrega_dias": proveedor.tiempo_entrega_dias,
                    "retraso_dias": proveedor.retraso_dias,
                },
            )

        habitual = config.proveedores["P1"]
        elegido = config.proveedores[eleccion.proveedor_id]
        oferta = {
            "proveedor": elegido.id,
            "precio_unitario": elegido.precio(med),
            "tiempo_entrega_dias": elegido.tiempo_entrega_dias,
            "retraso_dias": elegido.retraso_dias,
            "plazo_dias": elegido.plazo_efectivo(),
            "disponible": True,
        }
        self.accion(
            "compararOfertas",
            {
                "ofertas": [
                    {
                        "proveedor": o.proveedor_id,
                        "precio_unitario": o.precio_unitario,
                        "plazo_dias": o.plazo_dias,
                    }
                    for o in ofertas
                ],
                "elegido": elegido.id,
            },
        )

        if habitual.retraso_dias > 0 and elegido.id != habitual.id:
            self.enviar(
                INFORM,
                "coordinador",
                {
                    "tipo": "retraso_proveedor",
                    "proveedor_retrasado": habitual.id,
                    "retraso_dias": habitual.retraso_dias,
                    "oferta": oferta,
                    "cantidad_solicitada": cantidad,
                },
                conversation_id=mensaje.conversation_id,
            )
            self.enviar(
                INFORM,
                "supervisor",
                {
                    "tipo": "retraso_proveedor",
                    "proveedor": habitual.id,
                    "retraso_dias": habitual.retraso_dias,
                },
            )
            self.accion(
                "alertarRetraso",
                {"proveedor": habitual.id, "retraso_dias": habitual.retraso_dias},
            )
        else:
            self.enviar(
                INFORM,
                "coordinador",
                {
                    "tipo": "oferta_proveedor",
                    "proveedor": elegido.id,
                    "oferta": oferta,
                    "cantidad_solicitada": cantidad,
                },
                conversation_id=mensaje.conversation_id,
            )

    # ------------------------------------------------------------------
    def _comprar(self, mensaje: Any) -> None:
        contenido = mensaje.contenido
        med = contenido["medicamento"]
        cantidad = int(contenido["cantidad"])
        proveedor = self.model.config.proveedores[contenido["proveedor"]]
        coste = cantidad * proveedor.precio(med)

        if (
            self.model.config.opciones.forzar_presupuesto_insuficiente
            or coste > self.model.presupuesto_restante + 1e-9
        ):
            self.enviar(
                FAILURE,
                "coordinador",
                {
                    "motivo": "presupuesto_insuficiente",
                    "coste": round(coste, 2),
                    "presupuesto": round(self.model.presupuesto_restante, 2),
                },
                conversation_id=mensaje.conversation_id,
                in_reply_to=mensaje.reply_with,
            )
            self.accion(
                "rechazarPorPresupuesto",
                {"coste": round(coste, 2)},
            )
            return

        orden = self.model.crear_orden(med, cantidad, proveedor.id, coste)
        self.orden = orden
        self.model.gastar(coste)
        self.accion("generarOrdenCompra", orden.a_dict())

        alias = "proveedor_2" if proveedor.id == "P2" else "proveedor_1"
        self.model.traza.registrar_entorno(
            self.model.ronda,
            "crear_orden",
            orden.a_dict(),
            origen="compras",
            destino="orden_compra",
        )
        self.model.traza.registrar_entorno(
            self.model.ronda,
            "enviar_orden",
            {"proveedor": proveedor.id, "cantidad": cantidad},
            origen="compras",
            destino=alias,
        )
        self.model.traza.registrar_entorno(
            self.model.ronda,
            "confirmacion_recepcion",
            {"proveedor": proveedor.id},
            origen=alias,
            destino="compras",
        )

        self.enviar(
            INFORM,
            "coordinador",
            {"tipo": "orden_generada", "orden": orden.a_dict()},
            conversation_id=mensaje.conversation_id,
            in_reply_to=mensaje.reply_with,
        )

    # ------------------------------------------------------------------
    def _confirmar(self, mensaje: Any) -> None:
        if self.orden is None:
            self.enviar(
                INFORM,
                "coordinador",
                {"tipo": "orden_confirmada", "confirmada": False, "orden": None},
                conversation_id=mensaje.conversation_id,
            )
            return

        self.orden.estado = "confirmada"
        self.accion("confirmarOrden", self.orden.a_dict())
        self.enviar(
            INFORM,
            "coordinador",
            {
                "tipo": "orden_confirmada",
                "confirmada": True,
                "orden": self.orden.a_dict(),
            },
            conversation_id=mensaje.conversation_id,
            in_reply_to=mensaje.reply_with,
        )
