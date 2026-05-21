---
title: Aktiviteter och omraden
status: aktiv
updated: 2026-05-21
tags: [aktiviteter, omraden, ui, import]
---

# Aktiviteter och omraden

Kort svar: Aktiviteter ar de valbara varden som bemanningsceller kan fa. Varje aktivitet har etikett, farg, omrade, kategori, sortering och eventuell summeringsaktivitet.

## Knappar och kontroller

| Kontroll | Vad anvandaren gor | Vad systemet gor | API/kod | Vanliga fel |
| --- | --- | --- | --- | --- |
| Ny aktivitet | Oppnar modal | Skapar aktivitet | `POST /api/activities` | Etikett kravs. |
| Ladda ner importmall | Hamter Excelmall | Laddar ner mall | `GET /api/activities/import-template` | Dold utan `activityImport` edit. |
| Importera Excel | Oppnar filval | Importerar aktiviteter | `POST /api/activities/import` | Max 5 MB; dubblettkod stoppas. |
| Hjalp med import | Oppnar hjalpmodal | Visar importstod | `setupImportHelpButton` | Ingen serverkoppling. |
| Redigera | Oppnar modal for befintlig aktivitet | Sparar andringar | `PUT /api/activities/{id}` | Kod kan vara read-only for icke-super-user. |
| Ta bort | Bekraftar | Inaktiverar aktivitet | `DELETE /api/activities/{id}` | Text sager permanent men beteendet ar soft delete. |

## Aktivitet-modal

Falt:

- Etikett: synligt namn i dropdowns och rapporter.
- Kod: visas/hanteras bara for anvandare som far se koder.
- Omrade: kopplar aktiviteten till MG/GG/AS/EH eller inget omrade.
- Summeras som: pekar pa annan aktivitet for summering.
- Farg: anvands i schema och oversikt.
- Kategori: t.ex. work/annan kategori enligt UI.
- Sortering: ordning i listor/dropdowns.

Knappar:

- `Avbryt`: stanger utan sparning.
- `Spara`: skickar `POST`/`PUT`.

## Omraden

Omraden finns som egen backendresurs (`/api/areas`) men nuvarande synlig registervy ar `aktiviteter.html`. `stallen.html` ar legacy-redirect till `aktiviteter.html`.

Omradesfokus i sidebar paverkar sortering och standardval i flera sidor, men andrar inte databasens omrade.

## Summeringsaktivitet

`summary_activity_id` gor att en aktivitet kan raknas som en annan i summeringar. Backend ska hindra loopar. Om summering verkar konstig, kontrollera om aktiviteten summeras som annan aktivitet.

## Felsokningssvar for framtida chat

| Fraga | Svar |
| --- | --- |
| "Varfor ser jag inte kodkolumnen?" | Endast anvandare med ratt behorighet/super-user-lage ser eller far andra aktivitetskoder. |
| "Varfor kan jag inte skapa aktivitet?" | Anvandaren saknar edit-atkomst till `activities` eller etiketten saknas. |
| "Varfor blir summeringen fel?" | Kontrollera `Summeras som`; aktiviteten kan vara mappad till annan summeringsaktivitet. |
| "Varfor hittar jag inte Stallen?" | `stallen.html` redirectar till Aktiviteter. Begreppet har migrerats. |

## Kallor

- `../app/frontend/aktiviteter.html`
- `../app/frontend/stallen.html`
- `../app/frontend/js/activities.js`
- `../app/backend/routers/activities.py`
- `../app/backend/routers/areas.py`

