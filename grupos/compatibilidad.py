"""Comprobación de restricciones e incompatibilidades al asignar un aula a un grupo."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Incompatibilidad:
    mensaje: str
    bloquea: bool  # True = error (no se puede asignar); False = aviso


def comprobar(grupo, aula):
    """Devuelve la lista de incompatibilidades entre un grupo y un aula."""
    if aula is None:
        return []
    res = []

    if aula.sede_id != grupo.sede_id:
        res.append(Incompatibilidad(f"El aula «{aula.nombre}» pertenece a otra sede.", True))
    if not aula.activa:
        res.append(Incompatibilidad(f"El aula «{aula.nombre}» está desactivada.", True))
    if grupo.num_alumnos > aula.capacidad:
        res.append(Incompatibilidad(
            f"Capacidad insuficiente: el grupo tiene {grupo.num_alumnos} alumnos y el aula admite {aula.capacidad}.",
            True,
        ))
    if grupo.requiere_ordenadores and not aula.ordenadores:
        res.append(Incompatibilidad("El grupo necesita ordenadores y el aula no dispone de ellos.", True))
    if grupo.requiere_accesibilidad and not aula.accesible:
        res.append(Incompatibilidad("El grupo tiene alumnos con movilidad reducida y el aula no es accesible.", True))
    if grupo.requiere_proyector and not aula.proyector:
        res.append(Incompatibilidad("El grupo necesita proyector y el aula no tiene.", False))
    if aula.restricciones.strip():
        res.append(Incompatibilidad(f"Restricciones del aula: {aula.restricciones.strip()}", False))
    return res
