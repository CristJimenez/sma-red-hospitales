"""Ejecución del escenario desde la línea de comandos.

Uso:
    python -m sma.run
    python -m sma.run --variante solo_traslado
    python -m sma.run --rondas 20 --salida out
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .config import cargar_config
from .domain.models import Configuracion
from .model import RedHospitalaria
from .scenario.s1 import verificar
from .variantes import cargar_variante, listar_variantes


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


def imprimir_timeline(modelo: RedHospitalaria) -> None:
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Situación 1 del SMA hospitalario")
    parser.add_argument("--rondas", type=int, default=20)
    parser.add_argument("--salida", type=str, default="out")
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--variante", type=str, default=None)
    parser.add_argument("--listar", action="store_true")
    args = parser.parse_args()

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

    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    (salida / f"{etiqueta}_traza.json").write_text(
        json.dumps(modelo.traza.a_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (salida / f"{etiqueta}_secuencia.mmd").write_text(
        modelo.traza.a_mermaid(), encoding="utf-8"
    )
    print(f"\nTraza y diagrama Mermaid guardados en {salida.resolve()}")


if __name__ == "__main__":
    main()
