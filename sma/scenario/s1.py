"""Verificación de la Situación 1.

Cada comprobación se corresponde con un paso del flujo descrito en
``SITUACION.md``. Sirve tanto a los tests como al panel web.
"""

from __future__ import annotations

from typing import Any

from ..model import RedHospitalaria


def _tiene(modelo: RedHospitalaria, **filtros: Any) -> bool:
    for evento in modelo.traza.mensajes():
        if all(evento.get(clave) == valor for clave, valor in filtros.items()):
            return True
    return False


def verificar(modelo: RedHospitalaria) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def check(nombre: str, ok: bool, detalle: str = "") -> None:
        checks.append({"nombre": nombre, "ok": bool(ok), "detalle": detalle})

    riesgo = [
        e
        for e in modelo.traza.mensajes()
        if e["emisor"] == "inventario"
        and e["receptor"] == "coordinador"
        and e["contenido"].get("tipo") == "riesgo_desabastecimiento"
    ]
    check("1. Inventario detecta el riesgo y envía INFORM al Coordinador", bool(riesgo))

    check(
        "2. Inventario informa al Supervisor",
        _tiene(
            modelo,
            emisor="inventario",
            receptor="supervisor",
            performativa="inform",
        ),
    )

    proyeccion = [
        e
        for e in modelo.traza.mensajes()
        if e["emisor"] == "pronostico"
        and e["receptor"] == "coordinador"
        and e["contenido"].get("tipo") == "demanda_proyectada"
    ]
    check(
        "3. Pronóstico envía la demanda proyectada",
        bool(proyeccion),
        f"demanda={proyeccion[0]['contenido'].get('demanda_proyectada')}" if proyeccion else "",
    )

    check(
        "4. Coordinador consulta excedentes (QUERY-REF)",
        _tiene(
            modelo,
            emisor="coordinador",
            receptor="inventario",
            performativa="query-ref",
        ),
    )

    excedentes = [
        e
        for e in modelo.traza.mensajes()
        if e["emisor"] == "inventario"
        and e["contenido"].get("tipo") == "excedentes"
        and e["contenido"].get("total", 0) > 0
    ]
    check("5. Inventario responde con excedentes de la red", bool(excedentes))

    check(
        "6. Coordinador ejecuta el traslado sobre el entorno",
        any(e["accion"] == "traslado" for e in modelo.traza.entorno()),
    )

    check(
        "7. Coordinador decide traslado y compra",
        modelo.decision is not None
        and modelo.decision.get("traslado", 0) > 0
        and modelo.decision.get("faltante", 0) > 0,
    )

    check(
        "8. Coordinador envía REQUEST de compra a Compras",
        _tiene(
            modelo,
            emisor="coordinador",
            receptor="compras",
            performativa="request",
        ),
    )

    check(
        "9. Compras acepta con AGREE",
        _tiene(modelo, emisor="compras", receptor="coordinador", performativa="agree"),
    )

    check(
        "10. Compras alerta el retraso del Proveedor 1",
        any(
            e["contenido"].get("tipo") == "retraso_proveedor"
            and e["emisor"] == "compras"
            and e["receptor"] == "coordinador"
            for e in modelo.traza.mensajes()
        ),
    )

    check(
        "11. Coordinador pide comprar al Proveedor 2",
        any(
            e["performativa"] == "request"
            and e["contenido"].get("proveedor") == "P2"
            for e in modelo.traza.mensajes()
        ),
    )

    check(
        "12. Se genera la OrdenCompra",
        modelo.orden_actual is not None,
    )

    check(
        "13. La OrdenCompra queda confirmada",
        modelo.orden_actual is not None and modelo.orden_actual.estado == "confirmada",
    )

    check(
        "14. Supervisor registra los eventos",
        len(modelo.supervisor.registros) >= 3,
        f"eventos={len(modelo.supervisor.registros)}",
    )

    check(
        "15. Supervisor genera el reporte de cierre",
        modelo.supervisor.reporte is not None,
    )

    check(
        "16. La demanda proyectada queda cubierta",
        (modelo.metricas().get("cobertura_proyectada") or 0) >= 0.999,
    )

    return checks
