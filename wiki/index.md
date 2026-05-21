---
title: Bemanning wiki-index
status: aktiv
updated: 2026-05-21
tags: [wiki, index]
---

# Bemanning wiki-index

Kort svar: Bemanning ar en FastAPI/vanilla-JS webbapp och PyQt-baserad Windows-app for planering av bemanning, register, historik, produktivitet och lagerverktyg. Den har wikin ar agentens forsta stopp innan kodlasning.

## Starta har

- [Projektoversikt](overview.md) - vad produkten gor och vilka delar som finns.
- [Arkitektur](architecture.md) - webb, backend, databas, desktop och deployment.
- [Datamodell](data-model.md) - tabeller, relationer och viktiga invariants.
- [Roller och behorighet](auth-roles-access.md) - session, roller, vyatkomst och read-only.
- [UI-karta och alla kontroller](ui-map.md) - snabbkarta over knappar, menyer och generella UI-funktioner.
- [API-karta](api.md) - endpoints grupperade efter funktion.
- [Test och release](testing-release.md) - hur en agent verifierar andringar.

## Funktionssidor

- [Bemanning dagsschema](bemanning-schedule.md) - matrisen, celler, split, drag, kopiera, rensa, undo/redo och kalkyl.
- [Oversikt](overview-page.md) - vecka/manad, heldagsbemanning, drag och undo/redo.
- [Personer](persons.md) - personregister, inline-edit, import och veckomall.
- [Aktiviteter och omraden](activities-areas.md) - aktivitetsregister, kod, summering och legacy-stalle.
- [Anvandare och installningar](users-settings.md) - anvandare, roller, vybehorigheter, meny och cell-las.
- [Historik och audit](history-audit.md) - filter, statistik och auditlogg.
- [Produktivitet](productivity.md) - lokala loggfiler, KPI-mal, berakningar och vanliga stopp.
- [Lagerverktyg](warehouse-tools.md) - Uppladdningar, Bearbeta, Dela, Harleda och allokeringsfloden.

## Chat- och felsokningsstod

- [Felsokning och framtida LLM-chat](troubleshooting-chat.md) - fragor/svar och symptom till rotorsak.
- [Kallmanifest](sources.md) - vilka filer som anvandes nar wikin skapades.
- [Logg](log.md) - append-only historik over wikiarbete.

## Underhallsregel

Las [Wiki-agentregler](AGENTS.md) innan du uppdaterar wikin. Nar kod eller produktbeteende andras ska relevanta sidor och `log.md` uppdateras i samma arbete.

