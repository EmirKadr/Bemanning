---
title: Meta-uppladdning
status: aktiv
updated: 2026-05-31
tags: [meta, media, publik, uppladdning]
---

# Meta-uppladdning

Kort svar: `meta-upload.html` ar en fristaende publik mobilvy utan sidebar och utan inloggning. Den ar till for att snabbt ladda upp flera bilder och videor fran Android, iPhone eller desktop. Filerna sparas i databastabellen `meta_media_uploads` med tidsstamplat `stored_filename`, SHA-256-baserat `content_hash` och status `pending_analysis` for senare LLM-analys. Exakta dubbletter sparas inte igen. Super User ser en skyddad sidebarvy `meta.html` med alla uppladdningar.

## Anvandarflode

1. Anvandaren oppnar `/meta` eller `/meta-upload.html`.
2. Sidan visar bara en enkel uppladdningsyta, ingen sidebar och ingen inloggningskontroll.
3. Anvandaren trycker `Valj bilder eller videor` och kan markera flera bilder/videor i mobilens fil- eller bildvaljare.
4. Valda filer listas med namn och storlek.
5. `Ladda upp` skickar alla filer till `/api/meta/uploads`.
6. Under uppladdningen visas total progress, kvarvarande mangd och status per fil.
7. Vid lyckad uppladdning visas hur manga filer som sparades och hur manga dubbletter som hoppades over. Vid fel visas ett kort felmeddelande pa sidan.
8. Super User kan oppna `Meta` i sidebaren, filtrera pa alla/videor/bilder och klicka `Visa` eller `Oppna` for varje mediafil.

## Knappar och kontroller

| Kontroll | Var | Vem far | Vad hander | API/kod | Vanliga fel |
| --- | --- | --- | --- | --- | --- |
| Valj bilder eller videor | `meta-upload.html` | Alla med lank | Oppnar enhetens filvaljare med `accept="image/*,video/*"` och `multiple` | `meta-upload.html`, `meta_upload.js` | Vissa mobiler kan visa olika valjare beroende pa browser. |
| Ladda upp | `meta-upload.html` | Alla med lank | Skickar valda filer som multipart till backend och visar progress via `XMLHttpRequest.upload` | `POST /api/meta/uploads` | Nekas om inga filer skickas, om filtypen inte ar bild/video eller om maxstorlek passeras. Exakta dubbletter sparas inte igen utan visas som overhoppade. |
| Typ | `meta.html` | Super User | Filtrerar Meta-listan pa alla, videor eller bilder | `GET /api/meta/uploads?media_type=...` | Visar tomt lage om urvalet saknar uppladdningar. |
| Uppdatera | `meta.html` | Super User | Laddar om listan och visar toast nar det ar klart | `meta.js`, `api.get` | API-fel visas via standardlogg/toast. |
| Visa | `meta.html` | Super User | Oppnar modal med video eller bild | `GET /api/meta/uploads/{upload_id}/content` | Stora videor strommas med byte-range men hamtas fran databasen. |
| Oppna | `meta.html` | Super User | Oppnar media i ny flik | `GET /api/meta/uploads/{upload_id}/content` | 403 om anvandaren inte ar Super User. |

## Tekniskt flode

- `app/frontend/meta-upload.html` laddar bara `css/meta-upload.css` och `js/meta_upload.js`; den laddar inte `common.js` och far darfor ingen sidebar/auth-guard.
- `app/backend/routers/meta_uploads.py` accepterar flera `UploadFile` i faltet `files`.
- Backend tillater bild- och videofiler via MIME-typ eller kand filandelse.
- `meta_upload.js` anvander `XMLHttpRequest` i stallet for `fetch` for att kunna visa upload-progress. Filraderna far individuella progressbarer beraknade fran filernas storlek och total `loaded`.
- Varje uppladdning far ett gemensamt `batch_id`. Varje fil sparas som egen rad i `meta_media_uploads`.
- Tabellen sparar `original_filename`, `stored_filename`, `content_type`, `media_type`, `size_bytes`, `content_hash`, binar `data`, `status`, `analysis`, `source` och `created_at`.
- `stored_filename` byggs av serverns UTC-datum/timestamp och filens ordning i batchen, till exempel `20260531_120102_123456Z_01.mov`.
- `content_hash` ar SHA-256 av filens bytes. Backend kollar bade redan sparade filer och filer i samma batch. Om hash finns sedan tidigare sparas inte blobben igen, och svaret far `skipped_count` samt poster med `reason=duplicate`.
- Ny media far status `pending_analysis`. Faltet `analysis` ar reserverat for senare kategorisering/LLM-resultat.
- `GET /api/meta/uploads` och content-endpointen kraver Super User. `meta.html` anvander `initPage("meta", { requireSuperUser: true })` och visas bara for Super User i sidebaren.

## Felsokningssvar for framtida chat

| Fraga | Svar |
| --- | --- |
| "Varfor ser jag ingen meny?" | Meta-uppladdningen ar en fristaende publik sida utan sidebar. Det ar avsiktligt. |
| "Kan jag valja flera filer pa mobilen?" | Ja, inputen har `multiple` och `accept="image/*,video/*"`. Exakt valjarvy beror pa iOS/Android och browser. |
| "Hur vet jag att det laddar upp?" | Sidan visar total progress, kvarvarande mangd och status per fil medan uppladdningen pagar. |
| "Varfor heter videon datum och siffror?" | Backend doper sparade filer med uppladdningsdatum och timestamp sa varje fil blir unik och latt att sortera i Meta. Originalnamnet sparas separat. |
| "Var hittar Super User uppladdade videos?" | I sidebarvyn `Meta`. Dar kan Super User filtrera pa videor och oppna varje fil. |
| "Varfor sparades inte alla filer?" | Om en fil ar exakt samma som en redan sparad fil hoppas den over som dubblett for att inte ta onodigt databas-utrymme. Sidan visar hur manga som hoppades over. |
| "Varfor gick inte filen upp?" | Sidan accepterar bara bilder och videor. Backend kan ocksa neka tomma filer eller for stora batchar. |
| "Analyseras filerna direkt?" | Nej. De sparas med status `pending_analysis` sa ett senare LLM-flode kan analysera dem. |

## Kallor

- `../app/frontend/meta-upload.html`
- `../app/frontend/meta.html`
- `../app/frontend/js/meta_upload.js`
- `../app/frontend/js/meta.js`
- `../app/frontend/css/meta-upload.css`
- `../app/backend/routers/meta_uploads.py`
- `../app/backend/models.py`
- `../app/alembic/versions/0022_meta_media_uploads.py`
- `../app/alembic/versions/0023_meta_upload_stored_filename.py`
- `../app/alembic/versions/0024_meta_upload_content_hash.py`
