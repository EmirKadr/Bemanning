---
title: Roller och behorighet
status: aktiv
updated: 2026-05-21
tags: [auth, roller, behorighet]
---

# Roller och behorighet

Kort svar: inloggning ar sessionsbaserad. Roller styr vad anvandaren ser och far redigera. Nyare klienter anvander `roles` som lista, men `role` finns kvar for bakatkompatibilitet.

## Inloggningsflode

1. Anvandaren skickar anvandarnamn och losenord till `/api/auth/login`.
2. Backend accepterar bara aktiv anvandare.
3. Om anvandaren saknar/far satt forsta losenord markeras `must_change_password`.
4. Klienten skickar anvandaren till `set-password.html` om losenord maste skapas.
5. Varje skyddad sida anropar `/api/auth/me` via `initPage`.
6. `401` leder till `login.html`; `403 password_setup_required` leder till `set-password.html`.

## Roller

| Roll | Svensk etikett | Typisk atkomst |
| --- | --- | --- |
| `leader` | Arbetsledare | Redigera Bemanning/Oversikt och normalt Personer/Aktiviteter |
| `staffing_manager` | Bemanningsansvarig | Liknar arbetsledare med planeringsansvar |
| `admin` | Administrator | Register, anvandare och settings, men inte automatiskt super user |
| `super_user` | Super User | Kravs for historik och produktivitet enligt skyddade vyer/API |
| `warehouse_clerk` | Lagerkontorist | Lagerverktyg, framfor allt uppladdning, Dela och Harleda |
| `article_placer` | Artikelplacerare | Lagerverktyg med liknande sjalvservicebehov |
| `viewer` | Visning | Laslage for Bemanning/Oversikt |

## Vyatkomst

`common.js` och backendens `require_view_access` anvander samma koncept: varje roll kan ha `none`, `view` eller `edit` per vy. Super user kan fa extra vyer beroende pa installning och serverregler.

Vyer som kan styras:

- `schedule`, `overview`, `productivity`
- `allocationUploads`, `allocationProcess`, `allocationSplit`, `allocationTrace`
- `persons`, `personImport`
- `activities`, `activityImport`, `areas`
- `analytics`, `users`, `userImport`
- `appSettings`, `sidebarLayout`, `roleAccess`

## Read-only-lage

Om anvandaren bara har `view`:

- Bemanning visar celler men sparar inte andringar.
- Oversikt visar dagar men sparar inte andringar.
- Knappar som kopiera/rensa kan vara disabled eller ge varning.
- Toasten forklarar: "Visningslage: du kan se ... men inte andra den."

## Vanliga orsaker till nekad funktion

- Vyn syns inte i sidebar: rollen har `none` for vyn eller sidan filtreras bort.
- Knappen syns men fungerar inte: anvandaren har `view`, inte `edit`.
- Importknapp ar dold: importvyn saknar edit-atkomst.
- Historik/Produktivitet nekas: kraver super user/vyatkomst.
- Bearbeta nekas for lagerroller: bara sjalvservicefloden ar tillatna utan processbehorighet.

## Kallor

- `../app/backend/deps.py`
- `../app/backend/user_access.py`
- `../app/frontend/js/common.js`
- `../app/frontend/js/users.js`
- `../APP_MIGRATION_PLAN.md`

