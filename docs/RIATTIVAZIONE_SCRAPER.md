# Scraper: nuovi settori e scheda Italy

Configurazione richiesta il 3 novembre 2026: un giro ogni 20 minuti nella fascia
09:00–19:00 Europe/Rome, tutti i giorni. Il controllo della frequenza resta nello
Scheduler; per richiesta del proprietario non viene aggiunto un limite giornaliero
o mensile nel codice.

Il cron è `*/20 9-18 * * *`: 30 avvii, dal primo alle 09:00 all'ultimo alle 18:40.
Il cron `*/20 9-19 * * *` includerebbe anche le 19:00, 19:20 e 19:40, arrivando a
33 avvii. Retry e avvii manuali possono aggiungere chiamate: il numero programmato
non è un blocco applicativo della spesa.

## Settori e ripresa

Il profilo expanded_v4 comprende 21 settori: ai 13 di expanded_v3 si aggiungono
gli otto segmenti per NFC e Video & Slide descritti in
[SEGMENTI_NFC_VIDEO.md](SEGMENTI_NFC_VIDEO.md).
Il precontrollo verifica Italy e ConfigState. Se il profilo era precedente,
converte il cursore una sola volta mantenendo la stessa prossima città e lo stesso
settore di ricerca. I nuovi settori entrano nel giro corrente e in quelli successivi;
non si azzera il percorso né si ricomincia Milano.

Un cursore mancante, una scheda sbagliata o un errore di lettura impediscono
di chiamare Maps. Il numero di ricerche per giro rimane MAX_SEARCH_QUERIES_PER_RUN=1.

## Scrittura nel file con più schede

Lo scraper seleziona Italy per nome: ordine e numero delle altre schede non
influiscono sulla destinazione. Aggiunge nuove righe di 16 colonne A:P (A:K come
prima, segnali in L:P) e mantiene le righe esistenti, inclusi gli stati e le date
di invio storici. Se L1:P1 contengono colonne manuali, scrive solo A:K. Rating e numero
di recensioni sono numeri; i testi sono scritti con RAW.

I Place ID già presenti vengono scartati. La posizione di avanzamento viene
salvata dopo la scrittura delle nuove righe. Se la scrittura fallisce, il punto
resta disponibile al giro successivo. Se fallisce solo il salvataggio del cursore,
il nuovo tentativo rilegge i Place ID e non duplica le righe già salvate.

Lo scraper non scrive in Contatti, Invii o Panoramica. I nuovi contatti idonei
arrivano in quelle viste con il normale job di sincronizzazione.

## Attivazione dopo il deploy Git

Con Scraper in pausa e l'ultimo giro concluso, eseguire lo script del commit
appena distribuito:

```bash
bash scripts/activate_scraper.sh COMMIT_COMPLETO
```

Lo script attende la revisione pronta, aggiorna l'immagine di campaign-admin e
avvia scraper-check con argomenti validi soltanto per quella esecuzione. Il
precontrollo legge le intestazioni e prepara il profilo, senza ricerche Maps né
nuove righe fittizie in Italy. Solo dopo il successo aggiorna e riprende lo
Scheduler Scraper in europe-west8. Il job amministrativo conserva sync come
comando permanente. Le impostazioni degli invii email non vengono modificate.
Il controllo verifica anche che il servizio abbia SHEET_NAME=Italy e una sola
ricerca Maps per giro; non stampa chiavi o credenziali presenti nell'ambiente.

## Consumo Maps

Con una ricerca per giro, 30 avvii/giorno corrispondono a 900 ricerche in un mese
di 30 giorni o 930 in uno di 31, esclusi retry, prove manuali e altri consumatori.
I campi attuali websiteUri, rating e userRatingCount attivano Text Search Enterprise;
businessStatus, primaryTypeDisplayName, googleMapsUri e photos sono Pro e non
cambiano il livello fatturato.
Il listino standard consultato il 3 novembre 2026 prevede 1.000 richieste gratuite
mensili di questo SKU; eventuali piani, crediti e utilizzi condivisi del billing
account vanno verificati nella fatturazione del proprietario. Le eventuali
richieste di Custom Search per cercare siti mancanti appartengono a un'API distinta.

Fonti: [campi Text Search](https://developers.google.com/maps/documentation/places/web-service/text-search#fieldmask),
[listino Google](https://developers.google.com/maps/billing-and-pricing/pricing).
