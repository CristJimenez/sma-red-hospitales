"""Entorno y modelo Mesa de la Situación 2.

``RedHospitalariaS2`` es el entorno compartido: tres hospitales, un lote que
está por vencer y un objeto de dominio ``Lote`` que solo puede pertenecer a un
hospital a la vez. Los agentes de esta situación son Inventario, Pronóstico,
Coordinador y Supervisor; Compras y los proveedores no participan.
"""

from __future__ import annotations

from typing import Any

import mesa

from .agents.s2 import (
    AgenteCoordinadorS2,
    AgenteInventarioS2,
    AgentePronosticoS2,
    AgenteSupervisorS2,
)
from .bus import Bus
from .config_s2 import ConfiguracionS2
from .trace import ALIAS_S2, PARTICIPANTES_S2, Traza


class RedHospitalariaS2(mesa.Model):
    def __init__(self, config: ConfiguracionS2) -> None:
        super().__init__(rng=config.semilla)
        self.config = config
        self.ronda = 0
        # El diagrama de la Situación 2 no numera las flechas.
        self.traza = Traza(PARTICIPANTES_S2, ALIAS_S2, autonumerar=False)
        self.bus = Bus(self)

        self.medicamento = config.medicamento
        self.hospital_origen = config.hospital_origen
        lotes = config.hospitales[self.hospital_origen].lotes.get(self.medicamento, [])
        lote_id = str(config.lote_riesgo.get("lote", ""))
        self.lote = next((l for l in lotes if l.id == lote_id), lotes[0])
        self.cantidad_lote = self.lote.cantidad
        self.traslado_total = 0

        self.lote_asignado: str | None = None
        self.lista_espera: str | None = None
        self.demanda_proyectada: dict[str, int] = {}
        self.ultima_estimacion: dict[str, int] = {}
        self.consulta_pronostico: dict[str, Any] | None = None
        self.timeout_pronostico = False
        self.pronostico_recuperado = False
        self.reinicio_estado = ""
        self.escalado = False
        self.rechazos_pendientes = int(config.opciones.rechazos_traslado)

        self.decision: dict[str, Any] | None = None
        self.decisiones: list[dict[str, Any]] = []
        self.resultado = ""
        self.riesgo_residual = 0
        self.reasignaciones = 0
        self.cierre = False
        self.latidos: dict[str, int] = {}

        self.stock_inicial = {
            hospital.id: hospital.stock(self.medicamento)
            for hospital in config.hospitales.values()
        }

        # Orden de creación = orden de activación en cada ronda
        self.inventario = AgenteInventarioS2(self)
        self.pronostico = AgentePronosticoS2(self)
        self.coordinador = AgenteCoordinadorS2(self)
        self.supervisor = AgenteSupervisorS2(self)

        self.por_nombre = {
            agente.nombre: agente
            for agente in (
                self.inventario,
                self.pronostico,
                self.coordinador,
                self.supervisor,
            )
        }

    # ------------------------------------------------------------------
    # Ciclo de simulación
    # ------------------------------------------------------------------
    def step(self) -> None:
        self.ronda += 1
        for mensaje in self.bus.entregar():
            agente = self.por_nombre.get(mensaje.receptor)
            if agente is None:
                self.traza.registrar_accion(
                    self.ronda, "bus", "mensaje_sin_destino", {"receptor": mensaje.receptor}
                )
                continue
            agente.buzon.append(mensaje)
        self.agents.do("step")

    # ------------------------------------------------------------------
    # Acciones sobre el entorno
    # ------------------------------------------------------------------
    def asignar_lote(self, destino_id: str) -> int:
        """Mueve el lote completo a un único hospital (nunca se reparte)."""
        if self.lote_asignado is not None or self.lote.cantidad <= 0:
            return 0
        origen = self.config.hospitales[self.lote.hospital_id]
        destino = self.config.hospitales[destino_id]
        cantidad = self.lote.cantidad

        origen.lotes[self.medicamento].remove(self.lote)
        self.lote.hospital_id = destino.id
        destino.lotes.setdefault(self.medicamento, []).append(self.lote)

        self.lote_asignado = destino.id
        self.traslado_total += cantidad
        self.traza.registrar_entorno(
            self.ronda,
            "traslado_lote",
            {
                "lote": self.lote.id,
                "origen": origen.id,
                "destino": destino.id,
                "medicamento": self.medicamento,
                "cantidad": cantidad,
            },
            origen="inventario",
            destino="entorno",
        )
        self.traza.registrar_entorno(
            self.ronda,
            "actualizar_lote",
            {
                "lote": self.lote.id,
                "hospital": destino.id,
                "cantidad": self.lote.cantidad,
            },
            origen="inventario",
            destino="lote",
        )
        return cantidad

    # ------------------------------------------------------------------
    # Indicadores
    # ------------------------------------------------------------------
    def metricas(self) -> dict[str, Any]:
        decision = self.decision or {}
        return {
            "lote": self.lote.id,
            "medicamento": self.medicamento,
            "hospital_origen": self.hospital_origen,
            "cantidad_lote": self.cantidad_lote,
            "lote_asignado": self.lote_asignado,
            "lista_espera": self.lista_espera,
            "demanda_proyectada": self.demanda_proyectada,
            "hospital_prioritario": decision.get("hospital"),
            "faltante": decision.get("faltante", 0),
            "urgencias": decision.get("urgencias", []),
            "fuente_demanda": decision.get("fuente_demanda"),
            "timeout_pronostico": self.timeout_pronostico,
            "pronostico_recuperado": self.pronostico_recuperado,
            "reinicio": self.reinicio_estado or None,
            "reasignaciones": self.reasignaciones,
            "escalado": self.escalado,
            "riesgo_residual": self.riesgo_residual,
            "resultado": self.resultado or None,
            "rondas": self.ronda,
            "mensajes": len(self.traza.mensajes()),
            "eventos_registrados": len(self.supervisor.registros),
            "stock_final": {
                hospital.id: hospital.stock(self.medicamento)
                for hospital in self.config.hospitales.values()
            },
        }
