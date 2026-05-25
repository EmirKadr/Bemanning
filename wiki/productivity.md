---
title: Produktivitet
status: aktiv
updated: 2026-05-25
tags: [produktivitet, filer, kpi, ui]
---

# Produktivitet

Kort svar: Produktivitet analyserar stora lokala CSV-loggar i klienten och kombinerar dem med permanenta KPI-mal fran servern. KPI-malet ar en verksamhetsseparerad karnfil: Stigamo, R3 och framtida verksamheter har samma filtyp men egna data. Tre synliga loggar kravs lokalt: Plocklogg, Translogg och Palllastningslogg. Atkomst styrs via Vybehorigheter for `productivity`, inte via hard Super User-krav.

## Behorighet

Rollen behover minst `productivity=view` for att oppna sidan och lasa status/KPI-mal. `productivity=edit` kravs for serverhanterade produktivitetsfiler, till exempel uppladdning eller rensning av permanent KPI-mal. Super User har fortfarande full atkomst automatiskt.

## Knappar och kontroller pa sidan

| Kontroll | Vad anvandaren gor | Vad systemet gor | API/kod | Vanliga fel |
| --- | --- | --- | --- | --- |
| Datum | Valjer rapportdatum | Renderar rapport for datumet | `loadProductivity`, lokal cache | Om filerna saknar datumet visas tom/ingen data. |
| Foregaende/nasta datum | Klickar pilar | Hoppar till narliggande datum som finns i datasetet | `shiftProductivityDate` | Disabled om inget fore/efter-datum finns. |
| Omradesfokus i sidebar | Valjer Alla/GG/AS/EH/MG | Filtrerar rapportsektioner; `∞` visar alla block | `flow:areaFocusChanged`, `preferredProductivityGroupFilter` | Om fel block visas, kontrollera togglen nere i sidebar. |
| Sok | Skriver text | Filtrerar sektioner/rader klient-side | `activeSearch`, `renderContent` | Sokningen ar lokal och paverkar inte datan. |
| Filkrav/dropzoner | Drar filer till kravslot | Sparar lokal fil i IndexedDB | `productivityUploads.saveFiles` | Okand filtyp om namn/header inte matchar. |
| Välj per filslot | Oppnar filval for viss filtyp | Sparar vald fil pa den sloten | IndexedDB `flow-productivity-files` | Vald fel fil kan klassas om targetKey anvands. |
| Rensa per filslot | Klick pa x | Tar bort lokal fil | `deleteFile` | KPI-mal ar permanent och kan inte rensas via x. |

## Filer och identifiering

| Nyckel | Label | Prefix/header-hints | Var sparas |
| --- | --- | --- | --- |
| `pick` | Plocklogg | `v_ask_pick_log_full`, headers `Zon`, `Plockat`, `Anvandare`, `Andrad`, `Bolag` | IndexedDB lokalt |
| `trans` | Translogg | `v_ask_trans_log`, headers `Pallid`, `Fran`, `Till`, `Antal`, `Timestamp` | IndexedDB lokalt |
| `pallet` | Palllastningslogg | `v_ask_palletloading_log`, headers `Plockpallsnr.`, `Palltyp`, `Pallplacering`, `Transnr.`, `Vikt` | IndexedDB lokalt |
| `kpi` | KPI-mal | `v_ask_kpi_target`, headers `Flodesnamn`, `Processnamn`, `Beskrivning`, `Rader`, `Kollin` | Server/permanent verksamhetskatalog |

## Karnfiler och verksamhet

- KPI-mal ar permanent serverdata och fungerar som produktivitetens karnfil.
- Backend laser och sparar KPI-mal via inloggad anvandares verksamhetskod.
- Stigamo, R3 och nyare verksamheter far separata kataloger under `data/coredata/`, till exempel `data/coredata/stigamo/`, `data/coredata/r3/` och `data/coredata/<verksamhetskod>/`.
- En KPI-fil uppladdad for R3 ska aldrig anvandas for Stigamo, och tvartom.
- Stigamo kan lasa den gamla root-filen i `data/` som bakatkompatibel fallback om ingen Stigamo-scopead KPI-fil finns. Nya uppladdningar sparas alltid verksamhetsscopeat i `data/coredata/`.

## Berakningsgrupper

Rapporten grupperar bland annat:

- Granngarden: plockzon A/B och S.
- Autostore: butik plock AS, dekantering GG/MG.
- E-Handel: GG/MG E-handel plock och pack.
- Mestergruppen: plockzon A/B/N och O.

Vissa anvandare exkluderas hardkodat i frontend/backendlogik for specifika grupper.

## Tekniskt flode

1. `productivity_uploads.js` sparar synliga loggar lokalt i IndexedDB.
2. KPI-fil laddas upp via `/api/productivity/files/raw` och sparas server-side i anvandarens verksamhetskatalog.
3. `productivity.js` laser lokala filer radvis i browsern, bygger dataset och hamtar verksamhetens KPI-mal via `/api/productivity/targets`.
4. Rapport for vald dag byggs lokalt och cachas. Intilliggande datum kan forhamtas.
5. Backend har motsvarande service for serverklassning/status och permanenta KPI-mal.
6. Serverhanterade uppladdningar/rensningar via `/api/productivity/files*` auditloggas som `productivity_file` med filtyp, antal forsokta, antal sparade och antal okanda filer. Om uppladdningen kraschar innan svar loggas `upload_failed` med feltyp och eventuell HTTP-status. Privata filnamn sparas inte i auditloggen.

## Felsokningssvar for framtida chat

| Fraga | Svar |
| --- | --- |
| "Varfor raknas inte Produktivitet?" | Kontrollera att Plocklogg, Translogg, Palllastningslogg och permanent KPI-mal finns for anvandarens verksamhet. |
| "Varfor ar nasta/foregaende datum disabled?" | Datasetet har inget tillgangligt datum i den riktningen. |
| "Varfor kanner appen inte igen filen?" | Filnamnet maste matcha prefix eller header-raden maste innehalla forvantade kolumner. |
| "Varfor syns KPI inte som fil jag kan rensa?" | KPI-mal ar permanent serverdata for verksamheten, inte lokal loggfil. |
| "Varfor skiljer Produktivitet fran annan anvandares dator?" | De stora loggfilerna ar lokala per klient; KPI-mal ar gemensamt inom verksamheten. |

## Kallor

- `../app/frontend/produktivitet.html`
- `../app/frontend/js/productivity.js`
- `../app/frontend/js/productivity_uploads.js`
- `../app/backend/productivity_service.py`
- `../app/backend/coredata_service.py`
- `../app/backend/routers/productivity.py`
