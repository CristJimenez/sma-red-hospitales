"""Pronóstico Holt + estacionalidad semanal, compartido por S1 y S2.

La Situación 1 lo usa para proyectar la demanda del hospital en brote; la
Situación 2, para estimar la demanda de los dos hospitales que compiten por un
lote. Al vivir en un módulo aparte, ambas situaciones calculan igual.
"""

from __future__ import annotations

from statistics import mean

DIAS_SEMANA = 7


def holt(serie: list[float], alfa: float = 0.4, beta: float = 0.2) -> tuple[float, float]:
    nivel = serie[0]
    tendencia = serie[1] - serie[0]
    for valor in serie[1:]:
        nivel_previo = nivel
        nivel = alfa * valor + (1 - alfa) * (nivel + tendencia)
        tendencia = beta * (nivel - nivel_previo) + (1 - beta) * tendencia
    return nivel, tendencia


def factores_estacionales(serie: list[float]) -> list[float]:
    promedio = mean(serie)
    if promedio <= 0:
        return [1.0] * DIAS_SEMANA
    factores = []
    for dia in range(DIAS_SEMANA):
        valores = [serie[i] for i in range(dia, len(serie), DIAS_SEMANA)]
        factores.append(mean(valores) / promedio if valores else 1.0)
    return factores


def mape(serie: list[float], factores: list[float]) -> float:
    if len(serie) < 10:
        return 0.0
    entrenamiento, prueba = serie[:-7], serie[-7:]
    nivel, tendencia = holt(entrenamiento)
    errores = []
    for i, real in enumerate(prueba):
        indice = len(entrenamiento) + i
        predicho = (nivel + (i + 1) * tendencia) * factores[indice % DIAS_SEMANA]
        errores.append(abs(predicho - real) / real)
    return round(mean(errores), 4)


def proyectar(serie: list[float], horizonte: int, factor: float = 1.0) -> int:
    """Suma de la proyección para ``horizonte`` días, con estacionalidad."""
    if not serie:
        return 0
    factores = factores_estacionales(serie)
    nivel, tendencia = holt(serie)
    total = 0.0
    for paso in range(1, horizonte + 1):
        indice = len(serie) - 1 + paso
        total += (nivel + paso * tendencia) * factores[indice % DIAS_SEMANA] * factor
    return int(round(total))
