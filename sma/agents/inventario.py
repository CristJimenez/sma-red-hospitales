"""Agente de Inventario: arquitectura reactiva (simple reflejo).

Rol: Monitor de Inventario. Compara existencias con umbrales, detecta niveles
críticos y lotes próximos a vencer, y emite eventos de riesgo.
"""

from __future__ import annotations

from typing import Any

from ..acl import FIPA_QUERY, INFORM, QUERY_REF
from .base import AgenteBase


class AgenteInventario(AgenteBase):
    nombre = "inventario"

    def procesar(self, mensajes: list[Any]) -> None:
        for mensaje in mensajes:
            if mensaje.performativa == QUERY_REF and mensaje.contenido.get(
                "consulta"
            ) in ("excedentes", "excedentes_emergencia"):
                self._responder_excedentes(mensaje)

        if self.model.ronda == self.model.config.evento.ronda_inicio:
            self._detectar_riesgos()

    # ------------------------------------------------------------------
    def _detectar_riesgos(self) -> None:
        config = self.model.config
        for hospital in config.hospitales.values():
            for med_id in config.medicamentos:
                factor = self.model.factor_brote(hospital.id, med_id)
                stock = hospital.stock(med_id)
                umbral = hospital.umbral(med_id)
                dias = hospital.dias_hasta_agotamiento(med_id, factor)
                por_vencer = hospital.lotes_proximos_a_vencer(med_id, 60)

                if stock <= umbral or dias <= hospital.stock_seguridad_dias:
                    evento = {
                        "tipo": "riesgo_desabastecimiento",
                        "hospital": hospital.id,
                        "medicamento": med_id,
                        "stock": stock,
                        "umbral": round(umbral, 2),
                        "consumo_diario": round(
                            hospital.consumo_efectivo(med_id, factor), 2
                        ),
                        "dias_hasta_agotamiento": round(dias, 2),
                        "lotes_por_vencer": len(por_vencer),
                        "factor_brote": factor,
                    }
                    self.accion("generarEventoRiesgo", evento)
                    self.enviar(INFORM, "coordinador", evento)
                    self.enviar(
                        INFORM,
                        "supervisor",
                        {
                            "tipo": "informe_inventario",
                            "hospital": hospital.id,
                            "medicamento": med_id,
                            "nivel": "critico",
                        },
                    )

    # ------------------------------------------------------------------
    def _responder_excedentes(self, consulta: Any) -> None:
        config = self.model.config
        med_id = consulta.contenido["medicamento"]
        hospital_riesgo = consulta.contenido.get("hospital")
        emergencia = consulta.contenido.get("consulta") == "excedentes_emergencia"
        modo = "emergencia" if emergencia else "normal"
        colchon = 0.0 if emergencia else 2.0
        excluir = set(consulta.contenido.get("excluir", [])) | {hospital_riesgo}
        self.accion("leerRegistros", {"medicamento": med_id, "modo": modo})

        excedentes: dict[str, dict[str, Any]] = {}
        for hospital in config.hospitales.values():
            if hospital.id in excluir:
                continue
            cantidad = hospital.excedente(med_id, colchon_dias=colchon)
            if cantidad <= 0:
                continue
            lotes = hospital.lotes.get(med_id, [])
            vence = min((l.vence_en_dias for l in lotes), default=365)
            excedentes[hospital.id] = {
                "cantidad": cantidad,
                "lote_vence_en_dias": vence,
                "cadena_frio_ok": True,
            }

        respuesta = {
            "tipo": "excedentes",
            "modo": modo,
            "medicamento": med_id,
            "hospital_riesgo": hospital_riesgo,
            "excedentes": excedentes,
            "total": sum(e["cantidad"] for e in excedentes.values()),
        }
        self.enviar(
            INFORM,
            "coordinador",
            respuesta,
            protocolo=FIPA_QUERY,
            conversation_id=consulta.conversation_id,
            in_reply_to=consulta.reply_with,
        )
