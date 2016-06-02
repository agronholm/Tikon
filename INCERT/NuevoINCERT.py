import os
import warnings as avisar
import numpy as np
import scipy.stats as estad
import matplotlib.pyplot as dib
import pymc

import INCERT.Distribuciones as Ds

"""
Este código contiene funciones para manejar datos de incertidumbre.
"""


def gen_vector_coefs(dic_parám, calibs, n_rep_parám, comunes=None):
    """
    Esta función genera una matríz de valores posibles para un coeficiente, dado los nombres de las calibraciones
      que queremos usar y el número de repeticiones que queremos.

    :param dic_parám: Un diccionario de un parámetro con todas sus calibraciones
    :type dic_parám: dict

    :param calibs: Cuáles calibraciones hay que incluir
    :type calibs: list

    :param n_rep_parám: El número de repeticiones paramétricas que queremos en nuestra simulación.
    :type n_rep_parám: int

    :param comunes: Una matriz con la ubicación de cuál dato tomar de cada traza, si queremos que haya correspondencia
      entre los datos elegidos de cada parámetro.
    :type comunes: np.ndarray

    :return: Una matriz unidimensional con los valores del parámetro.
    :rtype: np.ndarray

    """

    # Hacer una lista con únicamente las calibraciones que estén presentes y en la lista de calibraciones acceptables,
    # y en el diccionario del parámetro
    calibs_usables = [x for x in dic_parám if x in calibs]

    # La lista para guardar las partes de las trazas de cada calibración que queremos incluir en la traza final
    lista_trazas = []

    # El número de calibraciones en la lista de calibraciones usables
    n_calibs = len(calibs_usables)

    # Calcular el número de repeticiones paramétricas por calibración. Produce una lista, en el mismo orden que calibs,
    # del número de repeticiones para cada calibración.
    rep_per_calib = np.array([n_rep_parám // n_calibs] * n_calibs)

    # Calcular el número que repeticiones que no se dividieron igualmente entre las calibraciones...
    resto = n_rep_parám % n_calibs
    # ...y añadirlas la principio de la lista de calibraciones.
    rep_per_calib[:resto + 1] += 1

    # Para cada calibración en la lista...
    for n_id, id_calib in enumerate(calibs_usables):

        # Sacar su traza (o distribución) del diccionario del parámetro.
        traza = dic_parám[id_calib]

        # Si la traza es una matriz numpy...
        if type(traza) is np.ndarray:

            # Verificamos si necesitamos más repeticiones de esta traza que tiene de datos disponibles.
            if rep_per_calib[n_id] > len(dic_parám[id_calib]):

                # Si es el caso que la traza tiene menos datos que las repeticiones que queremos...
                avisar.warn('Número de replicaciones superior al tamaño de la traza de '
                            'parámetro disponible.')

                # Vamos a tener que repetir datos
                devolver = True

            else:
                # Si no, no hay pena
                devolver = False

            # Tomar, al hazar, datos de la traza. Si estamos usando calibraciones comunes para todos los parámetros,
            # usar la ubicación de los datos predeterminada.
            if comunes is not None:
                ubic_datos = comunes[:rep_per_calib[n_id]]
                nuevos_vals = traza[ubic_datos]
            else:
                nuevos_vals = np.random.choice(traza, size=rep_per_calib[n_id], replace=devolver)

        elif type(traza) is str:
            # Si la traza es en formato de texto...

            if comunes:
                avisar.warn('No se pudo guardar la correspondencia entre todas las calibraciones por presencia'
                            'de distribuciones SciPy. La correspondencia sí se guardo para las otras calibraciones.')

            # Convertir el texto a distribución de SciPy
            dist_sp = texto_a_distscipy(traza)

            # Sacar los datos necesarios de la distribución SciPy
            nuevos_vals = dist_sp.rvs(rep_per_calib[n_id])

        elif isinstance(traza, pymc.Stochastic):

            # Si es un variable de calibración activo, poner el variable sí mismo en la matriz
            nuevos_vals = traza

        else:
            raise ValueError

        # Añadir los datos de esta calibración a la lista de datos para la traza general.
        lista_trazas.append(nuevos_vals)

    # Combinar las trazas de cada calibración en una única matriz numpy unidimensional.
    return np.concatenate(lista_trazas)


def texto_a_distscipy(texto):
    """
    Esta función convierte texto a su distribución SciPy correspondiente.

    :param texto: La distribución a convertir.
    :type texto: str
    """

    # Dividir el nombre de la distribución de sus parámetros.
    nombre, paráms = texto.split('~')

    # Si el nombre de la distribución está en la lista arriba...
    if nombre in Ds.dists:
        # Devolver la distribución SciPy appropiada
        return Ds.dists[nombre]['scipy'](paráms)

    # Si no encontramos el nombre de la distribución, hay un error.
    raise ValueError('No se pudo decodar la distribución "%s".' % texto)


def ajustar_dist(datos, límites, cont, usar_pymc=False, nombre=None):
    """
    Esta función, tomando las límites teoréticas de una distribución y una serie de datos proveniendo de dicha
      distribución, escoge la distribución de Scipy o PyMC la más apropriada y ajusta sus parámetros.

    :param datos: Un vector de valores del parámetro
    :type datos: np.ndarray

    :param nombre: El nombre del variable, si vamos a generar un variable de PyMC
    :type nombre: str

    :param cont: Determina si la distribución es contínua (en vez de discreta)
    :type cont: bool

    :param usar_pymc: Determina si queremos una distribución de tipo PyMC (en vez de SciPy)
    :type usar_pymc: bool

    :param límites: Las límites teoréticas de la distribucion (p. ej., (0, np.inf), (-np.inf, np.inf), etc.)
    :type límites: tuple

    :return: Distribución PyMC y su ajuste (p)
    :rtype: (pymc.Stochastic, float)

    """

    # Separar el mínimo y el máximo de la distribución
    mín_parám, máx_parám = límites

    # Un diccionario para guardar el mejor ajuste
    mejor_ajuste = dict(dist=None, p=0)

    # Sacar las distribuciones del buen tipo (contínuas o discretas)
    if cont:
        categ_dist = 'cont'
    else:
        categ_dist = 'discr'

    dists_potenciales = [x for x in Ds.dists if Ds.dists[x]['tipo'] == categ_dist]

    # Si queremos generar una distribución PyMC, guardar únicamente las distribuciones con objeto de PyMC disponible
    if usar_pymc is True:
        dists_potenciales = [x for x in dists_potenciales if Ds.dists[x]['pymc'] is not None]

    # Para cada distribución potencial para representar a nuestros datos...
    for nombre_dist in dists_potenciales:

        # El diccionario de la distribución
        dic_dist = Ds.dists[nombre_dist]

        # El máximo y el mínimo de la distribución
        mín_dist, máx_dist = dic_dist['límites']

        # Verificar que los límites del parámetro y de la distribución son compatibles
        lím_igual = (((mín_dist == mín_parám == -np.inf) or
                     (not np.isinf(mín_dist) and not np.isinf(mín_parám))) and
                     ((máx_dist == máx_parám == np.inf) or
                     (not np.isinf(máx_dist) and not np.isinf(máx_parám))))

        # Si son compatibles...
        if lím_igual:

            # Restringimos las posibilidades para las distribuciones a ajustar, si necesario
            if np.isinf(mín_parám):

                if np.isinf(máx_parám):
                    # Para el caso de un parámetro sín límites teoréticos (-inf, inf), no hay restricciones en la
                    # distribución.
                    restric = {}

                else:
                    # TIKON (por culpa de SciPy), no puede tomar distribuciones en (-inf, R].
                    raise ValueError('Tikon no puede tomar distribuciones en el intervalo (-inf, R]. Hay que '
                                     'cambiar tus ecuaciones para usar un variable en el intervalo [R, inf). '
                                     'Disculpas. Pero de verdad es la culpa del módulo SciPy.')
            else:

                if np.isinf(máx_parám):
                    # En el caso [R, inf), limitamos el valor inferior de la distribución al límite inferior del
                    # parámtro
                    restric = {'floc': mín_parám}

                else:
                    # En el caso [R, R], limitamos los valores inferiores y superiores de la distribución.
                    restric = {'floc': mín_parám, 'fscale': máx_parám - mín_parám}

            # Ajustar los parámetros de la distribución SciPy para caber con los datos.
            args = dic_dist['scipy'].fit(datos, **restric)

            # Medir el ajuste de la distribución
            p = estad.kstest(datos, nombre_dist, args=args)[1]

            # Si el ajuste es mejor que el mejor ajuste anterior...
            if p > mejor_ajuste['p']:

                # Guardarlo
                mejor_ajuste['p'] = p

                # Guardar también el objeto de la distribución, o de PyMC, o de SciPy, según lo que queremos
                if usar_pymc:
                    mejor_ajuste['dist'] = dic_dist['pymc'](nombre, *args)
                else:
                    mejor_ajuste['dist'] = dic_dist['scipy'](*args)

    # Si no logramos un buen aujste, avisar al usuario.
    if mejor_ajuste['p'] <= 0.10:
        avisar.warn('El ajuste de la mejor distribución quedó muy mala (p = %f).' % round(mejor_ajuste['p'], 4))

    # Devolver la distribución con el mejor ajuste, tanto como el valor de su ajuste.
    return mejor_ajuste['dist'], mejor_ajuste['p']


def límites_a_dist(límites, cont=True):
    """
    Esta función toma un "tuple" de límites para un parámetro de una función y devuelve una descripción de una
      destribución a priori no informativa (espero) para los límites dados. Se usa en la inicialización de las
      distribuciones de los parámetros de ecuaciones.

    :param límites: Las límites para los valores posibles del parámetro. Para límites infinitas, usar np.inf y
      -np.inf. Ejemplos: (0, np.inf), (-10, 10), (-np.inf, np.inf). No se pueden especificar límites en el rango
      (-np.inf, R), donde R es un número real. En ese caso, usar las límites (R, np.inf) y tomar el negativo del
      variable en las ecuaciones que lo utilisan.
    :type límites: tuple

    :param cont: Determina si el variable es continuo o discreto
    :type cont: bool

    :return: Descripción de la destribución no informativa que conforme a las límites especificadas. Devuelve una
      cadena de carácteres, que facilita guardar las distribuciones de los parámetros. Otras funciones la convertirán
      en distribución de scipy o de pymc donde necesario.
    :rtype: str
    """

    # Sacar el mínimo y máximo de los límites.
    mín = límites[0]
    máx = límites[1]

    # Verificar que máx > mín
    if máx <= mín:
        raise ValueError('El valor máximo debe ser superior al valor máximo.')

    # Pasar a través de todos los casos posibles
    if mín == -np.inf:
        if máx == np.inf:  # El caso (-np.inf, np.inf)
            if cont:
                dist = 'Normal~(0, 1e10)'
            else:
                dist = 'DiscrUnif~(1e-10, 1e10)'

        else:  # El caso (-np.inf, R)
            raise ValueError('Tikón no tiene funcionalidades de distribuciones a priori en intervalos (-inf, R). Puedes'
                             'crear un variable en el intervalo (R, inf) y utilisar su valor negativo en las '
                             'ecuaciones.')

    else:
        if máx == np.inf:  # El caso (R, np.inf)
            if cont:
                dist = 'Gamma~({}, 0.0001, 0.0001)'.format(mín)
            else:
                loc = mín - 1
                dist = 'Geom~(1e-8, {})'.format(loc)

        else:  # El caso (R, R)
            if cont:
                dist = 'Unif~({}, {})'.format(mín, máx)
            else:
                dist = 'DiscrUnif~({}, {})'.format(mín, mín+1)

    return dist


def gráfico(matr_predic, vector_obs, nombre, etiq_y=None, etiq_x='Día', color=None, mostrar=True, archivo=''):
    """
    Esta función genera un gráfico, dato una matriz de predicciones y un vector de observaciones temporales.

    :param matr_predic: La matriz de predicciones. Eje 0 = incertidumbre estocástica, eje 1 = incertidumbre
      paramétrica, eje 2 = día.
    :type matr_predic: np.ndarray

    :param vector_obs: El vector de las observaciones. Eje 0 = tiempo.
    :type vector_obs: np.ndarray

    :param nombre: El título del gráfico
    :type nombre: str

    :param etiq_y: La etiqueta para el eje y del gráfico.
    :type etiq_y: str

    :param etiq_x: La etiqueta para el eje x del gráfico
    :type etiq_x: str

    :param color: El color para el gráfico
    :type color: str

    :param mostrar: Si hay que mostrar el gráfico de inmediato, o solo guardarlo.
    :type mostrar: bool

    :param archivo: El archivo donde guardar el gráfico
    :type archivo: str

    """

    assert len(vector_obs) == matr_predic.shape[2]

    if color is None:
        color = '#99CC00'

    if etiq_y is None:
        etiq_y = nombre

    if mostrar is False:
        if len(archivo) == 0:
            raise ValueError('Hay que especificar un archivo para guardar el gráfico de %s.' % nombre)

    prom_predic = matr_predic.mean(axis=(0, 1))

    x = np.arange(len(vector_obs))

    dib.plot(x, prom_predic, lw=2, color=color)

    dib.plot(x, vector_obs, 'o', color=color)

    # Una matriz sin la incertidumbre estocástica
    matr_prom_estoc = matr_predic.mean(axis=0)

    # Ahora, el eje 0 es el eje de incertidumbre paramétrica
    máx_parám = matr_prom_estoc.max(axis=0)
    mín_parám = matr_prom_estoc.min(axis=0)

    dib.fill_between(x, máx_parám, mín_parám, facecolor=color, alpha=0.5)

    máx_total = matr_predic.max(axis=(0, 1))
    mín_total = matr_predic.min(axis=(0, 1))

    dib.fill_between(x, máx_total, mín_total, facecolor=color, alpha=0.3)

    dib.xlabel(etiq_x)
    dib.ylabel(etiq_y)
    dib.title(nombre)

    if mostrar is True:
        dib.show()
    else:
        if '.png' not in archivo:
            archivo = os.path.join(archivo, nombre + '.png')
        dib.savefig(archivo)