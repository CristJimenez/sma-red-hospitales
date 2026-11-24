"""Entorno y modelo Mesa del SMA.

``RedHospitalaria`` es el entorno compartido (Environment en MAS-ML): contiene
hospitales, proveedores y órdenes, y expone las acciones que los agentes
ejecutan sobre él. Mesa gestiona el registro y la activación de los agentes.
"""

from __future__ import annotations

from typing import Any

import mesa

from .agents import (
    AgenteCompras,
    AgenteCoordinador,
    AgenteInventario,
    AgentePronostico,
    AgenteSupervisor,
)
from .bus import Bus
from .domain.models import Configuracion, OrdenCompra
from .trace import Traza


class RedHospitalaria(mesa.Model):
    def __init__(self, config: Configuracion) -> None:
        super().__init__(rng=config.semilla)
        self.config = config
        self.ronda = 0
        self.traza = Traza()
        self.bus = Bus(self)

        self.presupuesto_restante = config.presupuesto_inicial
        self.coste_total = 0.0
        self.ordenes: list[OrdenCompra] = []
        self.orden_actual: OrdenCompra | None = None
        self.traslado_total = 0
        self.demanda_proyectada: int | None = None
        self.decision: dict[str, Any] | None = None
        self.decisiones: list[dict[str, Any]] = []
        self.resultado = ""
        self.riesgo_residual = 0
        self.replanificaciones = 0
        self.cierre = False
        self.latidos: dict[str, int] = {}

        self._n_traslados = 0
        self._n_ordenes = 0

        self.stock_inicial = {
            (hospital.id, med_id): hospital.stock(med_id)
            for hospital in config.hospitales.values()
            for med_id in config.medicamentos
        }

        # Orden de creación = orden de activación en cada ronda
        self.inventario = AgenteInventario(self)
        self.pronostico = AgentePronostico(self)
        self.coordinador = AgenteCoordinador(self)
        self.compras = AgenteCompras(self)
        self.supervisor = AgenteSupervisor(self)

        self.por_nombre = {
            agente.nombre: agente
            for agente in (
                self.inventario,
                self.pronostico,
                self.coordinador,
                self.compras,
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
    def factor_brote(self, hospital_id: str, medicamento_id: str) -> float:
        evento = self.config.evento
        if (
            self.ronda >= evento.ronda_inicio
            and evento.hospital == hospital_id
            and evento.medicamento == medicamento_id
        ):
            return evento.factor_consumo
        return 1.0

    def trasladar(
        self, origen_id: str, destino_id: str, medicamento_id: str, cantidad: int
    ) -> int:
        origen = self.config.hospitales[origen_id]
        destino = self.config.hospitales[destino_id]
        lotes = [l for l in origen.lotes.get(medicamento_id, []) if l.cantidad > 0]
        vence = min((l.vence_en_dias for l in lotes), default=365)

        movido = origen.retirar(medicamento_id, cantidad)
        if movido <= 0:
            return 0

        self._n_traslados += 1
        destino.agregar(
            medicamento_id,
            movido,
            lote_id=f"TR-{self._n_traslados:03d}",
            vence_en_dias=vence,
        )
        self.traslado_total += movido
        self.traza.registrar_entorno(
            self.ronda,
            "traslado",
            {
                "origen": origen_id,
                "destino": destino_id,
                "medicamento": medicamento_id,
                "cantidad": movido,
            },
            origen="coordinador",
            destino="entorno",
        )
        return movido

    def crear_orden(
        self, medicamento_id: str, cantidad: int, proveedor_id: str, coste: float
    ) -> OrdenCompra:
        self._n_ordenes += 1
        orden = OrdenCompra(
            id=f"OC-{self._n_ordenes:03d}",
            medicamento_id=medicamento_id,
            cantidad=cantidad,
            proveedor_id=proveedor_id,
            ronda_creacion=self.ronda,
            coste=coste,
        )
        self.ordenes.append(orden)
        self.orden_actual = orden
        return orden

    def gastar(self, monto: float) -> None:
        self.presupuesto_restante -= monto
        self.coste_total += monto

    # ------------------------------------------------------------------
    # Indicadores
    # ------------------------------------------------------------------
    def metricas(self) -> dict[str, Any]:
        evento = self.config.evento
        hospital = self.config.hospitales[evento.hospital]
        med = evento.medicamento
        stock = hospital.stock(med)
        comprado = sum(orden.cantidad for orden in self.ordenes)
        coste = sum(orden.coste for orden in self.ordenes)
        demanda = self.demanda_proyectada or 0
        cobertura = (stock + comprado) / demanda if demanda else 0.0
        accion = (self.decision or {}).get("accion")
        if accion is None and self.resultado == "sin_riesgo":
            accion = "ninguna"

        return {
            "hospital": hospital.id,
            "medicamento": med,
            "stock_inicial": self.stock_inicial.get((hospital.id, med), 0),
            "stock_actual": stock,
            "umbral": round(hospital.umbral(med), 2),
            "traslado_recibido": self.traslado_total,
            "cantidad_comprada": comprado,
            "coste_compra": round(coste, 2),
            "presupuesto_inicial": self.config.presupuesto_inicial,
            "presupuesto_restante": round(self.presupuesto_restante, 2),
            "orden_estado": self.orden_actual.estado if self.orden_actual else None,
            "demanda_proyectada": demanda,
            "cobertura_proyectada": round(cobertura, 3),
            "accion": accion,
            "motivo": (self.decision or {}).get("motivo"),
            "riesgo_residual": self.riesgo_residual,
            "replanificaciones": self.replanificaciones,
            "resultado": self.resultado or None,
            "rondas": self.ronda,
            "mensajes": len(self.traza.mensajes()),
            "eventos_registrados": len(self.supervisor.registros),
        }
