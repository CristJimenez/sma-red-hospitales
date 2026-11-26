"""Agente de Pronóstico de la Situación 2.

Comparte el modelo Holt + estacionalidad de la Situación 1 (``sma.forecast``).
En esta situación deja de responder en una ronda configurada, conserva su
última estimación y atiende el procedimiento de recuperación del Supervisor.
"""

from __future__ import annotations

from typing import Any

from ...acl import AGREE, FAILURE, FIPA_QUERY, FIPA_REQUEST, INFORM, QUERY_REF, REQUEST
from ...forecast import factores_estacionales, mape, proyectar
from ..base import AgenteBase


class AgentePronosticoS2(AgenteBase):
    nombre = "pronostico"

    def __init__(self, modelo: Any) -> None:
        super().__init__(modelo)
        self.caido = False
        self.recuperado = False
        self.reinicio_pendiente = False
        self.fallo_reinicio = False

    # ------------------------------------------------------------------
    def procesar(self, mensajes: list[Any]) -> None:
        if self.reinicio_pendiente:
            self._completar_reinicio()
            return

        opciones = self.model.config.opciones
        if (
            opciones.pronostico_caido
            and not self.recuperado
            and self.model.ronda >= opciones.ronda_fallo_pronostico
        ):
            self.caido = True

        if self.caido:
            # Un agente caído no atiende consultas, pero el procedimiento de
            # recuperación del Supervisor sí puede reiniciarlo.
            for mensaje in mensajes:
                if (
                    mensaje.performativa == REQUEST
                    and mensaje.contenido.get("accion") == "solicitar_reinicio"
                ):
                    self._responder_reinicio(mensaje)
            return

        for mensaje in mensajes:
            if mensaje.performativa == QUERY_REF and mensaje.contenido.get(
                "consulta"
            ) == "demanda_proyectada":
                self._responder_demanda(mensaje)

        if self.model.ronda == self.model.config.ronda_inicio:
            self._estimar_previa()

    # ------------------------------------------------------------------
    # Proyección
    # ------------------------------------------------------------------
    def _hospitales_consulta(self) -> list[str]:
        return sorted(
            hospital_id
            for hospital_id in self.model.config.hospitales
            if hospital_id != self.model.hospital_origen
        )

    def _proyectar(self, hospital_id: str) -> int:
        config = self.model.config
        hospital = config.hospitales[hospital_id]
        serie = hospital.historial.get(self.model.medicamento, [])
        return proyectar(serie, config.horizonte_pronostico_dias)

    def _estimar_previa(self) -> None:
        """Estimación que queda disponible aunque el agente falle después."""
        hospitales = self._hospitales_consulta()
        self.accion(
            "leerRegistros",
            {"consulta": "historial_consumo", "hospitales": hospitales},
        )
        demanda = {
            hospital_id: self._proyectar(hospital_id)
            for hospital_id in hospitales
        }
        self.model.ultima_estimacion = demanda
        self.accion(
            "calcularProyeccion",
            {
                "hospitales": demanda,
                "horizonte_dias": self.model.config.horizonte_pronostico_dias,
                "fuente": "estimacion_previa",
            },
        )

    def _responder_demanda(self, consulta: Any) -> None:
        hospitales = consulta.contenido.get("hospitales") or self._hospitales_consulta()
        self.accion(
            "leerRegistros",
            {"consulta": "historial_consumo", "hospitales": hospitales},
        )
        demanda = {hospital_id: self._proyectar(hospital_id) for hospital_id in hospitales}
        self.model.ultima_estimacion = demanda
        self.model.demanda_proyectada = demanda
        if self.model.consulta_pronostico is not None:
            self.model.consulta_pronostico["respondida"] = True

        error = 0.0
        for hospital_id in hospitales:
            serie = self.model.config.hospitales[hospital_id].historial.get(
                self.model.medicamento, []
            )
            if serie:
                error = max(error, mape(serie, factores_estacionales(serie)))

        self.accion(
            "calcularProyeccion",
            {
                "hospitales": demanda,
                "horizonte_dias": self.model.config.horizonte_pronostico_dias,
                "mape": error,
                "fuente": "modelo",
            },
        )
        self.accion("enviarEstimacion", {"hospitales": demanda})
        self.enviar(
            INFORM,
            "coordinador",
            {
                "tipo": "demanda_proyectada",
                "hospitales": demanda,
                "horizonte_dias": self.model.config.horizonte_pronostico_dias,
                "mape": error,
                "fuente": "modelo",
            },
            protocolo=FIPA_QUERY,
            conversation_id=consulta.conversation_id,
            in_reply_to=consulta.reply_with,
        )

    # ------------------------------------------------------------------
    # Fase D: recuperación
    # ------------------------------------------------------------------
    def _responder_reinicio(self, peticion: Any) -> None:
        if self.model.config.opciones.reinicio_falla:
            self.fallo_reinicio = True
            self.accion("falloReinicio", {"motivo": "error_al_reiniciar"})
            self.enviar(
                FAILURE,
                "supervisor",
                {"tipo": "error_al_reiniciar", "motivo": "error_al_reiniciar"},
                protocolo=FIPA_REQUEST,
                conversation_id=peticion.conversation_id,
                in_reply_to=peticion.reply_with,
            )
            return

        self.accion("aceptarReinicio", {"agente": self.nombre})
        self.enviar(
            AGREE,
            "supervisor",
            {"tipo": "reinicio_aceptado", "agente": self.nombre},
            protocolo=FIPA_REQUEST,
            conversation_id=peticion.conversation_id,
            in_reply_to=peticion.reply_with,
        )
        self.reinicio_pendiente = True

    def _completar_reinicio(self) -> None:
        self.reinicio_pendiente = False
        self.caido = False
        self.recuperado = True
        self.accion(
            "actualizarModelo",
            {"motivo": "reinicio", "modelo_actualizado": True},
        )
        self.enviar(
            INFORM,
            "supervisor",
            {
                "tipo": "reinicio_completado",
                "agente": self.nombre,
                "modelo_actualizado": True,
            },
            protocolo=FIPA_REQUEST,
            conversation_id="reinicio-1",
            in_reply_to="req-reinicio-1",
        )
