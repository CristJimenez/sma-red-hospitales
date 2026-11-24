"""Modelo de dominio del abastecimiento hospitalario.

Objetos del dominio según MAS-ML: Lote, OrdenCompra, Proveedor. Los agentes
los consultan y modifican a través del entorno (RedHospitalaria).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Medicamento:
    id: str
    nombre: str
    critico: bool = True
    cadena_frio: bool = False
    precio_referencia: float = 0.0
    vida_util_dias: int = 365


@dataclass
class Lote:
    id: str
    medicamento_id: str
    cantidad: int
    vence_en_dias: int
    hospital_id: str = ""

    def a_dict(self) -> dict[str, Any]:
        return {
            "lote": self.id,
            "medicamento": self.medicamento_id,
            "cantidad": self.cantidad,
            "vence_en_dias": self.vence_en_dias,
        }


@dataclass
class Hospital:
    id: str
    nombre: str
    complejidad: str
    camas: int
    stock_seguridad_dias: float
    lotes: dict[str, list[Lote]] = field(default_factory=dict)
    consumo_diario: dict[str, float] = field(default_factory=dict)
    historial: dict[str, list[float]] = field(default_factory=dict)

    # -- percepción -----------------------------------------------------
    def stock(self, medicamento_id: str) -> int:
        return sum(l.cantidad for l in self.lotes.get(medicamento_id, []))

    def umbral(self, medicamento_id: str) -> float:
        return self.consumo_diario.get(medicamento_id, 0.0) * self.stock_seguridad_dias

    def consumo_efectivo(self, medicamento_id: str, factor: float = 1.0) -> float:
        return self.consumo_diario.get(medicamento_id, 0.0) * factor

    def dias_hasta_agotamiento(self, medicamento_id: str, factor: float = 1.0) -> float:
        consumo = self.consumo_efectivo(medicamento_id, factor)
        if consumo <= 0:
            return float("inf")
        return self.stock(medicamento_id) / consumo

    def excedente(self, medicamento_id: str, colchon_dias: float = 2.0) -> int:
        """Unidades por encima del stock de seguridad más un colchón logístico."""
        consumo = self.consumo_diario.get(medicamento_id, 0.0)
        reserva = consumo * (self.stock_seguridad_dias + colchon_dias)
        return max(0, int(self.stock(medicamento_id) - reserva))

    def lotes_proximos_a_vencer(self, medicamento_id: str, dias: int = 60) -> list[Lote]:
        return [
            lote
            for lote in self.lotes.get(medicamento_id, [])
            if lote.vence_en_dias <= dias and lote.cantidad > 0
        ]

    # -- acciones sobre el entorno --------------------------------------
    def retirar(self, medicamento_id: str, cantidad: int) -> int:
        """Retira unidades aplicando FIFO por fecha de vencimiento."""
        restante = cantidad
        retirado = 0
        for lote in sorted(
            self.lotes.get(medicamento_id, []), key=lambda l: l.vence_en_dias
        ):
            if restante <= 0:
                break
            tomar = min(lote.cantidad, restante)
            lote.cantidad -= tomar
            restante -= tomar
            retirado += tomar
        return retirado

    def agregar(self, medicamento_id: str, cantidad: int, lote_id: str, vence_en_dias: int = 365) -> Lote:
        lote = Lote(
            id=lote_id,
            medicamento_id=medicamento_id,
            cantidad=cantidad,
            vence_en_dias=vence_en_dias,
            hospital_id=self.id,
        )
        self.lotes.setdefault(medicamento_id, []).append(lote)
        return lote


@dataclass
class Proveedor:
    id: str
    nombre: str
    tiempo_entrega_dias: int
    retraso_dias: int
    precios: dict[str, float] = field(default_factory=dict)

    @property
    def cumple_plazo(self) -> bool:
        return self.retraso_dias <= 0

    def precio(self, medicamento_id: str) -> float:
        return self.precios.get(medicamento_id, 0.0)

    def plazo_efectivo(self) -> int:
        return self.tiempo_entrega_dias + self.retraso_dias


@dataclass
class OrdenCompra:
    id: str
    medicamento_id: str
    cantidad: int
    proveedor_id: str
    ronda_creacion: int
    coste: float
    estado: str = "generada"

    def a_dict(self) -> dict[str, Any]:
        return {
            "orden": self.id,
            "medicamento": self.medicamento_id,
            "cantidad": self.cantidad,
            "proveedor": self.proveedor_id,
            "coste": round(self.coste, 2),
            "estado": self.estado,
        }


@dataclass
class Evento:
    tipo: str
    descripcion: str
    hospital: str
    medicamento: str
    factor_consumo: float = 1.0
    ronda_inicio: int = 1


@dataclass
class Opciones:
    compras_puede_gestionar: bool = True
    forzar_presupuesto_insuficiente: bool = False
    simular_agente_caido: bool = False
    transporte_refrigerado: bool = True
    politica_presupuesto: str = "rechazar"
    traslado_emergencia: bool = True
    prioridad_riesgos: str = "agotamiento"  # agotamiento | orden_deteccion


@dataclass
class Configuracion:
    semilla: int
    presupuesto_inicial: float
    horizonte_pronostico_dias: int
    medicamentos: dict[str, Medicamento]
    hospitales: dict[str, Hospital]
    proveedores: dict[str, Proveedor]
    evento: Evento
    opciones: Opciones = field(default_factory=Opciones)
    tiempo_traslado_dias: int = 1

    def factor_brote(self, hospital_id: str, medicamento_id: str) -> float:
        evento = self.evento
        if evento.hospital == hospital_id and evento.medicamento == medicamento_id:
            return evento.factor_consumo
        return 1.0
