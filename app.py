"""Panel web de la Situación 1.

Ejecuta el SMA y muestra la traza real, las métricas y el diagrama de
secuencia generado desde esa misma traza.
"""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from sma.config import cargar_config
from sma.run import ejecutar
from sma.scenario.s1 import verificar

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


@st.cache_data(show_spinner=False)
def correr(
    forzar_presupuesto: bool, compras_no_puede: bool, simular_caido: bool
) -> dict:
    config = cargar_config()
    config.opciones.forzar_presupuesto_insuficiente = forzar_presupuesto
    config.opciones.compras_puede_gestionar = not compras_no_puede
    config.opciones.simular_agente_caido = simular_caido

    modelo = ejecutar(config)
    return {
        "metricas": modelo.metricas(),
        "checks": verificar(modelo),
        "eventos": modelo.traza.eventos,
        "mermaid": modelo.traza.a_mermaid(),
        "decision": modelo.decision,
    }


def resumen(contenido: dict, maximo: int = 70) -> str:
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
    "Situación 1 · brote respiratorio en el Hospital A · Mesa 3 + capa FIPA-ACL · "
    "el diagrama de secuencia se genera desde la traza real."
)

with st.sidebar:
    st.header("Escenario")
    st.markdown(
        "**Hospital A** (alta complejidad) sufre un brote respiratorio. "
        "Inventario detecta el riesgo, Pronóstico proyecta la demanda y el "
        "Coordinador combina traslado desde el Hospital B con compra al "
        "proveedor alterno."
    )
    st.divider()
    st.subheader("Ramas alternativas")
    forzar_presupuesto = st.checkbox("Forzar presupuesto insuficiente")
    compras_no_puede = st.checkbox("Compras no puede gestionar la compra")
    simular_caido = st.checkbox("Simular agente caído (aviso del Supervisor)")
    st.divider()
    if st.button("Re-ejecutar escenario", type="primary"):
        st.cache_data.clear()
        st.rerun()
    st.caption("Semilla fija: cada ejecución produce exactamente la misma traza.")

resultado = correr(forzar_presupuesto, compras_no_puede, simular_caido)
metricas = resultado["metricas"]
checks = resultado["checks"]

ok = sum(1 for check in checks if check["ok"])

columnas = st.columns(6)
columnas[0].metric("Verificaciones", f"{ok}/{len(checks)}")
columnas[1].metric("Cobertura proyectada", f"{metricas['cobertura_proyectada'] * 100:.0f}%")
columnas[2].metric("Traslado", f"{metricas['traslado_recibido']} uds")
columnas[3].metric("Compra", f"{metricas['cantidad_comprada']} uds")
columnas[4].metric("Coste", f"{metricas['coste_compra']:.2f} €")
columnas[5].metric("Presupuesto restante", f"{metricas['presupuesto_restante']:.2f} €")

if metricas["orden_estado"]:
    st.success(
        f"Orden de compra en estado **{metricas['orden_estado']}** · "
        f"{metricas['demanda_proyectada']} unidades de demanda proyectada cubiertas."
    )
else:
    st.warning("No se generó orden de compra en esta ejecución.")

pestanas = st.tabs(
    ["Secuencia", "Verificación", "Diagrama de secuencia", "Traza y métricas"]
)

with pestanas[0]:
    st.subheader("Rondas de comunicación")
    st.dataframe(
        tabla_eventos(resultado["eventos"]),
        hide_index=True,
        height=560,
    )

with pestanas[1]:
    st.subheader("Pasos del escenario")
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

with pestanas[2]:
    st.subheader("Generado desde la traza")
    st.caption(
        "Este diagrama no está dibujado a mano: se produce a partir de los "
        "mensajes realmente intercambiados."
    )
    components.html(
        f"""
        <pre class="mermaid" id="src"></pre>
        <script type="module">
          import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
          const origen = {json.dumps(resultado["mermaid"])};
          const nodo = document.getElementById('src');
          nodo.textContent = origen;
          mermaid.initialize({{ startOnLoad: false, theme: 'default' }});
          mermaid.run({{ nodes: [nodo] }});
        </script>
        """,
        height=1200,
        scrolling=True,
    )
    st.download_button(
        "Descargar diagrama (.mmd)",
        resultado["mermaid"],
        file_name="s1_secuencia.mmd",
        mime="text/plain",
    )

with pestanas[3]:
    st.subheader("Métricas")
    st.json(metricas)
    st.subheader("Decisión del Coordinador")
    st.json(resultado["decision"] or {})
    st.download_button(
        "Descargar traza completa (.json)",
        json.dumps({"eventos": resultado["eventos"]}, ensure_ascii=False, indent=2),
        file_name="s1_traza.json",
        mime="application/json",
    )
