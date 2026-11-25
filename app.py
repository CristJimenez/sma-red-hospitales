"""Panel web del SMA de abastecimiento hospitalario.

Ejecuta cualquiera de las variantes del escenario y muestra la traza real, las
métricas y la verificación. El diagrama de secuencia se exporta desde esa misma
traza (`python -m sma.diagrama`), sin depender de servicios externos.
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from sma.run import ejecutar
from sma.scenario.s1 import verificar
from sma.variantes import cargar_variante, listar_variantes

st.set_page_config(
    page_title="SMA Red de Hospitales",
    page_icon="🏥",
    layout="wide",
)

FASES = {
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

VARIANTES = listar_variantes()


@st.cache_data(show_spinner=False)
def correr(nombre: str) -> dict:
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


def resumen(contenido: dict, maximo: int = 80) -> str:
    partes = [f"{clave}={valor}" for clave, valor in contenido.items()]
    texto = ", ".join(partes)
    return texto[: maximo - 3] + "..." if len(texto) > maximo else texto


def tabla_eventos(eventos: list[dict]) -> pd.DataFrame:
    filas = []
    for evento in eventos:
        if evento["tipo"] == "mensaje":
            filas.append(
                {
                    "Ronda": evento["ronda"],
                    "Fase": FASES.get(evento["ronda"], ""),
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
                    "Fase": FASES.get(evento["ronda"], ""),
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
                    "Fase": FASES.get(evento["ronda"], ""),
                    "Tipo": "Acción",
                    "De": evento["agente"],
                    "Para": "",
                    "Acción": evento["accion"],
                    "Detalle": resumen(evento["detalle"]),
                }
            )
    return pd.DataFrame(filas)


st.title("SMA de abastecimiento de medicamentos")
st.caption(
    "Red de hospitales públicos · Mesa 3 + capa FIPA-ACL · "
    "todos los datos salen de la traza real de la ejecución."
)

with st.sidebar:
    st.header("Escenario")
    nombre = st.selectbox(
        "Variante",
        options=list(VARIANTES),
        format_func=lambda clave: VARIANTES[clave].titulo,
    )
    variante = VARIANTES[nombre]
    st.markdown(variante.descripcion)
    st.divider()
    if st.button("Re-ejecutar", type="primary"):
        st.cache_data.clear()
        st.rerun()
    st.caption("Semilla fija: cada ejecución produce exactamente la misma traza.")

resultado = correr(nombre)
metricas = resultado["metricas"]
real = resultado["real"]
esperado = resultado["esperado"]
checks = resultado["checks"]

ok = sum(1 for check in checks if check["ok"])
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
        tabla_eventos(resultado["eventos"]),
        hide_index=True,
        height=540,
    )

with pestanas[1]:
    if checks:
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
    else:
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
                for clave, item in VARIANTES.items()
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
    st.subheader("Descargas")
    st.caption(
        "El diagrama de secuencia sale de esta misma traza. `Diagrama.drawio` se "
        "regenera con `python -m sma.diagrama`."
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
