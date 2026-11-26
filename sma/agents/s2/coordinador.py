"""Agente Coordinador de la Situación 2: arquitectura basada en utilidad.

Resuelve la competencia entre los hospitales A y B por un único lote. Si el
Pronóstico no responde, sigue operando con su última estimación o con el
historial de consumo; si el traslado se rechaza, reasigna el lote al otro
hospital. Las reglas puras viven en ``sma.decision_s2``.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from ...acl import (
    AGREE,
    FIPA_QUERY,
    FIPA_REQUEST,
    INFORM,
    QUERY_REF,
    REFUSE,
    REQUEST,
)
from ...decision_s2 import (
    PlanTraslado,
    calcular_urgencias,
    demanda_sustituta,
    planificar_traslado,
)
from ..base import AgenteBase


class AgenteCoordinadorS2(AgenteBase):
    nombre = "coordinador"

    def __init__(self, modelo: Any) -> None:
        super().__init__(modelo)
        self.riesgo: dict[str, Any] | None = None
        self.demanda: dict[str, int] = {}
        self.fuente_demanda = ""
        self.urgencias: list[Any] = []
        self.plan: PlanTraslado | None = None
        self.esperando = ""
        self.intentos: list[str] = []
        self.finalizado = False
        self._n_consultas = 0
        self._n_traslados = 0

    # ------------------------------------------------------------------
    def procesar(self, mensajes: list[Any]) -> None:
        for mensaje in mensajes:
            if mensaje.performativa == INFORM:
                self._procesar_inform(mensaje)
            elif mensaje.performativa == REFUSE:
                self._reasignar(mensaje)
            elif mensaje.performativa == AGREE:
                self.accion(
                    "recibirAgree", {"conversation_id": mensaje.conversation_id}
                )

    # ------------------------------------------------------------------
    def _procesar_inform(self, mensaje: Any) -> None:
        contenido = mensaje.contenido
        tipo = contenido.get("tipo")
        if tipo == "riesgo_vencimiento":
            self._analizar(contenido)
        elif tipo == "fallo_detectado":
            self._usar_sustituto(contenido)
        elif tipo == "demanda_proyectada":
            self._usar_demanda(contenido)
        elif tipo == "stock":
            self._decidir(contenido)
        elif tipo == "traslado_realizado":
            self._cerrar(contenido)

    # ------------------------------------------------------------------
    # Fase B: consulta de demanda
    # ------------------------------------------------------------------
    def _hospitales_consulta(self) -> list[str]:
        return sorted(
            hospital_id
            for hospital_id in self.model.config.hospitales
            if hospital_id != self.model.hospital_origen
        )

    def _analizar(self, riesgo: dict[str, Any]) -> None:
        if self.riesgo is not None:
            return
        self.riesgo = riesgo
        self._n_consultas += 1
        hospitales = self._hospitales_consulta()
        self.accion(
            "analizarEventos",
            {"riesgo": riesgo, "hospitales": hospitales},
        )
        self.enviar(
            QUERY_REF,
            "pronostico",
            {
                "consulta": "demanda_proyectada",
                "hospitales": hospitales,
                "medicamento": self.model.medicamento,
            },
            protocolo=FIPA_QUERY,
            conversation_id=f"demanda-{self._n_consultas}",
            reply_with=f"q-demanda-{self._n_consultas}",
        )
        self.model.consulta_pronostico = {
            "ronda": self.model.ronda,
            "respondida": False,
        }
        self.esperando = "demanda"

    def _usar_demanda(self, contenido: dict[str, Any]) -> None:
        if self.esperando != "demanda":
            return
        self.demanda = {
            hospital_id: int(round(valor))
            for hospital_id, valor in contenido.get("hospitales", {}).items()
        }
        self.fuente_demanda = contenido.get("fuente", "modelo")
        self.model.demanda_proyectada = self.demanda
        self.accion(
            "usarEstimacion",
            {"demanda": self.demanda, "fuente": self.fuente_demanda},
        )
        self._consultar_stock()

    def _usar_sustituto(self, contenido: dict[str, Any]) -> None:
        if self.esperando != "demanda":
            return
        historial = {
            hospital_id: self.model.config.hospitales[hospital_id].historial.get(
                self.model.medicamento, []
            )
            for hospital_id in self._hospitales_consulta()
        }
        self.demanda = demanda_sustituta(
            self.model.ultima_estimacion,
            historial,
            self.model.config.horizonte_pronostico_dias,
        )
        self.fuente_demanda = (
            "ultima_estimacion" if self.model.ultima_estimacion else "historial"
        )
        self.model.demanda_proyectada = self.demanda
        self.accion(
            "usarUltimaEstimacion",
            {
                "demanda": self.demanda,
                "fuente": self.fuente_demanda,
                "motivo": contenido.get("motivo", "timeout"),
            },
        )
        self.enviar(
            INFORM,
            "supervisor",
            {
                "tipo": "decision",
                "accion": "uso_ultima_estimacion",
                "fuente": self.fuente_demanda,
                "demanda": self.demanda,
            },
        )
        self._consultar_stock()

    # ------------------------------------------------------------------
    # Fase C: stock, urgencia y traslado
    # ------------------------------------------------------------------
    def _consultar_stock(self) -> None:
        self._n_consultas += 1
        hospitales = self._hospitales_consulta()
        self.esperando = "stock"
        self.accion("consultarStock", {"hospitales": hospitales})
        self.enviar(
            QUERY_REF,
            "inventario",
            {
                "consulta": "stock",
                "hospitales": hospitales,
                "medicamento": self.model.medicamento,
            },
            protocolo=FIPA_QUERY,
            conversation_id=f"stock-{self._n_consultas}",
            reply_with=f"q-stock-{self._n_consultas}",
        )

    def _decidir(self, contenido: dict[str, Any]) -> None:
        if self.esperando != "stock" or self.plan is not None:
            return
        stock = contenido.get("hospitales", {})
        self.urgencias = calcular_urgencias(stock, self.demanda)
        self.plan = planificar_traslado(
            self.urgencias, self.model.lote.cantidad
        )
        self.accion(
            "decidirTrasladoOCompra",
            {
                "urgencias": [asdict(urgencia) for urgencia in self.urgencias],
                "hospital": self.plan.hospital,
                "cantidad": self.plan.cantidad,
                "faltante": self.plan.faltante,
                "motivo": self.plan.motivo,
            },
        )
        self._publicar_decision("traslado")
        self._solicitar_traslado(self.plan.hospital)
        self.esperando = "traslado"

    def _publicar_decision(self, accion: str) -> None:
        assert self.plan is not None
        decision = {
            "tipo": "decision",
            "accion": accion,
            "lote": self.model.lote.id,
            "hospital": self.plan.hospital,
            "cantidad": self.plan.cantidad,
            "faltante": self.plan.faltante,
            "motivo": self.plan.motivo,
            "fuente_demanda": self.fuente_demanda,
            "demanda": self.demanda,
            "urgencias": [asdict(urgencia) for urgencia in self.plan.urgencias],
        }
        self.model.decision = decision
        self.model.decisiones.append(decision)
        self.enviar(INFORM, "supervisor", decision)

    def _solicitar_traslado(self, hospital: str) -> None:
        self._n_traslados += 1
        self.intentos.append(hospital)
        self.enviar(
            REQUEST,
            "inventario",
            {
                "tipo": "preparar_traslado",
                "accion": "preparar_traslado",
                "lote": self.model.lote.id,
                "origen": self.model.hospital_origen,
                "destino": hospital,
                "cantidad": self.model.lote.cantidad,
            },
            protocolo=FIPA_REQUEST,
            conversation_id=f"traslado-{self._n_traslados}",
            reply_with=f"req-traslado-{self._n_traslados}",
        )
        self.accion(
            "enviarRequest",
            {"destinatario": "inventario", "destino": hospital},
        )

    def _reasignar(self, mensaje: Any) -> None:
        if self.plan is None or self.finalizado:
            return
        alterno = next(
            (
                urgencia.hospital
                for urgencia in self.plan.urgencias
                if urgencia.hospital not in self.intentos
            ),
            "",
        )
        if not alterno:
            self._escalar("sin_receptor")
            return

        urgencia = next(
            urgencia for urgencia in self.plan.urgencias if urgencia.hospital == alterno
        )
        self.model.reasignaciones += 1
        self.plan = PlanTraslado(
            hospital=alterno,
            cantidad=self.model.lote.cantidad,
            faltante=max(0, urgencia.necesidad - self.model.lote.cantidad),
            urgencias=self.plan.urgencias,
            motivo="reasignacion",
        )
        self.accion(
            "decidirTrasladoOCompra",
            {
                "motivo": "reasignacion",
                "hospital": alterno,
                "rechazo": mensaje.contenido.get("motivo"),
            },
        )
        self._publicar_decision("reasignacion")
        self._solicitar_traslado(alterno)

    # ------------------------------------------------------------------
    # Cierre
    # ------------------------------------------------------------------
    def _cerrar(self, contenido: dict[str, Any]) -> None:
        if self.finalizado or self.plan is None:
            return
        self.finalizado = True
        self.esperando = ""
        destino = contenido.get("destino", self.model.lote_asignado)
        cantidad = int(contenido.get("cantidad", 0))

        residual = 0
        for urgencia in self.plan.urgencias:
            recibido = cantidad if urgencia.hospital == destino else 0
            residual += max(0, urgencia.necesidad - recibido)
        self.model.riesgo_residual = residual
        self.model.lista_espera = next(
            (
                urgencia.hospital
                for urgencia in self.plan.urgencias
                if urgencia.hospital != destino and urgencia.necesidad > 0
            ),
            None,
        )
        self.accion(
            "verificarAcciones",
            {
                "lote": self.model.lote.id,
                "hospital": destino,
                "cantidad": cantidad,
                "riesgo_residual": residual,
            },
        )
        if self.model.lista_espera:
            self.accion(
                "enviarListaEspera", {"hospital": self.model.lista_espera}
            )
            self.enviar(
                INFORM,
                "supervisor",
                {
                    "tipo": "decision",
                    "accion": "lista_espera",
                    "hospital": self.model.lista_espera,
                    "motivo": "demanda_no_cubierta",
                    "riesgo_residual": residual,
                },
            )

        self.model.resultado = "exito"
        self.model.cierre = True
        self.enviar(
            INFORM,
            "supervisor",
            {
                "tipo": "cierre",
                "resultado": "exito",
                "motivo": "traslado_realizado",
                "lote": self.model.lote.id,
                "hospital": destino,
                "riesgo_residual": residual,
                "lista_espera": self.model.lista_espera,
            },
        )

    def _escalar(self, motivo: str) -> None:
        if self.finalizado:
            return
        self.finalizado = True
        self.esperando = ""
        residual = sum(urgencia.necesidad for urgencia in self.urgencias)
        self.model.resultado = "escalado"
        self.model.escalado = True
        self.model.riesgo_residual = residual
        self.accion("escalar", {"motivo": motivo, "riesgo_residual": residual})
        self.enviar(
            INFORM,
            "supervisor",
            {
                "tipo": "decision",
                "accion": "escalado",
                "motivo": motivo,
                "hospital": self.plan.hospital if self.plan else None,
                "riesgo_residual": residual,
            },
        )
        self.model.cierre = True
        self.enviar(
            INFORM,
            "supervisor",
            {
                "tipo": "cierre",
                "resultado": "escalado",
                "motivo": motivo,
                "lote": self.model.lote.id,
                "lote_sin_asignar": self.model.lote.id,
                "riesgo_residual": residual,
            },
        )
