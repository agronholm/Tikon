import os
from CULTIVO.DSSAT.DSSAT import DocDssat


# Objeto para representar documentos de typo FILES de DSSAT (información de suelos)
class Files(DocDssat):
    def __init__(simismo, dic="", *args, **kwargs):
        super().__init__(*args, **kwargs)  # Esta variable se initializa como DocDssat
        simismo.dic = dic

        # Si no existe el documento de suelos especificos a Tikon, crearlo
        if not os.path.isfile(os.path.join(simismo.dir_DSSAT, 'Soil', 'Python.sol')):
            with open(os.path.join(simismo.dir_DSSAT, 'Soil', 'Python.sol'), 'w') as d:
                pass

        if len(simismo.dic) == 0:
            simismo.dic = {"ID_SOIL": [], "SLSOURCE": [], "SLTX": [], "SLDP": [], "SLDESCRIP": [],
                           "SITE": [], "COUNTRY": [], "LAT": [], "LONG": [], "SCS": [], "SCOM": [], "SALB": [],
                           "SLU1": [], "SLDR": [], "SLRO": [], "SLNF": [], "SLPF": [], "SMHB": [], "SMPX": [], "SMKE": [],
                           "SLB": [], "SLMH": [], "SLLL": [], "SDUL": [], "SSAT": [], "SRGF": [], "SSKS": [], "SBDM": [],
                           "SLOC": [], "SLCL": [], "SLSI": [], "SLCF": [], "SLNI": [], "SLHW": [], "SLHB": [], "SCEC": [],
                           "SADC": [], "SLPX": [], "SLPT": [], "SLPO": [], "CACO3": [], "SLAL": [], "SLFE": [], "SLMN": [],
                           "SLBS": [], "SLPA": [], "SLPB": [], "SLKE": [], "SLMG": [], "SLNA": [], "SLSU": [], "SLEC": [],
                           "SLCA": []}

        # Lista del tamaño (en carácteres) de cada variable
        simismo.prop_vars = {
            "ID_SOIL": 12, "SLSOURCE": 11, "SLTX": 5, "SLDP": 5, "SLDESCRIP": 50,
            "SITE": 12, "COUNTRY": 11, "LAT": 8, "LONG": 8, "SCS": 50,
            "SCOM": 5, "SALB": 5, "SLU1": 5, "SLDR": 5, "SLRO": 5, "SLNF": 5, "SLPF": 5, "SMHB": 5, "SMPX": 5, "SMKE": 5,
            "SLB": 5, "SLMH": 5, "SLLL": 5, "SDUL": 5, "SSAT": 5, "SRGF": 5, "SSKS": 5, "SBDM": 5,
            "SLOC": 5, "SLCL": 5, "SLSI": 5, "SLCF": 5, "SLNI": 5, "SLHW": 5, "SLHB": 5, "SCEC": 5, "SADC": 5,
            "SLPX": 5, "SLPT": 5, "SLPO": 5, "CACO3": 5, "SLAL": 5, "SLFE": 5, "SLMN": 5, "SLBS": 5, "SLPA": 5, "SLPB": 5, "SLKE": 5, "SLMG": 5, "SLNA": 5, "SLSU": 5, "SLEC": 5, "SLCA": 5
        }

    def leer(simismo, cod_suelo):
        # Los datos de suelos están combinados, con muchos en la misma carpeta.
        # Este programa primero verifica si se ubica el suelo en la carpeta "Python.sol".
        # Si el suelo no se ubica allá, buscará en los otros documentos de la carpeta "DSSAT45/soil/"

        # Vaciar el diccionario
        for i in simismo.dic:
            simismo.dic[i] = []

        def buscar_suelo(patrón):
            with open(patrón, "r") as p:
                patrón = []
                for línea in p:
                    patrón.append(línea)
            for línea in patrón:
                if cod_suelo in línea:
                    decodar(patrón, cod_suelo)
                    return True  # Si lo encontramos
            return False  # Si no lo encontramos

        # Esta funcción convierte una suelo de un documento FILES en diccionario Python.
        def decodar(doc, suelo):
            # Encuentra la ubicación del principio y del fin de cada sección
            prin = fin = None
            for línea in doc:
                if "*" in línea and suelo in línea:
                    prin = doc.index(línea)  # Empezamos a la línea con "*" y el código del suelo
                    fin = doc.index("\n", prin)  # Y terminamos donde hay una línea vacía
                    break

            if prin is not None:  # Si existe el suelo
                for línea, texto in enumerate(doc[prin:fin-1], start=prin):
                    if "@" in texto or "*" in texto:
                        if "@" not in texto:  # Para la primera línea
                            variables = ['ID_SOIL', 'SLSOURCE', 'SLTX', 'SLDP', 'SLDESCRIP']
                            núm_lin = línea
                        else:
                            variables = texto.replace('@', '').split()
                            # Empezamos a leer los valores en la línea que sigue los nombres de los variables
                            núm_lin = línea + 1
                        if "FAMILY" in variables:
                            variables.pop(len(variables)-1)

                        # Mientras no llegamos a la próxima línea de nombres de variables o el fin de la sección
                        while "@" not in doc[núm_lin] and len(doc[núm_lin].replace('\n', '')) > 0:
                            valores = doc[núm_lin].replace('\n', '')
                            for j, var in enumerate(variables):
                                if var in simismo.dic:
                                    valor = valores[:simismo.prop_vars[var]+1].replace('*', '').strip()
                                    simismo.dic[var].append(valor)
                                    valores = valores[simismo.prop_vars[var]+1:]
                            núm_lin += 1

        # Primero, miremos en el documento "Python.sol"
        encontrado = buscar_suelo(os.path.join(simismo.dir_DSSAT, 'Soil', 'Python.sol'))
        # Si no encontramos el suelo en el documento "Python.sol"...
        if not encontrado:
            documentos = []
            for doc_suelo in os.listdir(os.path.join(simismo.dir_DSSAT, 'Soil')):
                if doc_suelo.lower().endswith(".sol"):
                    documentos.append(doc_suelo)
            for documento in documentos:
                buscar_suelo(os.path.join(simismo.dir_DSSAT, 'Soil', documento))

        # Si no lo encontramos en ningún lado
        if not encontrado:
            return "Error: El código de suelo no se ubica en la base de datos de DSSAT."

    # Esta función automáticamente escribe los datos del suelo en el documento "Python.sol". No excepciones.
    def escribir(simismo, cod_suelo):

        def encodar(doc_suelo):
            for n, línea_suelo in enumerate(doc_suelo):
                l = n
                texto = línea_suelo
                if '{' in texto:   # Si la línea tiene variables a llenar
                    # Leer el primer variable de la línea (para calcular el número de niveles de suelo más adelante)
                    var = texto[texto.index("{")+2:texto.index("]")]
                    copia = texto   # Copiar la línea vacía (en caso que hayan otras líneas que agregar)
                    for k, a in enumerate(simismo.dic[var]):    # Para cada nivel del perfil del suelo
                        l += 1
                        texto = texto.replace('[', '').replace("]", "[" + str(k) + "]")
                        try:
                            texto = texto.format(**simismo.dic)
                            doc_suelo.insert(l, texto)
                        except IndexError:
                            pass

                        texto = copia  # Reinicializar "texto"
                    doc_suelo.remove(copia)
            return doc_suelo

        for i in simismo.dic:    # Llenar variables vacíos con -99 (el código de DSSAT para datos que faltan)
            for j in simismo.dic[i]:
                if not len(j):
                    j = [["-99"]]

        with open("FILES.txt", "r") as d:    # Abrir el patrón general para archivos FILES
            patrón = []
            for línea in d:
                patrón.append(línea)
        patrón.append("\n")  # Terminar con una línea vacía para marcar el fin del documento

        patrón = encodar(patrón)
        patrón = ''.join(patrón)  # Lo que tenemos que añadir a la carpeta Python.sol

        # Salvar la carpeta FILES en Python.sol
        with open(os.path.join(simismo.dir_DSSAT, 'Soil', 'Python.sol'), "r+") as d:
            doc_final = d.readlines()
            for j, i in enumerate(doc_final):  # Quitar las líneas vacías iniciales
                if i == '\n':
                    del doc_final[j]
                else:
                    break
            for i, línea in enumerate(doc_final):
                if cod_suelo in línea:
                    prin = doc_final.index(línea)
                    fin = doc_final.index("\n", prin)
                    del doc_final[prin:fin]
                    break
            doc_final.append(patrón)
            d.seek(0)
            d.truncate()  # Borrar el documento
            d.write(''.join(doc_final))

# Pruebas:
prueba = Files()
prueba.leer('IB00000002')
prueba.escribir('IB00000002')

prueba.leer('SARA020001')
prueba.escribir('SARA020001')