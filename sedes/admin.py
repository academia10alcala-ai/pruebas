from django.contrib import admin

from .models import PerfilSede, Sede, sedes_de


@admin.register(Sede)
class SedeAdmin(admin.ModelAdmin):
    list_display = ("nombre", "ciudad", "activa")

    def get_queryset(self, request):
        return super().get_queryset(request).filter(pk__in=sedes_de(request.user))


@admin.register(PerfilSede)
class PerfilSedeAdmin(admin.ModelAdmin):
    filter_horizontal = ("sedes",)


class FiltroPorSedeMixin:
    """Limita listados y desplegable de sede a las sedes del usuario."""

    def get_queryset(self, request):
        return super().get_queryset(request).filter(sede__in=sedes_de(request.user))

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "sede":
            kwargs["queryset"] = sedes_de(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
