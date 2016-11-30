import os

import numpy as np
import pymc
from matplotlib import pyplot as dib
import matplotlib.patches as patches
from scipy import stats as estad

from Matemáticas.NuevoIncert import texto_a_dist


def gráfico(matr_predic, título, vector_obs=None, tiempos_obs=None,
            etiq_y=None, etiq_x='Día', color=None, promedio=True, incert='componentes', todas_líneas=False,
            mostrar=True, archivo=''):
    """
    Esta función genera un gráfico, dato una matriz de predicciones y un vector de observaciones temporales.

    :param matr_predic: La matriz de predicciones. Eje 0 = incertidumbre estocástica, eje 1 = incertidumbre
      paramétrica, eje 2 = día.
    :type matr_predic: np.ndarray

    :param vector_obs: El vector de las observaciones. Eje 0 = tiempo.
    :type vector_obs: np.ndarray

    :param tiempos_obs: El vector de los tiempos de las observaciones.
    :type tiempos_obs: np.ndarray

    :param título: El título del gráfico
    :type título: str

    :param etiq_y: La etiqueta para el eje y del gráfico.
    :type etiq_y: str

    :param etiq_x: La etiqueta para el eje x del gráfico
    :type etiq_x: str

    :param color: El color para el gráfico
    :type color: str

    :param promedio: Si hay que mostrar el promedio de las repeticiones o no.
    :type promedio: bool

    :param incert: El tipo de incertidumbre para mostrar (o no). Puede ser None, 'confianza', o 'descomponer'.
    :type incert: str

    :param todas_líneas: Si hay que mostrar todas las líneas de las repeticiones o no.
    :type todas_líneas: bool

    :param mostrar: Si hay que mostrar el gráfico de inmediato, o solo guardarlo.
    :type mostrar: bool

    :param archivo: El archivo donde guardar el gráfico
    :type archivo: str

    """

    if color is None:
        color = '#99CC00'

    if etiq_y is None:
        etiq_y = título

    if mostrar is False:
        if len(archivo) == 0:
            raise ValueError('Hay que especificar un archivo para guardar el gráfico de %s.' % título)

    # El vector de días
    x = np.arange(matr_predic.shape[2])

    # Si necesario, incluir el promedio de todas las repeticiones (estocásticas y paramétricas)
    prom_predic = matr_predic.mean(axis=(0, 1))
    if promedio:
        dib.plot(x, prom_predic, lw=2, color=color)

    # Si hay observaciones, mostrarlas también
    if vector_obs is not None:
        if tiempos_obs is None:
            tiempos_obs = np.arange(len(vector_obs))

        vacíos = np.where(~np.isnan(vector_obs))
        tiempos_obs = tiempos_obs[vacíos]
        vector_obs = vector_obs[vacíos]

        dib.plot(tiempos_obs, vector_obs, 'o', color=color)
        dib.plot(tiempos_obs, vector_obs, lw=1, color='#000000')

    # Incluir la incertidumbre
    if incert is None:
        # Si no quiso el usuario, no poner la incertidumbre
        pass

    elif incert == 'confianza':
        # Mostrar el nivel de confianza en la incertidumbre

        # Los niveles de confianza a mostrar
        percentiles = [50, 75, 95, 99, 100]
        percentiles.sort()

        # Mínimo y máximo del percentil anterior
        máx_perc_ant = mín_perc_ant = prom_predic

        # Para cada percentil...
        for n, p in enumerate(percentiles):

            # Percentiles máximos y mínimos
            máx_perc = np.percentile(matr_predic, 50+p/2, axis=(0, 1))
            mín_perc = np.percentile(matr_predic, (100-p)/2, axis=(0, 1))

            # Calcular el % de opacidad y dibujar
            op_máx = 0.5
            op_mín = 0.01
            opacidad = (1-n/(len(percentiles)-1)) * (op_máx - op_mín) + op_mín

            dib.fill_between(x, máx_perc_ant, máx_perc,
                             facecolor=color, alpha=opacidad, linewidth=0.5, edgecolor=color)
            dib.fill_between(x, mín_perc, mín_perc_ant,
                             facecolor=color, alpha=opacidad, linewidth=0.5, edgecolor=color)

            # Guardar los máximos y mínimos
            mín_perc_ant = mín_perc
            máx_perc_ant = máx_perc

    elif incert == 'componentes':
        # Mostrar la incertidumbre descompuesta por sus fuentes

        # Una matriz sin la incertidumbre estocástica
        matr_prom_estoc = matr_predic.mean(axis=0)

        # Ahora, el eje 0 es el eje de incertidumbre paramétrica
        máx_parám = matr_prom_estoc.max(axis=0)
        mín_parám = matr_prom_estoc.min(axis=0)

        dib.fill_between(x, máx_parám, mín_parám, facecolor=color, alpha=0.5)

        máx_total = matr_predic.max(axis=(0, 1))
        mín_total = matr_predic.min(axis=(0, 1))

        dib.fill_between(x, máx_total, mín_total, facecolor=color, alpha=0.3)

    else:
        raise ValueError('No entiendo el tipo de incertidumbre "%s" que especificaste para el gráfico.' % incert)

    # Si lo especificó el usuario, mostrar todas las líneas de todas las repeticiones.
    if todas_líneas:
        for incert_estóc in matr_predic:
            for incert_parám in incert_estóc:
                dib.plot(x, incert_parám, lw=1, color=color)

    dib.xlabel(etiq_x)
    dib.ylabel(etiq_y)
    dib.title(título)

    if mostrar is True:
        dib.show()
    else:
        if '.png' not in archivo:
            archivo = os.path.join(archivo, título + '.png')
        dib.savefig(archivo)


def graficar_dists(dists, n=1000, valores=None, rango=None, título=None, archivo=None):
    """
    Esta función genera un gráfico de una o más distribuciones y valores.

    :param dists: Una lista de las distribuciones para graficar.
    :type dists: list

    :param n: El número de puntos para el gráfico.
    :type n: int

    :param valores: Una matriz numpy de valores para hacer un histograma (opcional)
    :type valores: np.ndarray

    :param rango: Un rango de valores para resaltar en el gráfico (opcional).
    :type rango: tuple

    :param título: El título del gráfico, si hay.
    :type título: str

    :param archivo: Dónde hay que guardar el dibujo. Si no se especifica, se presentará el gráfico al usuario en una
      nueva ventana (y el programa esperará que la usadora cierra la ventana antes de seguir con su ejecución).
    :type archivo: str

    """

    if type(dists) is not list:
        dists = [dists]

    dib.close()

    # Poner cada distribución en el gráfico
    for dist in dists:

        if type(dist) is str:
            dist = texto_a_dist(texto=dist, usar_pymc=False)

        if isinstance(dist, pymc.Stochastic):
            puntos = np.array([dist.rand() for _ in range(n)])
            y, delim = np.histogram(puntos, normed=True, bins=100)
            x = 0.5 * (delim[1:] + delim[:-1])

        elif isinstance(dist, pymc.Deterministic):
            dist_stoc = min(dist.extended_parents)
            puntos = np.array([(dist_stoc.rand(), dist.value)[1] for _ in range(n)])
            y, delim = np.histogram(puntos, normed=True, bins=100)
            x = 0.5 * (delim[1:] + delim[:-1])

        elif isinstance(dist, estad._distn_infrastructure.rv_frozen):
            x = np.linspace(dist.ppf(0.01), dist.ppf(0.99), n)
            y = dist.pdf(x)

        else:
            raise TypeError('El tipo de distribución "%s" no se reconoce como distribución aceptada.' % type(dist))

        # Dibujar la distribución
        dib.plot(x, y, 'b-', lw=2, alpha=0.6)

        # Resaltar un rango, si necesario
        if rango is not None:
            if rango[1] < rango[0]:
                rango = (rango[1], rango[0])
            dib.fill_between(x[(rango[0] <= x) & (x <= rango[1])], 0, y[(rango[0] <= x) & (x <= rango[1])],
                             color='blue', alpha=0.2)

    # Si hay valores, hacer un histrograma
    if valores is not None:
        dib.hist(valores, normed=True, color='green', histtype='stepfilled', alpha=0.2)

    # Si se especificó un título, ponerlo
    if título is not None:
        dib.title(título)

    # Mostrar o guardar el gráfico
    if archivo is None:
        dib.show()
    else:
        dib.savefig(archivo)