"""Decisiones puras de la Situación 2.

Igual que en la Situación 1, aquí no hay agentes ni mensajes: solo funciones
que reciben el estado del mundo y devuelven un plan. Así la competencia por el
lote se puede probar sin simular rondas.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean


@dataclass(frozen=True)
class Urgencia:
    hospital: str
    stock: int
    consumo: float
    dias: float
    demanda: int
    necesidad: int


@dataclass(frozen=True)
class PlanTraslado:
    hospital: str
    cantidad: int
    faltante: int
    urgencias: tuple[Urgencia, ...]
    motivo: str


def demanda_sustituta(
    ultima: dict[str, int],
    historial: dict[str, list[float]],
    horizonte: int,
) -> dict[str, int]:
    """Última estimación del Pronóstico; si no hay, media del historial."""
    if ultima:
        return {hospital: int(round(valor)) for hospital, valor in ultima.items()}
    return {
        hospital: int(round(mean(serie) * horizonte))
        for hospital, serie in historial.items()
        if serie
    }


def calcular_urgencias(
    stock: dict[str, dict[str, float]], demanda: dict[str, int]
) -> list[Urgencia]:
    urgencias = []
    for hospital, datos in stock.items():
        existencias = int(datos.get("stock", 0))
        consumo = float(datos.get("consumo_diario", 0.0))
        dias = float(
            datos.get(
                "dias_hasta_agotamiento",
                existencias / consumo if consumo > 0 else float("inf"),
            )
        )
        necesidad = int(demanda.get(hospital, 0))
        urgencias.append(
            Urgencia(
                hospital=hospital,
                stock=existencias,
                consumo=consumo,
                dias=dias,
                demanda=necesidad,
                necesidad=max(0, necesidad - existencias),
            )
        )
    return urgencias


def elegir_hospital_prioritario(urgencias: list[Urgencia]) -> Urgencia:
    """El que se agota antes; desempata quien tiene más necesidad y el id."""
    return min(urgencias, key=lambda u: (u.dias, -u.necesidad, u.hospital))


def planificar_traslado(
    urgencias: list[Urgencia], cantidad_lote: int
) -> PlanTraslado:
    """Asigna el lote completo a un solo hospital: nunca se reparte."""
    if not urgencias:
        return PlanTraslado("", 0, 0, tuple(), "sin_hospitales")
    ordenadas = tuple(sorted(urgencias, key=lambda u: (u.dias, -u.necesidad, u.hospital)))
    prioridad = ordenadas[0]
    return PlanTraslado(
        hospital=prioridad.hospital,
        cantidad=cantidad_lote,
        faltante=max(0, prioridad.necesidad - cantidad_lote),
        urgencias=ordenadas,
        motivo="mayor_urgencia",
    )


def hospital_alterno(plan: PlanTraslado) -> str:
    """Siguiente hospital por urgencia, para reasignar si rechazan el traslado."""
    for urgencia in plan.urgencias:
        if urgencia.hospital != plan.hospital:
            return urgencia.hospital
    return ""
