# Client Booking Flow

This document describes the end-to-end appointment booking flow on the public provider page (`/<identifier>/`).

---

## Overview

The flow is driven entirely by three Bootstrap modals and a set of REST API calls. No page reloads occur after the initial page load.

```
Provider page loads
    │
    ▼
User clicks "Book appointment" on a specialist card
    │
    ├── selectServer(providerServerId, serverName)
    │       GET /provider-server/<id>/   →  services + initial time slots
    │
    ▼
[Modal #book] — Step 1: Select Services
    │   fillServices()     renders service checkboxes
    │   handleServiceCheckboxChange()  tracks selection, updates total duration
    │
    ├── User ticks one or more services → "Next" button enables
    │
    ▼
[Modal #date-time] — Step 2: Select Date & Time
    │   renderDates()      renders date buttons from pre-loaded slot data
    │   renderTimeSlots()  renders time slots for selected date
    │   isSlotAvailable()  validates that consecutive 30-min slots cover total duration
    │
    ├── [Prev/Next] getDates() → GET /provider-server/<id>/available-slots/?start_date=…
    ├── User picks date → renderTimeSlots() for that date
    ├── User picks valid time → "Next" button enables
    │
    ▼
[Modal #confirm] — Step 3: Client Details + OTP
    │   renderConfirm()    populates appointment summary (left panel)
    │
    ├── User selects Phone or Email tab
    ├── Enters phone/email → checkPhoneInput / checkEmailInput
    │       searchClient() → GET /client/search/?phone_number=… | ?email=…
    │           On found:  pre-fills name/dob/sex, shows "Client exists" message
    │           On 404:    shows empty form for manual entry
    │
    ├── User fills required fields (full_name, dob, sex, agree)
    │       checkConfirmButton()  enables "Confirm" button
    │
    ├── User clicks "Confirm"
    │       sendToConfirm() → POST /client/appointment/create/
    │           Request body:
    │               client: { client_id, full_name, phone_number, email,
    │                         sex, dob (YYYY-MM-DD), confirmation_method ('p'|'e') }
    │               provider_id, server_id (ProviderServer.id)
    │               date (YYYY-MM-DD), time (HH:MM)
    │               services: [{ service_id, duration }, …]
    │               comments, language_code
    │           Response: { success, otp_id, confirmation_method,
    │                       masked_phone_number, masked_email, is_demo }
    │
    ├── showOTPConfirmation()
    │       Hides client form, shows OTP input section
    │       Starts 60-second countdown (startOTPTimer)
    │       If is_demo: shows raw OTP code for testing
    │
    ├── User enters 6-digit OTP code
    │       updateOTPConfirmButton()  enables "Confirm" when 6 digits entered
    │
    ├── User clicks "Confirm" (OTP)
    │       confirmOTP() → POST /client/appointment/confirm/
    │           Body: { otp_id, otp_code, provider_identifier }
    │           On success: appointment.status → CONFIRMED
    │                       SMS notification sent to server/specialist
    │
    ├── [Resend] resendOTP() → POST /client/appointment/confirm/resend/
    │       Body: { otp_id }
    │       Regenerates OTP code and resends via SMS or email
    │
    ▼
showSuccessMessage() — "Appointment confirmed!" displayed
```

---

## Files

| File | Responsibility |
|------|----------------|
| `templates/booket/client/index.html` | Page structure: nav, sections, three booking modals |
| `static/design/js/script.js` | All booking flow JS, organized into sections |
| `static/design/css/base.css` | Page and modal styles |
| `static/design/css/main.css` | Service list styles added during refactor |
| `booket/client/views.py` | `main_page` — serves the provider page |
| `booket/client/api_views.py` | All booking REST endpoints |
| `booket/client/serializers.py` | `ProviderServerSerializer` — services + slot calculation |
| `booket/client/urls.py` | URL patterns for the booking API |

---

## API Endpoints

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| GET | `/<identifier>/` | none | Provider public page |
| GET | `/provider-server/<id>/` | Signature | Specialist services + initial slots |
| GET | `/provider-server/<id>/available-slots/?start_date=YYYY-MM-DD` | Signature | Paginated date/slot data |
| GET | `/client/search/?phone_number=…\|?email=…` | Signature | Look up existing client |
| POST | `/client/appointment/create/` | Signature + CSRF | Create appointment + send OTP |
| POST | `/client/appointment/confirm/` | Signature + CSRF | Verify OTP → confirm appointment |
| POST | `/client/appointment/confirm/resend/` | Signature + CSRF | Resend OTP code |

### Signature Authentication

All client-facing API calls include an `X-Signature` header containing a time-limited (10 min) Fernet-encrypted token generated server-side and embedded in the page as a hidden input:

```html
<input type="hidden" id="signature" value="{{ signature }}">
```

The token encodes `provider_id:unix_timestamp`. The server decrypts it to validate the request originated from a legitimate page load. See `booket/utils.py` → `generate_signature` / `valid_signature`.

---

## State Object

All booking state is accumulated in a single JS object (`appointment`) throughout the flow:

```js
appointment = {
    provider_identifier: "my-salon",  // from hidden input
    server_id: 42,                    // ProviderServer.id
    server_name: "Alice",
    services: [
        { service_id: 5, service_name: "Haircut", price: 150000, duration: 60 }
    ],
    date: "2025-08-01",               // set in Step 2
    time: "10:00",                    // set in Step 2
    otp_id: 7,                        // returned from create endpoint, used in OTP calls
}
```

---

## Data Format Notes

- **Phone number**: stored and sent as `+998XXXXXXXXX` (country code prepended to 9-digit input)
- **Date of birth**: user sees `dd.mm.yyyy` (flatpickr format); sent to API as `YYYY-MM-DD`. The `parseDob()` helper handles both formats (flatpickr output and ISO auto-fill from `/client/search/`)
- **Confirmation method**: `'p'` = phone/SMS, `'e'` = email
- **Appointment status lifecycle**: `NEW` → `CONFIRMED` (after OTP) → `ACCEPTED` / `COMPLETED` / `NO_SHOW` / `CANCELLED`

---

## Demo Providers

Providers listed in `booket/constants.py → DEMO_PROVIDERS` skip actual SMS/email sending. Instead, the `create` endpoint returns `is_demo: true` and includes the raw `otp_code` in the response, which the frontend displays in an info banner inside the OTP section.
