# Guida GCP: attivazione delle sei campagne

> Aggiornamento: per il nuovo coordinatore unico, 150 email/giorno e gestione
> quotidiana seguire `GESTIONE_CAMPAGNE.md`. La precedente proposta dei sei
> Scheduler di invio è superata: NON crearli insieme al coordinatore unico.

Questa guida accompagna il codice del nuovo motore. Nessun account GCP o foglio
live è stato modificato durante lo sviluppo. Il collegamento Sheets esistente si
riutilizza. Non inviare password, chiavi o esportazioni dei contatti in chat.

## Cosa cambia quando il codice viene distribuito

ATTENZIONE: `/send-emails` smette intenzionalmente di spedire e risponde
`legacy_sender_retired`. I vecchi Scheduler d'invio non possono aggirare il nuovo
registro. `/worker` e lo scraping mantengono il loro funzionamento.

Le sei nuove route sono POST `/send-emails/consulenza`, `/training`, `/nfc`, `/sito`,
`/social`, `/media` (ciascuna preceduta da `/send-emails`). Nessuna spedisce con
la configurazione iniziale: `SENDING_ENABLED=False`.

Il trasporto implementato in questa versione è SMTP Workspace già usato dal
progetto, con il nuovo catalogo HTML e immagini incorporate. Non servono domini
o provider aggiuntivi per collaudare questa versione. Nessuna integrazione API
SendGrid viene presunta attiva. Una futura sostituzione del trasporto non richiede
di riscrivere quote e storico.

## 1. Annotare la configurazione esistente

Nella console GCP seleziona il progetto reale dello scraper e apri Cloud Run.
Annota: nome servizio, regione, URL, service account esecutore, immagine della
revisione e immagine/container pubblicata dal trigger GitHub. Non indovinarli dai
nomi presenti nel codice. Conserva gli ID di progetto, foglio e scheda già funzionanti.

Apri Cloud Scheduler e annota i job che puntano a `/worker` e `/send-emails`.
Metti in pausa SOLO quelli d'invio prima della migrazione; non eliminare lo
Scheduler dello scraper. Il codice nuovo impedirà comunque l'invio dalla route vecchia.

Controlla che il trigger di build pubblichi l'immagine corretta e che i test GitHub
siano verdi. Le modifiche sono pubblicate sul repository collegato. Verifica sempre il commit
effettivamente distribuito prima di aggiornare il job amministrativo.

## 2. Abilitare servizi, database e backup

In API e servizi abilita Firestore e Cloud Storage, se non già disponibili.
Usa Firestore in modalità Native; verifica se `(default)` esiste già e NON
reinizializzarlo. La regione di un database non è una scelta da cambiare a posteriori:
scegli una località UE compatibile con la tua configurazione. Se usi un database
dedicato, imposta `FIRESTORE_DATABASE` con il suo ID in servizio e job.

Il motore usa collezioni con prefisso `campaign_sender_v1_`; non tocca altre
collezioni del progetto. Non aprire le regole Firestore ai browser: il backend usa IAM.

Crea un bucket di backup privato, con accesso uniforme e prevenzione dell'accesso
pubblico. Nome unico, per esempio un nome scelto da te legato al progetto.
I backup contengono indirizzi e dati del foglio: accesso limitato e conservazione
concordata. Come impostazione iniziale puoi applicare la regola di eliminazione
a 30 giorni in `infra/backup-lifecycle.json`. Valuta separatamente la cancellazione
dei dati nel registro quando un trattamento viene cessato.

## 3. Permessi

Al service account del servizio Cloud Run assegna `Cloud Datastore User`
(`roles/datastore.user`) per il database usato. Mantieni l'accesso Sheets esistente.
Se il foglio è condiviso con il service account attuale, non occorre ricondividerlo.

Per il job amministrativo puoi riutilizzare lo stesso esecutore già autorizzato
al foglio, oppure crearne uno dedicato e condividere il foglio come Editor con
quest'ultimo. Deve poter leggere/scrivere Firestore e creare gli oggetti nel
bucket di backup (`Storage Object Creator` sul solo bucket). Il codice non richiede
lettura dei backup; chi farà un ripristino dovrà avere i permessi per leggerli.

In Secret Manager conserva password SMTP e segreto del nuovo sender. Concedi
`Secret Manager Secret Accessor` all'esecutore sulle sole risorse necessarie.
Non servono nuovi file JSON di service account scaricati.

## 4. Variabili del servizio

Cloud Run → servizio → Modifica e distribuisci nuova revisione → Variabili e segreti.
Conserva quelle dello scraper. Aggiungi:

| Nome | Valore iniziale |
| --- | --- |
| SENDING_ENABLED | False |
| SENDER_MODE | dry_run |
| SENDER_CRON_SECRET | Segreto dedicato da Secret Manager |
| TEST_RECIPIENTS | Una tua casella di test, non un lead |
| FIRESTORE_DATABASE | (default), oppure database scelto |
| CAMPAIGN_NAMESPACE | campaign_sender_v1 |
| GLOBAL_DAILY_LIMIT | 50 |
| GLOBAL_INTERVAL_SECONDS | 120 |
| CONTACT_COOLDOWN_DAYS | 30 |
| CONTACT_WINDOW_DAYS | 90 |
| CONTACT_WINDOW_MAX_SENDS | 2 |
| SENDER_START_TIME | 08:30 |
| SENDER_END_TIME | 18:30 |
| CAMPAIGN_SHEET_MAX_AGE_MINUTES | 30 |

Conserva `WORKSPACE_EMAIL`, `WORKSPACE_APP_PASSWORD`, `SMTP_HOST`, `SMTP_PORT`,
`SPREADSHEET_ID`, `SHEET_NAME`, `GCP_PROJECT` e le impostazioni dello scraper.
SMTP usa TLS su 587 o TLS implicito su 465, senza allegare l'immagine NFC alle
altre campagne. Le immagini approvate vengono incorporate come CID.

La quota globale appartiene alla casella condivisa: sei quote da 50 non significano
sei caselle. Non aumentare il totale solo per riempire tutte le quote.
Il vecchio `MAX_DAILY_EMAILS` e il vecchio jitter non governano le nuove campagne:
usa GLOBAL_DAILY_LIMIT, intervallo globale e impostazioni della scheda Campagne.

## 5. Indice Firestore

Firestore → Indici → Composito → Crea indice:

- Collection ID: `campaign_sender_v1_pairs`
- `campaign`: crescente
- `state`: crescente
- `eligible_at`: crescente
- Ambito: collection

Aspetta che sia pronto. La stessa definizione è in `infra/firestore.indexes.json`.
Se scegli un namespace diverso, aggiorna anche il nome della collection dell'indice.
Se Firestore restituisce un link per un indice richiesto, verifica che punti al
database e ai campi qui indicati prima di crearlo.

## 6. Creare il job amministrativo, inizialmente in anteprima

Cloud Run → Jobs → Crea job. Usa la stessa immagine del servizio nuovo, aggiornata
alla revisione che contiene `scripts/campaign_admin.py`. Il job non segue da solo
gli aggiornamenti del servizio: a ogni rilascio verifica e aggiorna l'immagine del job.

Impostazioni:

- Comando container: `python`
- Argomenti: `scripts/campaign_admin.py`, `plan`, `--legacy-campaign`, `unknown`
- Un task, parallelismo 1, retry 0, timeout fino a 3600 secondi.
- Service account e variabili come sopra, inclusi foglio, progetto, database e namespace.
- Non sono necessarie password SMTP nel job amministrativo.

Esegui il job. Nei log deve comparire `status: plan` con i conteggi, senza scrivere
nel foglio o in Firestore. L'anteprima richiede comunque accesso in lettura al database.

Controlla: righe, email uniche, duplicati, stati sconosciuti, errori precedenti,
date mancanti e contatti da verificare. I contatti non sono mostrati nei log.

Se SAI che gli Inviato storici corrispondono tutti alla campagna NFC, imposta
`--legacy-campaign nfc`. Altrimenti lascia `unknown`: non inventiamo lo storico.
Gli invii con campagna o data incerta rimangono in revisione.

## 7. Eseguire la migrazione

Con vecchi Scheduler d'invio in pausa e `SENDING_ENABLED=False`, esegui il job
con questi argomenti:

`scripts/campaign_admin.py apply --legacy-campaign nfc --backup-bucket NOME_BUCKET`

Usa `unknown` al posto di `nfc` se la provenienza non è confermata. Inserisci gli
argomenti come elementi separati nell'interfaccia del container. Il codice attiva
una pausa persistente, salva una copia di TUTTE le schede nel bucket e poi importa.

Risultato atteso: `status: applied`, percorso `gs://...` e ID esecuzione.
Il foglio avrà Contatti, Campagne, RegoleSettori, Invii, Esclusioni, Panoramica e
ControlloInvii. Italy A:K e ConfigState non vengono riscritti.
Gli stati H/I di Italy restano lo storico del vecchio sender; per le nuove
spedizioni si consultano Contatti e Invii. Non usare H per riavviare una campagna.

La migrazione è ripetibile: gli stessi eventi legacy non si duplicano. In caso
di errore rimane la pausa manutenzione; risolvi il problema e riesegui. Non
abilitare l'invio per aggirare un errore di migrazione. Gli esiti incerti del vecchio
sistema non vengono rimessi automaticamente in coda.

## 8. Come usare il foglio

### Campagne

Ogni ID è fisso. Modifica solo gli altri campi:

- Attiva: TRUE/FALSE. Tutte iniziano FALSE.
- Quota: tetto per giornata italiana.
- Quota iniziale: tetto prima della data di attivazione.
- Inizio: `YYYY-MM-DD`, facoltativo. Una data futura impedisce l'invio.
- Rampa: tetti settimanali separati da `;`, per esempio `5;10;20;40` per una
  campagna con quota almeno 40. Il valore finale continua nelle settimane successive.
- Intervallo secondi: pausa minima della campagna, indipendente dal polling Scheduler.

Il valore iniziale della rampa è solo `5`: alzare Quota a 50 NON la alza da solo.
La crescita non è legata a un presunto completamento del warm-up.

### Contatti

Colonne manuali: D Abilitato e H Riferimento autorizzazione. Le altre sono generate.
Non cambiare ID/email, intestazioni o ordine delle righe mentre sincronizzi: usa
viste filtro per consultare. Proteggi le colonne generate e le schede Invii,
RegoleSettori e Panoramica con i permessi Sheets appropriati.

Abilitato è un controllo operativo, non una certificazione di consenso. La
migrazione non crea autorizzazioni che non esistono. Il riferimento può documentare
una richiesta effettiva. Una riga in revisione non si riattiva semplicemente con TRUE:
serve chiarire il motivo e correggere lo storico con evidenze.

### Esclusioni e cancellazioni manuali

Aggiungi Email, Ambito (`globale` oppure un campaign_id), Motivo, Data e Attiva TRUE.
Un rifiuto generico si registra come globale. L'esclusione è letta a ogni chiamata
del sender e resta persistente anche eliminando la riga: non basta cancellare
una riga per riabilitare qualcuno. Non eliminare l'indirizzo soltanto da Italy,
altrimenti potrebbe ricomparire nello scraping.

Per blocco urgente: SENDING_ENABLED=False nel servizio, oppure esegui il job con
`scripts/campaign_admin.py pause`; attendi che eventuali invii in corso finiscano.
Registra l'opposizione e sincronizza prima di riattivare. Un messaggio già accettato
dal server non può essere richiamato dal registro.

ControlloInvii A2 TRUE mette in pausa il sender al successivo controllo. Il valore
FALSE permette l'invio solo se tutti gli altri interruttori lo consentono.

## 9. Sincronizzazione ricorrente

Per importare nuovi record dello scraper, applicare i cambiamenti in Contatti e
aggiornare report/storico, cambia gli argomenti del job amministrativo in:

`scripts/campaign_admin.py sync --legacy-campaign nfc --backup-bucket NOME_BUCKET`

Mantieni la stessa scelta legacy della migrazione. Eseguilo manualmente e verifica.
La sincronizzazione prende un lock, mantiene intatte le colonne manuali D/H,
aggiorna i report e rilascia la manutenzione solo a successo completo. Esclusioni
e quote vengono lette anche dal sender, senza attendere questa sincronizzazione.

Crea uno Scheduler tecnico separato, ogni 15 minuti, per lanciare il job. Non è
una settima campagna. Target HTTP POST:

`https://run.googleapis.com/v2/projects/PROJECT_ID/locations/REGIONE/jobs/NOME_JOB:run`

Body `{}` e autenticazione OAuth (non OIDC per googleapis.com), con un service
account autorizzato a eseguire quel job, per esempio Cloud Run Invoker sulla
risorsa job. Imposta retry 0; il job stesso ha retry 0. Se un import dura più di
15 minuti, riduci la frequenza e adegua consapevolmente il requisito di freschezza.
Le esecuzioni sovrapposte non devono forzare il lock: una fallisce e viene segnalata.

Un sync fallito lascia manutenzione attiva. Se l'ultimo import contatti è più
vecchio di 30 minuti, il sender si ferma. Controlla quindi i job falliti e configura
un avviso Cloud Logging/Monitoring; non confidare solo nei log dello Scheduler che
ha ottenuto l'accettazione dell'avvio del job.

## 10. Sei Scheduler di campagna

Usa un service account invocatore dedicato e concedigli Cloud Run Invoker sul
servizio. Per un servizio privato usa OIDC con audience uguale all'URL base Cloud Run.
Ogni chiamata richiede ANCHE l'header `X-Sender-Secret` uguale al segreto configurato.
Non inserire il segreto nell'URL. Evita di copiarlo in screenshot e documenti.

Se rendi privato un servizio prima pubblico, aggiorna anche l'autenticazione dello
Scheduler `/worker`, conservando il suo X-Cron-Secret se usato. Verifica lo scraper
prima di rimuovere l'accesso pubblico: OIDC sui nuovi job non aggiorna quelli vecchi.

Esempi di polling, timezone Europe/Rome, metodo POST:

| Job | Percorso | Cron |
| --- | --- | --- |
| campaign-consulenza | /send-emails/consulenza | */5 8-18 * * 1-5 |
| campaign-training | /send-emails/training | 1-59/6 8-18 * * 1-5 |
| campaign-nfc | /send-emails/nfc | 2-59/7 8-18 * * 1-5 |
| campaign-sito | /send-emails/sito | 3-59/8 8-18 * * 1-5 |
| campaign-social | /send-emails/social | 4-59/9 8-18 * * 1-5 |
| campaign-media | /send-emails/media | 5-59/10 8-18 * * 1-5 |

Il codice elimina invii prima delle 08:30 e dalle 18:30, oltre ai weekend. Il cron
non garantisce cadenze uniformi al cambio dell'ora; i limiti temporali persistenti
governano l'invio. Retry dello Scheduler: 0 per il collaudo iniziale. Il motore
protegge comunque dalle esecuzioni duplicate. Le quote sono massimi, non obiettivi:
pause, equità, mancanza di candidati o manutenzione possono ridurre il totale.

Crea i job quando SENDING_ENABLED è ancora False, poi mettili in pausa. Non
riattivare i vecchi job d'invio.

## 11. Collaudo globale, in tre passaggi

1. **Anteprima:** SENDING_ENABLED=True, SENDER_MODE=dry_run, A2 ControlloInvii FALSE,
   una campagna attiva. Avvia il suo Scheduler in un giorno/orario ammesso. Atteso:
   preview oppure una ragione esplicita di rinvio. Nessuna quota/history di invio consumata.
2. **Test sulla tua casella:** SENDER_MODE=test, TEST_RECIPIENTS una tua email.
   Attiva a turno le sei campagne e avvia i job. Il motore sostituisce sempre il
   destinatario con la prima casella della allowlist; non spedisce al lead selezionato.
   Quote di campagna e storico test sono separati da quelli live; il tetto globale
   della casella somma entrambi. Il test usa candidati reali
   ammissibili: senza candidati non spedisce. Non inserisce nuovi contatti fittizi
   nell'archivio produttivo. Verifica oggetti, immagini, mobile, link e risposta.
3. **Controlli:** ripeti una chiamata, verifica pause e limiti, registra l'esclusione
   di un indirizzo di collaudo, verifica che non venga selezionato da nessuna campagna.
   Avvia sync e confronta Invii/Panoramica con i log. Le quote test contano anch'esse
   il consumo reale della casella SMTP nel contatore globale condiviso.

Solo dopo conferma: SENDING_ENABLED=False durante i cambiamenti, impostazioni
definitive, lista utilizzabile, SENDER_MODE=live, poi SENDING_ENABLED=True e
riattivazione progressiva dei nuovi job. Mantieni quota globale iniziale 50 o meno.
L'attivazione tecnica non risolve l'idoneità dei contatti al primo invio.

## 12. Errori e arresto

- `sending_disabled`: interruttore ambiente spento.
- `not_ready_or_paused`: migrazione non completata, manutenzione o pausa foglio.
- `contact_sync_required`: eseguire/riparare il sync, non aumentare il timeout alla cieca.
- `fair_turn`: un'altra campagna con candidati recenti ha priorità sullo slot.
- `contact_cooldown`: candidato rinviato; il sistema prova gli altri.
- `campaign_execution_failed` (503): leggere l'errore nei log; non viene tradotto
  in un falso successo. Non eliminare lo storico per riprovare.
- `uncertain` oppure `started` senza esito: possibile accettazione SMTP. Non
  rispedire finché verificato. Sono disponibili i comandi amministrativi sotto.

Per riconciliare una spedizione irrisolta: prima pausa, attendi scadenza del lock
e verifica l'esito in modo indipendente. Esegui il job con:

`scripts/campaign_admin.py resolve --dispatch-id ID --outcome accepted --evidence RIFERIMENTO`

Oppure `--outcome not_sent` SOLO se hai prova della mancata spedizione. Non
consuma una nuova quota e non invia. Conserva il riferimento dell'accertamento.
Un evento iniziato ma abbandonato può restare bloccato fino a questa verifica:
è preferibile a una seconda email non voluta.

Con SMTP accettato non significa consegnato: questa versione non legge automaticamente
le risposte o i bounce arrivati in casella. I rifiuti permanenti riconoscibili come
casella inesistente sono bloccati; gli altri errori sono messi in revisione.
Controlla manualmente bounce e opposizioni e registrali in Esclusioni. Un futuro
provider con webhook aggiungerà la conferma di consegna e bounce asincroni.

Per aggiornare solo i report usa `scripts/campaign_admin.py report` con sender
in pausa e senza modificare il foglio durante l'operazione.

## 13. Backup e ritorno a una revisione precedente

I backup GCS sono JSON con tutte le schede, prima delle modifiche. Per un ripristino,
prima interrompi gli invii e conserva il registro Firestore degli eventi recenti.
Non cancellare le collezioni per fare ripartire gli invii. Importa i dati da backup
su una COPIA del foglio per confronto, non sovrascrivere automaticamente il foglio
attivo. Non è stato implementato un ripristino distruttivo automatico.

Se ripristini una vecchia immagine Cloud Run, verifica prima che i vecchi job siano
in pausa: quella revisione potrebbe riabilitare il sender privo dei nuovi controlli.

## Costi e verifiche ancora da eseguire sul cloud

Firestore aggiunge letture/scritture per contatti, coppie campagna-contatto ed eventi.
La prima importazione può creare decine di migliaia di documenti; il sync esegue
letture/scritture e report sull'intero archivio. Cloud Run Jobs, Scheduler, Storage
e Secret Manager possono aggiungere costi. Configura budget/avvisi e misura la
prima esecuzione prima di scegliere la frequenza definitiva.

I test automatici locali non sostituiscono: indice/database reali, IAM, scrittura
Sheets, backup, autenticazione Scheduler, consegna SMTP e rendering nelle caselle.
Questi sono precisamente gli obiettivi del collaudo GCP prima del live.

Fonti: [Scheduler autenticato](https://docs.cloud.google.com/scheduler/docs/http-target-auth),
[Cloud Run con Scheduler](https://docs.cloud.google.com/run/docs/triggering/using-scheduler),
[esecuzione Jobs](https://docs.cloud.google.com/run/docs/execute/jobs),
[quote Sheets](https://developers.google.com/workspace/sheets/api/limits).
