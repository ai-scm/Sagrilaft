"""Comparación de cada nombre documentado; nunca mezcla fragmentos de alias."""
from collections import Counter
from dataclasses import dataclass
import re
import unicodedata


@dataclass(frozen=True)
class ComparacionNombre:
    metodo: str
    completo: bool


def partes_nombre(valor):
    sin_tildes = "".join(c if c == "ñ" else "".join(p for p in unicodedata.normalize("NFD", c)
                        if not unicodedata.combining(p)) for c in unicodedata.normalize("NFC", valor.casefold()))
    return tuple(re.findall(r"[^\W_]+", sin_tildes, re.UNICODE))


def una_edicion(uno, otro):
    """Inserción, omisión, sustitución o transposición adyacente de una letra."""
    if uno == otro:
        return True
    if min(len(uno), len(otro)) < 4 or any(c.isdigit() for c in uno + otro):
        return False
    if abs(len(uno) - len(otro)) > 1:
        return False
    if len(uno) == len(otro):
        distintas = [i for i, (a, b) in enumerate(zip(uno, otro)) if a != b]
        return len(distintas) == 1 or (len(distintas) == 2 and distintas[1] == distintas[0] + 1
            and uno[distintas[0]] == otro[distintas[1]] and uno[distintas[1]] == otro[distintas[0]])
    corto, largo = sorted((uno, otro), key=len)
    return any(corto == largo[:i] + largo[i + 1:] for i in range(len(largo)))


def emparejar(consultadas, publicadas, admitir_iniciales=False):
    asignadas = {}
    def buscar(indice, visitadas):
        opciones = sorted(range(len(publicadas)), key=lambda j: consultadas[indice] != publicadas[j])
        for j in opciones:
            a, b = consultadas[indice], publicadas[j]
            inicial = admitir_iniciales and min(len(a), len(b)) == 1 and a[0] == b[0]
            if j in visitadas or not (una_edicion(a, b) or inicial):
                continue
            visitadas.add(j)
            if j not in asignadas or buscar(asignadas[j], visitadas):
                asignadas[j] = indice
                return True
        return False
    return all(buscar(i, set()) for i in range(len(consultadas)))


def prefijo_compartido(uno, otro):
    """Palabras iniciales idénticas y en el mismo orden (sin quitar ninguna)."""
    prefijo = []
    for a, b in zip(uno, otro):
        if a != b:
            break
        prefijo.append(a)
    return tuple(prefijo)


# Conectores y artículos: no identifican una empresa ni una persona por sí solos.
CONECTORES = frozenset({"del", "las", "los", "and", "the", "of", "con", "por", "para"})


def relevante_por_prefijo(prefijo, uno, otro, genericos):
    """Un prefijo sustenta una revisión solo si es sustancial: al menos una palabra distintiva
    (no genérica, no conector, de tres letras o más), al menos dos palabras en el prefijo, y al
    menos la mitad del nombre más corto. 'Servicios Horizonte' basta por 'horizonte';
    'Comercial del Norte' no basta: 'comercial' es genérica y 'del' un conector."""
    distintivas = [p for p in prefijo if p not in genericos and p not in CONECTORES and len(p) >= 3]
    # La proporción se mide con palabras de dos letras o más: las iniciales de "S.A.S." no
    # deben diluir el prefijo. Esto no quita ninguna palabra de la comparación.
    tamano = min(sum(len(p) >= 2 for p in uno), sum(len(p) >= 2 for p in otro))
    return len(distintivas) >= 1 and len(prefijo) >= 2 and len(prefijo) * 2 >= tamano


def comparar_nombre(consultado, publicado, genericos=(), admitir_iniciales=True):
    """Compara la razón social completa tal como fue ingresada: ninguna palabra se quita
    (incluidas las terminaciones societarias como S.A., S.A.S., SAS, SA o LTDA).
    Las coincidencias exactas y de variación van primero y no cambian.
    Una letra suelta solo cuenta como inicial en nombres de personas; en empresas, las
    letras de una forma societaria (S.A.S.) no deben coincidir con cualquier palabra."""
    uno, otro = partes_nombre(consultado), partes_nombre(publicado)
    if not uno or not otro:
        return None
    if Counter(uno) == Counter(otro):
        return ComparacionNombre("NOMBRE_NORMALIZADO" if uno == otro else "ORDEN_DE_PARTES", True)
    if len(uno) == len(otro) and sum((Counter(uno) - Counter(otro)).values()) <= 1 and emparejar(uno, otro):
        return ComparacionNombre("VARIACION_MENOR", True)
    corto, largo = sorted((uno, otro), key=len)
    if emparejar(corto, largo, admitir_iniciales=admitir_iniciales):
        # No equipara empresas distintas por un término compartido genérico.
        if len(corto) >= 2 or len(corto[0]) >= 5:
            return ComparacionNombre("NOMBRE_PARCIAL", False)
    # Segunda vía: nombres con un tramo inicial sustancial en común y palabras finales distintas.
    prefijo = prefijo_compartido(uno, otro)
    if relevante_por_prefijo(prefijo, uno, otro, genericos):
        return ComparacionNombre("PREFIJO_COMPARTIDO", False)
    return None
