import os
import subprocess

import numpy as np

from tikon.Coso import Simulable
from tikon.Cultivo import Controles as ctrl
from tikon.Cultivo.ModExtern.DSSAT import DSSAT


class Cultivo(Simulable):
    """
    Esta clase sirve para representar cultivos agrícolas.
    """

    # La extension para guardar archivos de cultivos.
    ext = '.clt'

    def __init__(símismo, cultivo, variedad, programa=None, cód_modelo=None):
        super().__init__(nombre=variedad)

        símismo.cultivo = cultivo
        símismo.variedad = variedad

        símismo.programa = None
        símismo.cód_modelo = None

        símismo.modelo = np.array([], dtype=object)

    def estab_modelo(símismo, programa, cód_modelo, dir_trabajo):
        """

        :param programa:
        :type programa: str

        :param cód_modelo:
        :type cód_modelo: str

        :param dir_trabajo:
        :type dir_trabajo: str

        :return:
        :rtype: EnvolturaModCult
        """

        símismo.programa = programa
        símismo.cód_modelo = cód_modelo

        if programa is None:
            programa = list(sorted(mods_cult[símismo.cultivo]))[0]
        if cód_modelo is None:
            cód_modelo = list(sorted(mods_cult[símismo.cultivo][programa]))[0]

        if programa == 'DSSAT':
            modelo = EnvolturaDSSAT(cultivo=símismo.cultivo, variedad=símismo.variedad,
                                    cód_mod=cód_modelo,
                                    dir_trabajo=dir_trabajo)
        elif programa == 'CropSyst':
            raise ValueError('Marcela, ¡este es para ti! Haz CLIC en este error y ya puedes empezar a codigar. :)')
        else:
            raise ValueError('Falta implementar el modelo "{}" en Tiko\'n.'.format(programa))

        return modelo

    def actualizar(símismo):
        pass

    def _sacar_coefs_interno(símismo):
        pass

    def _llenar_coefs(símismo, nombre_simul, n_rep_parám, dib_dists, calibs=None):
        pass

    def _sacar_coefs_no_espec(símismo):
        pass

    def _gen_dics_valid(símismo, exper, paso, n_pasos, n_rep_estoc, n_rep_parám):
        pass

    def dibujar(símismo, mostrar=True, directorio=None, exper=None, **kwargs):
        pass

    def _actualizar_vínculos_exps(símismo):
        pass

    def especificar_apriori(símismo, **kwargs):
        pass

    def _procesar_simul(símismo):
        pass

    def _justo_antes_de_simular(símismo):
        pass

    def _gen_dic_predics_exps(símismo, exper, n_rep_estoc, n_rep_parám, paso, n_pasos, detalles):
        pass

    def incrementar(símismo, paso, i, detalles, extrn):
        pass

    def _sacar_líms_coefs_interno(símismo):
        pass

    def _analizar_valid(símismo):
        pass

    def _gen_dics_calib(símismo, exper):
        pass


class EnvolturaModCult(object):

    def __init__(símismo, cultivo, variedad, dir_trabajo):

        símismo.cultivo = cultivo
        símismo.variedad = variedad

        símismo.dir = os.path.join(dir_trabajo, "Tiko'n_Docs_mod_cult")

        # El diccionario con los valores de egreso
        símismo.egresos = {
            "raices": None, "hojas": None, "asim": None, "tallo": None, "semillas": None, "frutas": {},
            "nubes": None, "humrel": None, "lluvia": None, "tprom": None, "tmin": None, "tmax": None, "radsol": None,
            "tsuelo": None, "humsuelo": None
        }

        símismo.comanda = NotImplemented

        símismo.proceso = None

    def prep_simul(símismo, info_simul):
        """

        :param info_simul:
        :type info_simul: dict

        """
        raise NotImplementedError

    def empezar_simul(símismo):

        símismo.proceso = subprocess.Popen(
            símismo.comanda,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            cwd=símismo.dir,
            universal_newlines=True
        )

    def incrementar(símismo, paso, daño_plagas=None):
        """

        :param paso:
        :type paso: int


        :param daño_plagas:
        :type daño_plagas: dict

        """

        # Convertir el diccionario de daño de plagas al formato texto (para ingresar en la línea de comanda)
        # El diccionario debe tener el formato siguiente: daño_plagas = dict(daño_hojas = (), daño_raíces = (),
        # daño_tallo = (), daño_semillas = (), daño_frutas = (), daño_asim = ()}
        if daño_plagas is None:
            tx_daño_plagas = ''
        else:
            tx_daño_plagas = ''.join(['{}: {};'.format(nmb, dñ) for nmb, dñ in daño_plagas.items()])

        # Para compatibilidad con FORTRAN (el modelo de cultivos DSSAT) y probablemente C++ también:
        conv_utf = [("ñ", "n"), ("í", "i"), ('é', 'e'), ('á', 'a'), ('ó', 'o'), ('ú', 'u'), ('Á', 'A'), ('É', 'E'),
                    ('Í', 'I'), ('Ó', 'O'), ('Ú', 'U')]
        for c in conv_utf:
            tx_daño_plagas.replace(c[0], c[1])

        # Agregar el paso
        tx = 'paso: {}:'.format(paso) + tx_daño_plagas

        símismo.proceso.stdin.write(tx)  # Envía el estado de daño al modelo de cultivo
        símismo.proceso.stdin.flush()  # Una tecnicalidad obscura
        egr = símismo.proceso.stdout.readline()

        # Los egresos llegarán en el formato siguiente:
        # raices: valor; hojas: valor; ...
        l_egr = egr.split(';')

        # Guardar los valores comunicados por el modelo externo
        for e in l_egr:
            nmb, val = e.split(': ')
            símismo.egresos[nmb] = float(val)

    def leer_resultados(símismo):
        raise NotImplementedError


class EnvolturaDSSAT(EnvolturaModCult):

    def __init__(símismo, cultivo, variedad, cód_mod, dir_trabajo):
        super().__init__(cultivo=cultivo, variedad=variedad, dir_trabajo=dir_trabajo)

        comanda = mods_cult[cultivo]['DSSAT'][cód_mod]['Comanda']
        símismo.comanda = os.path.join(ctrl.dir_DSSAT, comanda) + " B " + símismo.dir + "DSSBatch.v46"

    def prep_simul(símismo, info_simul):
        """

        :param info_simul:
        :type info_simul:

        """
        DSSAT.gen_ingr(directorio=símismo.dir, cultivo=símismo.cultivo, variedad=símismo.variedad,
                       disuelo=info_simul['suelo'], meteo=info_simul['meteo'], manejo=info_simul['manejo'])

    def leer_resultados(símismo):
        resul = DSSAT.leer_egr(directorio=símismo.dir)


dic_info = {
    'exe_DSSAT': 'DSCSM046_TKN.EXE'
}

mods_cult = {
    'Maíz': {
        'DSSAT': {
            'IXIM': {
                'Comanda': '{exe_DSSAT} MZIXM046'.format(**dic_info),
                'Código cultivo': 'MZ'
            },
            'CERES': {
                'Comanda': '{exe_DSSAT} MZCER046'.format(**dic_info),
                'Código cultivo': 'MZ'
            }
        }
    },
    'Tomate': {
        'DSSAT': {
            'CROPGRO': {
                'Comanda': '{exe_DSSAT} CRGRO046'.format(**dic_info),
                'Código cultivo': 'TM'
            }
        }
    },
    'Frijol': {
        'DSSAT': {
            'CROPGRO': {
                'Comanda': '{exe_DSSAT} CRGRO046'.format(**dic_info),
                'Código cultivo': 'BN'
            }
        }
    },
    'Repollo': {
        'DSSAT': {
            'CROPGRO': {
                'Comanda': '{exe_DSSAT} CRGRO046'.format(**dic_info),
                'Código cultivo': 'CB'
            }
        }
    },
    'Papas': {
        'DSSAT': {
            'SUBSTOR': {
                'Comanda': '{exe_DSSAT} PTSUB046'.format(**dic_info),
                'Código cultivo': 'PT'
            }
        }
    },
    'Piña': {
        'PIAL': {
            'CROPGRO': {
                'Comanda': 'MDRIV980.EXE MINPT980.EXE PIALO980.EXE I',
                'Código cultivo': 'PI'
            }
        }
    },
    'Habas': {
        'DSSAT': {
            'CROPGRO': {
                'Comanda': '{exe_DSSAT} CRGRO046'.format(**dic_info),
                'Código cultivo': 'FB'
            }
        }
    },
    'Garbanzo': {
        'DSSAT': {
            'CROPGRO': {
                'Comanda': '{exe_DSSAT} CRGRO046'.format(**dic_info),
                'Código cultivo': 'CH'
            }
        }
    }
}
