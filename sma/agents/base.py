"""Base común de los agentes.

Los agentes heredan de ``mesa.Agent`` (registro, ciclo de vida y activación
gestionados por Mesa) y toda la comunicación pasa por el bus FIPA-ACL.
"""

from __future__ import annotations

from typing import Any

import mesa

from ..acl import FIPA_REQUEST, MensajeACL


class AgenteBase(mesa.Agent):
    nombre = "agente"

    def __init__(self, modelo: Any) -> None:
        super().__init__(modelo)
        self.buzon: list[MensajeACL] = []

    # -- ciclo de vida ---------------------------------------------------
    def step(self) -> None:
        self.model.latidos[self.nombre] = self.model.ronda
        mensajes, self.buzon = self.buzon, []
        self.procesar(mensajes)

    def procesar(self, mensajes: list[MensajeACL]) -> None:  # pragma: no cover
        raise NotImplementedError

    # -- utilidades ------------------------------------------------------
    def enviar(
        self,
        performativa: str,
        receptor: str,
        contenido: dict[str, Any],
        protocolo: str = FIPA_REQUEST,
        conversation_id: str = "",
        reply_with: str = "",
        in_reply_to: str = "",
    ) -> MensajeACL:
        mensaje = MensajeACL(
            performativa=performativa,
            emisor=self.nombre,
            receptor=receptor,
            contenido=contenido,
            protocolo=protocolo,
            conversation_id=conversation_id,
            reply_with=reply_with,
            in_reply_to=in_reply_to,
        )
        self.model.bus.enviar(mensaje)
        return mensaje

    def accion(self, nombre: str, detalle: dict[str, Any] | None = None) -> None:
        self.model.traza.registrar_accion(
            self.model.ronda, self.nombre, nombre, detalle
        )
