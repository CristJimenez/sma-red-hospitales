"""Motor de decisión del Coordinador.

Funciones puras y testeables: reciben el estado del mundo y devuelven un plan.
El agente solo ejecuta el plan y emite los mensajes FIPA correspondientes.

La matriz de casos que cubre este módulo:

=====================  ==========================================
Situación              Acción resultante
=====================  ==========================================
Sin necesidad          ``ninguna``
Excedente suficiente   ``traslado``
Sin excedente apto     ``compra``
Excedente parcial      ``traslado_y_compra``
Sin proveedor viable   ``traslado_parcial`` / ``escalar``
Presupuesto corto      ``escalar`` / compra parcial
=====================  ==========================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MARGEN_DIAS = 1.0  # holgura entre la llegada del traslado y el agotamiento
VIDA_MINIMA_LOTE_DIAS = 2
PENALIZACION_DIA = 0.5  # € por día de plazo, para desempatar ofertas


@dataclass(frozen=True)
class Donante:
    hospital_id: str
    cantidad: int
    vence_en_dias: int
    cadena_frio_ok: bool = True


@dataclass(frozen=True)
class Oferta:
    proveedor_id: str
    precio_unitario: float
    plazo_dias: int
    disponible: bool = True


@dataclass
class ResultadoTraslado:
    traslados: list[dict[str, Any]] = field(default_factory=list)
    total: int = 0
    faltante: int = 0
    descartes: list[dict[str, Any]] = field(default_factory=list)
    accion: str = "ninguna"


@dataclass
class ResultadoCompra:
    proveedor_id: str | None = None
    cantidad: int = 0
    coste: float = 0.0
    motivo: str = "sin_proveedor_viable"
    viables: list[str] = field(default_factory=list)


@dataclass
class Plan:
    accion: str
    traslados: list[dict[str, Any]] = field(default_factory=list)
    traslado_total: int = 0
    faltante: int = 0
    compra: ResultadoCompra | None = None
    motivo: str = ""
    descartes: list[dict[str, Any]] = field(default_factory=list)


# ----------------------------------------------------------------------
# Traslados
# ----------------------------------------------------------------------
def _motivo_descarte(
    donante: Donante,
    requiere_frio: bool,
    transporte_refrigerado: bool,
    dias_hasta_agotamiento: float,
    tiempo_traslado_dias: int,
    vida_minima_dias: int,
) -> str | None:
    if donante.cantidad <= 0:
        return "sin_excedente"
    if donante.vence_en_dias < vida_minima_dias:
        return "lote_por_vencer"
    if not donante.cadena_frio_ok:
        return "cadena_frio_incompatible"
    if requiere_frio and not transporte_refrigerado:
        return "transporte_sin_refrigeracion"
    if tiempo_traslado_dias > dias_hasta_agotamiento + MARGEN_DIAS:
        return "llega_tarde"
    return None


def seleccionar_traslado(
    donantes: list[Donante],
    necesidad: int,
    requiere_frio: bool = False,
    transporte_refrigerado: bool = True,
    dias_hasta_agotamiento: float = float("inf"),
    tiempo_traslado_dias: int = 1,
    vida_minima_dias: int = VIDA_MINIMA_LOTE_DIAS,
    permitir_emergencia: bool = True,
) -> ResultadoTraslado:
    """Reparte la necesidad entre donantes aptos, empezando por el lote que antes vence."""
    necesidad = max(0, int(necesidad))

    elegibles: list[Donante] = []
    descartes: list[dict[str, Any]] = []
    for donante in donantes:
        motivo = _motivo_descarte(
            donante,
            requiere_frio,
            transporte_refrigerado,
            dias_hasta_agotamiento,
            tiempo_traslado_dias,
            vida_minima_dias,
        )
        if motivo == "llega_tarde" and permitir_emergencia:
            motivo = None
        if motivo:
            descartes.append({"hospital": donante.hospital_id, "motivo": motivo})
            continue
        elegibles.append(donante)

    elegibles.sort(key=lambda d: (d.vence_en_dias, -d.cantidad))

    restante = necesidad
    traslados: list[dict[str, Any]] = []
    for donante in elegibles:
        if restante <= 0:
            break
        cantidad = min(donante.cantidad, restante)
        traslados.append({"hospital": donante.hospital_id, "cantidad": cantidad})
        restante -= cantidad

    total = sum(t["cantidad"] for t in traslados)
    return ResultadoTraslado(
        traslados=traslados,
        total=total,
        faltante=max(0, necesidad - total),
        descartes=descartes,
        accion=decidir_accion(necesidad, total),
    )


def decidir_accion(necesidad: int, traslado_total: int) -> str:
    if necesidad <= 0:
        return "ninguna"
    if traslado_total <= 0:
        return "compra"
    if traslado_total >= necesidad:
        return "traslado"
    return "traslado_y_compra"


# ----------------------------------------------------------------------
# Compras
# ----------------------------------------------------------------------
def elegir_proveedor(
    ofertas: list[Oferta],
    cantidad: int,
    dias_cobertura: float,
    presupuesto: float,
    politica: str = "rechazar",
) -> ResultadoCompra:
    """Elige la oferta viable con mejor coste ajustado por plazo.

    Una oferta es viable si está disponible y llega antes de que se agote la
    cobertura (traslado incluido). El precio se penaliza por día de plazo para
    preferir entregas rápidas cuando dos proveedores cuestan parecido.
    """
    if cantidad <= 0:
        return ResultadoCompra(motivo="sin_necesidad")

    viables = [
        oferta
        for oferta in ofertas
        if oferta.disponible
        and oferta.precio_unitario > 0
        and oferta.plazo_dias <= dias_cobertura + 1e-9
    ]
    if not viables:
        return ResultadoCompra(motivo="sin_proveedor_viable")

    mejor = min(
        viables,
        key=lambda o: o.precio_unitario + PENALIZACION_DIA * o.plazo_dias,
    )
    coste = cantidad * mejor.precio_unitario

    if coste <= presupuesto + 1e-9:
        return ResultadoCompra(
            proveedor_id=mejor.proveedor_id,
            cantidad=cantidad,
            coste=round(coste, 2),
            motivo="ok",
            viables=[o.proveedor_id for o in viables],
        )

    if politica == "parcial":
        parcial = int(presupuesto // mejor.precio_unitario)
        if parcial > 0:
            return ResultadoCompra(
                proveedor_id=mejor.proveedor_id,
                cantidad=parcial,
                coste=round(parcial * mejor.precio_unitario, 2),
                motivo="parcial",
                viables=[o.proveedor_id for o in viables],
            )

    return ResultadoCompra(
        proveedor_id=mejor.proveedor_id,
        cantidad=cantidad,
        coste=round(coste, 2),
        motivo="presupuesto_insuficiente",
        viables=[o.proveedor_id for o in viables],
    )


# ----------------------------------------------------------------------
# Plan completo
# ----------------------------------------------------------------------
def planificar(
    necesidad: int,
    stock: int,
    consumo: float,
    donantes: list[Donante],
    ofertas: list[Oferta],
    presupuesto: float,
    requiere_frio: bool = False,
    transporte_refrigerado: bool = True,
    tiempo_traslado_dias: int = 1,
    politica: str = "rechazar",
    permitir_emergencia: bool = True,
) -> Plan:
    """Plan completo, útil para probar la matriz sin ejecutar la simulación."""
    necesidad = max(0, int(necesidad))
    dias_agotamiento = stock / consumo if consumo > 0 else float("inf")

    traslado = seleccionar_traslado(
        donantes=donantes,
        necesidad=necesidad,
        requiere_frio=requiere_frio,
        transporte_refrigerado=transporte_refrigerado,
        dias_hasta_agotamiento=dias_agotamiento,
        tiempo_traslado_dias=tiempo_traslado_dias,
        permitir_emergencia=permitir_emergencia,
    )

    if necesidad <= 0:
        return Plan(accion="ninguna", motivo="sin_necesidad")
    if traslado.faltante <= 0:
        return Plan(
            accion="traslado",
            traslados=traslado.traslados,
            traslado_total=traslado.total,
            faltante=0,
            motivo="excedente_suficiente",
            descartes=traslado.descartes,
        )

    cobertura = (stock + traslado.total) / consumo if consumo > 0 else float("inf")
    compra = elegir_proveedor(
        ofertas, traslado.faltante, cobertura, presupuesto, politica
    )

    if compra.motivo in ("ok", "parcial"):
        accion = "traslado_y_compra" if traslado.total > 0 else "compra"
        motivo = "cobertura_combinada" if traslado.total > 0 else "sin_excedente"
        return Plan(
            accion=accion,
            traslados=traslado.traslados,
            traslado_total=traslado.total,
            faltante=compra.cantidad,
            compra=compra,
            motivo=motivo,
            descartes=traslado.descartes,
        )

    return Plan(
        accion="traslado_parcial" if traslado.total > 0 else "escalar",
        traslados=traslado.traslados,
        traslado_total=traslado.total,
        faltante=traslado.faltante,
        compra=compra,
        motivo=compra.motivo,
        descartes=traslado.descartes,
    )
