# Analisi e ottimizzazione costi — 23 ottobre 2026

## Risultato e limiti

Ottimizzazione interna: stessi orari, stesso Sheet, sincronizzazione ogni 15 minuti,
stesso tetto di 150 e stessi controlli transazionali prima dell'invio. Non sono
stati modificati quota Places, orari dello scraper, stato live/test o interruttori.
Nessun accesso alla fattura, alle metriche live o alle quote effettive del progetto:
i valori economici restano scenari, da verificare dopo il rilascio del job.

La fascia precedente di 50–100 USD/mese riguardava l'implementazione con scansioni
e riscritture complete a ogni ciclo, non il costo necessario per 150 email.

## Dove si spendeva

Con 7.577 contatti, 27.977 associazioni e circa 4.580 eventi storici:

| Processo precedente | Ordine di grandezza |
|---|---:|
| Letture per sincronizzazione | 64.000 |
| Scritture per sincronizzazione | 35.500 |
| Sincronizzazioni per giorno feriale | 44 |
| Letture per giorno | 2,8 milioni |
| Scritture per giorno | 1,56 milioni |

La vecchia query destinatari recuperava inoltre fino a 100 documenti anche quando
il primo era idoneo. Questa spesa era distinta dalla sincronizzazione.

## Modifiche implementate

1. Checkpoint compresso nel bucket UE già esistente, cartella campaign-checkpoints/.
   Contiene la proiezione per import/report, con datetime preservate, identità del
   progetto/database/namespace, watermark e versione del formato.
2. Primo ciclo: lettura completa per costruire il checkpoint. Cicli successivi:
   query solo sui documenti modificati, tramite _updated_at assegnato dal server
   Firestore. Una sovrapposizione di cinque minuti rende il replay conservativo.
3. Documento invariato: nessuna riscrittura. Anche le transazioni evitano set
   identici. Gli invii reali continuano a leggere direttamente Firestore: la cache
   non decide mai se si possa inviare, né sostituisce la transazione.
4. Report costruiti in memoria dalla proiezione aggiornata; niente riletture della
   collezione completa per ogni report o di ogni campagna per ogni giorno storico.
5. Sheet: intestazioni lette senza scaricare l'intera scheda; gruppi di celle dei
   contatti aggiornati solo se diversi. D e H restano manuali. Report identici
   non vengono cancellati e ricostruiti.
6. Backup completo quando cambiano input, controlli o versione targeting, e almeno
   una volta per giorno operativo anche senza modifiche. Prima di apply/configure
   resta obbligatorio un backup completo. Non si cambia la retention di 30 giorni.
   Gli stati nuovi degli invii restano nel registro Firestore e nel checkpoint;
   non si crea più uno snapshot Sheets identico ogni 15 minuti.
7. Query destinatari in pagine da 10, caricate solo quando servono, con lo stesso
   massimo di 100 candidati per tentativo. I candidati esclusi non vengono persi.
8. Riconciliazione completa settimanale: intercetta anche eventuali cancellazioni
   manuali fuori dall'applicazione. Il primo ciclo e questa riconciliazione hanno
   un picco di letture da considerare nel budget.
9. Salvataggio checkpoint con condizione sulla generazione GCS: un'esecuzione non
   può sovrascrivere silenziosamente il risultato concorrente. File corrotto,
   identità diversa o errore di accesso fanno fallire il job con invii in manutenzione.
10. Log di conteggi stimati document_reads/document_writes e dimensione checkpoint.
    Sono indicatori applicativi, non sostituiscono le metriche di fatturazione:
    possono contare diversamente retry, letture di indici e richieste fallite.

La sincronizzazione conserva la lettura completa degli input Sheets per rilevare
anche modifiche alle prime righe, rimozioni e abilitazioni manuali: non usa un
semplice indice dell'ultima riga che perderebbe le correzioni dei contatti vecchi.

## Budget dopo il rilascio

A dati invariati la sincronizzazione non riscrive contatti, associazioni o eventi:
le operazioni fisse sono poche query/controlli per ciclo. Con 150 invii, normali
modifiche e nessuna raccolta massiva, l'obiettivo è stare sotto 50.000 letture e
20.000 scritture/giorno nella maggior parte delle giornate. Non è un limite
tecnico automatico: candidati esclusi, replay, modifiche massive e riconciliazione
settimanale possono superarlo. Il primo bootstrap può avvicinarsi da solo alla
quota giornaliera di letture. Non promettiamo costo assoluto zero.

Il consumo delle nuove acquisizioni dipende dai contatti unici e dalle campagne
pertinenti: 1.000 nuovi contatti con quattro associazioni richiedono circa 5.000
scritture di import, non una riscrittura di tutto il database.

| Voce | Azione / valutazione |
|---|---|
| Firestore | Da milioni di operazioni ripetute a modifiche effettive. Misurare due sync consecutivi e una giornata con invii. |
| Cloud Run | Niente sleep tra invii. Il job termina dopo il lavoro; cache gzip limita trasferimento e parsing. Non ridurre memoria alla cieca. Verificare min instances=0 nel servizio e quote gratuite condivise. |
| Cloud Storage | Checkpoint gzip riutilizzato, backup senza duplicazioni inutili. Regione Belgio: non assumere il free tier Storage USA. Le vecchie generazioni in soft delete possono occupare spazio. |
| Scheduler | Prezzo per job, non per esecuzione. Quattro job noti, inclusi quelli in pausa; tre gratuiti per billing account, poi 0,10 USD/job/mese. Non eliminati automaticamente i vecchi job. |
| Secret Manager | Il segreto viene risolto nella revisione; non lo si legge con una chiamata API per ogni invio dal backend. Gli script di prova lo leggono esplicitamente. |
| Logging | Log essenziali, senza contenuti email/chiavi. Verificare volume fatturato prima di ridurre retention o diagnostica. |
| Artifact Registry | Le immagini dei deploy si accumulano. Valutare pulizia in dry run, preservando immagine del servizio, job e rollback: nessuna cancellazione automatica applicata qui. |
| Cloud Build | Una build per push; evitare push di sola configurazione quando basta aggiornare env. Verificare pool e minuti gratuiti effettivi. |
| Places / ricerca | Scraper resta controllato manualmente. MAX_SEARCH_QUERIES_PER_RUN e campi Places invariati, nessuna chiamata esterna fatta dai test. Custom Search è un fallback distinto se configurato. |
| Vertex AI | I percorsi AI sono condizionati da ENABLE_GEMINI_GROUNDING. Non abilitarlo per l'ottimizzazione. Verificarne il valore live senza mostrare chiavi. |

Le quote gratuite si condividono dove previsto dal servizio; un budget di
fatturazione con avvisi non è un interruttore automatico di spesa.

## Applicazione senza modificare la pausa globale

1. Lasciare ControlloInvii!A2=TRUE e scraper PAUSED. Mettere in pausa
   campaign-registry-sync e attendere che non ci siano esecuzioni admin attive.
2. Attendere il deploy del nuovo commit sul servizio, poi allineare il job alla
   stessa immagine. Non eseguire il job vecchio dopo aver inizializzato la cache:
   i vecchi writer non compilavano _updated_at.
3. Sul bucket esistente mantenere Object Creator per i backup e aggiungere
   Object User SOLO per campaign-checkpoints/, con condizione sul nome oggetto:

```bash
gcloud storage buckets add-iam-policy-binding gs://scraping-505816-campaign-backups-707079344561 --member="serviceAccount:707079344561-compute@developer.gserviceaccount.com" --role="roles/storage.objectUser" --condition="expression=resource.name.startsWith('projects/_/buckets/scraping-505816-campaign-backups-707079344561/objects/campaign-checkpoints/'),title=campaign_checkpoint_only" --format="value(etag)"
```

Il bucket ha già accesso uniforme. Il permesso serve a leggere e sostituire il
checkpoint; non concede la lettura o cancellazione dei backup in altre cartelle.
Non serve listare il bucket. Non scaricare credenziali JSON.

4. Conservare gli argomenti sync, --legacy-campaign nfc e --backup-bucket già
   presenti. Eseguire una volta: bootstrap=true è atteso. Eseguire una seconda
   volta: bootstrap=false e forte riduzione delle operazioni sono attesi.
5. Verificare che i due sync terminino, pause/quote restino invariate e lo storico
   sia integro. Solo allora riprendere campaign-registry-sync ogni 15 minuti.
6. Il codice non cambia SENDING_ENABLED, SENDER_MODE o Pausa globale. I contatti
   in revisione non vengono riabilitati e i contatori non vengono azzerati.

In caso di errore del checkpoint, non disattivare manutenzione o cancellare lo
storico per far ripartire gli invii. Riparare permessi/errore e rieseguire sync.
La perdita del solo checkpoint richiede una nuova scansione di bootstrap; il
registro autorevole rimane Firestore. Le modifiche native vanno sempre attraverso
il nuovo store per conservare il tracciamento server delle modifiche.

## Fonti ufficiali consultate

- https://cloud.google.com/firestore/pricing
- https://cloud.google.com/run/pricing
- https://cloud.google.com/scheduler/pricing
- https://cloud.google.com/storage/docs/access-control/iam
- https://cloud.google.com/storage/docs/access-control/iam-roles
- https://cloud.google.com/artifact-registry/docs/repositories/cleanup-policy
