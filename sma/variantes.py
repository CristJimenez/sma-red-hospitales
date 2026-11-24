"""Catálogo de variantes ("y si") del escenario.

Cada variante es un override declarativo sobre ``config/s1.yaml``. Así se
prueban todos los caminos del Coordinador sin duplicar el escenario base.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .config import RAIZ, cargar_config
from .domain.models import Configuracion

RUTA_VARIANTES = RAIZ / "config" / "variantes.yaml"


@dataclass
class Variante:
    nombre: str
    titulo: str
    descripcion: str
    esperado: dict[str, Any]
    overrides: dict[str, Any]

    def configuracion(self) -> Configuracion:
        return cargar_config(overrides=self.overrides)


def _leer(ruta: str | Path | None = None) -> dict[str, Any]:
    archivo = Path(ruta) if ruta else RUTA_VARIANTES
    return yaml.safe_load(archivo.read_text(encoding="utf-8"))["variantes"]


def listar_variantes(ruta: str | Path | None = None) -> dict[str, Variante]:
    datos = _leer(ruta)
    return {
        nombre: Variante(
            nombre=nombre,
            titulo=cuerpo.get("titulo", nombre),
            descripcion=cuerpo.get("descripcion", ""),
            esperado=cuerpo.get("esperado", {}),
            overrides=cuerpo.get("overrides", {}),
        )
        for nombre, cuerpo in datos.items()
    }


def cargar_variante(nombre: str) -> Variante:
    variantes = listar_variantes()
    if nombre not in variantes:
        disponibles = ", ".join(sorted(variantes))
        raise KeyError(f"Variante '{nombre}' no existe. Disponibles: {disponibles}")
    return variantes[nombre]
