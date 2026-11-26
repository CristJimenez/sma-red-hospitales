"""Verificación de la Situación 2.

Cada comprobación se corresponde con un paso de ``SITUACION2.md``. La usan los
tests y el panel web; el escenario base es la rama de timeout del Pronóstico.
"""

from __future__ import annotations

from typing import Any

from ..model_s2 import RedHospitalariaS2


def _tiene(modelo: RedHospitalariaS2, **filtros: Any) -> bool:
    for evento in modelo.traza.mensajes():
        if all(evento.get(clave) == valor for clave, valor in filtros.items()):
            return True
    return False


def _mensaje(
    modelo: RedHospitalariaS2,
    emisor: str,
    receptor: str,
    tipo: str,
    performativa: str | None = None,
) -> dict[str, Any] | None:
    for evento in modelo.traza.mensajes():
        if (
            evento.get("emisor") == emisor
            and evento.get("receptor") == receptor
            and evento.get("contenido", {}).get("tipo") == tipo
            and (performativa is None or evento.get("performativa") == performativa)
        ):
            return evento
    return None


def verificar_s2(modelo: RedHospitalariaS2) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def check(nombre: str, ok: bool, detalle: str = "") -> None:
        checks.append({"nombre": nombre, "ok": bool(ok), "detalle": detalle})

    acciones = [evento["accion"] for evento in modelo.traza.acciones()]

    check(
        "1. Inventario lee registros y detecta el lote próximo a vencer",
        "generarEventoRiesgo" in acciones and "leerRegistros" in acciones,
    )

    riesgo = _mensaje(
        modelo, "inventario", "coordinador", "riesgo_vencimiento", "inform"
    )
    check(
        "2. Inventario informa el riesgo de vencimiento al Coordinador",
        riesgo is not None,
        f"lote={riesgo['contenido'].get('lote')}" if riesgo else "",
    )

    check(
        "3. Inventario informa al Supervisor",
        _mensaje(modelo, "inventario", "supervisor", "informe_inventario", "inform")
        is not None,
    )

    check(
        "4. Coordinador consulta la demanda de A y B (QUERY-REF)",
        _tiene(
            modelo,
            emisor="coordinador",
            receptor="pronostico",
            performativa="query-ref",
        ),
    )

    check(
        "5. Supervisor detecta el timeout del Pronóstico",
        "detectarTimeout" in acciones and modelo.timeout_pronostico,
    )

    check(
        "6. Supervisor notifica el fallo al Coordinador",
        _mensaje(modelo, "supervisor", "coordinador", "fallo_detectado", "inform")
        is not None,
    )

    check(
        "7. Supervisor solicita el reinicio del Pronóstico (REQUEST)",
        _tiene(
            modelo,
            emisor="supervisor",
            receptor="pronostico",
            performativa="request",
        ),
    )

    check(
        "8. Coordinador usa la última estimación o el historial",
        "usarUltimaEstimacion" in acciones
        and _mensaje(modelo, "coordinador", "supervisor", "decision", "inform")
        is not None,
    )

    check(
        "9. Pronóstico acepta el reinicio (AGREE)",
        _tiene(
            modelo,
            emisor="pronostico",
            receptor="supervisor",
            performativa="agree",
        ),
    )

    check(
        "10. Pronóstico informa el reinicio completado",
        _mensaje(
            modelo, "pronostico", "supervisor", "reinicio_completado", "inform"
        )
        is not None,
    )

    check(
        "11. Coordinador consulta el stock de A y B (QUERY-REF)",
        _tiene(
            modelo,
            emisor="coordinador",
            receptor="inventario",
            performativa="query-ref",
        ),
    )

    check(
        "12. Inventario responde con el stock de ambos hospitales",
        _mensaje(modelo, "inventario", "coordinador", "stock", "inform")
        is not None,
    )

    decision = next(
        (
            evento
            for evento in modelo.traza.mensajes()
            if evento.get("emisor") == "coordinador"
            and evento.get("receptor") == "supervisor"
            and evento.get("contenido", {}).get("tipo") == "decision"
            and evento.get("contenido", {}).get("accion") == "traslado"
        ),
        None,
    )
    check(
        "13. Coordinador informa la decisión de traslado al Supervisor",
        decision is not None,
    )

    check(
        "14. Coordinador pide preparar el traslado (REQUEST)",
        _tiene(
            modelo,
            emisor="coordinador",
            receptor="inventario",
            performativa="request",
        ),
    )

    check(
        "15. Inventario acepta y ejecuta el traslado sobre el entorno",
        _tiene(
            modelo,
            emisor="inventario",
            receptor="coordinador",
            performativa="agree",
        )
        and any(
            evento["accion"] == "traslado_lote" for evento in modelo.traza.entorno()
        ),
    )

    check(
        "16. Inventario confirma el traslado realizado",
        _mensaje(
            modelo, "inventario", "coordinador", "traslado_realizado", "inform"
        )
        is not None,
    )

    check(
        "17. El lote queda asignado a un único hospital",
        modelo.lote_asignado in ("H_A", "H_B")
        and modelo.lote.hospital_id == modelo.lote_asignado
        and modelo.config.hospitales[modelo.hospital_origen].stock(
            modelo.medicamento
        )
        == 0,
        f"asignado={modelo.lote_asignado}",
    )

    check(
        "18. El otro hospital queda en lista de espera con riesgo residual",
        modelo.lista_espera in ("H_A", "H_B")
        and modelo.lista_espera != modelo.lote_asignado
        and modelo.riesgo_residual > 0,
        f"lista_espera={modelo.lista_espera}, residual={modelo.riesgo_residual}",
    )

    check(
        "19. Supervisor genera el reporte de cierre",
        modelo.supervisor.reporte is not None,
    )

    return checks
