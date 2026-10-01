from django.core.exceptions import ValidationError
from django.test import TestCase

from aulas.models import Aula
from sedes.models import Sede

from .models import Grupo


class LimiteAulasTests(TestCase):
    def test_maximo_10_aulas_por_sede(self):
        sede = Sede.objects.create(nombre="Alcalá")
        for i in range(10):
            Aula.objects.create(sede=sede, nombre=f"A{i}", capacidad=20)
        with self.assertRaises(ValidationError):
            Aula.objects.create(sede=sede, nombre="A11", capacidad=20)

    def test_el_limite_es_por_sede(self):
        s1, s2 = Sede.objects.create(nombre="S1"), Sede.objects.create(nombre="S2")
        for i in range(10):
            Aula.objects.create(sede=s1, nombre=f"A{i}", capacidad=20)
        Aula.objects.create(sede=s2, nombre="A0", capacidad=20)

    def test_editar_aula_existente_con_sede_llena(self):
        sede = Sede.objects.create(nombre="S")
        aulas = [Aula.objects.create(sede=sede, nombre=f"A{i}", capacidad=20) for i in range(10)]
        aulas[0].capacidad = 30
        aulas[0].save()


class CompatibilidadTests(TestCase):
    def setUp(self):
        self.sede = Sede.objects.create(nombre="Alcalá")
        self.aula = Aula.objects.create(sede=self.sede, nombre="Aula 1", capacidad=15)

    def grupo(self, **kw):
        return Grupo(sede=self.sede, nombre="G1", aula=self.aula, **kw)

    def test_compatible(self):
        self.grupo(num_alumnos=10).full_clean()

    def test_capacidad_insuficiente(self):
        with self.assertRaises(ValidationError):
            self.grupo(num_alumnos=16).full_clean()

    def test_necesita_ordenadores(self):
        with self.assertRaises(ValidationError):
            self.grupo(num_alumnos=5, requiere_ordenadores=True).full_clean()

    def test_necesita_accesibilidad(self):
        with self.assertRaises(ValidationError):
            self.grupo(num_alumnos=5, requiere_accesibilidad=True).full_clean()

    def test_aula_de_otra_sede(self):
        otra = Sede.objects.create(nombre="Otra")
        g = Grupo(sede=otra, nombre="G2", aula=self.aula, num_alumnos=5)
        with self.assertRaises(ValidationError):
            g.full_clean()

    def test_aula_desactivada(self):
        self.aula.activa = False
        self.aula.save()
        with self.assertRaises(ValidationError):
            self.grupo(num_alumnos=5).full_clean()

    def test_proyector_y_restricciones_son_solo_avisos(self):
        self.aula.restricciones = "Sin uso después de las 21h"
        self.aula.save()
        g = self.grupo(num_alumnos=5, requiere_proyector=True)
        g.full_clean()  # no bloquea
        avisos = g.comprobar_aula()
        self.assertEqual(len(avisos), 2)
        self.assertFalse(any(a.bloquea for a in avisos))
