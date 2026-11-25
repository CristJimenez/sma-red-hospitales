"""Genera el diagrama de secuencia de la Situación 1 en formato draw.io.

El dibujo se construye a partir de la traza real (`out/s1_traza.json`), no de
una lista escrita a mano: cada mensaje ACL, cada auto-llamada y cada evento de
entorno salen de la ejecución. Si cambia una regla, se vuelve a generar y el
diagrama sigue cuadrando con la traza y con el Mermaid.

Uso:
    python -m sma.diagrama
"""

from __future__ import annotations

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TRAZA = RAIZ / "out" / "s1_traza.json"
SALIDA = RAIZ / "Diagrama.drawio"

ANCHO_CAJA = 140
ALTO_CAJA = 64
PASO = 200
CENTRO_0 = 130
Y_INICIAL = 180

PARTICIPANTES = (
    ("RED", "&lt;&lt;environment&gt;&gt;", "Red de hospitales públicos"),
    ("INV", "&lt;&lt;agent&gt;&gt;", "Agente de Inventario"),
    ("PRO", "&lt;&lt;agent&gt;&gt;", "Agente de Pronóstico"),
    ("COORD", "&lt;&lt;agent&gt;&gt;", "Agente Coordinador"),
    ("COMP", "&lt;&lt;agent&gt;&gt;", "Agente de Compras"),
    ("SUP", "&lt;&lt;agent&gt;&gt;", "Agente Supervisor"),
    ("P1", "&lt;&lt;object&gt;&gt;", "Proveedor 1<br>(habitual)"),
    ("P2", "&lt;&lt;object&gt;&gt;", "Proveedor 2<br>(alterno)"),
    ("OC", "&lt;&lt;object&gt;&gt;", "OrdenCompra"),
)

CENTROS = {pid: CENTRO_0 + i * PASO for i, (pid, _, _) in enumerate(PARTICIPANTES)}
IZQUIERDA = {pid: CENTROS[pid] - ANCHO_CAJA // 2 for pid in CENTROS}

AGENTE = {
    "inventario": "INV",
    "pronostico": "PRO",
    "coordinador": "COORD",
    "compras": "COMP",
    "supervisor": "SUP",
}

ENTORNO = {
    "coordinador": "COORD",
    "compras": "COMP",
    "proveedor_2": "P2",
    "entorno": "RED",
    "orden_compra": "OC",
}

ESTILO_ACL = (
    "endArrow=classic;html=1;rounded=0;verticalAlign=bottom;"
    "labelBackgroundColor=#ffffff;fontSize=10;strokeColor=#1a1a1a;"
)
ESTILO_RET = (
    "endArrow=open;endFill=0;dashed=1;html=1;rounded=0;verticalAlign=bottom;"
    "labelBackgroundColor=#ffffff;fontSize=10;strokeColor=#666666;"
)
ESTILO_VAR = (
    "endArrow=classic;html=1;rounded=0;verticalAlign=bottom;"
    "labelBackgroundColor=#ffffff;fontSize=10;strokeColor=#999999;"
    "fontColor=#666666;dashed=1;"
)


def xml(texto: str) -> str:
    """Escapa para atributo XML. El valor se interpreta luego como HTML."""
    return (
        texto.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _lineas(etiqueta: str) -> int:
    return etiqueta.count("<br>") + 1


# --------------------------------------------------------------------------
# Formato del contenido de los mensajes
# --------------------------------------------------------------------------

def fmt_mensaje(c: dict) -> str:
    if "consulta" in c:
        if c["consulta"] == "excedentes":
            excluir = ", ".join(c.get("excluir", []))
            return f"excedentes({c['medicamento']}, excluir={excluir})"
        if c["consulta"] == "orden_confirmada":
            return f"orden_confirmada({c['orden']})"
    tipo = c.get("tipo", "")
    if tipo == "riesgo_desabastecimiento":
        return (
            f"riesgo_desabastecimiento({c['hospital']}, {c['medicamento']})<br>"
            f"stock={c['stock']}, umbral={c['umbral']:g}, "
            f"consumo={c['consumo_diario']:g}/día, "
            f"agotamiento={c['dias_hasta_agotamiento']:g} d"
        )
    if tipo == "informe_inventario":
        return (
            f"informe_inventario({c['hospital']}, {c['medicamento']})<br>"
            f"nivel={c['nivel']}"
        )
    if tipo == "demanda_proyectada":
        return (
            f"demanda_proyectada({c['demanda_proyectada']} uds / "
            f"{c['horizonte_dias']} d)<br>"
            f"tendencia={c['tendencia']}, MAPE={c['mape'] * 100:.2f} %"
        )
    if tipo == "excedentes":
        partes = [f"{h}={v['cantidad']}" for h, v in c["excedentes"].items()]
        return "excedentes(" + ", ".join(partes) + f", total={c['total']})"
    if tipo == "decision":
        compra = c.get("compra_prevista") or {}
        return (
            f"decision(traslado={c['traslado']}, faltante={c['faltante']})<br>"
            f"compra={compra.get('proveedor', '—')} "
            f"{compra.get('cantidad', 0)} uds / "
            f"{compra.get('coste', 0):g} €, "
            f"residual={c['riesgo_residual']}"
        )
    if tipo == "comprar":
        return (
            f"comprar({c['medicamento']}, {c['cantidad']}, {c['hospital']})<br>"
            f"presupuesto={c['presupuesto_autorizado']:g}"
        )
    if tipo == "gestion_compra":
        return f"gestion_compra({c.get('cantidad', 0)} uds)"
    if tipo == "retraso_proveedor":
        if "oferta" in c:
            of = c["oferta"]
            return (
                f"retraso_proveedor({c['proveedor_retrasado']}, "
                f"{c['retraso_dias']} d)<br>"
                f"oferta {of['proveedor']}: {of['precio_unitario']:g} €/ud, "
                f"plazo {of['plazo_dias']} d"
            )
        return f"retraso_proveedor({c['proveedor']}, {c['retraso_dias']} d)"
    if tipo == "comprar_a_proveedor":
        return (
            f"comprar_a_proveedor({c['proveedor']}, {c['cantidad']})<br>"
            f"presupuesto={c['presupuesto_autorizado']:g}"
        )
    if tipo == "orden_generada":
        o = c["orden"]
        return (
            f"orden_generada({o['orden']})<br>"
            f"{o['cantidad']} uds, {o['proveedor']}, {o['coste']:g} €, "
            f"{o['estado']}"
        )
    if tipo == "orden_confirmada":
        return (
            f"orden_confirmada({c['orden']['orden']}, "
            f"{str(c['confirmada']).lower()})"
        )
    if tipo == "cierre":
        return (
            f"cierre(resultado={c['resultado']})<br>"
            f"riesgos_atendidos={c['riesgos_atendidos']}"
        )
    return tipo + "(" + ", ".join(f"{k}={v}" for k, v in c.items()) + ")"


def fmt_accion(accion: str, d: dict) -> str:
    if accion == "generarEventoRiesgo":
        return f"generarEventoRiesgo({d['hospital']})"
    if accion == "calcularProyeccion":
        return f"calcularProyeccion({d['medicamento']})"
    if accion == "actualizarModelo":
        return f"actualizarModelo(MAPE {d['mape'] * 100:.2f} %)"
    if accion == "analizarEventos":
        return (
            f"analizarEventos({d['riesgo']['hospital']}, "
            f"{d['demanda_proyectada']})"
        )
    if accion == "decidirTrasladoOCompra":
        return (
            f"decidirTrasladoOCompra({d['necesidad']}, "
            f"{d['traslado']}, {d['faltante']})"
        )
    if accion == "enviarRequest":
        extra = f", {d['proveedor']}" if "proveedor" in d else ""
        return f"enviarRequest({d['destinatario']}{extra}, {d['cantidad']})"
    if accion == "recibirAgree":
        return f"recibirAgree({d['conversation_id']})"
    if accion == "compararOfertas":
        return f"compararOfertas() → elige {d['elegido']}"
    if accion == "alertarRetraso":
        return f"alertarRetraso({d['proveedor']}, {d['retraso_dias']} d)"
    if accion == "generarOrdenCompra":
        return f"generarOrdenCompra({d['orden']})"
    if accion == "solicitarConfirmacion":
        return f"solicitarConfirmacion({d['orden']})"
    if accion == "confirmarOrden":
        return f"confirmarOrden({d['orden']})"
    if accion == "verificarAcciones":
        return f"verificarAcciones({d['orden']['orden']}, confirmada)"
    if accion == "registrarEvento":
        return f"registrarEvento({d['evento']})"
    if accion == "generarReporte":
        return f"generarReporte({d['hospital']})"
    return accion + "()"


# --------------------------------------------------------------------------
# Construcción de la secuencia de dibujo
# --------------------------------------------------------------------------

def items_desde_traza(eventos: list[dict]) -> list[dict]:
    """Convierte los eventos de la traza en filas dibujables."""
    items: list[dict] = []

    def msg(src, dst, etiqueta, estilo="acl", seq=None):
        prefijo = f"[{seq}] " if seq is not None else ""
        items.append(
            {
                "k": "msg",
                "src": src,
                "dst": dst,
                "label": prefijo + etiqueta,
                "estilo": estilo,
            }
        )

    def auto(part, etiqueta):
        items.append({"k": "self", "part": part, "label": etiqueta})

    def frag(op, frame, guard=None):
        items.append({"k": "frag", "op": op, "frame": frame, "guard": guard})

    for ev in eventos:
        orden = ev["orden"]
        tipo = ev["tipo"]

        if orden == 1:
            # La lectura inicial del inventario no se registra como acción en
            # la traza (el agente ya tiene el dato), pero el original la
            # mostraba y explica de dónde sale el riesgo.
            msg("INV", "RED", "leerRegistros(amoxicilina)")
            msg(
                "RED",
                "INV",
                "stock, umbral, consumo, lotes por vencer",
                estilo="ret",
            )
            frag("start", "par")
        if orden == 18:
            frag("start", "alt", "[Compras acepta el REQUEST]")
        if orden == 22:
            frag("start", "opt", "[retraso del proveedor habitual > plazo]")
        if orden == 30:
            frag("start", "alt", "[oferta viable y dentro del presupuesto]")

        if tipo == "mensaje":
            perf = ev["performativa"].upper()
            etiqueta = (
                f"&lt;&lt;ACL:{perf}&gt;&gt;<br>" + fmt_mensaje(ev["contenido"])
            )
            msg(
                AGENTE[ev["emisor"]],
                AGENTE[ev["receptor"]],
                etiqueta,
                seq=ev["seq"],
            )

        elif tipo == "accion":
            accion = ev["accion"]
            detalle = ev.get("detalle", {})
            part = AGENTE[ev["agente"]]

            if accion == "leerRegistros":
                modo = detalle.get("modo", "normal")
                msg(
                    part,
                    "RED",
                    f"leerRegistros({detalle.get('medicamento', '')}, "
                    f"modo={modo})",
                )
                msg("RED", part, "excedentes de la red", estilo="ret")

            elif accion == "consultarProveedor":
                proveedor = detalle["proveedor"]
                msg(
                    "COMP",
                    proveedor,
                    f"consultarProveedor({detalle['medicamento']})",
                )
                msg(
                    proveedor,
                    "COMP",
                    f"precio={detalle['precio']:g} €/ud, "
                    f"entrega={detalle['tiempo_entrega_dias']} d, "
                    f"retraso={detalle['retraso_dias']} d",
                    estilo="ret",
                )

            else:
                auto(part, fmt_accion(accion, detalle))

        elif tipo == "entorno":
            accion = ev["accion"]
            detalle = ev.get("detalle", {})
            origen = ENTORNO[ev["origen"]]
            destino = ENTORNO[ev["destino"]]

            if accion == "traslado":
                msg(
                    origen,
                    destino,
                    f"traslado({detalle['origen']} → {detalle['destino']}, "
                    f"{detalle['cantidad']} uds)",
                )
            elif accion == "crear_orden":
                msg(
                    origen,
                    destino,
                    f"crear_orden({detalle['orden']}, {detalle['cantidad']} uds, "
                    f"{detalle['proveedor']}, {detalle['coste']:g} €)",
                )
            elif accion == "enviar_orden":
                msg(
                    origen,
                    destino,
                    f"enviar_orden({detalle['cantidad']} uds)",
                )
            elif accion == "confirmacion_recepcion":
                msg(
                    origen,
                    destino,
                    f"confirmacion_recepcion({detalle['proveedor']})",
                    estilo="ret",
                )

        # Cierres de fragmento
        if orden == 3:
            frag("div", "par")
        if orden == 6:
            frag("end", "par")
        if orden == 18:
            frag("div", "alt", "[Compras no puede gestionarla]")
            msg(
                "COMP",
                "COORD",
                "&lt;&lt;ACL:FAILURE&gt;&gt;<br>no_puede_gestionar "
                "(variante compras_no_puede)",
                estilo="var",
            )
            frag("end", "alt")
        if orden == 24:
            frag("end", "opt")
        if orden == 34:
            frag("div", "alt", "[sin proveedor viable / presupuesto insuficiente]")
            msg(
                "COMP",
                "COORD",
                "&lt;&lt;ACL:FAILURE&gt;&gt;<br>sin_proveedor_viable "
                "(variante presupuesto_insuficiente)",
                estilo="var",
            )
            frag("end", "alt")

    return items


# --------------------------------------------------------------------------
# Render XML
# --------------------------------------------------------------------------

def _alto(item: dict) -> int:
    if item["k"] == "msg":
        # La etiqueta va encima de la flecha: ocupa espacio antes de la línea.
        return 13 * _lineas(item["label"]) + 18
    if item["k"] == "self":
        return 34
    if item["k"] == "frag":
        return {"start": 26, "div": 20, "end": 14}[item["op"]]
    return 20


def _celda_mensaje(item: dict, idx: int) -> str:
    x1 = CENTROS[item["src"]]
    x2 = CENTROS[item["dst"]]
    estilo = {
        "acl": ESTILO_ACL,
        "ret": ESTILO_RET,
        "var": ESTILO_VAR,
    }[item["estilo"]]
    y = item["line_y"]
    return (
        f'<mxCell id="m{idx}" edge="1" parent="1" style="{estilo}" '
        f'value="{xml(item["label"])}">\n'
        f"  <mxGeometry relative=\"1\" as=\"geometry\">\n"
        f'    <mxPoint x="{x1}" y="{y}" as="sourcePoint"/>\n'
        f'    <mxPoint x="{x2}" y="{y}" as="targetPoint"/>\n'
        f"  </mxGeometry>\n"
        f"</mxCell>"
    )


def _celda_auto(item: dict, idx: int) -> tuple[str, str]:
    x = CENTROS[item["part"]]
    y = item["line_y"]
    dx = 34
    dy = 22
    celda = (
        f'<mxCell id="s{idx}" edge="1" parent="1" '
        f'style="endArrow=classic;html=1;rounded=0;strokeColor=#1a1a1a;" '
        f'value="">\n'
        f'  <mxGeometry relative="1" as="geometry">\n'
        f'    <Array as="points">\n'
        f'      <mxPoint x="{x + dx}" y="{y}"/>\n'
        f'      <mxPoint x="{x + dx}" y="{y + dy}"/>\n'
        f"    </Array>\n"
        f'    <mxPoint x="{x}" y="{y}" as="sourcePoint"/>\n'
        f'    <mxPoint x="{x}" y="{y + dy}" as="targetPoint"/>\n'
        f"  </mxGeometry>\n"
        f"</mxCell>"
    )
    texto = (
        f'<mxCell id="t{idx}" parent="1" '
        f'style="text;html=1;align=left;verticalAlign=middle;strokeColor=none;'
        f'fillColor=none;fontSize=10;fontStyle=2;" '
        f'value="{xml(item["label"])}" vertex="1">\n'
        f'  <mxGeometry x="{x + dx + 6}" y="{y + 1}" width="230" height="20" '
        f'as="geometry"/>\n'
        f"</mxCell>"
    )
    return celda, texto


def generar(traza: dict) -> str:
    eventos = traza["eventos"]
    items = items_desde_traza(eventos)

    y = Y_INICIAL
    for item in items:
        item["y"] = y
        alto = _alto(item)
        if item["k"] == "frag" and item["op"] in ("start", "div"):
            if item.get("guard"):
                alto += 16
        item["h"] = alto
        if item["k"] == "msg":
            item["line_y"] = y + 13 * _lineas(item["label"])
        else:
            item["line_y"] = y
        y += alto
    altura_total = y + 60

    # Cajas de participante y líneas de vida
    cabeceras: list[str] = []
    vidas: list[str] = []
    for pid, estereotipo, nombre in PARTICIPANTES:
        cx = CENTROS[pid]
        cabeceras.append(
            f'<mxCell id="p{pid}" parent="1" vertex="1" '
            f'style="rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;'
            f'strokeColor=#666666;fontSize=11;" '
            f'value="{xml(estereotipo + "<br>" + nombre)}">\n'
            f'  <mxGeometry x="{IZQUIERDA[pid]}" y="40" '
            f'width="{ANCHO_CAJA}" height="{ALTO_CAJA}" as="geometry"/>\n'
            f"</mxCell>"
        )
        vidas.append(
            f'<mxCell id="l{pid}" edge="1" parent="1" '
            f'style="endArrow=none;dashed=1;html=1;strokeColor=#999999;'
            f'dashPattern=6 4;" value="">\n'
            f'  <mxGeometry relative="1" as="geometry">\n'
            f'    <mxPoint x="{cx}" y="{40 + ALTO_CAJA}" as="sourcePoint"/>\n'
            f'    <mxPoint x="{cx}" y="{altura_total - 30}" as="targetPoint"/>\n'
            f"  </mxGeometry>\n"
            f"</mxCell>"
        )

    # Fragmentos: se dibujan antes que los mensajes para quedar detrás.
    # El ancho se calcula con los participantes que realmente aparecen dentro.
    marcos: list[str] = []
    abiertos: list[dict] = []
    for idx, item in enumerate(items):
        if item["k"] != "frag":
            continue
        if item["op"] == "start":
            abiertos.append(
                {
                    "frame": item["frame"],
                    "guard": item.get("guard"),
                    "top": item["y"] - 6,
                    "div": None,
                    "inicio": idx,
                }
            )
        elif item["op"] == "div":
            if abiertos:
                abiertos[-1]["div"] = item["y"]
                abiertos[-1]["div_guard"] = item.get("guard")
        elif item["op"] == "end":
            if not abiertos:
                continue
            f = abiertos.pop()
            bottom = item["y"] + 8

            centros: list[int] = []
            for dentro in items[f["inicio"]:idx]:
                if dentro["k"] == "msg":
                    centros += [CENTROS[dentro["src"]], CENTROS[dentro["dst"]]]
                elif dentro["k"] == "self":
                    centros.append(CENTROS[dentro["part"]])
            x0 = min(centros) - ANCHO_CAJA // 2 - 10
            x1 = max(centros) + ANCHO_CAJA // 2 + 10
            ancho = x1 - x0
            alto = bottom - f["top"]
            marcos.append(
                f'<mxCell id="f{len(marcos) + 1}" parent="1" vertex="1" '
                f'style="shape=umlFrame;whiteSpace=wrap;html=1;pointerEvents=0;'
                f'fillColor=none;strokeColor=#333333;fontSize=11;fontStyle=1;" '
                f'value="{f["frame"]}">\n'
                f'  <mxGeometry x="{x0}" y="{f["top"]}" width="{ancho}" '
                f'height="{alto}" as="geometry"/>\n'
                f"</mxCell>"
            )
            if f["guard"]:
                marcos.append(
                    f'<mxCell id="g{len(marcos) + 1}" parent="1" vertex="1" '
                    f'style="text;html=1;align=left;verticalAlign=top;'
                    f'strokeColor=none;fillColor=none;fontSize=10;fontStyle=1;" '
                    f'value="{xml(f["guard"])}">\n'
                    f'  <mxGeometry x="{x0 + 58}" y="{f["top"] + 4}" '
                    f'width="{ancho - 64}" height="18" as="geometry"/>\n'
                    f"</mxCell>"
                )
            if f["div"] is not None:
                marcos.append(
                    f'<mxCell id="d{len(marcos) + 1}" edge="1" parent="1" '
                    f'style="endArrow=none;dashed=1;html=1;strokeColor=#333333;" '
                    f'value="">\n'
                    f'  <mxGeometry relative="1" as="geometry">\n'
                    f'    <mxPoint x="{x0}" y="{f["div"]}" as="sourcePoint"/>\n'
                    f'    <mxPoint x="{x1}" y="{f["div"]}" as="targetPoint"/>\n'
                    f"  </mxGeometry>\n"
                    f"</mxCell>"
                )
                if f.get("div_guard"):
                    marcos.append(
                        f'<mxCell id="e{len(marcos) + 1}" parent="1" vertex="1" '
                        f'style="text;html=1;align=left;verticalAlign=top;'
                        f'strokeColor=none;fillColor=none;fontSize=10;" '
                        f'value="{xml(f["div_guard"])}">\n'
                        f'  <mxGeometry x="{x0 + 10}" y="{f["div"] + 3}" '
                        f'width="{ancho - 20}" height="18" as="geometry"/>\n'
                        f"</mxCell>"
                    )

    mensajes: list[str] = []
    textos: list[str] = []
    for idx, item in enumerate(items, start=1):
        if item["k"] == "msg":
            mensajes.append(_celda_mensaje(item, idx))
        elif item["k"] == "self":
            celda, texto = _celda_auto(item, idx)
            mensajes.append(celda)
            textos.append(texto)

    ancho_pagina = IZQUIERDA["OC"] + ANCHO_CAJA + 70
    titulo = (
        f'<mxCell id="titulo" parent="1" vertex="1" '
        f'style="text;html=1;align=left;verticalAlign=middle;strokeColor=none;'
        f'fillColor=none;fontSize=13;fontStyle=1;" '
        f'value="{xml("Situación 1 · brote respiratorio · ejecución base · 11 rondas · 15 mensajes ACL (numerados)")}">\n'
        f'  <mxGeometry x="40" y="6" width="1200" height="26" as="geometry"/>\n'
        f"</mxCell>"
    )

    cuerpo = "\n".join(
        cabeceras + vidas + marcos + mensajes + textos + [titulo]
    )
    return (
        '<mxfile host="app.diagrams.net">\n'
        '  <diagram id="s1-secuencia" name="Situación 1">\n'
        f'    <mxGraphModel grid="1" page="1" gridSize="10" guides="1" '
        f'tooltips="1" connect="1" arrows="1" fold="1" pageScale="1" '
        f'pageWidth="{ancho_pagina}" pageHeight="{altura_total}" '
        f'background="none" math="0" shadow="0">\n'
        "      <root>\n"
        '        <mxCell id="0"/>\n'
        '        <mxCell id="1" parent="0"/>\n'
        f"{cuerpo}\n"
        "      </root>\n"
        "    </mxGraphModel>\n"
        "  </diagram>\n"
        "</mxfile>\n"
    )


def main() -> None:
    traza = json.loads(TRAZA.read_text(encoding="utf-8"))
    SALIDA.write_text(generar(traza), encoding="utf-8")
    print(f"Diagrama generado: {SALIDA}")


if __name__ == "__main__":
    main()
