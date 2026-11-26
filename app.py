"""Panel web del SMA de abastecimiento hospitalario.

Permite cambiar entre la Situación 1 (brote respiratorio) y la Situación 2
(lote próximo a vencer, competencia A/B y falla del Pronóstico). Todo lo que se
muestra sale de la traza real; el diagrama Mermaid se descarga desde ella.
"""

from __future__ import annotations

import importlib
import json
import sys

import pandas as pd
import streamlit as st


def _importar_sma() -> dict[str, object]:
    """Importa el paquete ``sma`` descartando copias viejas en memoria.

    Streamlit recarga ``app.py`` en caliente al desplegar y conserva en
    ``sys.modules`` la versión anterior del paquete. Si el archivo nuevo pide
    símbolos que el módulo viejo no tiene, hay que limpiar y releer del disco.
    """
    modulos = {
        "sma.run": ("ejecutar", "ejecutar_s2"),
        "sma.scenario.s1": ("verificar",),
        "sma.scenario.s2": ("verificar_s2",),
        "sma.variantes": ("cargar_variante", "listar_variantes"),
        "sma.variantes_s2": ("cargar_variante_s2", "listar_variantes_s2"),
    }

    def cargar() -> dict[str, object]:
        return {
            nombre: importlib.import_module(nombre) for nombre in modulos
        }

    def completo(cargados: dict[str, object]) -> bool:
        return all(
            hasattr(cargados[nombre], atributo)
            for nombre, atributos in modulos.items()
            for atributo in atributos
        )

    cargados = cargar()
    if not completo(cargados):
        for clave in [m for m in list(sys.modules) if m == "sma" or m.startswith("sma.")]:
            del sys.modules[clave]
        cargados = cargar()
    return cargados


_modulos = _importar_sma()
_run = _modulos["sma.run"]
_s1 = _modulos["sma.scenario.s1"]
_s2 = _modulos["sma.scenario.s2"]
_v1 = _modulos["sma.variantes"]
_v2 = _modulos["sma.variantes_s2"]

ejecutar, ejecutar_s2 = _run.ejecutar, _run.ejecutar_s2
verificar, verificar_s2 = _s1.verificar, _s2.verificar_s2
cargar_variante, listar_variantes = _v1.cargar_variante, _v1.listar_variantes
cargar_variante_s2, listar_variantes_s2 = (
    _v2.cargar_variante_s2,
    _v2.listar_variantes_s2,
)

st.set_page_config(
    page_title="SMA Red de Hospitales",
    page_icon="🏥",
    layout="wide",
)

FASES_S1 = {
    1: "A/B · percepción",
    2: "C · análisis",
    3: "C · excedentes",
    4: "C · decisión",
    5: "D · compra",
    6: "D · proveedor alterno",
    7: "D · orden",
    8: "E · confirmación",
    9: "E · confirmación",
    10: "E · cierre",
    11: "E · reporte",
}

FASES_S2 = {
    1: "A · detección",
    2: "B · consulta",
    3: "B · timeout",
    4: "B/C · sustituto y stock",
    5: "C/D · stock y reinicio",
    6: "C · decisión",
    7: "C · traslado",
    8: "C · cierre",
    9: "E · reporte",
    10: "E · escalado",
    11: "E · reporte",
}

VARIANTES_S1 = listar_variantes()
VARIANTES_S2 = listar_variantes_s2()


@st.cache_data(show_spinner=False)
def correr_s1(nombre: str) -> dict:
    variante = cargar_variante(nombre)
    modelo = ejecutar(variante.configuracion(), max_rondas=24)
    metricas = modelo.metricas()
    real = {
        "accion": metricas["accion"],
        "traslado": metricas["traslado_recibido"],
        "compra": metricas["cantidad_comprada"],
        "proveedor": modelo.orden_actual.proveedor_id if modelo.orden_actual else None,
        "orden": modelo.orden_actual is not None,
        "resultado": metricas["resultado"],
        "riesgo_residual": metricas["riesgo_residual"],
        "decisiones": len(modelo.decisiones),
        "ordenes": len(modelo.ordenes),
        "donantes": modelo.decisiones[0].get("donantes") if modelo.decisiones else None,
    }
    return {
        "metricas": metricas,
        "checks": verificar(modelo) if nombre == "base" else [],
        "eventos": modelo.traza.eventos,
        "mermaid": modelo.traza.a_mermaid(),
        "decision": modelo.decision,
        "esperado": variante.esperado,
        "real": real,
        "titulo": variante.titulo,
        "descripcion": variante.descripcion,
        "resultado": modelo.resultado,
    }


@st.cache_data(show_spinner=False)
def correr_s2(nombre: str) -> dict:
    variante = cargar_variante_s2(nombre)
    modelo = ejecutar_s2(variante.configuracion(), max_rondas=24)
    metricas = modelo.metricas()
    real = {
        "resultado": metricas["resultado"],
        "lote_asignado": metricas["lote_asignado"],
        "reasignaciones": metricas["reasignaciones"],
        "timeout": metricas["timeout_pronostico"],
        "reinicio": metricas["reinicio"],
        "fuente_demanda": metricas["fuente_demanda"],
        "lista_espera": metricas["lista_espera"],
        "riesgo_residual": metricas["riesgo_residual"],
        "escalado": metricas["escalado"],
    }
    return {
        "metricas": metricas,
        "checks": verificar_s2(modelo) if nombre == "s2_base" else [],
        "eventos": modelo.traza.eventos,
        "mermaid": modelo.traza.a_mermaid(),
        "decision": modelo.decision,
        "esperado": variante.esperado,
        "real": real,
        "titulo": variante.titulo,
        "descripcion": variante.descripcion,
        "resultado": modelo.resultado,
    }


def resumen(contenido: dict, maximo: int = 80) -> str:
    partes = [f"{clave}={valor}" for clave, valor in contenido.items()]
    texto = ", ".join(partes)
    return texto[: maximo - 3] + "..." if len(texto) > maximo else texto


def tabla_eventos(eventos: list[dict], fases: dict[int, str]) -> pd.DataFrame:
    filas = []
    for evento in eventos:
        if evento["tipo"] == "mensaje":
            filas.append(
                {
                    "Ronda": evento["ronda"],
                    "Fase": fases.get(evento["ronda"], ""),
                    "Tipo": "ACL",
                    "De": evento["emisor"],
                    "Para": evento["receptor"],
                    "Acción": evento["performativa"].upper(),
                    "Detalle": resumen(evento["contenido"]),
                }
            )
        elif evento["tipo"] == "entorno":
            filas.append(
                {
                    "Ronda": evento["ronda"],
                    "Fase": fases.get(evento["ronda"], ""),
                    "Tipo": "Entorno",
                    "De": evento.get("origen") or "—",
                    "Para": evento.get("destino") or "—",
                    "Acción": evento["accion"],
                    "Detalle": resumen(evento["detalle"]),
                }
            )
        else:
            filas.append(
                {
                    "Ronda": evento["ronda"],
                    "Fase": fases.get(evento["ronda"], ""),
                    "Tipo": "Acción",
                    "De": evento["agente"],
                    "Para": "",
                    "Acción": evento["accion"],
                    "Detalle": resumen(evento["detalle"]),
                }
            )
    return pd.DataFrame(filas)


def tabla_verificacion(checks: list[dict]) -> None:
    st.subheader("Pasos del escenario base")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "": "✅" if check["ok"] else "❌",
                    "Paso": check["nombre"],
                    "Detalle": check["detalle"],
                }
                for check in checks
            ]
        ),
        hide_index=True,
        height=560,
    )


def tabla_esperado(esperado: dict, real: dict) -> None:
    st.subheader("Esperado vs. real")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "": "✅" if real.get(clave) == valor else "❌",
                    "Métrica": clave,
                    "Esperado": valor,
                    "Real": real.get(clave),
                }
                for clave, valor in esperado.items()
            ]
        ),
        hide_index=True,
    )


def descargas(nombre: str, resultado: dict) -> None:
    st.subheader("Descargas")
    st.caption(
        "El diagrama de secuencia sale de esta misma traza. En la Situación 2 "
        "no lleva numeración, igual que el diagrama del informe."
    )
    st.download_button(
        "Descargar diagrama (.mmd)",
        resultado["mermaid"],
        file_name=f"{nombre}_secuencia.mmd",
        mime="text/plain",
    )
    st.download_button(
        "Descargar traza completa (.json)",
        json.dumps({"eventos": resultado["eventos"]}, ensure_ascii=False, indent=2),
        file_name=f"{nombre}_traza.json",
        mime="application/json",
    )


st.title("SMA de abastecimiento de medicamentos")
st.caption(
    "Red de hospitales públicos · Mesa 3 + capa FIPA-ACL · "
    "todos los datos salen de la traza real de la ejecución."
)

with st.sidebar:
    st.header("Escenario")
    situacion = st.radio(
        "Situación",
        ["Situación 1", "Situación 2"],
        captions=[
            "Brote respiratorio: traslado y compra.",
            "Lote por vencer: competencia A/B y timeout.",
        ],
    )
    if situacion == "Situación 1":
        variantes = VARIANTES_S1
        nombre = st.selectbox(
            "Variante",
            options=list(variantes),
            format_func=lambda clave: variantes[clave].titulo,
        )
    else:
        variantes = VARIANTES_S2
        nombre = st.selectbox(
            "Variante",
            options=list(variantes),
            format_func=lambda clave: variantes[clave].titulo,
        )
    variante = variantes[nombre]
    st.markdown(variante.descripcion)
    st.divider()
    if st.button("Re-ejecutar", type="primary"):
        st.cache_data.clear()
        st.rerun()
    st.caption("Semilla fija: cada ejecución produce exactamente la misma traza.")

if situacion == "Situación 1":
    resultado = correr_s1(nombre)
    metricas = resultado["metricas"]
    real = resultado["real"]
    esperado = resultado["esperado"]
    checks = resultado["checks"]
    cumple = all(real.get(clave) == valor for clave, valor in esperado.items())

    columnas = st.columns(6)
    columnas[0].metric("Variante", "OK" if cumple else "Revisar")
    columnas[1].metric("Cobertura", f"{metricas['cobertura_proyectada'] * 100:.0f}%")
    columnas[2].metric("Traslado", f"{metricas['traslado_recibido']} uds")
    columnas[3].metric("Compra", f"{metricas['cantidad_comprada']} uds")
    columnas[4].metric("Coste", f"{metricas['coste_compra']:.2f} €")
    columnas[5].metric("Riesgo residual", f"{metricas['riesgo_residual']} uds")

    if resultado["resultado"] == "exito":
        st.success(
            f"Resultado **{resultado['resultado']}** · acción `{metricas['accion']}` · "
            f"{metricas['rondas']} rondas · {metricas['mensajes']} mensajes ACL."
        )
    elif resultado["resultado"] == "sin_riesgo":
        st.info("No se detectó riesgo: el sistema no genera órdenes.")
    else:
        st.warning(
            f"Resultado **{resultado['resultado']}** · acción `{metricas['accion']}` · "
            f"riesgo residual {metricas['riesgo_residual']} uds."
        )

    pestanas = st.tabs(["Secuencia", "Verificación", "Matriz de casos", "Traza"])

    with pestanas[0]:
        st.subheader("Rondas de comunicación")
        st.dataframe(
            tabla_eventos(resultado["eventos"], FASES_S1),
            hide_index=True,
            height=540,
        )

    with pestanas[1]:
        if checks:
            tabla_verificacion(checks)
        else:
            tabla_esperado(esperado, real)

    with pestanas[2]:
        st.subheader("Todos los 'y si' del escenario")
        st.caption(
            "Cada fila es una variante declarativa sobre `config/s1.yaml`. "
            "El selector de la izquierda la ejecuta."
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Variante": clave,
                        "Caso": item.titulo,
                        "Acción esperada": item.esperado.get("accion", ""),
                        "Orden": "sí" if item.esperado.get("orden") else "no",
                        "Resultado": item.esperado.get("resultado", ""),
                    }
                    for clave, item in VARIANTES_S1.items()
                ]
            ),
            hide_index=True,
            height=520,
        )

    with pestanas[3]:
        st.subheader("Métricas")
        st.json(metricas)
        st.subheader("Decisión del Coordinador")
        st.json(resultado["decision"] or {})
        descargas(nombre, resultado)

else:
    resultado = correr_s2(nombre)
    metricas = resultado["metricas"]
    real = resultado["real"]
    esperado = resultado["esperado"]
    checks = resultado["checks"]
    cumple = all(real.get(clave) == valor for clave, valor in esperado.items())

    columnas = st.columns(6)
    columnas[0].metric("Variante", "OK" if cumple else "Revisar")
    columnas[1].metric("Lote asignado", metricas["lote_asignado"] or "—")
    columnas[2].metric("Faltante prioritario", f"{metricas['faltante']} uds")
    columnas[3].metric("Riesgo residual", f"{metricas['riesgo_residual']} uds")
    columnas[4].metric("Timeout", "sí" if metricas["timeout_pronostico"] else "no")
    columnas[5].metric("Reinicio", metricas["reinicio"] or "—")

    if resultado["resultado"] == "exito":
        st.success(
            f"Lote **{metricas['lote']}** asignado a **{metricas['lote_asignado']}** · "
            f"{metricas['cantidad_lote']} uds · {metricas['rondas']} rondas · "
            f"{metricas['mensajes']} mensajes ACL."
        )
    elif resultado["resultado"] == "sin_riesgo":
        st.info("El lote no está próximo a vencer: no hay traslado ni incidente.")
    else:
        st.warning(
            f"Resultado **{resultado['resultado']}** · el lote queda sin asignar · "
            f"riesgo residual {metricas['riesgo_residual']} uds."
        )
    if metricas["escalado"]:
        st.warning(
            "El incidente del Pronóstico quedó escalado a intervención manual."
        )

    pestanas = st.tabs(["Secuencia", "Verificación", "Matriz de casos", "Traza"])

    with pestanas[0]:
        st.subheader("Rondas de comunicación")
        st.dataframe(
            tabla_eventos(resultado["eventos"], FASES_S2),
            hide_index=True,
            height=540,
        )

    with pestanas[1]:
        if checks:
            tabla_verificacion(checks)
        else:
            tabla_esperado(esperado, real)

    with pestanas[2]:
        st.subheader("Todos los 'y si' de la Situación 2")
        st.caption(
            "Cada fila es una variante declarativa sobre `config/s2.yaml`: "
            "timeout, reinicio, rechazos y lote sin riesgo."
        )
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Variante": clave,
                        "Caso": item.titulo,
                        "Resultado": item.esperado.get("resultado", ""),
                        "Lote": item.esperado.get("lote_asignado") or "—",
                        "Timeout": "sí" if item.esperado.get("timeout") else "no",
                        "Reinicio": item.esperado.get("reinicio") or "—",
                    }
                    for clave, item in VARIANTES_S2.items()
                ]
            ),
            hide_index=True,
            height=520,
        )

    with pestanas[3]:
        st.subheader("Métricas")
        st.json(metricas)
        st.subheader("Decisión del Coordinador")
        st.json(resultado["decision"] or {})
        descargas(nombre, resultado)
