"""Traza de la ejecución: eventos, mensajes y exportación a Mermaid.

El diagrama de secuencia del informe se genera desde la traza real, de modo
que el dibujo y la ejecución no pueden divergir.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .acl import MensajeACL

# Orden de participantes tal como aparece en SITUACION.md
PARTICIPANTES = [
    ("RED", "Red de hospitales"),
    ("INV", "Inventario"),
    ("PRO", "Pronostico"),
    ("COORD", "Coordinador"),
    ("COMP", "Compras"),
    ("SUP", "Supervisor"),
    ("P1", "Proveedor 1"),
    ("P2", "Proveedor 2"),
    ("OC", "OrdenCompra"),
]

ALIAS = {
    "entorno": "RED",
    "inventario": "INV",
    "pronostico": "PRO",
    "coordinador": "COORD",
    "compras": "COMP",
    "supervisor": "SUP",
    "proveedor_1": "P1",
    "proveedor_2": "P2",
    "orden_compra": "OC",
}

# Situación 2: sin Compras ni proveedores; el Lote es un objeto del dominio.
PARTICIPANTES_S2 = [
    ("RED", "Red de hospitales"),
    ("INV", "Inventario"),
    ("PRO", "Pronostico"),
    ("COORD", "Coordinador"),
    ("SUP", "Supervisor"),
    ("LOTE", "Lote"),
]

ALIAS_S2 = {
    "entorno": "RED",
    "inventario": "INV",
    "pronostico": "PRO",
    "coordinador": "COORD",
    "supervisor": "SUP",
    "lote": "LOTE",
}


class Traza:
    def __init__(
        self,
        participantes: list[tuple[str, str]] | None = None,
        alias: dict[str, str] | None = None,
        autonumerar: bool = True,
    ) -> None:
        self.eventos: list[dict[str, Any]] = []
        self.participantes = participantes or PARTICIPANTES
        self.alias = alias or ALIAS
        self.autonumerar = autonumerar

    # ------------------------------------------------------------------
    # Registro
    # ------------------------------------------------------------------
    def _nuevo(self, evento: dict[str, Any]) -> None:
        evento["orden"] = len(self.eventos) + 1
        self.eventos.append(evento)

    def registrar_mensaje(self, mensaje: MensajeACL) -> None:
        self._nuevo(mensaje.a_dict())

    def registrar_accion(
        self,
        ronda: int,
        agente: str,
        accion: str,
        detalle: dict[str, Any] | None = None,
    ) -> None:
        self._nuevo(
            {
                "ronda": ronda,
                "tipo": "accion",
                "agente": agente,
                "accion": accion,
                "detalle": deepcopy(detalle) if detalle else {},
            }
        )

    def registrar_entorno(
        self,
        ronda: int,
        accion: str,
        detalle: dict[str, Any] | None = None,
        origen: str | None = None,
        destino: str | None = None,
    ) -> None:
        self._nuevo(
            {
                "ronda": ronda,
                "tipo": "entorno",
                "accion": accion,
                "detalle": deepcopy(detalle) if detalle else {},
                "origen": origen,
                "destino": destino,
            }
        )

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------
    def mensajes(self) -> list[dict[str, Any]]:
        return [e for e in self.eventos if e["tipo"] == "mensaje"]

    def buscar(self, **filtros: Any) -> list[dict[str, Any]]:
        return [
            e
            for e in self.eventos
            if all(e.get(clave) == valor for clave, valor in filtros.items())
        ]

    def acciones(self) -> list[dict[str, Any]]:
        return [e for e in self.eventos if e["tipo"] == "accion"]

    def entorno(self) -> list[dict[str, Any]]:
        return [e for e in self.eventos if e["tipo"] == "entorno"]

    # ------------------------------------------------------------------
    # Exportación
    # ------------------------------------------------------------------
    def a_dict(self) -> dict[str, Any]:
        return {"eventos": self.eventos}

    def a_mermaid(self) -> str:
        lineas = ["sequenceDiagram"]
        if self.autonumerar:
            lineas.append("    autonumber")
        for alias, nombre in self.participantes:
            lineas.append(f"    participant {alias} as {nombre}")

        for evento in self.eventos:
            if evento["tipo"] == "mensaje":
                origen = self.alias.get(evento["emisor"], evento["emisor"])
                destino = self.alias.get(evento["receptor"], evento["receptor"])
                texto = f"{evento['performativa'].upper()}: {_resumen(evento['contenido'])}"
                lineas.append(f"    {origen}->>{destino}: {_limpiar(texto)}")
            elif evento["tipo"] == "entorno" and evento.get("origen") and evento.get("destino"):
                origen = self.alias.get(evento["origen"], evento["origen"])
                destino = self.alias.get(evento["destino"], evento["destino"])
                texto = f"{evento['accion']}: {_resumen(evento['detalle'])}"
                lineas.append(f"    {origen}->>{destino}: {_limpiar(texto)}")
            elif evento["tipo"] == "entorno":
                texto = f"{evento['accion']}: {_resumen(evento['detalle'])}"
                lineas.append(f"    Note over RED: {_limpiar(texto)}")
            elif evento["tipo"] == "accion":
                alias = self.alias.get(evento["agente"], evento["agente"])
                texto = f"{evento['accion']}({_resumen(evento['detalle'], 45)})"
                lineas.append(f"    {alias}->>{alias}: {_limpiar(texto)}")
        return "\n".join(lineas)


def _valor_texto(valor: Any) -> str:
    if isinstance(valor, dict):
        for clave in ("orden", "proveedor", "hospital", "medicamento", "tipo"):
            if clave in valor:
                return str(valor[clave])
        return ", ".join(f"{k}={v}" for k, v in list(valor.items())[:2])
    return str(valor)


def _resumen(contenido: dict[str, Any], maximo: int = 80) -> str:
    partes = [f"{clave}={_valor_texto(valor)}" for clave, valor in contenido.items()]
    texto = ", ".join(partes)
    if len(texto) > maximo:
        texto = texto[: maximo - 3] + "..."
    return texto


def _limpiar(texto: str) -> str:
    for caracter in ("\n", ";", "{", "}", '"', "'", "<", ">"):
        texto = texto.replace(caracter, " ")
    return " ".join(texto.split())
