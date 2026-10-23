# Settori e parole chiave: aggiornamento operativo

## Criterio di selezione

Tre nuovi settori con un utilizzo concreto dei servizi offerti. Si tratta di una
valutazione commerciale, non di una previsione di conversione o di una nuova
base di autorizzazione al contatto. Le quote restano 150 complessive.

| Nuovo settore | Bisogno plausibile | Campagne |
|---|---|---|
| Agenzie Immobiliari | Presentazioni immobili e incarichi, video dai materiali disponibili, contenuti social, sito e attività ripetitive del team | Consulenza, training, sito, social, media |
| Architettura e Interior Design | Portfolio progetti, presentazioni al cliente, montaggio materiali, comunicazione e procedure interne | Consulenza, training, sito, social, media |
| Eventi e Wedding | Presentazioni servizi, portfolio eventi, video e comunicazione social | Sito, social, media |

Per il settore immobiliare la pertinenza di social e formazione AI è supportata
anche dalle aree del piano formativo FIAIP 2026:
https://www.fiaip.it/piano-formativo-nazionale/
La scelta di architettura ed eventi è una valutazione di aderenza ai servizi,
non un dato misurato sul mercato.

Le agenzie di marketing, le software house e le web agency non entrano ora
nella raccolta: potrebbero richiedere una proposta di collaborazione distinta.
NFC resta rivolta ai settori esistenti, dove recensioni e interazione sul posto
sono già l'obiettivo della campagna approvata.

## Parole chiave dello scraper

Ogni query mantiene città, provincia, regione e Italia. Viene scelta una sola
parola chiave per ricerca, senza moltiplicare le chiamate Places o attivare
Grounding. Le varianti servono a diversificare la scoperta nei giri successivi.
Non si usano affermazioni come “ho visto che il tuo sito non funziona” senza
averlo effettivamente verificato. Gli HTML approvati non vengono sostituiti.

### Ristorazione

ristorante; pizzeria; trattoria; osteria; pizzeria d'asporto; pizzeria al taglio; pub e birreria; bistrot; sushi e poké; tavola calda.

### Studi Professionali

studio legale avvocato; avvocato penalista; avvocato civilista; dentista; studio dentistico; notaio; studio commercialista; studio consulente del lavoro; studio consulenza aziendale.

### Centri e Servizi

centro estetico; parrucchiere; salone barbiere; spa centro benessere; galleria d'arte.

### Hospitality

hotel; bed and breakfast; albergo; affittacamere; agriturismo; resort; residence turistico; boutique hotel.

### Boutique e Retail

boutique; negozio abbigliamento; negozio scarpe e calzature; negozio streetwear; boutique moda; negozio accessori moda; negozio borse e pelletteria; gioielleria; ottica; showroom arredamento; negozio illuminazione; negozio cucine.

### Automotive

officina meccanica; gommista; concessionaria auto; concessionario moto; carrozzeria; elettrauto; autolavaggio; centro revisioni.

### Fitness e Sport

palestra e centro fitness; personal trainer; studio pilates e yoga; box crossfit; centro sportivo; scuola arti marziali; padel club; centro danza.

### Veterinaria e Pet Care

clinica veterinaria; ambulatorio veterinario; toelettatura animali; pet shop negozio animali; ospedale veterinario; pensione per cani e gatti.

### Agenzie Immobiliari

agenzia immobiliare; agenzia compravendita immobiliare; agenzia affitti immobiliari; agenzia immobili commerciali; agenzia immobiliare di lusso; agenzia gestione immobili.

### Architettura e Interior Design

studio architettura; studio interior design; architetto progettazione interni; studio progettazione arredamento; studio home staging.

### Eventi e Wedding

organizzazione eventi; wedding planner; location matrimoni; agenzia eventi aziendali; allestimenti eventi; servizio catering eventi.

## Abbinamenti completi

- **consulenza**: Studi Professionali, Hospitality, Automotive, Agenzie Immobiliari, Architettura e Interior Design.
- **training**: Studi Professionali, Hospitality, Agenzie Immobiliari, Architettura e Interior Design.
- **nfc**: Ristorazione, Centri e Servizi, Hospitality, Boutique e Retail, Automotive, Fitness e Sport, Veterinaria e Pet Care.
- **sito**: Ristorazione, Centri e Servizi, Hospitality, Boutique e Retail, Automotive, Fitness e Sport, Veterinaria e Pet Care, Agenzie Immobiliari, Architettura e Interior Design, Eventi e Wedding.
- **social**: Ristorazione, Centri e Servizi, Hospitality, Boutique e Retail, Fitness e Sport, Veterinaria e Pet Care, Agenzie Immobiliari, Architettura e Interior Design, Eventi e Wedding.
- **media**: Studi Professionali, Hospitality, Boutique e Retail, Agenzie Immobiliari, Architettura e Interior Design, Eventi e Wedding.

## Applicazione controllata

Il comando configure150 fa prima il backup, corregge la tabella delle quote e
rende visibili tutti gli abbinamenti nella scheda RegoleSettori. La conversione
del cursore è esplicita con --expand-scraper e richiede scraper fermo.
La pubblicazione del codice da sola non abilita nuovi settori sullo scraper:
il profilo resta legacy_v1 finché non viene aggiornata ConfigState.
Raccolta, invio e sincronizzazione restano separati. Nessuna attivazione live
è inclusa in questo aggiornamento.
