# Booket

A multi-tenant appointment booking platform built with Django. Service providers (clinics, salons, studios, etc.) can onboard their staff and services, then share a public booking page where clients self-schedule appointments.

## Features

- **Provider management** — profile, logo, gallery, contact info, social media links
- **Staff (server) management** — working hours, off-days, per-server services and pricing
- **Service catalog** — multilingual (English, Uzbek, Russian) service types and services with custom pricing per staff member
- **Client booking flow** — public booking page per provider, time-slot availability, OTP verification via SMS (Eskiz) or email
- **Provider dashboard** — calendar view, appointment management (accept/cancel/no-show/reschedule)
- **Statistics** — appointment trends, top clients, service breakdown (per server and per provider)
- **Internationalization** — English, Russian, Uzbek with locale-aware URLs

## Tech Stack

- **Backend:** Django 5.1.2, Django REST Framework
- **Database:** PostgreSQL
- **Cache/Sessions:** Redis (local LocMemCache for development)
- **Storage:** AWS S3 (optional, controlled via `USE_S3` env var; local filesystem otherwise)
- **Email:** AWS SES
- **SMS:** Eskiz
- **Task scheduling:** APScheduler via django-apscheduler
- **Containerization:** Docker + docker-compose

## Project Structure

```
Blackstick/          # Django project configuration (settings, root urls, wsgi)
booket/              # Main application
├── models.py        # Provider, Server, Service, Client, Appointment, OTPVerification
├── views.py         # Provider/server/service management views
├── services.py      # Business logic layer
├── urls.py          # Provider management URL patterns (/b/...)
├── admin.py         # Django admin registrations
├── sms_service.py   # Eskiz SMS integration
├── scheduler.py     # Background scheduled tasks
├── utils.py         # Shared utilities
├── constants.py     # Application-wide constants
├── forms/           # Django form definitions
├── dashboard/       # Provider & server dashboards (views, API, serializers)
└── client/          # Public booking interface (views, API, serializers)
static/              # CSS, JS, vendor libraries
templates/           # HTML templates
locale/              # Translation files (en, ru, uz)
```

## Core Models

| Model                   | Purpose                                                               |
|-------------------------|-----------------------------------------------------------------------|
| `Provider`              | A business registered on the platform                                 |
| `Server`                | A staff member linked to a Django user account                        |
| `ProviderServer`        | Links a server to a provider with working hours and off-days          |
| `ServiceType`           | A category of services (multilingual)                                 |
| `Service`               | An individual service with pricing (multilingual)                     |
| `ProviderServerService` | Assigns a service to a server with optional private price and duration |
| `Client`                | An end user who books appointments                                    |
| `Appointment`           | A booking with status lifecycle: NEW → CONFIRMED → ACCEPTED → COMPLETED |
| `OTPVerification`       | One-time code used to confirm a booking via SMS or email              |

## Appointment Status Lifecycle

```
NEW → CONFIRMED (OTP verified) → ACCEPTED (by provider) → COMPLETED
                              ↘ REJECTED / CANCELLED / NO_SHOW
```

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL
- Redis (optional for development)

### Environment Variables

Copy `.env.example` to `.env` and fill in:

```
SECRET_KEY=
FERNET_KEY=
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=5432
USE_S3=0
ESKIZ_EMAIL=
ESKIZ_PASSWORD=
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_SES_USER_ACCESS_KEY_ID=
AWS_SES_USER_SECRET_ACCESS_KEY=
```

### Run with Docker

```bash
docker-compose up -d        # Start PostgreSQL and Redis
python manage.py migrate
python manage.py runserver
```

### Load Fixtures (development data)

```bash
make load_fixtures
```

## URL Structure

| Prefix           | Purpose                                              |
|------------------|------------------------------------------------------|
| `/b/`            | Provider/server management (login, profile, services) |
| `/dashboard/`    | Server and provider dashboards                       |
| `/<identifier>/` | Public booking page for a provider                   |
| `/client/...`    | Client-facing booking API endpoints                  |
| `/admin/`        | Django admin                                         |
