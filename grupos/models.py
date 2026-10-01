from django.core.exceptions import ValidationError
from django.db import models

from aulas.models import Aula
from sedes.models import Sede


class Grupo(models.Model):
    sede = models.ForeignKey(Sede, on_delete=models.PROTECT, related_name="grupos")
    nombre = models.CharField(max_length=150)
    curso = models.CharField(max_length=150, blank=True)
    num_alumnos = models.PositiveSmallIntegerField("nº de alumnos", default=0)
    requiere_ordenadores = models.BooleanField(default=False)
    requiere_proyector = models.BooleanField(default=False)
    requiere_accesibilidad = models.BooleanField(
        "tiene alumnos con movilidad reducida", default=False
    )
    aula = models.ForeignKey(
        Aula, null=True, blank=True, on_delete=models.SET_NULL, related_name="grupos"
    )

    class Meta:
        ordering = ["sede", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["sede", "nombre"], name="grupo_unico_por_sede")
        ]

    def __str__(self):
        return f"{self.nombre} ({self.sede})"

    def comprobar_aula(self, aula=None):
        from .compatibilidad import comprobar

        return comprobar(self, aula or self.aula)

    def clean(self):
        if not self.aula_id:
            return
        errores = [i.mensaje for i in self.comprobar_aula() if i.bloquea]
        if errores:
            raise ValidationError({"aula": errores})
