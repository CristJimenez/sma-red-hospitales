"""Agente Supervisor de la Situación 2: arquitectura deliberativa.

Monitorea el tiempo de respuesta del Pronóstico, registra el timeout, notifica
al Coordinador, activa la recuperación del agente y genera el reporte del
incidente y el reporte de cierre.
"""

from __future__ import annotations

from typing import Any

from ...acl import AGREE, FAILURE, FIPA_REQUEST, INFORM, REQUEST
from ..base import AgenteBase

EVENTOS = {
    "informe_inventario",
    "decision",
    "cierre",
    "reinicio_completado",
    "error_al_reiniciar",
}


class AgenteSupervisorS2(AgenteBase):
    nombre = "supervisor"

    def __init__(self, modelo: Any) -> None:
        super().__init__(modelo)
        self.registros: list[dict[str, Any]] = []
        self.reporte: dict[str, Any] | None = None
        self.reporte_incidente: dict[str, Any] | None = None
        self.timeout_detectado = False
        self.reinicio_solicitado = False

    # ------------------------------------------------------------------
    def procesar(self, mensajes: list[Any]) -> None:
        for mensaje in mensajes:
            if mensaje.performativa == INFORM:
                self._procesar_inform(mensaje)
            elif mensaje.performativa == AGREE:
                self._registrar("reinicio_aceptado", mensaje.contenido)
            elif mensaje.performativa == FAILURE:
                self._procesar_failure(mensaje)

        self._verificar_timeout()
        self._verificar_sin_riesgo()

    # ------------------------------------------------------------------
    def _procesar_inform(self, mensaje: Any) -> None:
        contenido = mensaje.contenido
        tipo = contenido.get("tipo")
        if tipo in EVENTOS:
            self._registrar(tipo, contenido)

        if tipo == "reinicio_completado":
            self.model.pronostico_recuperado = True
            self.model.reinicio_estado = "exitoso"
            self._reporte_incidente("exitoso")
        elif tipo == "cierre":
            self._generar_reporte(contenido)

    def _procesar_failure(self, mensaje: Any) -> None:
        contenido = mensaje.contenido
        if contenido.get("tipo") != "error_al_reiniciar":
            return
        self._registrar("error_al_reiniciar", contenido)
        self.model.reinicio_estado = "fallido"
        self.model.escalado = True
        self.accion(
            "notificarFallo",
            {"agente": "pronostico", "motivo": "error_al_reiniciar"},
        )
        self.accion("escalarIntervencionManual", {"agente": "pronostico"})
        self._reporte_incidente("fallido")

    # ------------------------------------------------------------------
    # Detección del timeout y recuperación
    # ------------------------------------------------------------------
    def _verificar_timeout(self) -> None:
        if self.timeout_detectado:
            return
        consulta = self.model.consulta_pronostico
        if not consulta or consulta.get("respondida"):
            return
        if self.model.ronda <= int(consulta.get("ronda", 0)):
            return

        self.timeout_detectado = True
        self.model.timeout_pronostico = True
        self.accion(
            "detectarTimeout",
            {"agente": "pronostico", "ronda_consulta": consulta.get("ronda")},
        )
        self._registrar(
            "timeout_pronostico",
            {"agente": "pronostico", "ronda_consulta": consulta.get("ronda")},
        )
        self.enviar(
            INFORM,
            "coordinador",
            {"tipo": "fallo_detectado", "agente": "pronostico", "motivo": "timeout"},
        )
        self.accion(
            "notificarFallo",
            {"agente": "pronostico", "motivo": "timeout"},
        )
        self.enviar(
            REQUEST,
            "pronostico",
            {
                "tipo": "solicitar_reinicio",
                "accion": "solicitar_reinicio",
                "agente": "pronostico",
            },
            protocolo=FIPA_REQUEST,
            conversation_id="reinicio-1",
            reply_with="req-reinicio-1",
        )
        self.accion("solicitarReinicio", {"agente": "pronostico"})
        self.reinicio_solicitado = True

    # ------------------------------------------------------------------
    # Registro y reportes
    # ------------------------------------------------------------------
    def _registrar(self, evento: str, contenido: dict[str, Any]) -> None:
        detalle = {k: v for k, v in contenido.items() if k != "tipo"}
        self.registros.append({"evento": evento, **detalle})
        self.accion("registrarEvento", {"evento": evento})

    def _reporte_incidente(self, resultado: str) -> None:
        self.reporte_incidente = {
            "tipo": "incidente",
            "agente": "pronostico",
            "resultado": resultado,
            "ronda": self.model.ronda,
            "lote_asignado": self.model.lote_asignado,
        }
        self.accion("generarReporte", {"alcance": "incidente", "resultado": resultado})

    def _verificar_sin_riesgo(self) -> None:
        if self.reporte is not None:
            return
        if self.model.ronda < self.model.config.ronda_inicio + 3:
            return
        if self.registros:
            return
        self.model.resultado = "sin_riesgo"
        self.model.cierre = True
        self.accion("generarReporte", {"resultado": "sin_riesgo"})
        self._generar_reporte({"resultado": "sin_riesgo", "motivo": "sin_riesgo"})

    def _generar_reporte(self, contenido: dict[str, Any] | None = None) -> None:
        contenido = contenido or {}
        self.reporte = self.model.metricas()
        self.reporte["resultado"] = contenido.get(
            "resultado", self.model.resultado or "exito"
        )
        self.reporte["motivo"] = contenido.get("motivo", "")
        self.reporte["incidente"] = self.reporte_incidente
        self.reporte["lote_asignado"] = self.model.lote_asignado
        self.reporte["riesgos_atendidos"] = len(self.model.decisiones)
        self.accion("generarReporte", self.reporte)
