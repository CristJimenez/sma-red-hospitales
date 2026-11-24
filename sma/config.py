"""Carga de configuración del escenario desde YAML."""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import yaml

from .domain.models import (
    Configuracion,
    Evento,
    Hospital,
    Lote,
    Medicamento,
    Opciones,
    Proveedor,
)

RAIZ = Path(__file__).resolve().parent.parent
RUTA_S1 = RAIZ / "config" / "s1.yaml"

FACTORES_SEMANA = [1.00, 1.05, 1.02, 1.00, 1.12, 0.92, 0.88]


def _generar_historial(
    semilla: int, hospital_id: str, medicamento_id: str, base: float, dias: int = 28
) -> list[float]:
    """Historial sintético reproducible: estacionalidad semanal + tendencia + ruido."""
    rng = random.Random(f"{semilla}:{hospital_id}:{medicamento_id}")
    serie: list[float] = []
    for dia in range(dias):
        tendencia = 1.0 + 0.006 * dia
        estacional = FACTORES_SEMANA[dia % 7]
        ruido = rng.uniform(0.93, 1.07)
        serie.append(round(max(1.0, base * tendencia * estacional * ruido), 2))
    return serie


def cargar_config(ruta: str | Path | None = None) -> Configuracion:
    ruta = Path(ruta) if ruta else RUTA_S1
    datos: dict[str, Any] = yaml.safe_load(ruta.read_text(encoding="utf-8"))

    semilla = int(datos.get("semilla", 7))

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
            consumo_diario={k: float(v) for k, v in cuerpo.get("consumo_diario", {}).items()},
        )
        hospital.historial = {
            med_id: _generar_historial(semilla, hosp_id, med_id, base)
            for med_id, base in hospital.consumo_diario.items()
        }
        hospitales[hosp_id] = hospital

    proveedores = {
        prov_id: Proveedor(id=prov_id, **cuerpo)
        for prov_id, cuerpo in datos["proveedores"].items()
    }

    evento = Evento(**datos["evento"])
    opciones = Opciones(**datos.get("opciones", {}))

    return Configuracion(
        semilla=semilla,
        presupuesto_inicial=float(datos.get("presupuesto_inicial", 0.0)),
        horizonte_pronostico_dias=int(datos.get("horizonte_pronostico_dias", 14)),
        medicamentos=medicamentos,
        hospitales=hospitales,
        proveedores=proveedores,
        evento=evento,
        opciones=opciones,
    )
