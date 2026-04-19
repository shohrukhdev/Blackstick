# Booket Demo Fixtures

Three demo providers with specialists, service types, services, and scheduling data.

| PK | Identifier | Name | Type |
|----|------------|------|------|
| 1 | `smile_dental` | Smile Dental Clinic | Dentistry |
| 2 | `thebeautybar` | The Beauty Bar | Beauty salon |
| 3 | `adolat_legal_services` | Adolat Legal Services | Notary / legal |

---

## Step 1 — Create User Accounts First

Fixtures reference Django `auth.User` rows by PK. **These users must exist before loading the fixtures**, otherwise you will get `IntegrityError: ForeignKey constraint failed`.

Create them in Django Admin at `/admin/auth/user/add/` or via the shell:

```bash
python manage.py shell
```

```python
from django.contrib.auth.models import User

users = [
    (10, "dental_owner",   "Aziz",    "Karimov",   True),   # Provider owner + Chief Dentist
    (11, "beautybar_owner","Asal",    "Shodieva",  True),   # Provider owner + Makeup Artist
    (14, "nail_specialist","Zulfiya", "Hasanova",  False),  # Nail Specialist
    (15, "wax_specialist", "Dilnoza", "Yusupova",  False),  # Wax Specialist
    (16, "barber",         "Akbar",   "Tursunov",  False),  # Barber
    (17, "legal_owner",    "Sherzod", "Nazarov",   True),   # Provider owner
    (18, "notary",         "Gulnora", "Rakhimova", False),  # Notary
    (19, "corp_consultant","Malika",  "Mirzayeva", False),  # Corporate Consultant
    (20, "legal_translator","Bobur",  "Sultonov",  False),  # Legal Translator
    (21, "legal_advisor",  "Jasur",   "Ergashev",  False),  # Senior Legal Advisor
    (22, "doc_specialist", "Feruza",  "Abdullayeva",False), # Document Specialist
    (23, "orthodontist",   "Nilufar", "Toshmatova",False),  # Orthodontist
    (24, "oral_surgeon",   "Jasur",   "Rakhimov",  False),  # Oral Surgeon
    (25, "pediatric_dentist","Shaxlo","Yusupova",  False),  # Pediatric Dentist
]

for pk, username, first, last, is_staff in users:
    u = User(pk=pk, username=username, first_name=first, last_name=last,
             is_staff=is_staff, is_active=True)
    u.set_password("changeme123")
    u.save()
    print(f"Created user {pk}: {username}")
```

> **Provider owners** (PKs 10, 11, 17) need `is_staff=True` to access the provider dashboard at `/dashboard/`.
> Server-only users (all others) do not need staff access unless they log in to the server dashboard.

---

## Step 2 — Load Fixtures

Run from the project root in this exact order (dependencies flow downward):

```bash
python manage.py loaddata \
  booket/fixtures/providers.json \
  booket/fixtures/servers.json \
  booket/fixtures/service_types.json \
  booket/fixtures/services.json \
  booket/fixtures/provider_server.json \
  booket/fixtures/provider_server_services.json
```

Optional sample appointment data (load after the above):

```bash
python manage.py loaddata \
  booket/fixtures/clients.json \
  booket/fixtures/provider_clients.json \
  booket/fixtures/appointments.json \
  booket/fixtures/appointment_services.json
```

---

## Loading into a database that already has data

If the target DB has records with conflicting PKs (e.g. re-loading after a previous run), clean the demo data first:

```bash
python manage.py shell -c "
from booket.models import ProviderServerService, ProviderServer, Service, ServiceType, Server, Provider
ProviderServerService.objects.filter(pk__range=(10, 200)).delete()
ProviderServer.objects.filter(pk__range=(1, 20)).delete()
Service.objects.filter(pk__range=(1, 60)).delete()
ServiceType.objects.filter(pk__range=(1, 15)).delete()
Server.objects.filter(pk__range=(1, 13)).delete()
Provider.objects.filter(pk__in=[1, 2, 3]).delete()
"
```

Then re-run the load commands from Step 2.

---

## File reference

| File | Model | Records |
|------|-------|---------|
| `providers.json` | `Provider` | 3 |
| `servers.json` | `Server` | 13 (1–10 existing, 11–13 dental) |
| `service_types.json` | `ServiceType` | 13 (types 1–2 dental, 3–6 beauty, 7–10 legal, 11–13 dental) |
| `services.json` | `Service` | 56 (1–2 dental consult/xray, 3–41 beauty/legal, 42–56 dental) |
| `provider_server.json` | `ProviderServer` | 13 (1 dental, 2–5 beauty, 6–10 legal, 11–13 dental) |
| `provider_server_services.json` | `ProviderServerService` | 110 entries |
| `clients.json` | `Client` | sample clients |
| `provider_clients.json` | `ProviderClient` | sample links |
| `appointments.json` | `Appointment` | sample appointments |
| `appointment_services.json` | `AppointmentService` | sample services per appointment |

---

## After loading

1. Visit `/smile_dental/` — Smile Dental Clinic booking page
2. Visit `/thebeautybar/` — The Beauty Bar booking page
3. Visit `/adolat_legal_services/` — Adolat Legal Services booking page
4. Log into Django Admin → **Servers** → assign profile photos for PKs 1, 11, 12, 13 (dental doctors)
5. Change all user passwords from `changeme123` before deploying
