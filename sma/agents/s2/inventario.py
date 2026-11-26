"""Agente de Inventario de la Situación 2: arquitectura reactiva.

Detecta el lote próximo a vencer en el hospital C, responde las consultas de
stock de A y B y ejecuta (o rechaza) el traslado que le pide el Coordinador.
"""

from __future__ import annotations

from typing import Any

from ...acl import AGREE, FIPA_QUERY, FIPA_REQUEST, INFORM, QUERY_REF, REFUSE, REQUEST
from ..base import AgenteBase


class AgenteInventarioS2(AgenteBase):
    nombre = "inventario"

    def procesar(self, mensajes: list[Any]) -> None:
        for mensaje in mensajes:
            if mensaje.performativa == QUERY_REF and mensaje.contenido.get(
                "consulta"
            ) == "stock":
                self._responder_stock(mensaje)
            elif (
                mensaje.performativa == REQUEST
                and mensaje.contenido.get("accion") == "preparar_traslado"
            ):
                self._preparar_traslado(mensaje)

        if self.model.ronda == self.model.config.ronda_inicio:
            self._detectar_vencimiento()

    # ------------------------------------------------------------------
    # Fase A: detección del riesgo de vencimiento
    # ------------------------------------------------------------------
    def _detectar_vencimiento(self) -> None:
        config = self.model.config
        self.accion("leerRegistros", {"consulta": "stock_fechas_consumo"})

        for hospital in config.hospitales.values():
            for med_id in config.medicamentos:
                consumo = hospital.consumo_diario.get(med_id, 0.0)
                for lote in hospital.lotes.get(med_id, []):
                    if lote.cantidad <= 0:
                        continue
                    if lote.vence_en_dias > config.opciones.dias_para_vencer:
                        continue
                    cobertura = lote.cantidad / consumo if consumo > 0 else float("inf")
                    # Solo es riesgo si no se alcanza a consumir antes de vencer.
                    if cobertura <= lote.vence_en_dias:
                        continue

                    evento = {
                        "tipo": "riesgo_vencimiento",
                        "hospital": hospital.id,
                        "medicamento": med_id,
                        "lote": lote.id,
                        "cantidad": lote.cantidad,
                        "vence_en_dias": lote.vence_en_dias,
                        "consumo_diario": round(consumo, 2),
                        "cobertura_dias": round(cobertura, 2),
                    }
                    self.accion("compararUmbral", evento)
                    self.accion("generarEventoRiesgo", evento)
                    self.enviar(INFORM, "coordinador", evento)
                    self.enviar(
                        INFORM,
                        "supervisor",
                        {
                            "tipo": "informe_inventario",
                            "hospital": hospital.id,
                            "medicamento": med_id,
                            "lote": lote.id,
                            "nivel": "vencimiento",
                        },
                    )

    # ------------------------------------------------------------------
    # Fase C: consulta de stock de los hospitales que compiten
    # ------------------------------------------------------------------
    def _responder_stock(self, consulta: Any) -> None:
        config = self.model.config
        med_id = consulta.contenido.get("medicamento", self.model.medicamento)
        hospitales = consulta.contenido.get("hospitales", [])
        self.accion("leerRegistros", {"consulta": "stock", "hospitales": hospitales})

        respuesta: dict[str, dict[str, Any]] = {}
        for hospital_id in hospitales:
            hospital = config.hospitales[hospital_id]
            lotes = [
                lote
                for lote in hospital.lotes.get(med_id, [])
                if lote.cantidad > 0
            ]
            respuesta[hospital_id] = {
                "stock": hospital.stock(med_id),
                "consumo_diario": round(hospital.consumo_diario.get(med_id, 0.0), 2),
                "dias_hasta_agotamiento": round(
                    hospital.dias_hasta_agotamiento(med_id), 2
                ),
                "vence_en_dias": min(
                    (lote.vence_en_dias for lote in lotes), default=365
                ),
            }

        self.enviar(
            INFORM,
            "coordinador",
            {"tipo": "stock", "medicamento": med_id, "hospitales": respuesta},
            protocolo=FIPA_QUERY,
            conversation_id=consulta.conversation_id,
            in_reply_to=consulta.reply_with,
        )

    # ------------------------------------------------------------------
    # Fase C: traslado del lote
    # ------------------------------------------------------------------
    def _preparar_traslado(self, peticion: Any) -> None:
        contenido = peticion.contenido
        destino = contenido["destino"]
        lote_id = contenido.get("lote", self.model.lote.id)

        if self.model.rechazos_pendientes > 0:
            self.model.rechazos_pendientes -= 1
            self.accion(
                "rechazarTraslado",
                {"lote": lote_id, "destino": destino, "motivo": "traslado_inconveniente"},
            )
            self.enviar(
                REFUSE,
                "coordinador",
                {
                    "tipo": "traslado_rechazado",
                    "lote": lote_id,
                    "destino": destino,
                    "motivo": "traslado_inconveniente",
                },
                protocolo=FIPA_REQUEST,
                conversation_id=peticion.conversation_id,
                in_reply_to=peticion.reply_with,
            )
            return

        self.accion(
            "prepararTraslado",
            {
                "lote": lote_id,
                "origen": contenido.get("origen", self.model.hospital_origen),
                "destino": destino,
                "cantidad": contenido.get("cantidad", self.model.lote.cantidad),
            },
        )
        self.enviar(
            AGREE,
            "coordinador",
            {"tipo": "traslado_aceptado", "lote": lote_id, "destino": destino},
            protocolo=FIPA_REQUEST,
            conversation_id=peticion.conversation_id,
            in_reply_to=peticion.reply_with,
        )

        movido = self.model.asignar_lote(destino)
        self.enviar(
            INFORM,
            "coordinador",
            {
                "tipo": "traslado_realizado",
                "lote": lote_id,
                "origen": contenido.get("origen", self.model.hospital_origen),
                "destino": destino,
                "cantidad": movido,
                "inventarios_actualizados": True,
                "restante": self.model.lote.cantidad,
            },
            protocolo=FIPA_REQUEST,
            conversation_id=peticion.conversation_id,
            in_reply_to=peticion.reply_with,
        )
