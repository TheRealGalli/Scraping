# Migrazione email CSD Station

Analisi locale del 23 ottobre 2026. Questo documento non modifica il servizio attivo.
La configurazione effettiva di Cloud Run, Scheduler, IAM e fatturazione non è stata letta.

## Aggiornamento: verifica preventiva richiesta dal proprietario

Prima dell'implementazione, approfondite condizioni di invio e ricezione. SendGrid
rimane un candidato, non è un servizio già collegato al progetto. Il dominio si
acquista su IONOS; SendGrid autentica il mittente e invia, ma non fornisce caselle
consultabili. Le risposte vanno a un servizio di posta distinto, tramite MX e
From/Reply-To coerenti. Inbound Parse è un webhook per un'applicazione, non una inbox.
Fonte: [SendGrid e caselle](https://help.twilio.com/articles/47305406750235-How-to-Find-the-Body-or-Contents-of-Emails).

La scelta di collocare le caselle nel Workspace principale semplifica la lettura
ma condivide l'ambiente amministrativo. Un servizio di posta separato, con webmail
o client, offre separazione operativa; l'inoltro da solo non fornisce l'invio manuale
dal nuovo mittente. Non promettere isolamento assoluto della reputazione.

Google distingue domini alias e domini secondari con utenti propri:
[guida ufficiale](https://support.google.com/a/answer/7502379).
La documentazione Gmail consultata annuncia inoltre modifiche da gennaio 2027 a
“Invia come” per indirizzi esterni. Non fondare la soluzione futura su questa
funzione senza verificare l'applicabilità all'account; gli alias Workspace sono
indicati come esclusi dalla modifica:
[guida Gmail](https://support.google.com/mail/answer/22370?hl=it).

Sul modello attuale, tre verifiche indipendenti:

- **Legge italiana:** la presentazione commerciale B2B a freddo non diventa lecita
  per il solo invio unico con opt-out. Il Garante ha affrontato un caso vicino
  nel provvedimento del 14 maggio 2026, respingendo il ricorso al legittimo interesse
  per l'email promozionale e la giustificazione della pertinenza professionale.
  [Provvedimento](https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/10262105).
- **Provider:** SendGrid richiede opt-in anche per indirizzi generici pubblici.
  Il soft spam eventualmente ammesso dalla legge non sostituisce automaticamente
  il requisito contrattuale del provider. Verificare prima dell'attivazione.
  [Email policy](https://www.twilio.com/en-us/legal/service-country-specific-terms/email).
- **Hosting:** l'AUP Google vieta anche di facilitare promozioni/email di massa
  non richieste. Il vincolo riguarda il dispatcher su Cloud Run anche se il
  trasporto avviene tramite un fornitore esterno; l'enforcement concreto non è
  stato stimato. [AUP Cloud](https://cloud.google.com/terms/aup),
  [AUP Workspace](https://workspace.google.com/terms/use_policy/).

Il GDPR e l'art. 130 non hanno ambito perfettamente sovrapponibile: l'esclusione
dei dati di persone giuridiche dal primo non equivale a libertà di invio promozionale
ai contraenti aziendali. Fonte: [linee guida Garante, sezioni 2.1–2.2](https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/2542348).

Per la protezione dei dati del servizio: verificare DPA di Google e del fornitore,
ruoli, subfornitori e trasferimenti, ubicazione delle singole risorse, accessi,
conservazione e gestione diritti. La regione UE di Cloud Run da sola non dimostra
che tutto il flusso resti in UE. I contratti di trattamento non autorizzano la
finalità promozionale. Fonti: [Google DPA](https://cloud.google.com/terms/data-processing-addendum),
[Twilio DPA](https://www.twilio.com/en-us/legal/data-protection-addendum).

Proposta per proseguire: costruire il motore per contatti con consenso documentato
e per risposte a richieste effettive, separando le comunicazioni di servizio dal
marketing. Per clienti esistenti verificare il soft spam per singola offerta, senza
estenderlo indiscriminatamente alle sei campagne. Acquisizione futura attraverso
form, richieste di preventivo/demo e iniziative con opt-in verificabile; le altre
forme di prospezione richiedono una propria verifica, non sono scorciatoie automatiche.

Disabilitare per default il tracciamento individuale delle aperture finché non
sono definiti presupposti e informativa; le immagini creative non richiedono di
per sé pixel individuali. Fonte: [Garante, tracking pixel](https://www.garanteprivacy.it/temi/tracking-pixel).

## Scelte confermate

- Domini acquistati su IONOS e DNS gestiti su IONOS. Nessuna delega a Cloud DNS.
- Invio da Cloud Run tramite API di un provider email esterno, da scegliere.
- Ricezione delle risposte e gestione manuale da definire con un servizio di posta/inoltro.
- Campagne: consulenza, training, card NFC, sito, social, slide e video.
  L'ultima è interpretata come una singola sezione; demo OS esclusa.
- Scraping invariato in questa fase; evoluzione successiva separata.
- Configurazione degli account e DNS eseguita manualmente dal proprietario.

## Stato rilevato nel codice

| Componente | Oggi | Conseguenza per la migrazione |
| --- | --- | --- |
| `main.py` | `/worker` e `/send-emails`, esecuzione sincrona | Gli invii sono già separati dalla raccolta |
| `smtp_service.py` | SMTP Gmail con email Workspace e password per app | Non usa Gmail API; va sostituito il trasporto |
| `sender_worker.py` | Una email per chiamata come valore predefinito | La frequenza reale dipende dagli Scheduler esterni |
| Limite giornaliero | Contatore locale azzerato a ogni esecuzione | `MAX_DAILY_EMAILS=50` non impone 50 al giorno |
| Finestra invii | 06:00–22:00, tutti i giorni | Da separare dalla finestra dello scraper |
| Deduplicazione | Indirizzi con stato `Inviato` nel foglio | Non distingue campagne; non protegge chiamate concorrenti |
| Errori lettura storico | Ritorno di un insieme vuoto | Un errore può disattivare di fatto la deduplicazione |
| Stato invio | Booleano SMTP e aggiornamento Sheets | Accettazione SMTP non equivale a consegna finale |
| Errori/bounce | Tutti confluiscono in `Errore Invio` | Mancano eventi di consegna, hard bounce e reclami |
| Filtro indirizzi | Esclusione di `support@` | Non esclude privacy/DPO/PEC/no-reply; filtro da aggiungere all'invio |
| Template | Un solo HTML NFC e testo semplice | Serve un catalogo di campagne con versioni |
| Nome attività | Non salvato/ricaricato dalla pipeline Sheets | Il template spesso ripiega su “la tua attività” |
| Raccolta | Places API New, siti web, fallback Custom Search/Vertex | Esaminare separatamente costi e licenza dei dati |
| Limiti raccolta | Una ricerca per esecuzione | Non è un limite giornaliero globale |
| Sicurezza endpoint | Segreto opzionale, anche in URL | Verificare IAM/OIDC e non esporre segreti nei log URL |
| CI locale | Workflow GitHub esegue pytest | Il trigger di deploy dichiarato va verificato su GCP |

## Architettura proposta

Scheduler autenticato → dispatcher Cloud Run → registro condiviso delle spedizioni
→ provider via API → webhook firmati → stato consegna e lista di esclusione.
Sheets resta l'interfaccia operativa comune; il registro transazionale, proposto su
Firestore, governa prenotazioni, quote e storico. Non usare la memoria dell'istanza
Cloud Run o un file locale per limiti giornalieri e lock.

1. Registro mittenti configurabile: indirizzo, dominio, data di attivazione, stato,
   tetto giornaliero e campagne ammesse. Un nuovo dominio non deve richiedere nuovo codice.
2. Rotazione tra mittenti abilitati e autenticati, con quote prenotate in transazione.
   I limiti sono anche globali e per destinatario, condivisi fra tutte le campagne.
3. Chiave di deduplicazione per destinatario normalizzato + campagna + passaggio.
   Bloccare la contemporaneità su uno stesso destinatario e applicare una pausa
   anche fra campagne diverse; cambiare dominio non aggira una cancellazione.
4. Stati distinti: prenotato, invio iniziato, accettato dal provider, consegnato,
   temporaneamente rifiutato, hard bounce, reclamo, disiscritto, esito incerto.
5. Se il provider accetta la richiesta ma la risposta si perde, niente reinvio
   automatico alla cieca: riconciliare tramite ID/eventi o revisione. Non promettere
   consegna esattamente una volta senza supporto di idempotenza del provider.
6. Webhook con verifica firma, protezione replay e deduplicazione degli eventi.
   Hard bounce, reclamo e disiscrizione bloccano il destinatario su tutti i domini.
7. Se lo storico o la lista di esclusione non sono leggibili, fermare l'invio.
8. Modalità anteprima senza invio, modalità collaudo con soli destinatari autorizzati,
   interruttore globale e arresto del singolo dominio. Nessun ritorno automatico a Workspace.
9. Log strutturati con ID spedizione, campagna/versione, dominio, stato, provider ID,
   pausa ed errore classificato. Nei log generali usare identificativi pseudonimi
   per i destinatari; indirizzi completi nel registro ad accesso limitato.

### Quote e temporizzazione

Proposta iniziale configurabile: 15, 35, 80, 200 invii/giorno per dominio nelle
settimane successive. Sono tetti, non obiettivi né garanzie di recapito: crescita
solo con traffico legittimo, autenticazione verificata e metriche sufficienti.
Fermare o ridurre il volume in presenza di reclami, bounce o problemi del provider.

Finestra proposta: lunedì–venerdì, 08:30 inclusa–18:30 esclusa, Europe/Rome,
con gestione ora legale. Verificare di nuovo la finestra dopo eventuale attesa.

Con una email ogni 2 e 4 minuti alternati, in 10 ore si ottengono circa 200 invii
totali. Tre domini non triplicano questo numero. 600 invii richiedono circa un
invio al minuto complessivo e una lista idonea abbastanza grande. A regime valutare
Cloud Tasks per distribuire le scadenze senza tenere richieste aperte in attesa.
Un dispatcher comune è preferibile a sei Scheduler indipendenti che competono
senza un controllo globale. Scheduler separati restano possibili se condividono quote e lock.

## Verifica policy prima della produzione

Il reperimento pubblico di una email non costituisce consenso promozionale.
Il Garante ribadisce il consenso preventivo e la limitata eccezione per clienti
esistenti e prodotti/servizi analoghi. La dicitura B2B e la sola possibilità di
rispondere CANCELLAMI non risolvono il problema della lista attuale.

Fonte: [Garante, provvedimento 23 ottobre 2025](https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/10197577).

SendGrid richiede consenso affermativo per le comunicazioni non transazionali;
non va scelto presumendo che accetti una lista ricavata dallo scraping.
Verificare le condizioni del provider selezionato e la provenienza dei contatti
prima di acquistare il piano o attivare le campagne.

Fonte: [Twilio Email Policy](https://www.twilio.com/en-us/legal/service-country-specific-terms/email).

I termini Maps pongono restrizioni all'estrazione e conservazione dei contenuti
fuori dai servizi. Usare le API ufficiali non autorizza qualsiasi archivio derivato.
Il codice salva fra l'altro rating e numero recensioni: serve una verifica puntuale
di provenienza, conservazione, eccezioni ammesse e contratto applicabile al progetto.
Per account con fatturazione SEE verificare anche i termini regionali e la data
dell'integrazione; non dedurre conformità da un rimborso ricevuto dal supporto.

Fonte: [Termini Maps correnti, sezioni introduttiva e 3.2.3](https://cloud.google.com/maps-platform/terms).

Separare i contatti raccolti dai contatti autorizzati all'invio. Il dispatcher deve
avere evidenza di idoneità per la campagna, fonte, data e motivo di esclusione.
Confermare con un consulente la base applicabile e il testo dell'informativa.

## Email e immagini

Sei template dedicati, con oggetto, preheader, una proposta chiara, una CTA,
testo semplice equivalente, identità, recapiti, privacy e disiscrizione funzionante.
Ogni spedizione registra la versione del template e della campagna.

Proposta visiva: HTML responsive con immagini ospitate via HTTPS, testo leggibile
anche a immagini bloccate, alternative testuali e una copertina per servizio.
Per movimento valutare una GIF breve con primo frame completo. Video, caroselli
interattivi e animazioni complesse appartengono alla pagina collegata: il rendering
nelle caselle email va collaudato su Gmail, Outlook e mobile prima del rilascio.
Generare gli asset una volta per campagna, non a ogni invio. Verificare offerte,
prezzi e affermazioni commerciali del template NFC attuale prima del riutilizzo.

## Guida manuale preliminare: IONOS e GCP

La guida finale con nomi e valori esatti dipenderà da domini e provider scelti.
Non incollare chiavi API o password in chat, nel foglio o nel repository.

1. Acquistare i domini; mantenere i nameserver IONOS. Salvare una copia dei record
   esistenti prima delle modifiche. Non occorre collegare i domini al servizio web
   Cloud Run per utilizzarli come mittenti email.
2. Scegliere provider di invio e servizio di ricezione/inoltro. Verificare eventuali
   costi per tre domini: l'inoltro gratuito non va dato per scontato. Cloudflare
   Email Routing richiede DNS Cloudflare, quindi non è la soluzione per questa scelta.
3. Nel provider aggiungere ciascun dominio e copiare i record forniti.
4. In IONOS → Domini & SSL → dominio → DNS aggiungere TXT/CNAME di verifica,
   DKIM e autenticazione del Return-Path come richiesto dal provider. I record
   DKIM preimpostati di IONOS non firmano l'invio del provider esterno.
5. SPF: un solo record SPF per nome DNS; unire le autorizzazioni necessarie,
   senza pubblicare due SPF concorrenti. Non inventare include o selettori DKIM.
6. DMARC: iniziare con monitoraggio `p=none`, report a un recapito dedicato e
   verifica dell'allineamento con il From. Predisporre l'eventuale autorizzazione
   per report verso un dominio esterno. Passare a policy più restrittive dopo analisi.
7. MX: configurare i valori del servizio che riceve le risposte; separare eventuali
   sottodomini di bounce del provider dagli MX del dominio principale.
8. Verificare l'inoltro con un account esterno. Ricevere nella casella Workspace
   non abilita automaticamente a rispondere dal nuovo indirizzo: configurare e
   collaudare l'invio manuale da quel mittente con autenticazione corretta.
9. In GCP usare l'identità del servizio Cloud Run e permessi minimi per risorse
   interne; salvare la chiave del provider in Secret Manager. Preferire identità
   e autenticazione delegata alle chiavi JSON scaricate dei service account.
10. Configurare registro persistente, webhook, autorizzazioni Scheduler/OIDC,
    metriche, avvisi e limiti. Se il webhook richiede ingresso pubblico, prevedere
    un ingresso separato o un disegno che mantenga protetti gli endpoint operativi.
11. Distribuire inizialmente con invio disabilitato; collaudare solo caselle proprie,
    DNS, consegna, risposta, disiscrizione, bounce e chiamate duplicate.
12. Dopo collaudo attivare pochi invii autorizzati; osservare gli esiti prima della
    crescita. Ritirare la password Workspace dal servizio dopo migrazione riuscita.

Riferimenti: [TXT IONOS](https://www.ionos.it/aiuto/domini/glossario-temi-relativi-ai-domini-spiegati-brevemente/record-txt/),
[CNAME IONOS](https://www.ionos.it/aiuto/domini/configurare-un-record-cname-per-un-sottodominio/configurare-uno-cname-per-un-sottodominio-gia-esistente/),
[requisito DNS Cloudflare](https://developers.cloudflare.com/email-service/get-started/route-emails/).

## Controllo spesa e accesso cloud

La causa dei 600 euro non si può attribuire senza report di fatturazione per SKU,
date, progetto e servizio. Verificare Places, Custom Search, Vertex/grounding,
retry e frequenza effettiva degli Scheduler. Il grounding risulta disabilitato nel
default locale, ma restano fallback Vertex: controllare la configurazione distribuita.

Budget con notifiche, quote API effettive, restrizioni delle chiavi, limiti di
concorrenza e contatori persistenti sono controlli distinti. Verificare se il progetto
supporta spend cap per i servizi interessati; la disponibilità e copertura non
vanno presunte, e l'applicazione non è istantanea.
Fonte: [Google Cloud spend cap budgets](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps).

Nella sessione non è disponibile un connettore di amministrazione Cloud Run/DNS;
la ricerca dei plugin non ne ha individuato uno adatto. Non è stato configurato
accesso GCP. La configurazione manuale resta la scelta confermata. Un eventuale
accesso futuro deve iniziare in sola lettura e senza ruoli Owner/Editor generici.

## Ordine dei lavori e criteri di completamento

1. Confermare domini, provider, ricezione risposte e idoneità dei contatti.
2. Implementare trasporto API, registro transazionale, quote, deduplicazione,
   esclusioni globali, eventi firmati, collaudo e interruttore. Nessun cambio allo scraper.
3. Creare template e anteprime per le sei campagne con asset e offerte verificati.
4. Consegnare guida specifica IONOS/GCP e configurare manualmente gli account.
5. Verificare deploy e collaudo completo prima dell'attivazione.
6. Evoluzione Sheets: contatti, campagne, invii e opposizioni; un contatto può avere
   più campagne ma la cronologia rimane consultabile in comune. Sheets è una vista
   operativa sincronizzata, non l'unica protezione contro i duplicati.
7. Successivamente rivedere estrazione multipla, selezione indirizzo, esclusione
   privacy/DPO/PEC/supporto/no-reply, settori e fonti ammesse. Non considerare
   automaticamente valido un indirizzo `hello@` o `info@` per fini promozionali.

Test necessari al nuovo invio: concorrenza su quote e destinatari, cambio giorno
Europe/Rome e ora legale, weekend e confini orari, rampa per data di attivazione,
timeout ambiguo, webhook duplicati/falsi/fuori ordine, esclusioni fra campagne,
errori del registro, disiscrizione e arresto globale. Nessun test deve inviare
email reali o consumare API a pagamento senza un collaudo esplicitamente attivato.

Stato alla consegna: analisi e piano redatti; nuovo motore e nuovi template non
ancora implementati; nessun DNS, account, invio o deploy modificato.
