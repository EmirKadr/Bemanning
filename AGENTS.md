# AGENTS.md

## Syfte

Detta repo innehaller tva forstaklassiga klienter for samma produkt:

- `app/` = webbappen
- `desktop/` = Windows-appen

De ska utvecklas som **en och samma produkt**, inte som tva separata varianter.

## Projektwiki

Det finns en LLM-underhallen projektwiki i `wiki/`.

- Las `wiki/index.md` tidigt nar du behover forsta projektet, anvandarfloden,
  knappar, behorigheter, API:er eller felsokning.
- Folj `wiki/AGENTS.md` nar du uppdaterar wikin.
- Nar en kodandring paverkar produktbeteende, knappar, vyer, roller, API eller
  felmeddelanden ska relevant wiki-sida och `wiki/log.md` uppdateras i samma
  arbetsinsats.

## Huvudregel: strikt funktionsparitet

Alla agenter som arbetar i detta repo ska utga fran att:

- allt som byggs eller andras i webbappen ocksa ska finnas i Windows-appen
- allt som byggs eller andras i Windows-appen ocksa ska finnas i webbappen

Detta galler bland annat:

- funktioner
- arbetsfloden
- knappar och menyval
- validering och regler
- vyer och navigering
- viktiga texter, varningar och anvandarbesked

Ingen agent far medvetet lamna webb och Windows ur synk utan uttrycklig instruktion
fran Emir.

## Praktisk tolkning

Nar du andrar nagot, kontrollera alltid konsekvensen for bada klienterna:

1. Om en ny funktion laggs i webbappen, lagg ocksa till den i Windows-appen.
2. Om en ny funktion laggs i Windows-appen, lagg ocksa till den i webbappen.
3. Om ett arbetsflode andras i ena klienten, uppdatera den andra klienten i samma arbete.
4. Om exakt samma implementation inte ar mojlig, los det med olika teknik men samma beteende for anvandaren.

## Tillatna undantag

Foljande far vara klientspecifikt utan att bryta mot paritetsregeln:

- Windows-installation, `Setup.exe`, auto-update och genvagar
- Render-/serverdrift, deployment och backend-infrastruktur
- andra rent plattformsspecifika detaljer som inte motsvarar en anvandarfunktion

Om du tror att nagot annat maste vara olika mellan klienterna ska det ses som ett
blockerande beslut och inte antas tyst.

## Arbetsregel for agenter

Vid varje andring som paverkar produktbeteende ska agenten:

- aktivt kontrollera bada klienterna
- uppdatera bada sidor i samma arbetsinsats nar paritet kravs
- uppdatera tester och dokumentation nar det ar relevant
- tydligt saga till om full paritet inte hanns med eller om nagot blockerar den

## Testregel for agenter

Varje gang en agent bygger nytt, andrar befintligt beteende eller lagger till ett
nytt arbetsflode ska agenten ocksa se till att det finns relevanta tester for
det nya. Befintliga tester ska uppdateras nar de gamla antagandena inte langre
stammer med hur appen fungerar.

Agenten ska inte lamna ett nytt beteende utan teststod om det gar att testa
rimligt med befintlig teststack. Om nagot inte gar att automatisera ska agenten
skriva tydligt vad som testats manuellt och varfor automatiskt test saknas.

## Beslutsregel

Om en uppgift verkar bara namna `app/` eller bara `desktop/`, men andringen
egentligen paverkar anvandarflodet, ska agenten anda behandla den som en
paritetsandring for bada klienterna om inte Emir uttryckligen sagt annat.
