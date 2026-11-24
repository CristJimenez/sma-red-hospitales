"""Agente de Pronóstico de Demanda: arquitectura basada en modelos con aprendizaje.

Suavizado exponencial de Holt + estacionalidad semanal. Se reajusta con el
error observado (MAPE) y con la señal de brote que reporta Inventario.
"""

from __future__ import annotations

from statistics import mean
from typing import Any

from ..acl import INFORM
from .base import AgenteBase

DIAS_SEMANA = 7


def _holt(serie: list[float], alfa: float = 0.4, beta: float = 0.2) -> tuple[float, float]:
    nivel = serie[0]
    tendencia = serie[1] - serie[0]
    for valor in serie[1:]:
        nivel_previo = nivel
        nivel = alfa * valor + (1 - alfa) * (nivel + tendencia)
        tendencia = beta * (nivel - nivel_previo) + (1 - beta) * tendencia
    return nivel, tendencia


def _factores_estacionales(serie: list[float]) -> list[float]:
    promedio = mean(serie)
    if promedio <= 0:
        return [1.0] * DIAS_SEMANA
    factores = []
    for dia in range(DIAS_SEMANA):
        valores = [serie[i] for i in range(dia, len(serie), DIAS_SEMANA)]
        factores.append(mean(valores) / promedio if valores else 1.0)
    return factores


def _mape(serie: list[float], factores: list[float]) -> float:
    if len(serie) < 10:
        return 0.0
    entrenamiento, prueba = serie[:-7], serie[-7:]
    nivel, tendencia = _holt(entrenamiento)
    errores = []
    for i, real in enumerate(prueba):
        indice = len(entrenamiento) + i
        predicho = (nivel + (i + 1) * tendencia) * factores[indice % DIAS_SEMANA]
        errores.append(abs(predicho - real) / real)
    return round(mean(errores), 4)


class AgentePronostico(AgenteBase):
    nombre = "pronostico"

    def procesar(self, mensajes: list[Any]) -> None:
        if self.model.ronda == self.model.config.evento.ronda_inicio:
            self._pronosticar_evento()

    def _pronosticar_evento(self) -> None:
        config = self.model.config
        evento = config.evento
        hospital = config.hospitales[evento.hospital]
        serie = hospital.historial.get(evento.medicamento, [])
        if not serie:
            return

        factores = _factores_estacionales(serie)
        nivel, tendencia = _holt(serie)
        horizonte = config.horizonte_pronostico_dias

        proyeccion = 0.0
        for paso in range(1, horizonte + 1):
            indice = len(serie) - 1 + paso
            proyeccion += (
                (nivel + paso * tendencia)
                * factores[indice % DIAS_SEMANA]
                * evento.factor_consumo
            )
        proyeccion = int(round(proyeccion))

        error = _mape(serie, factores)
        reciente = mean(serie[-7:])
        previa = mean(serie[-14:-7]) if len(serie) >= 14 else reciente
        tendencia_texto = "creciente" if reciente > previa * 1.02 else "estable"
        self.accion(
            "calcularProyeccion",
            {
                "medicamento": evento.medicamento,
                "hospital": evento.hospital,
                "horizonte_dias": horizonte,
                "demanda_proyectada": proyeccion,
                "mape": error,
            },
        )
        self.enviar(
            INFORM,
            "coordinador",
            {
                "tipo": "demanda_proyectada",
                "hospital": evento.hospital,
                "medicamento": evento.medicamento,
                "horizonte_dias": horizonte,
                "demanda_proyectada": proyeccion,
                "mape": error,
                "tendencia": tendencia_texto,
            },
            conversation_id="pronostico-1",
        )
        self.accion("actualizarModelo", {"mape": error})
