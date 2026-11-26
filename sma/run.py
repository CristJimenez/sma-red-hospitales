"""Ejecución de los escenarios desde la línea de comandos.

Uso:
    python -m sma.run
    python -m sma.run --variante solo_traslado
    python -m sma.run --situacion 2
    python -m sma.run --situacion 2 --variante s2_pronostico_ok
    python -m sma.run --rondas 20 --salida out
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .config import cargar_config
from .config_s2 import cargar_config_s2
from .domain.models import Configuracion
from .model import RedHospitalaria
from .model_s2 import RedHospitalariaS2
from .scenario.s1 import verificar
from .scenario.s2 import verificar_s2
from .variantes import cargar_variante, listar_variantes
from .variantes_s2 import cargar_variante_s2, listar_variantes_s2


def ejecutar(
    config: Configuracion | None = None, max_rondas: int = 20
) -> RedHospitalaria:
    cfg = config or cargar_config()
    modelo = RedHospitalaria(cfg)
    for _ in range(max_rondas):
        modelo.step()
        if modelo.cierre and modelo.supervisor.reporte is not None:
            break
    return modelo


def ejecutar_variante(nombre: str, max_rondas: int = 20) -> RedHospitalaria:
    return ejecutar(cargar_variante(nombre).configuracion(), max_rondas=max_rondas)


def ejecutar_s2(config=None, max_rondas: int = 24) -> RedHospitalariaS2:
    cfg = config or cargar_config_s2()
    modelo = RedHospitalariaS2(cfg)
    for _ in range(max_rondas):
        modelo.step()
        if modelo.cierre and modelo.supervisor.reporte is not None:
            break
    return modelo


def ejecutar_variante_s2(nombre: str, max_rondas: int = 24) -> RedHospitalariaS2:
    return ejecutar_s2(cargar_variante_s2(nombre).configuracion(), max_rondas=max_rondas)


def imprimir_timeline(modelo: Any) -> None:
    for evento in modelo.traza.eventos:
        if evento["tipo"] == "mensaje":
            print(
                f"[r{evento['ronda']:02d}] "
                f"{evento['emisor']:>11} -> {evento['receptor']:<11} "
                f"{evento['performativa'].upper():<9} {evento['contenido']}"
            )
        elif evento["tipo"] == "entorno":
            print(
                f"[r{evento['ronda']:02d}] "
                f"{'ENTORNO':>11} :: {evento['accion']} {evento['detalle']}"
            )
        else:
            print(
                f"[r{evento['ronda']:02d}] "
                f"{evento['agente']:>11} :: {evento['accion']} {evento['detalle']}"
            )


def _resumen_variante(modelo: RedHospitalaria, esperado: dict[str, Any]) -> None:
    metricas = modelo.metricas()
    real = {
        "accion": metricas.get("accion"),
        "traslado": metricas.get("traslado_recibido"),
        "compra": metricas.get("cantidad_comprada"),
        "orden": modelo.orden_actual is not None,
        "resultado": metricas.get("resultado"),
        "riesgo_residual": metricas.get("riesgo_residual"),
    }
    print("\n=== Variante ===")
    for clave, valor in real.items():
        esperado_valor = esperado.get(clave)
        marca = ""
        if esperado_valor is not None:
            marca = "OK" if valor == esperado_valor else f"esperado {esperado_valor}"
        print(f"  {clave}: {valor} {marca}")


def _real_s2(modelo: RedHospitalariaS2) -> dict[str, Any]:
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


def _resumen_variante_s2(modelo: RedHospitalariaS2, esperado: dict[str, Any]) -> None:
    real = _real_s2(modelo)
    print("\n=== Variante ===")
    for clave, valor in real.items():
        esperado_valor = esperado.get(clave)
        marca = ""
        if esperado_valor is not None:
            marca = "OK" if valor == esperado_valor else f"esperado {esperado_valor}"
        print(f"  {clave}: {valor} {marca}")


def _guardar(modelo: Any, salida: Path, etiqueta: str) -> None:
    salida.mkdir(parents=True, exist_ok=True)
    (salida / f"{etiqueta}_traza.json").write_text(
        json.dumps(modelo.traza.a_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (salida / f"{etiqueta}_secuencia.mmd").write_text(
        modelo.traza.a_mermaid(), encoding="utf-8"
    )
    print(f"\nTraza y diagrama Mermaid guardados en {salida.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="SMA hospitalario: Situación 1 o 2")
    parser.add_argument("--situacion", type=int, choices=(1, 2), default=1)
    parser.add_argument("--rondas", type=int, default=20)
    parser.add_argument("--salida", type=str, default="out")
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--variante", type=str, default=None)
    parser.add_argument("--listar", action="store_true")
    args = parser.parse_args()

    if args.situacion == 2:
        _main_s2(args)
        return

    if args.listar:
        for nombre, variante in listar_variantes().items():
            print(f"{nombre:<28} {variante.titulo}")
        return

    if args.variante:
        variante = cargar_variante(args.variante)
        config = variante.configuracion()
        etiqueta = args.variante
    else:
        variante = None
        config = cargar_config(args.config)
        etiqueta = "s1"

    modelo = ejecutar(config, max_rondas=args.rondas)

    imprimir_timeline(modelo)

    print("\n=== Métricas ===")
    for clave, valor in modelo.metricas().items():
        print(f"  {clave}: {valor}")

    if variante is not None:
        _resumen_variante(modelo, variante.esperado)
    else:
        print("\n=== Verificación del escenario ===")
        for check in verificar(modelo):
            marca = "OK " if check["ok"] else "FALLA"
            print(f"  [{marca}] {check['nombre']} {check['detalle']}")

    _guardar(modelo, Path(args.salida), etiqueta)


def _main_s2(args: argparse.Namespace) -> None:
    if args.listar:
        for nombre, variante in listar_variantes_s2().items():
            print(f"{nombre:<28} {variante.titulo}")
        return

    if args.variante:
        variante = cargar_variante_s2(args.variante)
        config = variante.configuracion()
        etiqueta = args.variante
    else:
        variante = None
        config = cargar_config_s2(args.config)
        etiqueta = "s2"

    modelo = ejecutar_s2(config, max_rondas=args.rondas)

    imprimir_timeline(modelo)

    print("\n=== Métricas ===")
    for clave, valor in modelo.metricas().items():
        print(f"  {clave}: {valor}")

    if variante is not None:
        _resumen_variante_s2(modelo, variante.esperado)
    else:
        print("\n=== Verificación del escenario ===")
        for check in verificar_s2(modelo):
            marca = "OK " if check["ok"] else "FALLA"
            print(f"  [{marca}] {check['nombre']} {check['detalle']}")

    _guardar(modelo, Path(args.salida), etiqueta)


if __name__ == "__main__":
    main()
