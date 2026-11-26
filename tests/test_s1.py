"""Pruebas de la Situación 1 y de las ramas alternativas."""

import re
import xml.etree.ElementTree as ET

from sma import diagrama
from sma.config import cargar_config
from sma.diagrama import generar
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
    assert modelo.metricas()["traslado_recibido"] == 470
    assert modelo.metricas()["cantidad_comprada"] == 110
    assert modelo.metricas()["cobertura_proyectada"] >= 0.999
    assert modelo.resultado == "exito"


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
    assert modelo.resultado == "parcial"
    assert modelo.riesgo_residual > 0
    assert modelo.replanificaciones >= 1


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
    assert modelo.resultado == "parcial"
    assert modelo.riesgo_residual > 0


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


def test_diagrama_drawio_coincide_con_la_traza() -> None:
    """El .drawio de la S1 no se dibuja a mano: sale de los mismos eventos."""
    modelo = ejecutar()
    raiz = ET.fromstring(generar({"eventos": modelo.traza.eventos}))

    etiquetas = [
        celda.get("value") or ""
        for celda in raiz.iter("mxCell")
        if celda.get("edge") == "1"
    ]
    numeradas = [etiqueta for etiqueta in etiquetas if re.match(r"\[\d+\]", etiqueta)]

    assert diagrama.SALIDA.name == "s1_secuencia.drawio"
    assert len(numeradas) == 15
    assert [
        int(re.match(r"\[(\d+)\]", etiqueta).group(1))
        for etiqueta in numeradas
    ] == list(range(1, 16))

    texto = " ".join(etiquetas)
    for contenido in (
        "informe_inventario",
        "demanda_proyectada",
        "excedentes",
        "decision",
        "retraso_proveedor",
        "orden_generada",
        "orden_confirmada",
        "cierre",
    ):
        assert contenido in texto

    cabeceras = [
        celda.get("value") or ""
        for celda in raiz.iter("mxCell")
        if "rounded=1" in (celda.get("style") or "")
    ]
    assert len(cabeceras) == 9
