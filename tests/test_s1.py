"""Pruebas de la Situación 1 y de las ramas alternativas."""

from sma.config import cargar_config
from sma.run import ejecutar
from sma.scenario.s1 import verificar


def test_situacion_1_completa() -> None:
    modelo = ejecutar()

    fallos = [check for check in verificar(modelo) if not check["ok"]]
    assert not fallos, fallos

    assert modelo.cierre is True
    assert modelo.orden_actual is not None
    assert modelo.orden_actual.estado == "confirmada"
    assert modelo.orden_actual.proveedor_id == "P2"
    assert modelo.presupuesto_restante < modelo.config.presupuesto_inicial
    assert modelo.metricas()["cobertura_proyectada"] >= 0.999


def test_presupuesto_insuficiente() -> None:
    config = cargar_config()
    config.opciones.forzar_presupuesto_insuficiente = True

    modelo = ejecutar(config)
    fallos = [
        mensaje
        for mensaje in modelo.traza.mensajes()
        if mensaje["performativa"] == "failure"
    ]

    assert fallos, "debería emitirse un FAILURE por presupuesto"
    assert fallos[0]["contenido"]["motivo"] == "presupuesto_insuficiente"
    assert modelo.orden_actual is None
    assert modelo.cierre is False


def test_compras_no_puede_gestionar() -> None:
    config = cargar_config()
    config.opciones.compras_puede_gestionar = False

    modelo = ejecutar(config)
    motivos = [
        mensaje["contenido"].get("motivo")
        for mensaje in modelo.traza.mensajes()
        if mensaje["performativa"] == "failure"
    ]

    assert "no_puedo_gestionar_compra" in motivos
    assert modelo.orden_actual is None


def test_ejecucion_determinista() -> None:
    primera = ejecutar()
    segunda = ejecutar()

    assert primera.metricas() == segunda.metricas()
    assert len(primera.traza.eventos) == len(segunda.traza.eventos)


def test_diagrama_mermaid_se_genera_desde_la_traza() -> None:
    modelo = ejecutar()
    mermaid = modelo.traza.a_mermaid()

    assert mermaid.startswith("sequenceDiagram")
    for alias in ("INV", "PRO", "COORD", "COMP", "SUP", "P1", "P2", "OC"):
        assert f"participant {alias} " in mermaid
    assert "traslado" in mermaid
    assert "INFORM" in mermaid
