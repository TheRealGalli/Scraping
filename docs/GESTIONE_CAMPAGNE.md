# Gestione campagne: configurazione concordata

## Configurazione di riferimento

- Una casella Workspace: carlo@csd-station.it.
- Sei campagne; un SOLO Scheduler di invio su POST /dispatch-emails ogni minuto.
- Finestra servizio: lunedì–venerdì, 09:00 incluso–18:00 escluso, Europe/Rome.
- Massimo 150 tentativi prenotati al giorno, complessivi, non 150 per campagna.
- Il contatore include prove, invii storici odierni e tentativi incerti/rifiutati.
- GLOBAL_INTERVAL_SECONDS=120; GLOBAL_INTERVAL_MAX_SECONDS=240.
- La pausa viene estratta una volta, salvata atomicamente in Firestore prima
  dell'invio e prolungata dalla fine del trasporto; è rispettata da TUTTE le route, anche quelle per campagna.
- Uno Scheduler ogni minuto aggiunge fino a circa 60 secondi alla pausa:
  attesa osservata indicativamente 2–5 minuti, più eventuali ritardi operativi.
- Media nominale pausa 180 secondi + circa 30 secondi di attesa del controllo:
  capacità orientativa 154 messaggi in nove ore; il tetto limita comunque a 150.
  Non è una promessa di 150: quote, turni, contatti e sincronizzazioni riducono il totale.
- Ogni chiamata spedisce al massimo una email. Nessuna coda di recupero degli
  intervalli persi. Nessun processo rimane in attesa su Cloud Run tra gli invii.

## Stato prima dell'attivazione

La modalità deve restare test e TEST_RECIPIENTS=carlogalli15@gmail.com.
Non cambiare in live finché non sono state verificate tutte e sei le email,
risposte, immagini, collegamenti, esclusioni e i risultati del coordinatore.
Il vecchio trigger-email-sender rimane PAUSED; /send-emails è ritirato.
Lo Scheduler Scraper è stato trovato PAUSED: riavviarlo è un passaggio distinto.
La sincronizzazione campaign-registry-sync è ogni 15 minuti nei feriali 08–18.
Non abilitare sei Scheduler aggiuntivi per le singole campagne.
Il job campaign-admin deve essere aggiornato all'immagine del nuovo deploy,
conservando credenziali, variabili e argomenti sync già configurati.

## Fermare e riprendere

- Pausa di tutti gli invii: ControlloInvii!A2 = TRUE.
- Ripresa: A2 = FALSE, solo dopo aver verificato anche la modalità del servizio.
- Pausa di una campagna: Campagne, colonna Attiva = FALSE.
- Le modifiche vengono rilette prima della selezione; una spedizione già
  iniziata può terminare. Non annullano email già consegnate.
- Stop infrastrutturale: SENDING_ENABLED=False nel servizio Cloud Run.
- La pausa invii non ferma scraper o sincronizzazione.
- TRUE/FALSE vanno scritti come tali; evitare SI/NO e spostamenti di intestazioni.

## Quote della scheda Campagne

Campi modificabili: Attiva, Quota, Quota iniziale, Inizio, Rampa, Intervallo secondi.
La quota globale è configurata su Cloud Run e non si modifica da questa scheda.
Configurazione proposta A REGIME, da applicare dopo il collaudo:

| ID | Quota finale | Quota iniziale | Rampa settimanale | Intervallo secondi |
|---|---:|---:|---|---:|
| consulenza | 25 | 5 | 5;10;20;25 | 720 |
| training | 20 | 5 | 5;10;15;20 | 720 |
| nfc | 30 | 5 | 5;10;20;30 | 720 |
| sito | 25 | 5 | 5;10;20;25 | 720 |
| social | 25 | 5 | 5;10;20;25 | 720 |
| media | 25 | 5 | 5;10;20;25 | 720 |

Inizio è la data reale scelta per la rampa, YYYY-MM-DD. Senza data si applica
Quota iniziale. Rampa contiene i massimi per settimana, separati da punto e virgola.
Con questa proposta: 30/giorno prima settimana, 60 seconda, 115 terza, 150 quarta.
Una rampa diversa è possibile; non retrodatare per sbaglio la data.
Le impostazioni già presenti nel foglio NON vengono sovrascritte da un deploy.
Le quote sono massimi, non prenotazioni garantite: una campagna senza destinatari
non obbliga le altre a consumare la sua quota. Intervallo secondi è il minimo
fra due invii della stessa campagna; la pausa globale si applica in aggiunta.

## Contatti e storico

Italy e ConfigState restano le schede originali dello scraper. Non cancellare
colonne, non riutilizzare Stato Invio/Data Invio come interruttori del nuovo motore.
Contatti: Abilitato e Riferimento autorizzazione sono campi manuali conservati.
Abilitato non sostituisce la verifica del riferimento o della provenienza.
Gli altri campi sono proiezioni del registro e possono essere riscritti dal report.
Non cancellare semplicemente una riga per bloccare un contatto.
Invii conserva campagna, modalità e stato: accepted significa accettazione SMTP,
non prova di consegna. Le prove hanno storico separato dalle campagne reali.
Panoramica mostra quote effettive e budget casella condiviso. È aggiornata dal
job di sincronizzazione, quindi può essere indietro fino al prossimo ciclo.
RegoleSettori documenta il targeting nel codice: modificarla nello Sheet non
modifica il targeting. Nuovi settori richiedono aggiornamento e pubblicazione.

## Esclusioni, cancellazioni e rimbalzi

Per non scrivere più a un indirizzo, aggiungerlo a Esclusioni con Ambito=globale,
Motivo, Data e Attiva=TRUE. Consultare i valori effettivi del modulo prima di usare
ambiti specifici; globale blocca tutte le campagne. Il blocco viene letto all'invio.
Le esclusioni sono persistenti: cancellare la riga o Attiva=FALSE non riabilita
un indirizzo già bloccato. Una riabilitazione richiede intervento amministrativo.
Privacy, supporto e altri ruoli esclusi sono filtrati anche dal codice.
Lo stesso contatto non riceve nuovamente la stessa campagna, attende almeno
30 giorni fra campagne reali e riceve al massimo due email in 90 giorni.
Una risposta tardiva di mancata consegna nella casella va gestita manualmente:
questo sistema SMTP non legge automaticamente tutti i bounce o le risposte.
Uno stato uncertain richiede verifica prima della risoluzione: mai cancellare
il blocco o reinviare alla cieca. La guida tecnica descrive il comando resolve.

## Controlli prima del live

1. Tutte e sei le prove ricevute e verificate, autenticazione PASS.
2. Servizio in test, solo destinatario di proprietà; verifica /dispatch-emails.
3. Verifica che chiamate consecutive ravvicinate restituiscano global_interval.
4. Verifica quote effettive, data rampa, esclusioni, 132 contatti in revisione
   segnalati dalla prima migrazione e settori di ogni campagna.
5. Un solo Scheduler di invio; sincronizzazione funzionante, vecchio invio PAUSED.
6. Solo al termine impostare live e autorizzare la ripresa, poi controllare i log.

Gli invii test già fatti non consumano lo storico campagne reale, ma consumano
il budget della casella di oggi. Non azzerare i contatori per fare spazio.
