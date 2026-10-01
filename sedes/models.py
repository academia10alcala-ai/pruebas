from django.conf import settings
from django.db import models


class Sede(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    ciudad = models.CharField(max_length=100, blank=True)
    direccion = models.CharField("dirección", max_length=200, blank=True)
    telefono = models.CharField("teléfono", max_length=30, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class PerfilSede(models.Model):
    """Sedes a las que tiene acceso un usuario. Los superusuarios ven todas."""

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil_sede"
    )
    sedes = models.ManyToManyField(Sede, blank=True, related_name="usuarios")

    class Meta:
        verbose_name = "acceso a sedes"
        verbose_name_plural = "accesos a sedes"

    def __str__(self):
        return str(self.usuario)


def sedes_de(usuario):
    """Sedes visibles para un usuario."""
    if usuario.is_superuser:
        return Sede.objects.all()
    perfil = getattr(usuario, "perfil_sede", None)
    return perfil.sedes.all() if perfil else Sede.objects.none()
