"""Carga de la Situación 2 desde YAML.

Reutiliza los objetos de dominio de la Situación 1 (Hospital, Lote,
Medicamento) y el generador de historial sintético, pero tiene su propia
configuración: no hay proveedores ni presupuesto, y el riesgo es un lote
próximo a vencer en un tercer hospital.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .config import RAIZ, _fusionar, _generar_historial
from .domain.models import Hospital, Lote, Medicamento

RUTA_S2 = RAIZ / "config" / "s2.yaml"


@dataclass
class OpcionesS2:
    pronostico_caido: bool = True
    ronda_fallo_pronostico: int = 3
    reinicio_falla: bool = False
    rechazos_traslado: int = 0
    dias_para_vencer: int = 30


@dataclass
class ConfiguracionS2:
    semilla: int
    horizonte_pronostico_dias: int
    ronda_inicio: int
    medicamentos: dict[str, Medicamento]
    hospitales: dict[str, Hospital]
    lote_riesgo: dict[str, Any]
    opciones: OpcionesS2 = field(default_factory=OpcionesS2)

    @property
    def medicamento(self) -> str:
        return str(self.lote_riesgo["medicamento"])

    @property
    def hospital_origen(self) -> str:
        return str(self.lote_riesgo["hospital"])


def cargar_config_s2(
    ruta: str | Path | None = None, overrides: dict[str, Any] | None = None
) -> ConfiguracionS2:
    ruta = Path(ruta) if ruta else RUTA_S2
    datos: dict[str, Any] = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    if overrides:
        datos = _fusionar(datos, overrides)

    semilla = int(datos.get("semilla", 11))

    medicamentos = {
        med_id: Medicamento(id=med_id, **cuerpo)
        for med_id, cuerpo in datos["medicamentos"].items()
    }

    hospitales: dict[str, Hospital] = {}
    for hosp_id, cuerpo in datos["hospitales"].items():
        lotes: dict[str, list[Lote]] = {}
        for med_id, inv in cuerpo.get("inventario", {}).items():
            lotes[med_id] = [
                Lote(
                    id=inv["lote"],
                    medicamento_id=med_id,
                    cantidad=int(inv["cantidad"]),
                    vence_en_dias=int(inv.get("vence_en_dias", 365)),
                    hospital_id=hosp_id,
                )
            ]
        hospital = Hospital(
            id=hosp_id,
            nombre=cuerpo["nombre"],
            complejidad=cuerpo.get("complejidad", "media"),
            camas=int(cuerpo.get("camas", 0)),
            stock_seguridad_dias=float(cuerpo.get("stock_seguridad_dias", 5)),
            lotes=lotes,
            consumo_diario={
                k: float(v) for k, v in cuerpo.get("consumo_diario", {}).items()
            },
        )
        hospital.historial = {
            med_id: _generar_historial(semilla, hosp_id, med_id, base)
            for med_id, base in hospital.consumo_diario.items()
        }
        hospitales[hosp_id] = hospital

    return ConfiguracionS2(
        semilla=semilla,
        horizonte_pronostico_dias=int(datos.get("horizonte_pronostico_dias", 14)),
        ronda_inicio=int(datos.get("ronda_inicio", 1)),
        medicamentos=medicamentos,
        hospitales=hospitales,
        lote_riesgo=dict(datos["lote_riesgo"]),
        opciones=OpcionesS2(**datos.get("opciones", {})),
    )
