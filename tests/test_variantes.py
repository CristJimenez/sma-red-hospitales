"""Matriz de variantes: cada fila de "y si" se prueba de extremo a extremo."""

from __future__ import annotations

import pytest

from sma.decision import Donante, Oferta, elegir_proveedor, planificar
from sma.run import ejecutar
from sma.variantes import cargar_variante, listar_variantes

VARIANTES = sorted(listar_variantes())


def _real(modelo) -> dict:
    metricas = modelo.metricas()
    return {
        "accion": metricas["accion"],
        "traslado": metricas["traslado_recibido"],
        "compra": metricas["cantidad_comprada"],
        "proveedor": modelo.orden_actual.proveedor_id if modelo.orden_actual else None,
        "orden": modelo.orden_actual is not None,
        "resultado": metricas["resultado"],
        "riesgo_residual": metricas["riesgo_residual"],
        "decisiones": len(modelo.decisiones),
        "ordenes": len(modelo.ordenes),
        "donantes": modelo.decisiones[0].get("donantes") if modelo.decisiones else None,
    }


@pytest.mark.parametrize("nombre", VARIANTES)
def test_variante_cumple_lo_esperado(nombre: str) -> None:
    variante = cargar_variante(nombre)
    modelo = ejecutar(variante.configuracion(), max_rondas=24)
    real = _real(modelo)

    for clave, esperado in variante.esperado.items():
        assert real[clave] == esperado, f"{nombre}: {clave}={real[clave]!r}, esperado {esperado!r}"

    assert modelo.cierre is True, f"{nombre} no cerró"
    assert modelo.supervisor.reporte is not None, f"{nombre} sin reporte del Supervisor"


@pytest.mark.parametrize("nombre", VARIANTES)
def test_variante_es_reproducible(nombre: str) -> None:
    variante = cargar_variante(nombre)
    primera = ejecutar(variante.configuracion(), max_rondas=24)
    segunda = ejecutar(variante.configuracion(), max_rondas=24)

    assert primera.metricas() == segunda.metricas()
    assert len(primera.traza.eventos) == len(segunda.traza.eventos)


# ----------------------------------------------------------------------
# Funciones puras de decisión
# ----------------------------------------------------------------------
OFERTAS = [Oferta("P1", 2.40, 12), Oferta("P2", 2.60, 5)]


def test_plan_sin_necesidad() -> None:
    plan = planificar(0, 800, 48, [], OFERTAS, 5000)
    assert plan.accion == "ninguna"
    assert plan.traslados == []


def test_plan_solo_traslado() -> None:
    plan = planificar(
        580, 120, 48, [Donante("H_B", 700, 45)], OFERTAS, 5000
    )
    assert plan.accion == "traslado"
    assert plan.traslado_total == 580
    assert plan.compra is None


def test_plan_traslado_y_compra() -> None:
    plan = planificar(
        580, 120, 48, [Donante("H_B", 344, 45), Donante("H_C", 126, 150)], OFERTAS, 5000
    )
    assert plan.accion == "traslado_y_compra"
    assert plan.traslado_total == 470
    assert plan.faltante == 110
    assert plan.compra is not None and plan.compra.proveedor_id == "P2"


def test_plan_descarta_lote_por_vencer() -> None:
    plan = planificar(
        580,
        120,
        48,
        [Donante("H_B", 344, 1), Donante("H_C", 126, 150)],
        OFERTAS,
        5000,
    )
    assert plan.traslado_total == 126
    assert {"hospital": "H_B", "motivo": "lote_por_vencer"} in plan.descartes


def test_plan_descarta_cadena_frio_sin_transporte() -> None:
    plan = planificar(
        108,
        48,
        9.6,
        [Donante("H_B", 39, 120), Donante("H_C", 28, 90)],
        [Oferta("P1", 17.5, 12), Oferta("P2", 18.2, 5)],
        5000,
        requiere_frio=True,
        transporte_refrigerado=False,
    )
    assert plan.accion == "compra"
    assert plan.traslado_total == 0
    assert {d["motivo"] for d in plan.descartes} == {"transporte_sin_refrigeracion"}


def test_plan_sin_proveedor_viable() -> None:
    plan = planificar(
        580,
        120,
        48,
        [Donante("H_B", 344, 45), Donante("H_C", 126, 150)],
        [Oferta("P1", 2.40, 15), Oferta("P2", 2.60, 35)],
        5000,
    )
    assert plan.accion == "traslado_parcial"
    assert plan.compra is not None and plan.compra.motivo == "sin_proveedor_viable"


def test_compra_parcial_por_presupuesto() -> None:
    compra = elegir_proveedor([Oferta("P2", 2.60, 5)], 110, 12.3, 200, "parcial")
    assert compra.motivo == "parcial"
    assert compra.cantidad == 76
    assert compra.coste == pytest.approx(197.6)


def test_traza_no_se_muta_despues_de_replanificar() -> None:
    modelo = ejecutar(cargar_variante("proveedores_retrasados").configuracion(), 24)
    decisiones = [
        m
        for m in modelo.traza.mensajes()
        if m["contenido"].get("tipo") == "decision"
    ]

    assert decisiones
    assert decisiones[0]["contenido"]["accion"] == "traslado_parcial"
    assert decisiones[0]["contenido"]["traslado"] == 470
