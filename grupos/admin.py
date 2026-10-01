from django.contrib import admin, messages

from sedes.admin import FiltroPorSedeMixin

from .models import Grupo


@admin.register(Grupo)
class GrupoAdmin(FiltroPorSedeMixin, admin.ModelAdmin):
    list_display = ("nombre", "sede", "curso", "num_alumnos", "aula")
    list_filter = ("sede",)
    search_fields = ("nombre", "curso")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        for aviso in obj.comprobar_aula():
            if not aviso.bloquea:
                self.message_user(request, aviso.mensaje, messages.WARNING)
