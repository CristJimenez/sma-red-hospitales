"""Pruebas de la Situación 2 y de sus ramas alternativas."""

from __future__ import annotations

import pytest

from sma.decision_s2 import (
    calcular_urgencias,
    demanda_sustituta,
    elegir_hospital_prioritario,
    hospital_alterno,
    planificar_traslado,
)
from sma.run import ejecutar_s2
from sma.scenario.s2 import verificar_s2
from sma.variantes_s2 import cargar_variante_s2, listar_variantes_s2

VARIANTES = sorted(listar_variantes_s2())


def _real(modelo) -> dict:
    metricas = modelo.metricas()
    return {
        "resultado": metricas["resultado"],
        "lote_asignado": metricas["lote_asignado"],
        "reasignaciones": metricas["reasignaciones"],
        "timeout": metricas["timeout_pronostico"],
        "reinicio": metricas["reinicio"],
        "fuente_demanda": metricas["fuente_demanda"],
        "lista_espera": metricas["lista_espera"],
        "riesgo_residual": metricas["riesgo_residual"],
        "escalado": metricas["escalado"],
    }


# ----------------------------------------------------------------------
# Flujo base (timeout del Pronóstico)
# ----------------------------------------------------------------------
def test_situacion_2_completa() -> None:
    modelo = ejecutar_s2()

    fallos = [check for check in verificar_s2(modelo) if not check["ok"]]
    assert not fallos, fallos

    metricas = modelo.metricas()
    assert modelo.cierre is True
    assert modelo.resultado == "exito"
    assert modelo.lote_asignado == "H_A"
    assert modelo.lista_espera == "H_B"
    assert metricas["timeout_pronostico"] is True
    assert metricas["pronostico_recuperado"] is True
    assert metricas["reinicio"] == "exitoso"
    assert metricas["rondas"] == 9
    assert metricas["mensajes"] == 16
    assert metricas["stock_final"] == {"H_A": 260, "H_B": 40, "H_C": 0}


@pytest.mark.parametrize("nombre", VARIANTES)
def test_el_lote_nunca_se_duplica(nombre: str) -> None:
    modelo = ejecutar_s2(cargar_variante_s2(nombre).configuracion(), max_rondas=24)
    metricas = modelo.metricas()
    origen = modelo.hospital_origen
    asignado = metricas["lote_asignado"]

    if asignado is None:
        assert metricas["stock_final"][origen] == modelo.cantidad_lote
        assert modelo.lote.hospital_id == origen
    else:
        assert metricas["stock_final"][origen] == 0
        assert modelo.lote.hospital_id == asignado
        con_lote = [
            hospital
            for hospital, stock in metricas["stock_final"].items()
            if hospital != origen and stock >= modelo.cantidad_lote
        ]
        assert con_lote == [asignado]


def test_ejecucion_determinista_s2() -> None:
    primera = ejecutar_s2()
    segunda = ejecutar_s2()

    assert primera.metricas() == segunda.metricas()
    assert len(primera.traza.eventos) == len(segunda.traza.eventos)


@pytest.mark.parametrize("nombre", VARIANTES)
def test_variante_cumple_lo_esperado(nombre: str) -> None:
    variante = cargar_variante_s2(nombre)
    modelo = ejecutar_s2(variante.configuracion(), max_rondas=24)
    real = _real(modelo)

    for clave, esperado in variante.esperado.items():
        assert real[clave] == esperado, (
            f"{nombre}: {clave}={real[clave]!r}, esperado {esperado!r}"
        )

    assert modelo.cierre is True, f"{nombre} no cerró"
    assert modelo.supervisor.reporte is not None, f"{nombre} sin reporte"


def test_traslado_rechazado_genera_refuse_y_reasigna() -> None:
    modelo = ejecutar_s2(
        cargar_variante_s2("s2_traslado_rechazado").configuracion(), 24
    )

    assert any(
        mensaje["performativa"] == "refuse" for mensaje in modelo.traza.mensajes()
    )
    assert modelo.lote_asignado == "H_B"
    assert modelo.reasignaciones == 1
    assert modelo.resultado == "exito"


def test_sin_receptor_escala_y_deja_el_lote_en_c() -> None:
    modelo = ejecutar_s2(
        cargar_variante_s2("s2_sin_receptor").configuracion(), 24
    )

    assert modelo.resultado == "escalado"
    assert modelo.escalado is True
    assert modelo.lote_asignado is None
    assert modelo.lote.hospital_id == "H_C"
    assert modelo.riesgo_residual == 365


def test_diagrama_mermaid_s2() -> None:
    mermaid = ejecutar_s2().traza.a_mermaid()

    assert mermaid.startswith("sequenceDiagram")
    assert "autonumber" not in mermaid
    for alias in ("RED", "INV", "PRO", "COORD", "SUP", "LOTE"):
        assert f"participant {alias} " in mermaid
    assert "traslado_lote" in mermaid
    assert "INFORM" in mermaid


# ----------------------------------------------------------------------
# Funciones puras de decisión
# ----------------------------------------------------------------------
STOCK = {
    "H_A": {"stock": 60, "consumo_diario": 20.0, "dias_hasta_agotamiento": 3.0},
    "H_B": {"stock": 40, "consumo_diario": 10.0, "dias_hasta_agotamiento": 4.0},
}


def test_prioriza_el_hospital_que_se_agota_antes() -> None:
    urgencias = calcular_urgencias(STOCK, {"H_A": 310, "H_B": 155})

    assert [urgencia.hospital for urgencia in urgencias] == ["H_A", "H_B"]
    assert elegir_hospital_prioritario(urgencias).hospital == "H_A"

    plan = planificar_traslado(urgencias, 200)
    assert plan.hospital == "H_A"
    assert plan.cantidad == 200
    assert plan.faltante == 50
    assert hospital_alterno(plan) == "H_B"


def test_el_lote_completo_va_a_un_solo_hospital() -> None:
    urgencias = calcular_urgencias(STOCK, {"H_A": 310, "H_B": 155})
    plan = planificar_traslado(urgencias, 200)

    assert plan.cantidad == 200
    assert plan.hospital in ("H_A", "H_B")
    assert len({urgencia.hospital for urgencia in plan.urgencias}) == 2


def test_demanda_sustituta_usa_la_ultima_estimacion() -> None:
    assert demanda_sustituta({"H_A": 310, "H_B": 155}, {}, 14) == {
        "H_A": 310,
        "H_B": 155,
    }


def test_demanda_sustituta_cae_al_historial() -> None:
    historial = {"H_A": [10.0] * 14, "H_B": [5.0] * 14}

    assert demanda_sustituta({}, historial, 14) == {"H_A": 140, "H_B": 70}
