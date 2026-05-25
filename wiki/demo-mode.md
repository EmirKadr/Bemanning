---
title: Demo-läge
status: aktiv
updated: 2026-05-25
tags: [demo, sandbox, presentationsläge, försäljning]
---

# Demo-läge

Kort svar: flow har ett fast `demo`-konto som vid inloggning får en privat snapshot av live-databasen samt en privat filmapp. Alla ändringar landar i sandboxen — inget syns i produktion — och allt raderas vid utloggning så nästa demo startar rent. Demo-användaren ser samma vyer som en Stigamo-admin.

## Användningsflöde

1. Säljare loggar in i [login.html](../app/frontend/login.html) med `demo` / `demo1234` (eller den default som env `DEMO_USER_PASSWORD` har satt).
2. Backend identifierar demo via username (`DEMO_USERNAME = "demo"` i [demo_session.py](../app/backend/demo_session.py)) och kör `start_demo_session()`:
   - Genererar ett `demo_session_id` (UUID4)
   - Snapshottar live-databasen till `tempfile.gettempdir()/flow_demo_sessions/{uuid}.sqlite` via befintliga `sync_live_to_local.sync_database()`
   - Skapar privat datakatalog `flow_demo_sessions/{uuid}/data/`
   - Sparar `demo_session_id` i Starlette-sessionen
3. Frontend tar emot `is_demo: true` på `/api/auth/me`-svaret och:
   - Lägger på `body.demo-mode` + gul/röd `DEMO`-banner högst upp
   - Visar modal `Välkommen till demo-läget av flow. Vill du se en rundtur?`
   - Vid "Ja": iterativ guide som walkar igenom alla sidor i sidebaren (Bemanning → Översikt → Produktivitet → Hämta data → Bearbeta → Dela → Personer → Aktiviteter → Historik → Användare). Tour-state persistas i `sessionStorage` så den överlever sidbyten.
   - Vid "Nej": tour-flaggan markeras handled och visas inte igen den sessionen.
4. Säljare kan göra precis allt en Stigamo-admin kan — redigera bemanning, skapa personer, ladda upp coredata-filer — utan att det rör produktion.
5. Vid utloggning ringer frontend `/api/auth/logout` som anropar `end_demo_session()`: engine disposas, SQLite-filen raderas, datakatalogen `rmtree`:as, sessionStorage rensas på tour-flaggor.

## Tekniska komponenter

| Plats | Vad |
|---|---|
| [app/backend/demo_session.py](../app/backend/demo_session.py) | Hjärnan: snapshot, engine-cache, end-session, stale cleanup |
| [app/backend/deps.py](../app/backend/deps.py) | `get_db()` byter SessionFactory om `request.session["demo_session_id"]` finns och filen är intakt |
| [app/backend/routers/auth.py](../app/backend/routers/auth.py) | Startar/stoppar demo-session i `/api/auth/login` resp. `/api/auth/logout`. Snapshot-fel → 503 |
| [app/backend/main.py](../app/backend/main.py) | HTTP-middleware sätter `demo_data_root_var` per request; startup-hook rensar stale sessioner |
| [app/backend/coredata_service.py](../app/backend/coredata_service.py) | `default_data_dir()` returnerar demo-mapp under demo. `coredata_read_dirs()` faller tillbaka till prod-data så demo ser befintliga filer |
| [app/backend/allocation_bridge.py](../app/backend/allocation_bridge.py) | `_active_upload_cache_dir()` routar allokerings-uploads till demo-mapp |
| [app/backend/seed.py](../app/backend/seed.py) | `seed_demo_user()` skapar/uppdaterar `demo`-kontot vid varje deploy |
| [app/backend/config.py](../app/backend/config.py) | `DEMO_USER_PASSWORD` (default `demo1234`), `DEMO_SESSION_MAX_AGE_HOURS` (default 6) |
| [app/frontend/js/common.js](../app/frontend/js/common.js) | `ensureDemoBanner`, `maybeShowDemoTourPrompt`, tour-state via sessionStorage, rensning vid logout |
| [app/frontend/css/styles.css](../app/frontend/css/styles.css) | `.demo-banner`, `.demo-tour-card`, `.demo-user-pill` |

## Behörigheter och vyer

- Demo har `role = admin` mot Stigamo. Det betyder att Bemanning, Översikt, Personer, Aktiviteter och Användare är full edit; Bearbeta-matris kan redigeras (admin har `edit`). Historik och Verksamheter syns INTE (kräver super_user). Detta är medvetet — interna detaljer ska inte exponeras externt.
- `is_demo: true` returneras i `UserOut`/`UserAdminOut` så frontend kan trigga demo-UI.

## Skydd mot självskada

I [routers/users.py](../app/backend/routers/users.py):
- `delete_user`: nekar 409 om målet är demo-användaren.
- `update_user`: nekar 409 om någon försöker döpa om demo, ta bort admin-rollen eller inaktivera den.
- Lösenord, visningsnamn och område får fortfarande ändras av super_user (för rotation).

I [frontend/js/users.js](../app/frontend/js/users.js):
- Demo-raden visar en `DEMO`-pill, har dold delete-knapp.
- I edit-modalen är `Användarnamn` och `Roller` disablade när målet är demo. Användaren får en förklarande not.

## Edge cases

| Scenario | Beteende |
|---|---|
| Två samtidiga demo-inloggningar | Vardera får eget UUID och egen SQLite-fil; ingen kollision. |
| Serverkrasch mitt i en demo-session | Filen blir orphaned. Startup-hook `cleanup_stale_demo_sessions(max_age_hours=6)` raderar den vid nästa serverstart. |
| Demo-session äldre än 6h | Cleanup raderar filen. Om sessionen fortfarande har `demo_session_id` i cookien → `get_current_user` ger 401 `demo_session_expired` → frontend redirectar till login. |
| Live-DB nere vid demo-login | `sync_database()` faller. Auth-routern fångar och svarar 503 `Demo-läget kunde inte starta just nu. Försök igen om en stund.` Session rensas. |
| Demo försöker ladda upp coredata | Filen hamnar i `flow_demo_sessions/{uuid}/data/coredata/`, raderas vid logout. Reads ser både demo-mappen och prod-mappen, så produktdata visas. |
| Demo försöker ladda upp allokerings-CSV | Cache-fil hamnar i `flow_demo_sessions/{uuid}/data/allocation_upload_cache/`, raderas vid logout. |
| Desktop-appen | Identiskt beteende — desktop använder samma webbfrontend via [desktop/web_view.py](../desktop/web_view.py). Cookies persistas av QtWebEngine men sessionStorage-rensningen i logout-handlern gör att nästa login alltid får färsk tour-prompt. |

## Återanvändning av befintlig kod

- `sync_live_to_local.sync_database(source_url, target_url)`: one-way Postgres → SQLite, respekterar FK-ordning, hanterar default-businesses.
- Modal-pattern `.modal-backdrop` + `.modal`: samma som befintliga modaler i [users.js](../app/frontend/js/users.js).
- `sidebarPageDefinitions(user, activePage)` ([common.js](../app/frontend/js/common.js)): källa till tour-stegens labels och hrefs.
- `showToast()` för bekräftelse "Rundtur klar".

## Test

```powershell
python -m pytest tests/services/test_demo_session.py tests/services/test_demo_user_protection.py -q
```

Hela sviten ska fortsatt vara grön:

```powershell
python -m pytest -q
```

Manuellt verifiera:
1. Logga in som `demo` / `demo1234` → banner + tour-prompt.
2. Ändra något (skapa person, redigera bemanning) → logga ut → logga in som riktig Stigamo-admin → ändringarna syns INTE.
3. `%TEMP%\flow_demo_sessions\` ska vara tomt efter logout.
4. Två browsers parallellt med demo-konto → vardera sandbox är isolerad.

## Källor

- `../app/backend/demo_session.py`
- `../app/backend/deps.py`
- `../app/backend/routers/auth.py`
- `../app/backend/routers/users.py`
- `../app/backend/main.py`
- `../app/backend/seed.py`
- `../app/backend/coredata_service.py`
- `../app/backend/allocation_bridge.py`
- `../app/backend/sync_live_to_local.py`
- `../app/frontend/js/common.js`
- `../app/frontend/js/users.js`
- `../app/frontend/css/styles.css`
- `../tests/services/test_demo_session.py`
- `../tests/services/test_demo_user_protection.py`
