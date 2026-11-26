"""Catálogo de variantes ("y si") de la Situación 2.

Cada variante es un override declarativo sobre ``config/s2.yaml``: activa o
desactiva el timeout, el fallo del reinicio o los rechazos del traslado sin
duplicar el escenario.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .config import RAIZ
from .config_s2 import ConfiguracionS2, cargar_config_s2

RUTA_VARIANTES_S2 = RAIZ / "config" / "variantes_s2.yaml"


@dataclass
class VarianteS2:
    nombre: str
    titulo: str
    descripcion: str
    esperado: dict[str, Any]
    overrides: dict[str, Any]

    def configuracion(self) -> ConfiguracionS2:
        return cargar_config_s2(overrides=self.overrides)


def _leer(ruta: str | Path | None = None) -> dict[str, Any]:
    archivo = Path(ruta) if ruta else RUTA_VARIANTES_S2
    return yaml.safe_load(archivo.read_text(encoding="utf-8"))["variantes"]


def listar_variantes_s2(ruta: str | Path | None = None) -> dict[str, VarianteS2]:
    datos = _leer(ruta)
    return {
        nombre: VarianteS2(
            nombre=nombre,
            titulo=cuerpo.get("titulo", nombre),
            descripcion=cuerpo.get("descripcion", ""),
            esperado=cuerpo.get("esperado", {}),
            overrides=cuerpo.get("overrides", {}),
        )
        for nombre, cuerpo in datos.items()
    }


def cargar_variante_s2(nombre: str) -> VarianteS2:
    variantes = listar_variantes_s2()
    if nombre not in variantes:
        disponibles = ", ".join(sorted(variantes))
        raise KeyError(f"Variante '{nombre}' no existe. Disponibles: {disponibles}")
    return variantes[nombre]
