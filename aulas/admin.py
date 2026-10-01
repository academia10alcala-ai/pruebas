from django.contrib import admin

from sedes.admin import FiltroPorSedeMixin

from .models import Aula


@admin.register(Aula)
class AulaAdmin(FiltroPorSedeMixin, admin.ModelAdmin):
    list_display = ("nombre", "sede", "tipo", "capacidad", "proyector", "ordenadores", "accesible", "activa")
    list_filter = ("sede", "tipo", "activa")
    search_fields = ("nombre",)
