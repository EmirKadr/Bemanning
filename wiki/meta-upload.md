---
title: Meta-uppladdning
status: aktiv
updated: 2026-05-31
tags: [meta, media, publik, uppladdning]
---

# Meta-uppladdning

Kort svar: `meta-upload.html` ar en fristaende publik mobilvy utan sidebar och utan inloggning. Den ar till for att snabbt ladda upp flera bilder och videor fran Android, iPhone eller desktop. Filerna sparas i databastabellen `meta_media_uploads` med status `pending_analysis` for senare LLM-analys.

## Anvandarflode

1. Anvandaren oppnar `/meta` eller `/meta-upload.html`.
2. Sidan visar bara en enkel uppladdningsyta, ingen sidebar och ingen inloggningskontroll.
3. Anvandaren trycker `Valj bilder eller videor` och kan markera flera bilder/videor i mobilens fil- eller bildvaljare.
4. Valda filer listas med namn och storlek.
5. `Ladda upp` skickar alla filer till `/api/meta/uploads`.
6. Vid lyckad uppladdning visas hur manga filer som sparades. Vid fel visas ett kort felmeddelande pa sidan.

## Knappar och kontroller

| Kontroll | Var | Vem far | Vad hander | API/kod | Vanliga fel |
| --- | --- | --- | --- | --- | --- |
| Valj bilder eller videor | `meta-upload.html` | Alla med lank | Oppnar enhetens filvaljare med `accept="image/*,video/*"` och `multiple` | `meta-upload.html`, `meta_upload.js` | Vissa mobiler kan visa olika valjare beroende pa browser. |
| Ladda upp | `meta-upload.html` | Alla med lank | Skickar valda filer som multipart till backend | `POST /api/meta/uploads` | Nekas om inga filer skickas, om filtypen inte ar bild/video eller om maxstorlek passeras. |

## Tekniskt flode

- `app/frontend/meta-upload.html` laddar bara `css/meta-upload.css` och `js/meta_upload.js`; den laddar inte `common.js` och far darfor ingen sidebar/auth-guard.
- `app/backend/routers/meta_uploads.py` accepterar flera `UploadFile` i faltet `files`.
- Backend tillater bild- och videofiler via MIME-typ eller kand filandelse.
- Varje uppladdning far ett gemensamt `batch_id`. Varje fil sparas som egen rad i `meta_media_uploads`.
- Tabellen sparar `original_filename`, `content_type`, `media_type`, `size_bytes`, binar `data`, `status`, `analysis`, `source` och `created_at`.
- Ny media far status `pending_analysis`. Faltet `analysis` ar reserverat for senare kategorisering/LLM-resultat.

## Felsokningssvar for framtida chat

| Fraga | Svar |
| --- | --- |
| "Varfor ser jag ingen meny?" | Meta-uppladdningen ar en fristaende publik sida utan sidebar. Det ar avsiktligt. |
| "Kan jag valja flera filer pa mobilen?" | Ja, inputen har `multiple` och `accept="image/*,video/*"`. Exakt valjarvy beror pa iOS/Android och browser. |
| "Varfor gick inte filen upp?" | Sidan accepterar bara bilder och videor. Backend kan ocksa neka tomma filer eller for stora batchar. |
| "Analyseras filerna direkt?" | Nej. De sparas med status `pending_analysis` sa ett senare LLM-flode kan analysera dem. |

## Kallor

- `../app/frontend/meta-upload.html`
- `../app/frontend/js/meta_upload.js`
- `../app/frontend/css/meta-upload.css`
- `../app/backend/routers/meta_uploads.py`
- `../app/backend/models.py`
- `../app/alembic/versions/0022_meta_media_uploads.py`
