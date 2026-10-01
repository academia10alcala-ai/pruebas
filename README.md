# Academia 10 – Gestión integral

Software de gestión de la academia (multisede). Django + panel de administración.

## Arranque

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver   # http://localhost:8000/admin/
python manage.py test
```

## Módulos

- `sedes`: sedes y acceso de cada usuario a sus sedes (`PerfilSede`; los superusuarios ven todas).
- `aulas`: aulas por sede (máx. `MAX_AULAS_POR_SEDE` = 10), capacidad, equipamiento, accesibilidad y restricciones.
- `grupos`: grupos y asignación de aula con comprobación de incompatibilidades (`grupos/compatibilidad.py`):
  bloquean la capacidad, los ordenadores, la accesibilidad, la sede y el aula desactivada;
  solo avisan el proyector y las restricciones del aula.

## Próximos pasos

Horarios (profesor + franja, choques de aula/profesor), CRM con embudo y WhatsApp Business por sede, email marketing.
