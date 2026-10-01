from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from sedes.models import Sede


class Aula(models.Model):
    class Tipo(models.TextChoices):
        TEORICA = "teorica", "Teórica"
        INFORMATICA = "informatica", "Informática"
        TALLER = "taller", "Taller"
        REUNIONES = "reuniones", "Sala de reuniones"

    sede = models.ForeignKey(Sede, on_delete=models.PROTECT, related_name="aulas")
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.TEORICA)
    capacidad = models.PositiveSmallIntegerField(help_text="Número máximo de alumnos")
    proyector = models.BooleanField(default=False)
    ordenadores = models.BooleanField(default=False)
    accesible = models.BooleanField("accesible (movilidad reducida)", default=False)
    activa = models.BooleanField(default=True)
    restricciones = models.TextField(
        blank=True, help_text="Notas libres: ruido, horarios de uso, normas…"
    )

    class Meta:
        ordering = ["sede", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["sede", "nombre"], name="aula_unica_por_sede")
        ]

    def __str__(self):
        return f"{self.nombre} ({self.sede})"

    def clean(self):
        if self.capacidad is not None and self.capacidad < 1:
            raise ValidationError({"capacidad": "La capacidad debe ser al menos 1."})
        self._validar_limite_por_sede()

    def _validar_limite_por_sede(self):
        if not self.sede_id or self.pk:
            return
        maximo = settings.MAX_AULAS_POR_SEDE
        if Aula.objects.filter(sede_id=self.sede_id).count() >= maximo:
            raise ValidationError(
                f"La sede ya tiene el máximo de {maximo} aulas permitidas."
            )

    def save(self, *args, **kwargs):
        self._validar_limite_por_sede()
        super().save(*args, **kwargs)
