# Priorità dei contatti e distribuzione geografica

Preparata il 2 novembre 2026. L'attivazione su Cloud Run richiede il nuovo job
di sincronizzazione e SMART_SELECTION_ENABLED=True sul servizio di invio.
Il valore predefinito False conserva il selettore precedente fino all'attivazione.

## Regole

1. Usare soltanto contatti abilitati, senza revisione o esclusioni, compatibili
   con i settori della campagna e con gli intervalli previsti.
2. Dare precedenza a chi non ha mai ricevuto una campagna reale. Contano anche
   gli invii importati da Italy; le prove verso la casella del proprietario non
   consumano questa priorità. Uno storico incompleto con campagne già inviate o
   chiavi legacy viene comunque considerato un contatto già raggiunto.
3. Applicare questa precedenza fra tutte le campagne attive che hanno ancora
   quota disponibile. Una campagna senza primi contatti attende il turno di
   un'altra che ne ha, invece di anticipare una seconda proposta.
4. Fra i contatti della stessa categoria, favorire province e città con meno
   tentativi del nuovo selettore nella giornata. I conteggi iniziano
   all'attivazione e sono condivisi fra le campagne,
   persistono fra le esecuzioni e ripartono al cambio di giorno Europe/Rome.
5. Considerare contatti già raggiunti per una campagna diversa soltanto quando
   non risultano primi contatti disponibili nelle campagne con quota residua.
   Rimangono applicati i controlli su storico, pause, esiti incerti e duplicati.

Il criterio usa dati verificabili già presenti: settore, storico, città e provincia.
Non assegna probabilità di acquisto né deduce la pertinenza da stelle o recensioni.
L'ordine delle righe di Italy o Contatti non determina la sequenza degli invii.

## Sincronizzazione e limiti

Il sync importa anche le località di Italy, raggruppando lo stesso indirizzo in un
solo contatto. Per indirizzi condivisi fra sedi conserva fino a 100 località e usa
una sede rappresentativa in ordine stabile. Località mancanti restano distinte
come non specificate; non vengono inventate.

Ogni sync prepara una lista di massimo 300 candidati per campagna e modalità,
alternando le città sull'intero insieme idoneo. Il campione geografico ruota ogni
15 minuti. Queste liste sono salvate in campaign_sender_v1_selection_queues;
non richiedono nuovi indici Firestore, API Places o analisi AI.

Il sender ordina questa lista usando i conteggi geografici della giornata e
ricontrolla il contatto e le esclusioni nella transazione prima di prenotare.
Una lista mancante, incompatibile o più vecchia del limite di sincronizzazione
ferma la selezione con selection_sync_required.

Se i primi contatti di una lista sono stati nel frattempo esauriti o bloccati,
il sender attende il sync seguente anziché anticipare una seconda proposta.
Questo può lasciare temporaneamente uno slot vuoto. La lista non è una promessa
di invio né rappresenta tutti i destinatari disponibili.

Il checkpoint dei report mantiene il proprio formato: le liste sono dati derivati
separati. La prima sincronizzazione arricchisce i contatti con le località;
le successive conservano la scrittura incrementale. Ogni sync pubblica al massimo
sette documenti di selezione, senza scandire l'intero archivio a ogni email.

## Attivazione e ripristino

Il push su main attiva il deploy automatico del servizio Cloud Run. Il codice
mantiene il nuovo selettore disattivato per default fino alla prima preparazione
delle liste. Anche l'ordinamento aggiornato di Panoramica entra nel repository.

Dopo il deploy, eseguire in Cloud Shell lo script del medesimo commit:

```bash
bash scripts/activate_smart_selection.sh COMMIT_COMPLETO
```

Lo script attende la revisione pronta del commit indicato, aggiorna campaign-admin
alla stessa immagine ed esegue il normale sync. Solo dopo il successo imposta
SMART_SELECTION_ENABLED=True sul servizio. Conserva gli argomenti sync del job,
le campagne, le quote e gli orari. Sospende il solo Scheduler campaign-registry-sync
durante il passaggio e lo riprende in uscita se era abilitato. Attende eventuali
esecuzioni amministrative precedenti, senza annullarle. Se il nuovo sync fallisce,
la selezione resta disattivata: leggere i log prima di ripetere l'attivazione.

Il percorso di un file sul computer locale non lo rende disponibile in Cloud
Shell. Recuperare lo script dal commit Git prima di eseguirlo; il precedente
installer locale con build manuale non è necessario nel flusso Git automatico.

Per ripristinare il selettore precedente, mantenendo lo storico:

```bash
gcloud run services update scraping --project=scraping-505816 --region=europe-west1 --update-env-vars=SMART_SELECTION_ENABLED=False
```

Le liste restano dati derivati e gli invii già registrati non vengono azzerati.
