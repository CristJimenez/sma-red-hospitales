"""Agente Supervisor: arquitectura deliberativa.

Observa el sistema, registra eventos y decisiones, comprueba la disponibilidad
de los agentes y genera el reporte de cierre. El reinicio de agentes queda
fuera de la Situación 1 (se reserva para la Situación 2).
"""

from __future__ import annotations

from typing import Any

from ..acl import INFORM
from .base import AgenteBase

EVENTOS = {
    "informe_inventario",
    "decision",
    "retraso_proveedor",
    "fallo_compra",
    "fallo_presupuesto",
    "replanificacion",
    "escalado",
    "cierre",
}


class AgenteSupervisor(AgenteBase):
    nombre = "supervisor"

    def __init__(self, modelo: Any) -> None:
        super().__init__(modelo)
        self.registros: list[dict[str, Any]] = []
        self.reporte: dict[str, Any] | None = None
        self.fallo_notificado = False

    # ------------------------------------------------------------------
    def procesar(self, mensajes: list[Any]) -> None:
        for mensaje in mensajes:
            if mensaje.performativa != INFORM:
                continue
            tipo = mensaje.contenido.get("tipo")
            if tipo in EVENTOS:
                detalle = {k: v for k, v in mensaje.contenido.items() if k != "tipo"}
                self.registros.append({"evento": tipo, **detalle})
                self.accion("registrarEvento", {"evento": tipo})
                if tipo == "cierre":
                    self._generar_reporte(mensaje.contenido)

        self._verificar_sin_riesgo()
        self._verificar_disponibilidad()

    # ------------------------------------------------------------------
    def _verificar_sin_riesgo(self) -> None:
        if self.reporte is not None:
            return
        if self.model.ronda < self.model.config.evento.ronda_inicio + 3:
            return
        if self.registros:
            return
        self.model.resultado = "sin_riesgo"
        self.model.cierre = True
        self.accion("generarReporte", {"resultado": "sin_riesgo"})
        self._generar_reporte({"resultado": "sin_riesgo", "motivo": "sin_riesgo"})

    # ------------------------------------------------------------------
    def _verificar_disponibilidad(self) -> None:
        if not self.model.config.opciones.simular_agente_caido:
            return
        if self.fallo_notificado or self.model.ronda < 2:
            return
        self.fallo_notificado = True
        self.accion("notificarFallo", {"agente": "compras", "motivo": "sin respuesta"})
        self.enviar(
            INFORM,
            "coordinador",
            {"tipo": "fallo_detectado", "agente": "compras"},
        )

    def _generar_reporte(self, contenido: dict[str, Any] | None = None) -> None:
        contenido = contenido or {}
        self.reporte = self.model.metricas()
        self.reporte["resultado"] = contenido.get(
            "resultado", self.model.resultado or "exito"
        )
        self.reporte["motivo"] = contenido.get("motivo", "")
        self.reporte["riesgos_atendidos"] = contenido.get(
            "riesgos_atendidos", len(self.model.decisiones)
        )
        self.accion("generarReporte", self.reporte)
