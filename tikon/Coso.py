import copy as copiar
import json
import math as mat
import os
import random
import time
from datetime import datetime as ft
from warnings import warn as avisar

import numpy as np

from tikon.Matemáticas.Variables import VarSciPy, VarCalib
from tikon import __correo__
from tikon.Controles import directorio_base, dir_proyectos
from tikon.Matemáticas import Arte, Incert
from tikon.Matemáticas.Calib import ModBayes, ModGLUE, ModCalib
from tikon.Matemáticas.Experimentos import Experimento
from tikon.Matemáticas.Sensib import prep_anal_sensib


class Coso(object):
    """
    Un "coso", por falta de mejor palabra, se refiere a todo, TODO en el programa
    Tikon que representa un aspecto físico del ambiente y que tiene datos. Incluye
    paisajes, parcelas, variedades de cultivos, suelos, insectos, etc. Todos tienen la misma
    lógica para leer y escribir sus datos en carpetas externas, tanto como para la
    su calibración.
    """

    # La extensión para guardar recetas de este tipo de objeto
    ext = NotImplemented

    # Una referancia al diccionario con la información de los parámetros del objeto.
    dic_info_ecs = NotImplemented

    def __init__(símismo, nombre, proyecto):
        """
        Creamos un Coso con un numbre y, posiblemente, una fuente de cual cargarlo.

        :param nombre: El nombre del Coso
        :type nombre: str

        :param proyecto: Si este Coso hace parte de un proyecto (se creará, si necesario, el archivo apropiado
        para guardarlo).
        :type proyecto: str

        """

        # En 'coefs', ponemos todos los coeficientes del modelo (se pueden organizar en diccionarios). En 'estr',
        # pondremos la información estructural del modelo. En 'info', se pone información adicional del Coso.

        símismo.receta = dict(coefs={},
                              estr={},
                              info={}
                              )

        # Acordarse de dónde vamos a guardar este Coso
        símismo.proyecto = proyecto

        # También el nombre, para referencia fácil
        símismo.nombre = nombre

        # Para guardar los objetos relacionados con este Coso. Sirve para encontrar todos los objetos que hay que
        #  mirar para una simulación o calibración.
        símismo.objetos = []  # type: list[Coso]

    def actualizar(símismo):
        raise NotImplementedError

    def especificar_apriori(símismo, **kwargs):
        """
        Esta función permite al usuario especificar una distribución especial para el a priori de un parámetro.

        :param kwargs: Argumentos específicos a la instancia del Coso.

        :return: La distribución generada.
        :rtype: str

        """
        raise NotImplementedError

    def borrar_calib(símismo, id_calib, recursivo=True):
        """
        Esta función borra una calibración de la receta del Coso.

        :param id_calib: El nombre de la calibración que hay que borrar.
        :type id_calib: str

        :param recursivo: Si también borramos lo mismo en los otros Cosos asociados con este.
        :type recursivo: bool

        """

        # Borramos la distribución de la receta de coeficientes
        símismo._borrar_dist(d=símismo.receta['coefs'], nombre=id_calib)

        # Tambien borramos el nombre de la calibracion del diccionario de calibraciones, si es que existe allí.
        try:
            símismo.receta['Calibraciones'].pop(id_calib)
        except KeyError:
            pass

        # Si es una limpieza recursiva, limpiamos todos los objetos vinculados de manera recursiva también.
        if recursivo:
            for coso in símismo.objetos:
                coso.borrar_calib(id_calib=id_calib, recursivo=recursivo)

    def limpiar_especificados(símismo, recursivo=True):
        """
        Esta función limpia (borra) todas las distribuciones especificadas para este Coso.

        :param recursivo: Si también limpiamos las distribuciones especificadas de los otros Cosos asociados con este.
        :type recursivo: bool

        """
        símismo.borrar_calib(id_calib='especificado', recursivo=recursivo)

    def guardar_especificados(símismo, nombre_dist='dist_especificada'):
        """
        Esta función guarda los valores de distribuciones especificadas bajo un nuevo nombre. Esto permite, después,
        guardar y cargar el Coso sin perder las distribuciones especificadas, que son normalmente temporarias.

        :param nombre_dist: El nombre de la distribución.
        :type nombre_dist: str

        """

        # Cambiar el nombre de las distribuciones especificadas en el diccionario de coeficientes.
        símismo._renombrar_dist(símismo.receta['coefs'], nombre_ant='especificado', nombre_nuevo=nombre_dist)

    def guardar(símismo, proyecto=None, especificados=False, iterativo=True):
        """
        Esta función guarda el Coso para uso futuro.

        :param proyecto: Donde hay que guardar el Coso
        :type proyecto: str

        :param especificados: Si hay que guardar los valores especificados o no. En general, NO es buena idea.
        :type especificados: bool

        :param iterativo: Si también vamos a guardar todos los objetos vinculado con este (por ejemplo, todos los
          insectos vinculados con una Red).
        :type iterativo: bool

        """

        # Si no se especificó archivo...
        if proyecto is None:
            if símismo.proyecto is not None:
                proyecto = símismo.proyecto  # utilizar el archivo existente
            else:
                # Si no hay archivo existente, tenemos un problema.
                raise FileNotFoundError('Hay que especificar un archivo para guardar el objeto.')
        else:
            símismo.proyecto = proyecto

        # Si hay que guardar los especificados, hacerlo ahora.
        if especificados:
            símismo.guardar_especificados()

        # Preparar el directorio
        proyecto = símismo._prep_directorio(proyecto)

        # Convertir matrices a formato de lista y quitar objetos PyMC, si quedan
        receta_prep = prep_receta_json(símismo.receta)

        # Guardar el documento de manera que preserve carácteres no latinos (UTF-8)
        guardar_json(dic=receta_prep, archivo=os.path.join(proyecto, símismo.nombre + símismo.ext))

        # Si se especificó así, guardar todos los objetos vinculados con este objeto también.
        if iterativo:
            for coso in símismo.objetos:
                coso.guardar(iterativo=True)

    def cargar(símismo, fuente):
        """
        Esta función carga un archivo de receta para crear el Coso.

        :param fuente: Dónde se ubica el archivo.
        :type fuente: str

        """

        # Si necesario, agregar la extensión y el directorio
        if os.path.splitext(fuente)[1] != símismo.ext:
            fuente += símismo.ext
        if os.path.splitdrive(fuente)[0] == '':
            # Si no se especifica directorio, se usará el directorio de Proyectos de Tiko'n.
            fuente = os.path.join(directorio_base, 'Proyectos', fuente)

        # Intentar cargar el archivo (con formato UTF-8)
        try:
            with open(fuente, 'r', encoding='utf8') as d:
                nuevo_dic = json.load(d)

        except IOError as e:  # Si no funcionó, quejarse.
            raise IOError(e)

        else:  # Si se cargó el documento con éxito, usarlo
            # Copiar el documento a la receta de este Coso
            símismo.receta.clear()
            símismo.receta.update(nuevo_dic)

            # Convertir listas a matrices numpy en las ecuaciones (coeficientes)
            dic_lista_a_np(símismo.receta['coefs'])

    def ver_coefs_no_espec(símismo):
        """

        :return:
        :rtype: dict

        """

        sin_especif = {símismo.nombre: símismo._sacar_coefs_no_espec()}

        for obj in símismo.objetos:
            sin_especif[obj.nombre] = obj.ver_coefs_no_espec()

        return sin_especif

    def _sacar_coefs_interno(símismo):
        """
        Esta función genera una lista de los coeficientes propios al objeto de interés para la calibración actual.
        Se debe implementar para cada Coso (objeto) que tiene coeficientes.

        :return: Una lista de diccionarios de coeficientes, con el formato siguiente:
           [ {calib1: distribución o [lista de valores],
              calib2: ibid,
              ...},
              {coeficiente 2...},
              ...
           ]
        :rtype: list

        """

        raise NotImplementedError

    def _sacar_líms_coefs_interno(símismo):
        """
        Esta función genera una lista de las límites de los coeficientes propios al objeto de interés para la
        calibración actual. Se debe implementar para cada Coso (objeto) que tiene coeficientes.

        :return: Un tuple, conteniendo:
          1. Una lista de diccionarios de coeficientes, con el formato siguiente:
           [ {calib1: distribución o [lista de valores],
              calib2: ibid,
              ...},
              {coeficiente 2...},
              ...
           ]

           2. Una lista de los límites de los coeficientes, en el mismo orden que (1.)
        :rtype: (list, list)

        """

        raise NotImplementedError

    def _prep_directorio(símismo, directorio):
        """
        Esta función prepara una dirección de directorio.

        :param directorio: 
        :type directorio: str

        :return: 
        :rtype: str

        """

        if directorio[0] == '.':
            directorio = os.path.join(símismo.proyecto, directorio[1:])

        if not os.path.splitdrive(directorio)[0]:
            directorio = os.path.join(dir_proyectos, directorio)

        if not os.path.exists(directorio):
            os.makedirs(directorio)

        return directorio

    def _sacar_coefs_no_espec(símismo):
        """
        
        :return: 
        :rtype: dict
        
        """

        raise NotImplementedError

    @staticmethod
    def _estab_a_priori(dic_ecs, dic_parám, ubic_parám, rango, certidumbre, dibujar, inter=None,
                        archivo=None, título=None):
        """
        Esta función implementa una distribución a priori en el diccionario especificado. Se llama desde la
        implementación local de especificar_apriori.

        :param dic_ecs: El diccionario de información de los parámetros de las ecuaciones.
        :type dic_ecs: dict

        :param dic_parám: El diccionario de parámetros (él que hay que modificar).
        :type dic_parám: dict

        :param ubic_parám: Una lista con la ubicación del parámetro en dic_parám.
        :type ubic_parám: list

        :param rango: El rango de la distribución.
        :type rango: tuple

        :param certidumbre: La probabilidad, en (0, 1], que el valor verdadero se encuentre en el rango especificado.
        :type certidumbre: float

        :param dibujar: Si queremos dibujar el resultado o no.
        :type dibujar: bool

        :param inter: Un tuple de interacciones (opcional).
        :type inter: tuple | None

        """

        # Si "certidumbre" se especificó como un porcentaje, cambiarlo a una fracción.
        if certidumbre > 1:
            avisar('El parámetro "certidumbre" se especificó a un valor superior a 1. Lo tomaremos como un porcentaje.')
            certidumbre /= 100

        # Asegurarse de que "certidumbre" esté entre 0 y 1
        if not 0. < certidumbre <= 1:
            raise ValueError('El parámetro "certidumbre" debe ser un número en el rango (0, 1].')

        # Encontrar la ubicación del parámetro en el diccionario de especificaciones de parámetros y en el diccionario
        # de ecuaciones del Coso.
        for llave in ubic_parám:
            try:
                dic_parám = dic_parám[llave]
                dic_ecs = dic_ecs[llave]
            except KeyError:
                raise KeyError('Ubicación de parámetro erróneo.')

        # Sacar las límites teoréticas de la distribución.
        try:
            líms = dic_ecs['límites']
        except KeyError:
            raise KeyError('Ubicación de parámetro erróneo.')

        texto_dist = '{}; {}en{}'.format(str(líms), certidumbre, str(rango))

        # Si hay interacciones, buscar
        if inter is None:
            if 'inter' in dic_ecs and dic_ecs['inter'] is not None:
                raise ValueError('Hay que especificar interacciones para parámetros con interacciones.')
        else:
            for i in inter:
                if i not in dic_parám:
                    dic_parám[i] = {}

                dic_parám = dic_parám[i]

        # Guardar la distribución en el diccionario de parámetros
        dic_parám['especificado'] = texto_dist

        # Si necesario, dibujar y mostrar la nueva distribución.
        if dibujar:
            Arte.graficar_dists(texto_dist, rango=rango, título=título, archivo=archivo)

    @classmethod
    def generar_aprioris(cls, directorio=None):
        """
        Esta función, específica a cada subclase de Coso, debe generar valores a prioris a base de los objetos del
        mismo tipo que ya existen.

        :param directorio: El directorio en el cual buscar los objetos para generar a prioris.
        :type directorio: str

        """

        lista_objs = []

        # Sacar la lista de los objetos de este tipo en Proyectos
        for raíz, dirs, archivos in os.walk(dir_proyectos, topdown=False):
            for nombre in archivos:
                ext = os.path.splitext(nombre)[1]
                if ext == cls.ext:
                    lista_objs.append(cls(fuente=nombre))

        dic_aprioris = cls._apriori_de_existente(lista_objs=lista_objs, clase_objs=cls)

        archivo = os.path.join(directorio_base, 'A prioris', cls.__name__, '.apr')
        guardar_json(dic=dic_aprioris, archivo=archivo)

        # Para hacer: completar
        raise NotImplemented

    @classmethod
    def _borrar_dist(cls, d, nombre):
        """
        Esta función borra todas las distribuciones con un nombre específico en un diccionario de coeficientes.

        :param d: El diccionario de coeficientes.
        :type d: dict

        :param nombre: El nombre de la distribución.
        :type nombre: str

        """

        # Para cada itema (llave, valor) del diccionario
        for ll in list(d):
            v = d[ll]

            if type(v) is dict:

                # Si el itema era otro diccionario, llamar esta función de nuevo con el nuevo diccionario
                cls._borrar_dist(v, nombre=nombre)

            else:

                # Si la distribución lleva el nombre especificado...
                if ll == str(nombre):
                    # ...borrar la distribución
                    d.pop(ll)

    @classmethod
    def _renombrar_dist(cls, d, nombre_ant, nombre_nuevo):
        """
        Esta función cambia el nombre de una distribución en un diccionario de coeficientes.

        :param d: El diccionario de coeficientes.
        :type d: dict

        :param nombre_ant: El nombre actual de la distribución.
        :type nombre_ant: str

        :param nombre_nuevo: El nuevo nombre de la distribución.
        :type nombre_nuevo: str

        """

        # Para cada itema (llave, valor) del diccionario
        for ll, v in d.items():

            if type(v) is dict:

                # Si el itema era otro diccionario, llamar esta función de nuevo con el nuevo diccionario
                cls._renombrar_dist(v, nombre_ant=nombre_ant, nombre_nuevo=nombre_nuevo)

            elif type(v) is str:

                # Cambiar el nombre de la llave
                if ll == nombre_ant:
                    # Crear una llave con el nuevo nombre
                    d[nombre_nuevo] = d[ll]

                    # Quitar el viejo nombre
                    d.pop(ll)

    @staticmethod
    def _apriori_de_existente(lista_objs, clase_objs):
        """
        Esta función genera valores a prioris de un objeto existente.

        :param lista_objs:
        :type lista_objs: list[Coso]

        :param clase_objs:
        :type clase_objs: type | Coso

        """

        dic_info_ecs = clase_objs.dic_info_ecs

        # Unas funciones útiles:
        # 1) Una función para generar un diccionario vacío con la misma estructura que el diccionario de ecuaciones
        def gen_dic_vacío(d, d_copia=None):
            if d_copia is None:
                d_copia = []

            for ll, v in d.items():
                if 'límites' not in d:
                    d_copia[ll] = {}
                    gen_dic_vacío(v, d_copia=d_copia[ll])
                else:
                    d_copia[ll] = []

            return d_copia

        # 2) Una función para copiar_profundo las trazas de un diccionario de coeficientes de un objeto
        def sacar_trazas(d_fuente, d_final):
            """

            :param d_fuente:
            :type d_fuente: dict

            :param d_final:
            :type d_final: dict

            """

            def iter_sacar_trazas(d, l=None):
                """

                :param d:
                :type d: dict

                :param l:
                :type l: list

                :return:
                :rtype: list

                """

                if l is None:
                    l = []

                for val in d.values():
                    if type(val) is dict:
                        iter_sacar_trazas(val, l=l)
                    elif type(val) is np.ndarray:
                        np.append(l, val)
                    else:
                        pass
                return l

            for ll, v in d_final.items():

                if type(v) is dict:
                    sacar_trazas(d_fuente=d_fuente[ll], d_final=v)
                elif type(v) is list:
                    nuevas_trazas = iter_sacar_trazas(d_fuente[ll])
                    d_final[ll].append(nuevas_trazas)

        # 3) Una función para generar aprioris desde trazas
        def gen_aprioris(d, d_ecs):
            """

            :param d:
            :type d: dict

            :param d_ecs:
            :type d_ecs: dict

            """

            for ll, v in d.items():
                if type(v) is dict:
                    gen_aprioris(v, d_ecs=d_ecs[ll])

                elif type(v) is list:
                    datos = np.concatenate(v)
                    try:
                        cont = d_ecs['cont']
                    except KeyError:
                        cont = True

                    líms = d_ecs['límites']

                    dist = VarSciPy.ajust_dist(datos=datos, cont=cont, líms=líms)
                    d[ll] = dist.a_texto()

        # Generar un diccionario para guardar los a prioris
        dic_aprioris = gen_dic_vacío(dic_info_ecs)

        # Asegurarse que todos los objetos sean de la clase especificada.
        if not all([x.ext == clase_objs for x in lista_objs]):
            raise ValueError

        # Agregar el a priori de cada objeto a la lista para cada parámetro
        for obj in lista_objs:
            d_coefs = obj.receta['coefs']
            sacar_trazas(d_fuente=d_coefs, d_final=dic_aprioris)

        # Convertir trazas a distribuciones en formato texto
        gen_aprioris(d=dic_aprioris, d_ecs=dic_info_ecs)

    def __str__(símismo):
        return símismo.nombre


class Simulable(Coso):
    """
    Una subclase de Coso para objetos que se pueden simular y calibrar. (Por ejemplo, una Red AgroEcológica o una
    Parcela, pero NO un Insecto.
    """

    def __init__(símismo, nombre, proyecto):
        """
        Un simulable se inicia como Coso.

        :param nombre: El nombre del simulable
        :type nombre: str

        """

        # Primero, llamamos la función de inicio de la clase pariente 'Coso'
        super().__init__(nombre=nombre, proyecto=proyecto)

        # Añadir Calibraciones a la receta del Simulable. Este únicamente guarda la información sobre cada calibración.
        #   (Los resultados de las calibraciones se guardan en "coefs".
        if 'Calibraciones' not in símismo.receta:
            símismo.receta['Calibraciones'] = {'0': "A prioris no informativos generados automáticamente por Tiko'n."}

        # Un experimento interno al objeto. Muy útil para pequeñas simulaciones de exploración y con pocos datos.
        símismo.Experimento = Experimento(nombre='Intrínsico', proyecto=proyecto)

        # Indica si el Simulable está listo para una simulación.
        símismo.listo = False

        # Contendrá el objeto de modelo Bayesiano para la calibración
        símismo.ModCalib = None  # type: ModCalib

        # Experimentos asociados
        símismo.exps = {}

        # Parámetros activos en la simulación actual.
        símismo.coefs_act = {}
        símismo.coefs_act_númzds = {}

        #
        # NUNCA recrear este diccionario. Lo puedes borrar con .clear() en vez.
        símismo.dic_simul = {
            'd_predics_exps': {},
            'd_l_í_valid': {},
            'matrs_valid': {},
            'd_l_m_valid': {},
            'd_l_m_predics_v': {},
            'd_obs_valid': {},
            'd_obs_calib': {},
            'l_m_obs_todas': [],
            'l_días_obs_todas': [],
            'd_l_í_calib': {},
            'l_m_preds_todas': [],
            'l_ubics_m_preds': [],
            'd_calib': {},
            'inic_d_predics_exps': {}
        }
        símismo.predics_exps = símismo.dic_simul['d_predics_exps']  # Simplificación del código

        # Predicciones de datos (para simulaciones normales)
        símismo.predics = {}

    def info_clima(símismo):

        raise NotImplementedError

    def actualizar(símismo):
        """
        Esta función actualiza las matrices internas del Simulable para prepararlo para una simulación.
        Se aplica individualmente en todas las subclases de Simulable, que también deben poner símismo.listo = True
        al final.

        """

        raise NotImplementedError

    def incrementar(símismo, paso, i, detalles, extrn):
        """
        Esta función incrementa el modelo por un paso. Se tiene que implementar en cada subclase de Simulable.

        :param paso: El paso con cual incrementar el modelo
        :type paso: int

        :param i: El número de este incremento en la simulación
        :type i: int

        :param detalles: Si hay que hacer la simulación con resultaodos detallados o rápidos.
        :type detalles: bool

        :param extrn: Un diccionario de valores externos al modelo, si necesario
        :type extrn: dict

        """

        # Dejamos la implementación del incremento del modelo a las subclases individuales.
        raise NotImplementedError

    def _incrementar_depurar(símismo, paso, i, detalles, extrn, d_tiempo):
        raise NotImplementedError

    def simular(símismo, exper=None, nombre=None, paso=1, tiempo_final=None, n_rep_parám=100, n_rep_estoc=100,
                calibs='Todos', usar_especificadas=False, detalles=True, dibujar=True, directorio_dib=None,
                mostrar=True, opciones_dib=None, dib_dists=True, valid=False, depurar=False):
        """
        Esta función corre una simulación del Simulable.

        :param exper: Los experimentos para incluir en la simulación.
        :type exper: list | str | Experimento | None

        :param nombre: El nombre de la simulación.
        :type nombre: str

        :param paso: El paso de tiempo para la simulación
        :type paso: int

        :param tiempo_final: El tiempo final para la simulación.
        :type tiempo_final: dict | int

        :param n_rep_parám: El número de repeticiones paramétricas para incluir en la simulación.
        :type n_rep_parám: int

        :param n_rep_estoc: El número de repeticiones estocásticas para incluir en la simulación
        :type n_rep_estoc: int

        :param calibs: El nombre de la calibración que utilizar, o una lista de calibraciones para utilizar.
        :type calibs: list | str

        :param dibujar: Si hay que generar gráficos de los resultados.
        :type dibujar: bool

        :param mostrar: Si hay que mostrar los gráficos de la simulación. No hace nada si dibujar == False.
        :type mostrar: bool

        :param usar_especificadas: Si vamos a utilizar distribuciones a prioris especificadas por el usuario o no.
        :type usar_especificadas: bool

        :param opciones_dib: Un diccionario de opciones de dibujo a pasar a la función de generación de gráficos
        :type opciones_dib: dict

        :param directorio_dib: El directorio en el cuál guardar los dibujos de los resultados, si aplica.
        :type directorio_dib: str

        :param detalles: Para unos Simulables, especifica si hay que guardar resultados rápidos o detallados.
        :type detalles: bool

        :param dibujar: Si hay que generar gráficos de los resultados.
        :type dibujar: bool

        :param dib_dists: Si hay que dibujar las distribuciones utilizadas para la simulación.
        :type dib_dists: bool

        """

        # Validar el nombre de la simulaión
        nombre = símismo._valid_nombre_simul(nombre=nombre)

        # Cambiar no opciones de dibujo a un diccionario vacío
        if opciones_dib is None:
            opciones_dib = {}

        if directorio_dib is None:
            directorio_dib = os.path.join(símismo.proyecto, símismo.nombre, nombre, 'Grf simul')

        directorio_dib = símismo._prep_directorio(directorio=directorio_dib)

        # Actualizar el objeto
        símismo.actualizar()

        # Permitir que se use el experimento intrínsico de la Red si no se especificó otra cosa.
        if exper is None:
            exper = símismo.Experimento
            símismo.añadir_exp(exper)  # Para hacer

        # Poner los experimentos en la forma correcta:
        exper = símismo._prep_lista_exper(exper=exper)

        # Poner el tiempo final en la forma correcta
        if type(tiempo_final) is int:
            t_final = tiempo_final
            tiempo_final = {}
            for exp in exper:
                tiempo_final[exp] = t_final

        # Preparar la lista de parámetros de interés
        lista_paráms, _, ubics_paráms = símismo._gen_lista_coefs_interés_todos()
        lista_calibs = símismo._filtrar_calibs(calibs=calibs, l_paráms=lista_paráms,
                                               usar_especificadas=usar_especificadas)

        # Generar los vectores de coeficientes. Si es una simulación de análisis de sensibilidad, no tendrá impacto,
        # porque no cambiará el orden de los vectores de valores de parámetros ya establecido.
        Incert.trazas_a_dists(id_simul=nombre, l_d_pm=lista_paráms, l_trazas=lista_calibs, formato='valid',
                              comunes=(calibs == 'Comunes'), n_rep_parám=n_rep_parám)

        # Llenar las matrices internas de coeficientes
        símismo._llenar_coefs(nombre_simul=nombre, n_rep_parám=n_rep_parám, ubics_paráms=ubics_paráms,
                              dib_dists=dib_dists, calibs=lista_calibs)

        # Simular los experimentos
        dic_argums = símismo._prep_args_simul_exps(exper=exper, paso=paso, tiempo_final=tiempo_final)
        símismo._prep_dic_simul(exper=exper, n_rep_estoc=n_rep_estoc, n_rep_paráms=n_rep_parám, paso=paso,
                                n_pasos=dic_argums['n_pasos'], detalles=detalles, tipo='valid' if valid else 'simul')
        símismo._simul_exps(**dic_argums, paso=paso, detalles=detalles, devolver_calib=False, depurar=depurar)

        # Borrar los vectores de coeficientes temporarios
        símismo.borrar_calib(id_calib=nombre)

        # Si hay que dibujar, dibujar
        if dibujar:
            símismo.dibujar(exper=exper, directorio=directorio_dib, mostrar=mostrar, **opciones_dib)

    def calibrar(símismo, nombre=None, aprioris=None, exper=None, paso=1, n_rep_estoc=10, tiempo_final=None,
                 n_iter=10000, quema=100, extraer=10, método='Metrópolis adaptivo', pedazitos=None,
                 usar_especificadas=True, dibujar=False, depurar=False):
        """
        Esta función calibra un Simulable. Para calibrar un modelo, hay algunas cosas que hacer:
          1. Estar seguro de el el nombre de la calibración sea válido
          2. Preparar listas de parámetros a calibrar, tanto como de sus límites matemáticas (para estar seguro de no
             calibrar un parámetro afuera de sus límites teoréticas).
          3. Generar la lista de nombres de calibraciones anteriores para emplear como distribuciones a prioris
             en la calibración de cada parámetro.
          4. Preparar los argumentos para la calibración, dado los experimentos vinculados.
          5. Generar un vector unidimensional, en orden reproducible, de las observaciones de los experimentos (para
             comparar más rápido después con las predicciones del modelo).
          6. Crear el modelo (ModCalib) para la calibración
          7. Por fin, calibrar el modelo.

        :param nombre: El nombre de la calibración.
        :type nombre: str

        :param aprioris: Las calibraciones anteriores que hay que utilizar para los a prioris.
        :type aprioris: int | str | list | None

        :param exper: Los experimentos vinculados al objeto a usar para la calibración. exper=None lleva al uso de
          todos los experimentos disponibles.
        :type exper: list | str | Experimento | None

        :param paso: El paso para la calibración.
        :type paso: int

        :param n_rep_estoc: El número de repeticiones estocásticas.
        :type n_rep_estoc: int

        :param n_iter: El número de iteraciones para la calibración.
        :type n_iter: int

        :param quema: El número de iteraciones iniciales que hay que botar. (Para evitar el efecto de condiciones
          iniciales en la calibración).
        :type quema: int

        :param extraer: Cada cuantas iteraciones guardar (para limitar el efecto de autocorrelación entre iteraciones).
          extraer = 1 lleva al uso de todas las iteraciones.
        :type extraer: int

        :param dibujar: Si queremos dibujar los resultados de las calibraciones (cambios en distribuciones de
          parámetros) o no.
        :type dibujar: bool

        """

        # 0. Actualizar
        símismo.actualizar()

        # 1. Primero, validamos el nombre y, si necesario, lo creamos.
        nombre = símismo._valid_nombre_simul(nombre=nombre)

        # 4. Preparar el diccionario de argumentos para la función "simul_calib", según los experimentos escogidos
        # para la calibración.
        exper = símismo._prep_lista_exper(exper=exper)  # La lista de experimentos

        # 0.5 Hacer calibración por pedazitos, si lo queremos
        nombre_pdzt_ant = None
        if pedazitos is not None:

            tiempo_final = símismo._obt_tiempo_final(exper=exper, tiempo_final=tiempo_final)

            for f in range(1, pedazitos):

                nombre_pedazito = nombre + '_pdzt_{}'.format(f)

                símismo.calibrar(nombre=nombre_pedazito,
                                 aprioris=aprioris, exper=exper, paso=paso, n_rep_estoc=n_rep_estoc,
                                 n_iter=n_iter, quema=quema, extraer=extraer, método=método,
                                 tiempo_final={exp: int(tiempo_final[exp] * f / pedazitos) for exp in tiempo_final},
                                 pedazitos=None,  # Queremos cada subcalibración sin sus propias pedazitos
                                 usar_especificadas=usar_especificadas if f == 1 else False,
                                 dibujar=False, depurar=depurar)
                símismo.guardar_calib(descrip='Pedazito {} de calib {}'.format(f, nombre),
                                      utilizador='Interno a Tiko\'n. Nunca debería de ver esta calibración.',
                                      contacto=__correo__)

                if nombre_pdzt_ant is not None:
                    símismo.borrar_calib(id_calib=nombre_pdzt_ant)

                nombre_pdzt_ant = nombre_pedazito

                # Actualizar los aprioris
                aprioris = nombre_pedazito

        dic_argums = símismo._prep_args_simul_exps(exper=exper, paso=paso, tiempo_final=tiempo_final)
        dic_argums['paso'] = paso  # Guardar el paso en el diccionario también
        dic_argums['detalles'] = False  # Queremos una simulación rápida para calibraciones...  # Para hacer
        dic_argums['devolver_calib'] = True  # ...pero sí tenemos que vectorizar las predicciones.
        dic_argums['depurar'] = depurar

        símismo._prep_dic_simul(exper=exper, n_rep_estoc=n_rep_estoc, n_rep_paráms=1, paso=paso,
                                n_pasos=dic_argums['n_pasos'], detalles=False, tipo='calib')

        # 2. Creamos la lista de parámetros que hay que calibrar
        lista_paráms, lista_líms, nombres = símismo._gen_lista_coefs_interés_todos()
        guardar_json({'parám_{}'.format(i): n for i, n in enumerate(nombres)},
                     os.path.join(os.path.split(__file__)[0], 'paráms.txt'))

        # 3. Filtrar coeficientes por calib
        lista_aprioris = símismo._filtrar_calibs(calibs=aprioris, l_paráms=lista_paráms,
                                                 usar_especificadas=usar_especificadas)

        # 5. Conectar a las observaciones
        d_obs = símismo.dic_simul['d_obs_calib']  # type: dict[dict[np.ndarray]]

        # 6. Creamos el modelo ModCalib de calibración, lo cual genera variables PyMC
        if método.lower() == 'metrópolis' or método.lower() == 'metrópolis adaptivo':
            símismo.ModCalib = ModBayes(función=símismo._simul_exps,
                                        dic_argums=dic_argums,
                                        d_obs=d_obs,
                                        lista_d_paráms=lista_paráms,
                                        aprioris=lista_aprioris,
                                        lista_líms=lista_líms,
                                        id_calib=nombre,
                                        función_llenar_coefs=símismo._llenar_coefs,
                                        método=método
                                        )
        elif método.lower() == 'glue':
            símismo.ModCalib = ModGLUE()

        else:
            raise ValueError

        if nombre_pdzt_ant is not None:
            símismo.borrar_calib(id_calib=nombre_pdzt_ant)

        # 7. Calibrar el modelo, llamando las ecuaciones bayesianas a través del objeto ModCalib
        símismo.ModCalib.calib(rep=n_iter, quema=quema, extraer=extraer)

        # 8. Si querríamos dibujos de la calibración, hacerlos ahora
        if dibujar:
            símismo.dibujar_calib()

    def avanzar_calib(símismo, rep=10000, quema=100, extraer=10):
        """
        Añade a una calibración ya empezada.

        :param rep: El número de iteraciones extras.
        :type rep: int

        :param quema: El número de iteraciones iniciales que hay que botar.
        :type quema: int

        :param extraer: Cada cuántas iteraciones guardar.
        :type extraer: int

        """

        # Si ya no existe un modelo de calibración, no podemos avanzarla.
        if símismo.ModCalib is None:
            raise TypeError('Hay que iniciar una calibración antes de avanzarla.')

        # Avanzar la calibración.
        símismo.ModCalib.calib(rep=rep, quema=quema, extraer=extraer)

    def guardar_calib(símismo, descrip, utilizador, contacto=''):
        """
        Esta función guarda una calibración existente para uso futuro.

        :param descrip: La descripción de la calibración (para referencia futura).
        :type descrip: str

        :param utilizador: El nombre del utilizador que hizo la calibración.
        :type utilizador: str

        :param contacto: El contacto del utilizador
        :type contacto: str

        """

        # Si no hay modelo, no hay nada para guardar.
        if símismo.ModCalib is None:
            raise ValueError('No hay calibraciones para guardar.')

        # La fecha y hora a la cual se guardó
        ahora = ft.now().strftime('%Y-%m-%d %H:%M:%S')

        # El nombre de identificación de la calibración.
        nb = símismo.ModCalib.id

        # Guardar la descripción de esta calibración en el diccionario del objeto
        símismo.receta['Calibraciones'][nb] = dict(Descripción=descrip,
                                                   Fecha=ahora,
                                                   Utilizador=utilizador,
                                                   Contacto=contacto,
                                                   Config=copiar.deepcopy(símismo.receta['estr']))

        # Guardar los resultados de la calibración
        símismo.ModCalib.guardar()

        # Borrar el objeto de modelo, ya que no se necesita
        símismo.ModCalib = None

    def añadir_exp(símismo, experimento, corresp):
        """
        Esta función añade un experimento al Simulable.

        :param experimento: El experimento para añadir
        :type experimento: Experimento

        :param corresp: Un diccionario con la información necesaria para hacer la conexión entre el experimento
        y las predicciones del Simulable.
        :type corresp: dict

        """

        # Si necesario, actualizar el Simulable
        if not símismo.listo:
            símismo.actualizar()

        símismo.exps[experimento.nombre] = {'Exp': experimento, 'Corresp': corresp}

        símismo._actualizar_vínculos_exps()

    def validar(símismo, exper, nombre=None, calibs=None, paso=1, n_rep_parám=20, n_rep_estoc=20,
                usar_especificadas=False, detalles=False, guardar=True,
                dibujar=True, mostrar=False, opciones_dib=None, dib_dists=True, depurar=False):
        """
        Esta función valida el modelo con datos de observaciones de experimentos.

        :param exper: Los experimentos vinculados al objeto a usar para la calibración. exper=None lleva al uso de
        todos los experimentos disponibles.
        :type exper: list | str | Experimento | None

        :param nombre: El nombre de la validación.
        :type nombre: str

        :param calibs: Las calibraciones que hay que usar para la validación. Si calibs == None, se usará la
        calibración activa, si hay; si no hay, se usará todas las calibraciones existentes.
        :type calibs: list | str | None

        :param paso: El paso para la validación
        :type paso: int

        :param n_rep_parám: El número de repeticiones de parámetros.
        :type n_rep_parám: int

        :param n_rep_estoc: El número de repeticiones estocásticas.
        :type n_rep_estoc: int

        :param detalles: Para unos Simulables, especifica si hay que guardar resultados rápidos o detallados.
        :type detalles: bool

        :param guardar: Si hay que guardar los resultados dela validación
        :type guardar: bool

        :param dibujar: Si hay que generar gráficos de los resultados.
        :type dibujar: bool

        :param usar_especificadas: Si vamos a utilizar distribuciones a prioris especificadas por el usuario o no.
        :type usar_especificadas: bool

        :param opciones_dib: Argumentos opcionales para pasar a la función de dibujo de resultados.
        :type opciones_dib: dict

        :param mostrar: Si hay que mostrar los gráficos generados
        :type mostrar: bool

        :param dib_dists: Si hay que dibujar las distribuciones utilizadas para la simulación.
        :type dib_dists: bool

        :param dib_dists: Si hay que dibujar las distribuciones utilizadas para la simulación.
        :type dib_dists: bool

        :return: Un diccionario con los resultados de la validación.
        :rtype: dict
        """

        # Si no se especificaron calibraciones para validar, tomamos la calibración activa, si hay, y en el caso
        # contrario tomamos el conjunto de todas las calibraciones anteriores.
        if calibs is None:
            if símismo.ModCalib is None:
                calibs = 'Todos'
            else:
                calibs = símismo.ModCalib.id

        nombre = símismo._valid_nombre_simul(nombre)

        # Simular los experimentos
        símismo.simular(nombre=nombre, exper=exper, paso=paso, n_rep_parám=n_rep_parám, n_rep_estoc=n_rep_estoc,
                        calibs=calibs, usar_especificadas=usar_especificadas, detalles=detalles,
                        dibujar=dibujar, mostrar=mostrar,
                        opciones_dib=opciones_dib, dib_dists=dib_dists, valid=True, depurar=depurar)

        # Procesar los datos de la validación
        símismo._procesar_valid()
        valid = símismo._analizar_valid()

        if guardar:
            direc = os.path.join(símismo.proyecto, símismo.nombre, nombre)
            direc = símismo._prep_directorio(directorio=direc)
            archivo = os.path.join(direc, 'valid.json')

            guardar_json(dic=valid, archivo=archivo)

        return valid

    def sensibilidad(símismo, nombre, exper, n, método='Sobol', calibs=None, por_dist_ingr=0.95,
                     n_rep_estoc=30, tiempo_final=None, detalles=False, usar_especificadas=True,
                     opciones_sens=None, dibujar=False):
        """
        Esta función calcula la sensibilidad de los parámetros del modelo. Puede aplicar varios tipos de análisis de
        sensibilidad.

        :param nombre: El nombre para la simulación de incertidumbre.
        :type nombre: str
        :param exper: Los experimentos para incluir.
        :type exper: str | list | Experimento
        :param n: El número de valores de parámetros para intentar.
        :type n: int
        :param método: El método de análisis. Puede ser uno de `Sobol`, `FAST`, `Morris`, `DMIM`, `DGSM`, o `FF`. Ver
        el paquete `SALib` para más detalles.
        :type método: str
        :param calibs: Las calibraciones para incluir en el análisis.
        :type calibs: list | str
        :param por_dist_ingr: El porcentaje de las distribuciones cumulativas de los parámetros para incluir en el
        análisis.
        :type por_dist_ingr: float | int
        :param n_rep_estoc: El número de repeticiones estocásticas.
        :type n_rep_estoc: int
        :param tiempo_final: El tiempo final de la simulación
        :type tiempo_final: int
        :param detalles: Si quieres simular con detalles (o no).
        :type detalles: bool
        :param usar_especificadas: Si hay que utilizar a prioris especificados.
        :type usar_especificadas: bool
        :param opciones_sens: Opciones específicos al método de análisis de sensibilidad.
        :type opciones_sens: dict
        :param dibujar: Si hay que dibujar los resultados.
        :type dibujar: bool
        :return: Un tuple de la lista de nombres de los párámetros y de un diccionario con los resultados.
        :rtype: (list[list], dict)
        """

        # Validar el nombre de la simulación para esta corrida
        nombre = símismo._valid_nombre_simul(nombre=nombre)

        # Poner los experimentos en la forma correcta
        exper = símismo._prep_lista_exper(exper=exper)

        #
        if opciones_sens is None:
            opciones_sens = {}

        # La lista de diccionarios de parámetros y de sus límites teoréticos
        lista_paráms, lista_líms, nombres_paráms = símismo._gen_lista_coefs_interés_todos()

        # Las calibraciones para utilizar para el análisis
        lista_calibs = símismo._filtrar_calibs(calibs=calibs, l_paráms=lista_paráms,
                                               usar_especificadas=usar_especificadas)

        # Una lista de las distribuciones de los parámetros. Esta función también llena los diccionarios de los
        # parámetros con estas mismas distribuciones.
        lista_dists = Incert.trazas_a_dists(id_simul=nombre, l_d_pm=lista_paráms, l_trazas=lista_calibs,
                                            formato='sensib', comunes=False, l_lms=lista_líms, n_rep_parám=1000)

        # Basado en las distribuciones de los parámetros, establecer los límites para el análisis de sensibilidad
        lista_líms_efec = Incert.dists_a_líms(l_dists=lista_dists, por_dist_ingr=por_dist_ingr)

        # Definir los parámetros del análisis en el formato que le gusta al paquete SALib.
        i_acetables = [i for i, lms in enumerate(lista_líms_efec) if lms[0] != lms[1]]
        nombres = [str(x) for x in range(len(lista_paráms))]  # Nombres numéricos muy sencillos
        n_paráms = len(i_acetables)  # El número de parámetros para el análisis de sensibilidad
        problema = {
            'num_vars': n_paráms,  # El número de parámetros
            # Nombres numéricos muy sencillos
            'names': [n for i, n in enumerate(nombres) if i in i_acetables],
            # La lista de los límites de los parámetros para el analisis de sensibilidad
            'bounds': [n for i, n in enumerate(lista_líms_efec) if i in i_acetables]
        }

        # Finalmente, hacer el análisis de sensibilidad. Primero generamos los valores de parámetros para intentar.
        vals_paráms, fun_anlz, ops_anlz = prep_anal_sensib(método, n=n, problema=problema, opciones=opciones_sens)

        # Aplicar las matrices de parámetros generadas a los diccionarios de coeficientes. Las con distribuciones sin
        # incertidumbre guardarán su distribución SciPy original.
        for i in i_acetables:
            i_rel = i_acetables.index(i)
            lista_paráms[i][nombre] = vals_paráms[:, i_rel]

        # El número de repeticiones paramétricas
        n_rep_parám = vals_paráms.shape[0]

        # Correr la simulación. Hay que poner usar_especificadas=False aquí para evitar que distribuciones
        # especificadas tomen el lugar de las distribuciones que acabamos de generar por SALib. gen_dists=True
        # asegurar que se guarde el orden de los valores de los variables tales como especificados por SALib.
        símismo.simular(exper=exper, nombre=nombre, calibs=nombre, detalles=detalles, tiempo_final=tiempo_final,
                        n_rep_parám=n_rep_parám, n_rep_estoc=n_rep_estoc, usar_especificadas=False,
                        dibujar=False, mostrar=False, dib_dists=False)

        # Procesar las matrices
        l_matrs_proc, ubics_m = símismo._procesar_matrs_sens()

        # Borrar las distribuciones creadas para el análisis
        símismo.borrar_calib(id_calib=nombre)

        # Una lista para guardar los resultados. Cada diccionario en la lista tiene el formato siguiente:
        # {índice_sensibilidad1: [matriz de resultados, eje 0 = parám, (eje 1 = parám2), eje -1 = día)],
        #  índice_sensibilidad2: ...}
        l_d_sens = []

        # Por fin, analizar la sensibilidad
        for m in l_matrs_proc:
            # Para cada matriz procesada...

            # El diccionario para los resultados
            d_sens = {}

            # Agregarlo a la lista de resultados
            l_d_sens.append(d_sens)

            # Llenar la matriz de resultados para cada día de simulación
            n_días = m.shape[1]
            for d in range(n_días):
                # Para cada día de simulación...

                # Analizar la sensibilidad
                d_egr_sens = fun_anlz(problema, Y=m[:, d], **ops_anlz)

                for egr, m_egr in d_egr_sens.items():
                    # Para cada tipo de egreso del análisis de sensibilidad...

                    # Crear la matriz de resultados vacía, si necesario
                    if egr not in d_sens:
                        d_sens[egr] = np.zeros((*m_egr.shape, n_días))

                    # Llenar los datos para este día
                    d_sens[egr][..., d] = d_egr_sens[egr]

        # Convertir la lista de resultados de AS a un diccionario de resultados para devolver al usuario
        resultado = llaves_a_dic(l_ubics=ubics_m, vals=l_d_sens)

        # Si necesario, dibujar los resultados
        if dibujar:

            for ubic, d in zip(ubics_m, l_d_sens):
                # Para cada matriz de análisis de sensibilidad...

                for índ, m in d.items():
                    # Para cada índice de sensibilidad y su matriz de resultados correspondiente...

                    # El directorio del gráfico
                    direc = os.path.join(símismo.proyecto, símismo.nombre, nombre, *ubic)
                    direc = símismo._prep_directorio(directorio=direc)

                    if len(m.shape) == 2:
                        # Si no tenemos interacción de parámetros...

                        for i, prm in enumerate(nombres_paráms):
                            # Para cada parámetro...

                            # El título del gráfico
                            título = '{}: {}'.format(prm, índ)

                            # Dibujar el gráfico
                            Arte.graficar_línea(datos=m[i, :], título=título, etiq_y='{}: {}'.format(método, índ),
                                                etiq_x='Día', directorio=direc)
                    elif len(m.shape) == 3:
                        # Si tenemos interacciones entre parámetros...

                        for i, prm_1 in enumerate(nombres_paráms):
                            # Para cada parámetro...

                            for j, prm_2 in enumerate(nombres_paráms):
                                # Para cada parámetro otra vez...

                                # El título del gráfico
                                título = '{}-{}: {}'.format(prm_1, prm_2, índ)

                                # Dibujar el gráfico
                                Arte.graficar_línea(datos=m[i, j, :], título=título,
                                                    etiq_y='{}: {}'.format(método, índ), etiq_x='Día', directorio=direc)
                    else:
                        # Si tenemos otra forma de matriz, no sé qué hacer.
                        raise ValueError('Número de ejes ({}) inesperado. Quejarse al programador.'
                                         .format(len(m.shape)))

        # Devolver los resultados
        return nombres_paráms, resultado

    def dibujar(símismo, mostrar=True, directorio=None, exper=None, **kwargs):
        """
        Una función para generar gráficos de los resultados del objeto.

        :param mostrar: Si vamos a mostrar el gráfico al usuario de manera interactiva.
        :type mostrar: bool

        :param directorio: Donde vamos a guardar el gráfico. archivo = None indica que no se guardará el archivo.
        :type directorio: str

        :param exper: Una lista de los experimentos para dibujar. Con exper=None, tomamos los experimentos de la
        última calibración o validación.
        :type exper: list

        """

        raise NotImplementedError

    def _llenar_coefs(símismo, nombre_simul, n_rep_parám, dib_dists, ubics_paráms=None, calibs=None):
        """
        Transforma los diccionarios de coeficientes a matrices internas (para aumentar la rapidez de la simulación).
        Las matrices internas, por supuesto, dependerán del tipo de Simulable en cuestión. No obstante, todas
          tienen la forma siguiente: eje 0 = repetición paramétrica, eje 1+ : dimensiones opcionales.

        :param n_rep_parám: El número de repeticiones paramétricas que incluir.
        :type n_rep_parám: int

        :param calibs: Una lista de los nombres de las calibraciones, o el nomre de una calibración, que hay que
          incluir.
        :type calibs: list | str


        """

        raise NotImplementedError

    def _calc_simul(símismo, paso, n_pasos, detalles, extrn=None, depurar=False):
        """
        Esta función aumenta el modelo para cada paso en la simulación. Se usa en simulaciones normales, tanto como en
          simulaciones de experimentos.

        :param paso: El paso para la simulación
        :type paso: int

        :param n_pasos: El número de pasos en la simulación.
        :type n_pasos: int

        :param extrn: Un diccionario externo, si necesario, con información para la simulación.
        :type extrn: dict

        """

        # Cosas que hay que hacer justo antes de simular
        símismo._numerizar_coefs()
        símismo._justo_antes_de_simular()

        if not depurar:
            # Para cada paso de tiempo, incrementar el modelo
            for i in range(1, n_pasos):  # para hacer: ¿n_pasos o n_pasos+1?
                símismo.incrementar(paso, i=i, detalles=detalles, extrn=extrn)
        else:
            # Para cada paso de tiempo, incrementar el modelo
            d_tiempo = {}
            for i in range(1, n_pasos):  # para hacer: ¿n_pasos o n_pasos+1?
                d_tiempo = símismo._incrementar_depurar(paso, i=i, detalles=detalles, extrn=extrn, d_tiempo=d_tiempo)

            t_total_interno = sum(v for v in d_tiempo.values())

            print('Descomposición de tiempo de simulación\n')
            print('\t{:<13}{:>12}{:>14}'.format('Cálculo', 'Segundos', '% del total'))
            for ll, v in d_tiempo.items():
                print('\t{:<13}{:12.2f}{:12.2f} %'.format(ll, v, v / t_total_interno * 100))

    def _gen_lista_coefs_interés_todos(símismo):

        """
        Esta función devuelve una lista de todos los coeficientes de un Simulable y de sus objetos de manera
        recursiva, tanto como una lista, en el mismo orden, de los límites de dichos coeficientes.

        :return: Un tuple conteniendo una lista de todos los coeficientes de interés para la calibración y una lista
        de sus límites, seguido por una lista de las ubicaciones de cada parámetro.
        :rtype: (list, list, list)

        """

        def sacar_coefs_recursivo(objeto):
            """
            La implementación recursiva de la función.

            :param objeto: El objeto Coso a cual hay que sacar los coeficientes.
            :type objeto: Coso

            :return: Un tuple, como descrito en la documentación de la función arriba.
            :rtype: (list, list)
            """

            # Inicializar las listas de coeficientes y de límites con los coeficientes y límites del objeto actual.
            lista_coefs, lista_nombres = objeto._sacar_coefs_interno()
            lista_líms = objeto._sacar_líms_coefs_interno()

            if isinstance(objeto, Simulable):
                # Ahora, hacer lo mismo para cada objeto Simulable contenido en este objeto.
                for obj in objeto.objetos:
                    resultado = sacar_coefs_recursivo(obj)
                    lista_coefs += resultado[0]
                    lista_líms += resultado[1]
                    lista_nombres += [[obj.nombre] + x for x in resultado[2]]

            # Devolver la lista de coeficientes y la lista de límites
            return lista_coefs, lista_líms, lista_nombres

        # Implementar la función recursiva arriba
        return sacar_coefs_recursivo(símismo)

    def _sacar_coefs_interno(símismo):
        """
        Esta función genera una lista de los coeficientes propios al objeto de interés para la calibración actual.
        Se debe implementar para cada Coso (objeto) que tiene coeficientes.

        :return: Una lista de diccionarios de coeficientes, con el formato siguiente:
           [ {calib1: distribución o [lista de valores],
              calib2: ibid,
              ...},
              {coeficiente 2...},
              ...
           ]
        :rtype: list

        """

        raise NotImplementedError

    def _sacar_líms_coefs_interno(símismo):
        """
        Esta función genera una lista de las límites de los coeficientes propios al objeto de interés para la
        calibración actual. Se debe implementar para cada Coso (objeto) que tiene coeficientes.

        :return: Un tuple, conteniendo:
          1. Una lista de diccionarios de coeficientes, con el formato siguiente:
           [ {calib1: distribución o [lista de valores],
              calib2: ibid,
              ...},
              {coeficiente 2...},
              ...
           ]

           2. Una lista de los límites de los coeficientes, en el mismo orden que (1.)
        :rtype: (list, list)

        """

        raise NotImplementedError

    def _actualizar_vínculos_exps(símismo):
        """
        Esta función agrega un Experimento a un Simulable y conecta las predicciones futuras del Simulable con
          los datos contenidos en el Experimento.

        """

        raise NotImplementedError

    def _prep_args_simul_exps(símismo, exper, paso, tiempo_final):
        """
        Prepara un diccionaro de los argumentos para simul_exps. El diccionario debe de tener la forma elaborada
        abajo. Se implementa para cada subclase de Simulable.

        :param exper: Una lista de los nombres de los experimentos para incluir
        :type exper: list

        :param tiempo_final: Un diccionario del tiempo final para cada experimento. Un valor de 'None' resulta en
        tomar el último día de datos disponibles para cada experimento como su tiempo final.
        :type tiempo_final: dict | None

        :return: Un diccionario del formato siguiente:
           {
            n_pasos: {},
            extrn: {}
            }
          Donde cada elemento del diccionario es un diccionario con los nombres de los experimentos como llaves.
        :rtype: dict

        """

        dic_args = dict(n_pasos={},
                        extrn={})

        # Determinar el tiempo final, si es necesario
        if tiempo_final is None:
            tiempo_final = símismo._obt_tiempo_final(exper=exper)

        # Para cada experimento...
        for exp in exper:
            obj_exp = símismo.exps[exp]['Exp']

            # La superficie de cada parcela (en ha)
            parc = obj_exp.obt_parcelas(tipo=símismo.ext)
            tamaño_parcelas = obj_exp.superficies(parc=parc)

            n_pasos = mat.ceil(tiempo_final[exp] / paso) + 1

            # También guardamos el número de pasos y las superficies de las parcelas.
            dic_args['n_pasos'][exp] = n_pasos
            dic_args['extrn'][exp] = {'superficies': tamaño_parcelas}

        return dic_args

    def _obt_tiempo_final(símismo, exper, tiempo_final=None):
        """

        :param exper:
        :type exper:
        :return:
        :rtype: dict
        """

        if tiempo_final is None:
            return {exp: símismo.exps[exp]['Exp'].tiempo_final(tipo=símismo.ext) for exp in exper}
        else:
            return {exp: tiempo_final for exp in exper}

    def _prep_dic_simul(símismo, exper, n_rep_estoc, n_rep_paráms, paso, n_pasos, detalles, tipo):
        """

        :param exper:
        :type exper:
        :param n_rep_estoc:
        :type n_rep_estoc: int
        :param n_rep_paráms:
        :type n_rep_paráms: int
        :param paso:
        :type paso: int
        :param n_pasos:
        :type n_pasos: int
        :param detalles:
        :type detalles: bool
        :param tipo:
        :type tipo: str
        :return:
        :rtype:
        """

        #
        dic_simul = símismo.dic_simul

        for ll in dic_simul:
            dic_simul[ll].clear()

        símismo._gen_dic_predics_exps(exper=exper, n_rep_estoc=n_rep_estoc, n_rep_parám=n_rep_paráms,
                                      paso=paso, n_pasos=n_pasos, detalles=detalles)

        if tipo == 'valid' or tipo == 'calib':
            símismo._gen_dics_valid(exper=exper, paso=paso, n_pasos=n_pasos,
                                    n_rep_estoc=n_rep_estoc, n_rep_parám=n_rep_paráms)

        if tipo == 'calib':
            símismo._gen_dics_calib(exper=exper)

    def _gen_dic_predics_exps(símismo, exper, n_rep_estoc, n_rep_parám, paso, n_pasos, detalles):
        raise NotImplementedError

    def _gen_dics_valid(símismo, exper, paso, n_pasos, n_rep_estoc, n_rep_parám):
        raise NotImplementedError

    def _gen_dics_calib(símismo, exper):
        raise NotImplementedError

    def _simul_exps(símismo, paso, n_pasos, extrn, detalles, devolver_calib, depurar=False):
        """
        Esta es la función que se calibrará cuando se calibra o valida el modelo. Devuelve las predicciones del modelo
        correspondiendo a los valores observados, y eso en el mismo orden.

        Todos los argumentos de esta función, a parte "paso," son diccionarios con el nombre de los experimentos para
        simular como llaves.

        :param paso: El paso para la simulación
        :type paso: int

        :param n_pasos: Un diccionario con el número de pasos para cada simulación
        :type n_pasos: dict

        :param extrn: Un diccionario de valores externas a pasar a la simulación, si aplica.
        :type extrn: dict

        :param devolver_calib: (solamente se genera para calibraciones, no para validaciones).
        :type devolver_calib: bool

        :return:
        :rtype: None | dict[dict[np.ndarray]]

        """

        # Hacer una copia de los datos iniciales (así que, en la calibración del modelo, una iteración no borará los
        # datos iniciales para las próximas).
        llenar_copia_dic_matr(d_f=símismo.dic_simul['inic_d_predics_exps'], d_r=símismo.predics_exps)

        # Para cada experimento...
        for exp in símismo.predics_exps:
            # Apuntar el diccionario de predicciones del Simulable al diccionario apropiado en símismo.predics_exps.
            símismo.predics = símismo.predics_exps[exp]

            # Simular el modelo
            antes = time.time()
            símismo._calc_simul(paso=paso, n_pasos=n_pasos[exp], detalles=detalles, extrn=extrn[exp], depurar=depurar)
            print('Simulación (%s) calculada en: ' % exp, time.time() - antes)

        # Procesar los egresos de la simulación.
        antes = time.time()
        símismo._procesar_simul()
        dif_p_s = time.time() - antes

        if devolver_calib:
            # Convertir los diccionarios de predicciones en un vector numpy.
            antes = time.time()
            símismo._procesar_valid()
            dif_p_v = time.time() - antes
            antes = time.time()
            símismo._procesar_calib()
            dif_p_c = time.time() - antes
            print('Procesando predicciones: \n\tSimul: {}\n\tValid: {}\n\tCalib: {}\n\tTotal: {}'
                  .format(dif_p_s, dif_p_v, dif_p_c, dif_p_s + dif_p_v + dif_p_c))

            # Devolver las predicciones.
            return símismo.dic_simul['d_calib']

    def _procesar_simul(símismo):
        """
        Esta función procesa las predicciones del modelo después de una simulación, si necesario.
        """

        raise NotImplementedError

    def _procesar_valid(símismo):
        """
        Esta función procesa las predicciones de un modelo para usarlas en una validación (o también calibración).
        Por ejemplo, interpola las predicciones para coincidir con las fechas de las observaciones, etc. Todo se guarda
        en los diccionarios símismo.matrs_simul['d_l_matrs_valid'] y ['matrs_valid'].
        """

        d_l_m_predics = símismo.dic_simul['d_l_m_predics_v']
        d_l_m_valid = símismo.dic_simul['d_l_m_valid']
        info = símismo.dic_simul['d_l_í_valid']

        for t_dist, l_matr in d_l_m_valid.items():
            for i, m_v in enumerate(l_matr):
                # Días que corresponden exactamente
                días_v_e, días_p_e = info[t_dist][i]['exactos']
                if len(días_v_e):
                    m_p = d_l_m_predics[t_dist][i]
                    m_v[..., días_v_e] = m_p[..., días_p_e]

                # Días que hay que interpolar
                días_v_i, *días_p_i = info[t_dist][i]['interpol']
                if len(días_v_i):
                    # Pienso que este sería más rápido.
                    m_v[..., días_v_i] = días_p_i[1]  # El valor superior
                    m_v[..., días_v_i] -= días_p_i[0]  # La diferencia...
                    m_v[..., días_v_i] *= días_p_i[2]  # ...Multiplicada por la distancia relativa...
                    m_v[..., días_v_i] += días_p_i[0]  # ...Agragada al valor inferior

    def _analizar_valid(símismo):
        """
        Esta función procesa los resultados de la validación del modelo.

        :return: Un diccionario del análisis de la validación.
        :rtype: dict
        """

        raise NotImplementedError

    def _procesar_calib(símismo):
        """
        Procesa las predicciones de simulación de experimentos del modelo par auso en una calibración.

        :return: Un diccionario de las predicciones.
        :rtype: dict[dict[np.ndarray]]
        """

        d_l_m_valid = símismo.dic_simul['d_l_m_valid']
        d_calib = símismo.dic_simul['d_calib']
        d_índs = símismo.dic_simul['d_l_í_calib']

        for t_dist, l_matr_v in d_l_m_valid.items():
            d_dist = d_calib[t_dist]  # type: dict

            # Por una razón extraña, PyMC se queja si no hacemos copias aquí. A ver si hay que hacer lo mismo con PyMC3.
            d_dist['mu'] = np.zeros_like(d_dist['mu'])
            d_dist['sigma'] = np.zeros_like(d_dist['sigma'])

            for i, m in enumerate(l_matr_v):
                r = d_índs[t_dist][i]['rango']
                parc, etps, días = d_índs[t_dist][i]['índs']

                if t_dist == 'Normal':
                    d_dist['mu'][r[0]:r[1]] = np.mean(m[parc, :, 0, etps, días], axis=1)

                    # Evitar sigmas de 0. Causan muchos problemas después.
                    d_dist['sigma'][r[0]:r[1]] = np.maximum(1, np.std(m[parc, :, 0, etps, días], axis=1))

                else:
                    raise ValueError

    def _procesar_matrs_sens(símismo):
        """
        Esta función debe procesar las matrices de egresos de la última simulación para ponerlas en formato correcto
        para el análisis de sensibilidad.

        :return: Un tuple de la lista de las matrices procesadas y de una lista de las ubicaciones de estas matrices.
        :rtype: (list[np.ndarray], list[list[str]])
        """

        raise NotImplementedError

    def _prep_lista_exper(símismo, exper):
        """
        Esta lista prepara la lista de nombres de los experimentos para validación o calibración.

        :param exper: Los experimentos a usar.
        :type exper: list | str | Experimento | None

        :return: Una lista de los nombres de los experimentos.
        :rtype: list
        """

        # Si "experimentos" no se especificó, usar todos los experimentos vinculados con el Simulable
        if exper is None:
            exper = list(símismo.exps)

        # Si exper no era una lista, hacer una.
        if not type(exper) is list:
            exper = [exper]

        # Para cada elemento de exper, poner únicamente el nombre.
        for n, exp in enumerate(exper):
            if type(exp) is Experimento:
                exper[n] = exp.nombre

        # Devolver exper
        return exper

    def _filtrar_calibs(símismo, calibs, l_paráms, usar_especificadas):
        """
        Esta función, dado una lista de diccionarios de calibraciones de parámetros y una especificación de cuales
        calibraciones guardar, genera un lista de los nombre de las calibraciones que hay que incluir.
        Se usa para preparar simulaciones, calibraciones y validaciones.

        :param calibs: Una indicación de cuales calibraciones utilizar.
          Puede ser un número o texto con el nombre/id de la calibración deseada.
          Puede ser una lista de nombres de calibraciones deseadas.
          Puede ser una de las opciones siguientes:
             1. 'Todos': Usa todas las calibraciones disponibles en los objetos involucrados en la simulación.
             2. 'Comunes': Usa únicamente las calibraciones comunes entre todos los objetos involucrados en la
                simulación
             3. 'Correspondientes': Usa únicamente las calibraciones que fueron calibradas con este objeto Simulable
                en particular.

        :type calibs: str | float | list

        :param l_paráms: Una lista de los diccionarios de los parámetros a considerar.
        :type l_paráms: list

        :return: Una lista de las calibraciones que hay que utilizar. Cada elemento de esta lista es una lista sî
        mismo de las calibraciones que aplican a cada parâmetro, en el mismo orden que `l_paráms`.
        :rtype: list[list[str]]

        """

        # Preparar el parámetro "calibs"
        if calibs is None:
            calibs = ['0']

        if type(calibs) is str and calibs not in ['Todos', 'Comunes', 'Correspondientes']:
            # Si calibs es el nombre de una calibración (y no un nombre especial)...

            # Convertirlo en lista
            calibs = [calibs]

        # Si calibs es una lista...
        if type(calibs) is list:

            # Para cada elemento de la lista...
            for n, calib in enumerate(calibs):
                # Asegurarse de que es en formato de texto.
                calibs[n] = str(calib)

        # Ahora, preparar la lista de calibraciones según las especificaciones en "calibs". Primero, los casos
        # especiales.

        if type(calibs) is str:
            # Si "calibs" es un nombre especial...

            if calibs == 'Todos' or calibs == 'Correspondientes':
                # Tomamos todas las calibraciones existentes en cualquier de los parámetros.

                # Un conjunto vacío para contener las calibraciones
                conj_calibs = set()

                # Para cada parámetro...
                for parám in l_paráms:

                    # Agregamos el código de sus calibraciones
                    conj_calibs = conj_calibs.union(parám)

                    # Quitamos distribuciones especificadas manualmente (si usar_especificadas==True, se aplicarán
                    # más tarde.)
                    try:
                        conj_calibs.remove('especificado')
                    except KeyError:
                        pass

                if calibs == 'Correspondientes':
                    # Si querremos únicamente los que corresponden con este objeto Simulable..
                    # Usar todas las calibraciones calibradas
                    conj_calibs = {x for x in conj_calibs if x in símismo.receta['Calibraciones']}

            elif calibs == 'Comunes':
                # Tomamos todas las calibraciones en común entre los parámetros.

                # Hacemos un conjunto de calibraciones con las calibraciones del primer parámetro.
                conj_calibs = set(l_paráms[0])

                # Para cada otro parámetro en la lista...
                for parám in l_paráms[1:]:

                    # Para cada calibración en nuestro conjunto...
                    for id_calib in conj_calibs:

                        # Si la calibración no existe para este parámetro...
                        if id_calib not in parám:
                            # Borrarla de nuestro conjunto.
                            conj_calibs.remove(id_calib)

            else:

                # Si se especificó otro valor (lo que no debería ser posible dado la preparación que damos a
                # "calibs" arriba), hay un error.
                raise ValueError("Parámetro 'calibs' inválido.")

            # Quitar la distribución a priori no informativa, si hay otras alternativas.
            if '0' in conj_calibs and len(conj_calibs) > 1:
                conj_calibs.remove('0')

        elif type(calibs) is list:
            # Si se especificó una lista de calibraciones en particular, todo está bien.
            conj_calibs = set(calibs)

        else:
            # Si "calibs" no era ni texto ni una lista, hay un error.
            raise ValueError("Parámetro 'calibs' inválido.")

        # Verificar el conjunto de calibraciones generada
        if len(conj_calibs) == 0:
            # Si no quedamos con ninguna calibración, usemos la distribución a priori no informativa. Igual sería
            # mejor avisarle al usuario.
            conj_calibs = {'0'}
            avisar('Usando la distribución a priori no informativa por falta de calibraciones anteriores.')

        # Ahora, generamos una lista de calibraciones para utilizar para cada parámetro
        l_calibs_por_parám = []

        for d_p in l_paráms:
            # Para cada parámetro en la lista...

            if usar_especificadas and 'especificado' in d_p:
                # Si podemos y queremos usar especificados, aplicarlos aquí
                calibs_p = ['especificado']
            else:
                # Sino, aplicar todas las calibraciones deseadas que también están en el diccionario del parámetro
                calibs_p = [x for x in conj_calibs if x in d_p]

            # Asegurarse que no tenemos lista vacía (justo en caso)
            if len(calibs_p) == 0:
                calibs_p = ['0']

            # Agregar el diccionario del parámetro
            l_calibs_por_parám.append(calibs_p)

        # Devolver la lista de calibraciones por parámetro.
        return l_calibs_por_parám

    def dibujar_calib(símismo):
        """
        Esta función dibuja los parámetros incluidos en una calibración, antes y después de calibrar. Tiene
        funcionalidad para buscar a todos los parámetros incluidos en objetos vinculados a este Simulable también.

        """

        def sacar_dists_de_dic(d, l=None, u=None):
            """
            Esta función recursiva saca las distribuciones `VarCalib` de un diccionario de coeficientes.
            Devuelva los resultados en forma de tuple:


            :param d: El diccionario
            :type d: dict
            :param l:
            :type l: list
            :param u:
            :type u: list
            :return:
            :rtype: list
            """

            if l is None:
                l = []
            if u is None:
                u = []

            for ll, v in d.items():
                if type(v) is dict:
                    u.append(ll)
                    sacar_dists_de_dic(d=v, l=l, u=u)

                elif isinstance(v, VarCalib):
                    u.append(ll)
                    l.append((u.copy(), v))
                    u.pop()
                else:
                    # Si no, hacer nada
                    pass
            if len(u):
                u.pop()
            return l

        def sacar_dists_calibs(obj, l=None):
            """
            Esta función auxiliar saca las distribuciones PyMC de un objeto y de todos los otros objetos vinculados
            con este.

            :param obj: El objeto cuyas distribuciones de parámetros hay que sacar.
            :type obj: Coso

            :param l: Una lista para la recursión. Nunca especificar este parámetro mientras que se llama la función.
            :type l: list

            :return: Una lista de tuples de los parámetros, cada uno con la forma general:
            (lista de la ubicación del parámetro, distribución PyMC)
            :rtype: list

            """

            if l is None:
                l = []

            dic_coefs = obj.receta['coefs']

            if len(dic_coefs):
                l += sacar_dists_de_dic(dic_coefs, u=[obj.nombre])

            for o in obj.objetos:
                l += sacar_dists_calibs(obj=o)

            return l

        lista_dists = sacar_dists_calibs(símismo)

        for ubic, dist in lista_dists:

            directorio = os.path.join(directorio_base, 'Proyectos', os.path.splitext(símismo.proyecto)[0],
                                      símismo.nombre, 'Gráficos calibración', símismo.ModCalib.id, ubic[0])
            archivo = os.path.join(directorio, '_'.join(ubic[1:-1]) + '.png')

            if not os.path.exists(directorio):
                os.makedirs(directorio)

            título = ':'.join(ubic[1:-1])

            try:
                Arte.graficar_dists(dists=dist, título=título, archivo=archivo)
            except AttributeError:
                pass

    def especificar_apriori(símismo, **kwargs):
        """
        Dejamos este para las subclases de Simulable, se les aplica.

        :param kwargs:
        :type kwargs:

        """

        raise NotImplementedError

    def _numerizar_coefs(símismo):
        """
        Esta función numeriza los coeficientes de un Simulable (convierte variables PyMC a matrices NumPy).
        """

        # Numerizar el diccionario de coeficientes.
        numerizados = Incert.numerizar(f=símismo.coefs_act)

        # Vaciar el diccionario existente.
        símismo.coefs_act_númzds.clear()

        # Llenar el diccionario con los coeficientes numerizados.
        símismo.coefs_act_númzds.update(numerizados)

    def _justo_antes_de_simular(símismo):
        """
        Esta función, aplicada en las subclases de Simulable, efectua acciones necesarias una vez antes de cada
        simulación de cada experimento. Esto implica cosas que dependen en, por ejemplo, los valores de los parámetros
        de la simulación actual, pero que solamente necesitan hacerse una vez al principio de la simulación. Un ejemplo
        sería la inicialización de las poblaciones iniciales de organismos con poblaciones fijas en Redes según el valor
        del parámetro del tamaño de población fija.
        """

        raise NotImplementedError

    def _sacar_coefs_no_espec(símismo):
        """
        Esta función devuelve un diccionario de los coeficientes que no tienen distribuciones a priori especificadas.
        Se deja a las subclases de Simulable para implementar.

        :return: Un diccionario con los coeficientes que no tienen distribuciones a prioris especificadas.
        :rtype: dict
        """

        raise NotImplementedError

    def _valid_nombre_simul(símismo, nombre):
        """
        Esta función valida un nombre de simulación y, si nombre=None, genera un nombre aleatorio válido.

        :param nombre: El nombre propuesto para la simulación.
        :type nombre: str

        :return: El nombre validado.
        :rtype: str
        """

        # Si se especificó un nombre para la calibración, asegurarse de que no existe en la lista de calibraciones
        # existentes
        if nombre is not None and nombre in símismo.receta['Calibraciones']:
            avisar('Nombre de calibración ya existe en el objeto. Tomaremos un nombre aleatorio.')
            nombre = None

        # Si no se especificó nombre para la calibración, generar un número de identificación aleatorio.
        if nombre is None:
            nombre = int(random.random() * 1e10)

            # Evitar el caso muy improbable de que el código aleatorio ya existe
            while nombre in símismo.receta['Calibraciones']:
                nombre = int(random.random() * 1e10)

            avisar('Nombre aleatorio ("{}") escogido como nombre de esta calibración.'.format(nombre))

        return str(nombre)


def dic_lista_a_np(d):
    """
    Esta función recursiva toma las listas numéricas contenidas en un diccionario de estructura arbitraria y las
    convierte en matrices numpy. Cambia el diccionario in situ, así que no devuelve ningún valor.
    Una nota importante: esta función puede tomar diccionarios de estructura arbitraria, pero no convertirá
    exitosamente diccionarios que contienen listas que a su turno contienen otras listas para convertir a matrices
    numpy. No hay problema con listas compuestas representando matrices multidimensionales.

    :param d: El diccionario para convertir
    :type d: dict

    """

    # Para cada itema (llave, valor) del diccionario
    for ll, v in d.items():
        if type(v) is dict:
            # Si el itema era otro diccionario...

            # Llamar esta función de nuevo
            dic_lista_a_np(v)

        elif type(v) is list:
            # Si el itema era una lista...
            try:
                # Ver si se puede convertir a una matriz numpy
                d[ll] = np.array(v, dtype=float)
            except ValueError:
                # Si no funcionó, pasar al siguiente
                pass


def prep_receta_json(d, d_egr=None):
    """
    Esta función recursiva prepara un diccionario de coeficientes para ser guardado en formato json. Toma las matrices
    de numpy contenidas en un diccionario de estructura arbitraria listas y las convierte en numéricas. También
    quita variables de typo PyMC que no sa han guardado en forma de matriz. Cambia el diccionario in situ, así que
    no devuelve ningún valor. Una nota importante: esta función puede tomar diccionarios de estructura arbitraria,
    pero no convertirá exitosamente diccionarios que contienen listas de matrices numpy.

    :param d: El diccionario para convertir
    :type d: dict

    :param d_egr: El diccionario que se devolverá. Únicamente se usa para recursión (nunca especificar d_egr mientras
    se llama esta función)
    :type: dict

    """

    if d_egr is None:
        d_egr = {}

    # Para cada itema (llave, valor) del diccionario
    for ll, v in d.items():
        if type(v) is dict:
            d_egr[ll] = v.copy()
        else:
            d_egr[ll] = v

        if type(v) is dict:

            # Si el itema era otro diccionario, llamar esta función de nuevo con el nuevo diccionario
            prep_receta_json(v, d_egr=d_egr[ll])

        elif type(v) is str:

            # Quitar distribuciones a priori especificadas por el usuario.
            if ll == 'especificado':
                d_egr.pop(ll)

        elif type(v) is np.ndarray:

            # Transformar matrices numpy a texto
            d_egr[ll] = v.tolist()

        elif isinstance(v, VarCalib):

            # Si el itema es un variable de PyMC, borrarlo
            d_egr.pop(ll)

    return d_egr


def guardar_json(dic, archivo):
    """
    Esta función guarda un diccionario con carácteres internacionales en formato JSON.

    :param dic: El diccionario para guardar.
    :type dic: dict
    :param archivo: El archivo.
    :type archivo: str

    """

    with open(archivo, 'w', encoding='utf8') as d:
        json.dump(dic, d, ensure_ascii=False, sort_keys=True, indent=2)  # Guardar todo


def dic_a_lista(d, l=None, ll_f=None, l_u=None, u=None):
    """

    :param d:
    :type d: dict
    :param l:
    :type l: list
    :param ll_f:
    :type ll_f: str
    :param l_u: Si hay de devolver una lista de la ubicación de cada itema en la lista
    :type l_u: list
    :param u:
    :type u: list
    :return:
    :rtype: list
    """

    if l is None:
        l = []

    if l_u is not None and u is None:
        u = []

    for ll, v in d.items():
        if isinstance(v, dict) and ll_f not in v:
            if l_u is not None:
                u.append(ll)
            dic_a_lista(v, l=l, ll_f=ll_f, l_u=l_u, u=u)
        else:
            l.append(v)
            if l_u is not None:
                u.append(ll)
                l_u.append(u.copy())
                u.pop(-1)

    return l


def llenar_copia_dic_matr(d_f, d_r):
    """
    Llena una copia ya formada de un diccionario de matrices con los valores en un diccionario de la misma estructura.
    No recrea las matrices, lo cual ahorra tiempo.

    :param d_f: El diccionario fuente.
    :type d_f: dict
    :param d_r: El diccionario recipiente.
    :type d_r: dict

    """

    for ll, v in d_f.items():
        if isinstance(v, dict):
            llenar_copia_dic_matr(d_f=v, d_r=d_r[ll])
        elif isinstance(v, np.ndarray):
            if d_r[ll].shape == v.shape:
                d_r[ll][:] = v
            else:
                # Para unas matrices, copiar el primer día de datos solamente.
                d_r[ll][..., 0] = v
        else:
            pass


def llaves_a_dic(l_ubics, vals):
    """
    Esta función toma una lista de ubicaciones (listas de llaves) y valores correspondientes y genera un diccionario.
    Es el opuesto de `dic_a_lista`.

    :param l_ubics: La lista de ubicaciones de valores.
    :type l_ubics: list[list[str]]
    :param vals: La lista de los valores.
    :type vals: list
    :return: El diccionario reconstruido.
    :rtype: dict
    """

    # Asegurarse que cada valor tenga una ubicación en el diccionario, y vice versa.
    if len(l_ubics) != len(vals):
        raise ValueError('La lista de ubicaciones debe tener el mismo tamaño que la lista de valores.')

    # El diccionario, vacío, para devolver
    dic = {}

    # Llenar el diccionario
    for val, l_llvs in zip(vals, l_ubics):
        # Para cada pareja de valor y ubicación...

        d = dic
        for i, ll in enumerate(l_llvs):
            if i == len(l_llvs) - 1:
                # Si es el último elemento en la list de ubicaciones...
                d[ll] = val  # Guardar el valor
            else:
                # Sino, crear la llave y continuar
                if ll not in d:
                    d[ll] = {}
                d = d[ll]

    # Devolver el resultado
    return dic
