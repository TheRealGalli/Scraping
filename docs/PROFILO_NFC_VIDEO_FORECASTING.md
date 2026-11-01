# Campagne: NFC + Video & Slide, forecasting preparato

Aggiornamento del 1 novembre 2026. Il backend è su Google Cloud Run, non su
Salesforce. Il deploy del servizio da GitHub non cambia automaticamente le
righe dello Sheet né l'immagine del job amministrativo: occorre applicare il
profilo una volta con i comandi sotto. Non servono nuovi Scheduler o nuove chiavi.

## Decisioni adottate

- Totale mantenuto a 150/giorno: 75 NFC + 75 Video & Slide. Sono massimi, non
  promesse di invio: storico, esclusioni e disponibilità possono ridurre il totale.
- Solo nfc e media hanno Attiva=TRUE. Le altre campagne restano FALSE e quota 0.
  Per riattivarle in futuro bisogna impostare sia quota/iniziale/rampa sia Attiva,
  controllando il tetto globale: il solo TRUE su una quota zero non invia.
- La campagna media esisteva già. Rimane lo stesso ID: nessun azzeramento del suo
  storico e nessuna ripetizione ai contatti già raggiunti da media. Cambia il testo
  e l'immagine (media-v2.jpg), mantenendo gli asset precedenti per riferimento.
- Forecasting è la settima campagna, ID forecasting: HTML, testo e immagine pronti,
  ma Attiva=FALSE, quota 0. Il vecchio Sheet a sei righe resta valido al deploy:
  se la nuova riga manca, il backend considera forecasting disabilitata.
- Orari invariati 09–18 nei feriali; pause globali casuali 120–240 secondi.
- Nel profilo con due campagne, intervallo della singola campagna = 240 secondi.
  Con i vecchi 720 secondi due campagne arriverebbero a circa 90/giorno, non 150.
  Alternando due campagne e considerando il controllo al minuto, 75+75 sono
  raggiungibili in teoria; il totale reale dipende da pause e candidati validi.

## Calibrazione delle offerte sul sito

Analizzati i sorgenti aggiornati di MediaPage.tsx, ForecastPage.tsx, seo/content.ts
e Legal.tsx nel repository del sito. Il lettore web non ha restituito le pagine
pubbliche; il riferimento verificabile in questa sessione è la copia locale.

Video & Slide: mostrare menu, prodotti, collezioni, servizi e progetti partendo
anche da fotografie e materiali già disponibili. Un solo invito verso gli esempi
su /video-slide/, poi contatto; nessun video pesante dentro l'email. Non promettere
miglioramenti clinici o prima/dopo per gli studi dentistici. I materiali di pazienti
non vanno richiesti nel primo messaggio. Il testo resta generale sui servizi.

Forecasting: pianificazione di coperti, acquisti, scorte, ordini e capacità, anche
in locale dopo verifica. Prova gratuita di 7 giorni subordinata a qualità dei dati,
fattibilità e accordo sul perimetro, senza rinnovi automatici. Nessuna percentuale
promessa di accuratezza o risparmio. Nel primo contatto si descrive il bisogno,
senza allegare archivi aziendali o dati personali.

Le immagini sono originali, generate con image_gen: stessa identità di Otto,
avorio/lime, dimensione compressa, una sola immagine incorporata CID per email.
Prompt completi in image-prompts/campaigns-2026-11-01.md.

## Settori e parole chiave

Video & Slide copre tutti i 13 settori attuali, inclusi Ristorazione, Studi
Professionali e Boutique e Retail già presenti nello storico. Quindi non serve
riclassificare in modo arbitrario tutti gli studi professionali come dentisti.

Settori dedicati aggiunti:

| Settore | Query specifiche | Campagne pertinenti |
|---|---|---|
| Gioiellerie | gioielleria; oreficeria; gioielleria artigianale; gioielleria orologeria; laboratorio orafo; gioielleria anelli di fidanzamento | NFC, media, sito, social |
| Studi Dentistici | studio dentistico; clinica dentale; centro odontoiatrico; studio odontoiatria; studio ortodonzia; dentista | NFC, media, sito, social |

Prima gioielleria era già una variante di Boutique e Retail, e dentista/studio
dentistico di Studi Professionali. Si preservano quelle categorie vecchie; i
nuovi settori rendono distinguibili le nuove acquisizioni. I Place ID restano
soggetti alla deduplicazione: non si forza una seconda raccolta dei record già noti.

Forecasting: Ristorazione, Hospitality e Boutique e Retail. Sono gli abbinamenti
iniziali in attesa di studio e attivazione futura. Distribuzione/magazzini, produzione
ed energia sono citati nel sito, ma non si aggiungono qui settori generici solo per
allungare la lista. Richiedono query e targeting dedicati quando la campagna partirà.

Il profilo scraper diventa expanded_v3 (13 settori); legacy_v1=8 ed expanded_v2=11
mantengono esattamente i loro ordini. La conversione salva la stessa città, ciclo
e settore successivo e si applica una volta. Le città passate incontreranno i nuovi
settori al prossimo giro. Non aumenta MAX_SEARCH_QUERIES_PER_RUN, non riavvia lo
scraper e non abilita nuove API o Grounding.

## Applicazione su GCP

Tenere la pausa globale TRUE e il vecchio scraper PAUSED. Fermare solo lo Scheduler
di sincronizzazione e attendere che le esecuzioni precedenti siano concluse.

```bash
gcloud scheduler jobs pause campaign-registry-sync --project=scraping-505816 --location=europe-west1
```

Attendere che la build del nuovo commit sia SUCCESS. Verificare che servizio e
immagine del job usino la stessa nuova versione. Nei comandi seguenti sostituire
NUOVO_COMMIT con lo SHA completo del rilascio indicato in chat, non con main/latest.

```bash
gcloud run jobs update campaign-admin --project=scraping-505816 --region=europe-west1 --image="europe-west1-docker.pkg.dev/scraping-505816/cloud-run-source-deploy/scraping/scraping:NUOVO_COMMIT" --args="scripts/campaign_admin.py,focus150,--expand-scraper,--backup-bucket,scraping-505816-campaign-backups-707079344561"
gcloud run jobs execute campaign-admin --project=scraping-505816 --region=europe-west1 --wait
```

Il comando fa prima il backup completo, imposta 75/75 e le cinque campagne inattive,
aggiorna RegoleSettori, converte ConfigState a v3 e lascia la pausa globale TRUE.
Non riscrive Italy o lo storico, non invia email. È ripetibile senza spostare di
nuovo l'indice. Dopo l'esecuzione non lasciare il job sul comando focus150:

```bash
gcloud run jobs update campaign-admin --project=scraping-505816 --region=europe-west1 --args="scripts/campaign_admin.py,sync,--legacy-campaign,nfc,--backup-bucket,scraping-505816-campaign-backups-707079344561"
gcloud run jobs execute campaign-admin --project=scraping-505816 --region=europe-west1 --wait
```

Il sync importa i nuovi abbinamenti nel registro incrementale, preservando
contatori, esclusioni e storico, incluso il vecchio ID media. La prima volta può
scrivere diverse migliaia di nuove associazioni (anche per la campagna forecasting
preparata), ma non ripete questa spesa ogni 15 minuti.

Verificare Campagne: nfc/media TRUE e 75, tutte le altre FALSE e 0; RegoleSettori
con nuova versione; ConfigState sector_profile=expanded_v3. Impostare esplicitamente
il tetto globale a 150 se è stato cambiato nel frattempo:

```bash
gcloud run services update scraping --project=scraping-505816 --region=europe-west1 --update-env-vars="GLOBAL_DAILY_LIMIT=150"
gcloud scheduler jobs resume campaign-registry-sync --project=scraping-505816 --location=europe-west1
```

I comandi non cambiano SENDER_MODE, TEST_RECIPIENTS o SENDING_ENABLED. Quindi non
presumere di essere in test: prima di provare una nuova email, verificare la modalità
e usare test con una casella propria. Dopo il collaudo, tornare a live, mantenere
la pausa globale finché non si intende partire. Non inviare mai una prova a un lead.
Il coordinatore d'invio esistente resta unico; il suo Scheduler non va duplicato.

## Verifiche locali

Test su compatibilità del vecchio Sheet, forecasting disabilitata senza riga,
profilo 75/75 e storico conservato, conversione cursor v1/v2/v3 con cicli diversi,
HTML/testo/CID e asset, più controlli esistenti su esclusioni, quote, intervalli,
checkpoint e duplicazioni. Anteprime browser desktop e mobile prima della consegna.
