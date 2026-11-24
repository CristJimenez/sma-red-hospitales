"""Ejecución del escenario desde la línea de comandos.

Uso:
    python -m sma.run
    python -m sma.run --rondas 12 --salida out
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import cargar_config
from .domain.models import Configuracion
from .model import RedHospitalaria
from .scenario.s1 import verificar


def ejecutar(
    config: Configuracion | None = None, max_rondas: int = 12
) -> RedHospitalaria:
    cfg = config or cargar_config()
    modelo = RedHospitalaria(cfg)
    for _ in range(max_rondas):
        modelo.step()
        if modelo.cierre and modelo.supervisor.reporte is not None:
            break
    return modelo


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Situación 1 del SMA hospitalario")
    parser.add_argument("--rondas", type=int, default=12)
    parser.add_argument("--salida", type=str, default="out")
    parser.add_argument("--config", type=str, default=None)
    args = parser.parse_args()

    modelo = ejecutar(cargar_config(args.config), max_rondas=args.rondas)

    imprimir_timeline(modelo)

    print("\n=== Métricas ===")
    for clave, valor in modelo.metricas().items():
        print(f"  {clave}: {valor}")

    print("\n=== Verificación del escenario ===")
    for check in verificar(modelo):
        marca = "OK " if check["ok"] else "FALLA"
        print(f"  [{marca}] {check['nombre']} {check['detalle']}")

    salida = Path(args.salida)
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "s1_traza.json").write_text(
        json.dumps(modelo.traza.a_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (salida / "s1_secuencia.mmd").write_text(
        modelo.traza.a_mermaid(), encoding="utf-8"
    )
    print(f"\nTraza y diagrama Mermaid guardados en {salida.resolve()}")


if __name__ == "__main__":
    main()
