from tikon.Coso import Coso


def encontrar_subclase_coso(ext):
    """
    Esta función devuelve la clase de objeto asociada con la extensión especificada.

    :param ext: La extensión de interés.
    :type ext: str

    :return: El objeto de la subclase de Coso asociado con la extensión.
    :rtype: Coso
    """

    def sacar_subclases(cls):
        """

        :param cls: La clase cuyas subclases querremos
        :type cls: type

        :return: Una lista de las subclases del la clase
        :rtype: list

        """
        return cls.__subclasses__() + [g for s in cls.__subclasses__()
                                       for g in sacar_subclases(s)]

    for sub in sacar_subclases(Coso):
        if sub.ext == ext:
            return sub

    raise ValueError('No se encontró subclase de Coso con extensión %s.' % ext)