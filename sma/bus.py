"""Bus de mensajes ACL en proceso.

Entrega diferida: un mensaje enviado en la ronda N se entrega al inicio de la
ronda N+1. Eso hace determinista el orden de las conversaciones y reproduce
las rondas de comunicación del escenario.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .acl import MensajeACL

if TYPE_CHECKING:
    from .model import RedHospitalaria


class Bus:
    def __init__(self, modelo: "RedHospitalaria") -> None:
        self.modelo = modelo
        self.pendientes: list[MensajeACL] = []
        self._seq = 0

    def enviar(self, mensaje: MensajeACL) -> None:
        self._seq += 1
        mensaje.seq = self._seq
        mensaje.ronda = self.modelo.ronda
        self.pendientes.append(mensaje)
        self.modelo.traza.registrar_mensaje(mensaje)

    def entregar(self) -> list[MensajeACL]:
        entregados, self.pendientes = self.pendientes, []
        return entregados
