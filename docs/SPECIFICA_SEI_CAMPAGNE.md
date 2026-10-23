# Sei campagne su un archivio condiviso

Specifica per implementazione, 23 ottobre 2026. Nessun codice operativo, Scheduler
o foglio live modificato. Questo documento precisa e aggiorna i piani precedenti.

## 1. Perimetro ed evidenze

Richiesta: sei Scheduler indipendenti, un mittente iniziale, campagne con settori e
quote proprie, niente invii nel weekend, storico condiviso e destinatari protetti
da contatti ravvicinati. Scraping invariato in questa fase.

È stato analizzato il codice locale. L'accesso ADC locale non è disponibile e non
è collegato un connettore Sheets utilizzabile: intestazioni, quantità effettive,
valori, date e stati del foglio reale non sono stati verificati. Circa 15.000
contatti è un dato riferito dal proprietario, non un conteggio eseguito.

Il progetto configura una scheda `Italy` e una scheda `ConfigState`. La prima
contiene, secondo il codice, questi campi in posizioni fisse:

| Colonna | Campo | Uso attuale |
| --- | --- | --- |
| A | Place ID | Deduplicazione delle attività raccolte |
| B | Regione | Provenienza geografica |
| C | Provincia | Provenienza geografica |
| D | Città | Provenienza geografica |
| E | Settore | Categoria dello scraper |
| F | Sito Web | Sito di origine |
| G | Email | Un indirizzo per riga |
| H | Stato Invio | Da inviare, Inviato, Errore Invio e stati di esclusione |
| I | Data Invio | Testo YYYY-MM-DD HH:MM, Europe/Rome |
| J | Rating | Dato proveniente da Places |
| K | Recensioni | Numero recensioni proveniente da Places |

`ConfigState!B2` conserva l'avanzamento della ricerca: non azzerarlo.
Il nome dell'attività non viene salvato né riletto dal sender, benché sia
disponibile durante la ricerca. La scheda reale potrebbe contenere colonne aggiunte
manualmente: la migrazione deve scoprirle, non assumere che coincidano col codice.

Difetti da risolvere nel nuovo sender:

- Un solo stato e una sola data non rappresentano sei campagne.
- La deduplicazione attuale vieta qualsiasi nuova campagna dopo un primo Inviato.
- Si selezionano sempre le prime righe Da inviare, prima di verificarne l'idoneità:
  con batch di una riga, errori e rinvii possono bloccare il progresso.
- La quota giornaliera è in memoria e si azzera a ogni chiamata.
- Il controllo supporto cerca solo la sottostringa support@.
- Nessun lock fra Scheduler, né distinzione fra SMTP accettato e consegnato.
- Errori di lettura dello storico restituiscono insieme vuoto: manca un arresto sicuro.
- Le righe sono aggiornate tramite indice: ordinamenti concorrenti possono spostarle.
- Finestra invio 06:00–22:00 senza esclusione weekend.

## 2. Struttura del foglio proposta

Conservare `Italy` A:K e `ConfigState` per non rompere lo scraper. Nuove schede:

| Scheda | Una riga rappresenta | Gestione |
| --- | --- | --- |
| Contatti | Un indirizzo normalizzato | Import/sincronizzazione; campi manuali distinti |
| Campagne | Una delle sei campagne | Quote, stato e impostazioni visibili |
| RegoleSettori | Una coppia campagna-settore | Vista delle regole versionate nel codice |
| Invii | Un tentativo o evento storico identificato | Scrittura dal sistema, protetta |
| Esclusioni | Un blocco globale o di campagna | Inserimento manuale, applicazione automatica |
| Panoramica | Riepilogo per giorno/campagna | Vista calcolata/sincronizzata |

Non creare sei copie dell'archivio. I record originali restano nella scheda Italy;
un contatto può collegarsi a più attività e settori. Conservare tutte le provenienze,
senza appiattire arbitrariamente al primo settore trovato.

### Contatti

Campi: contact_id stabile e opaco, email originale, email normalizzata, business_group_id
se verificato, nome attività se disponibile, settori canonici, origine/data della
raccolta se note, riferimento righe originali, stato operativo, idoneità documentata
al contatto e riferimento alla prova, ultimo invio accettato, prossima data utile,
totale invii, eventuale assegnazione commerciale, stato sincronizzazione.

Normalizzazione: spazi esterni, dominio IDNA/lowercase, politica conservativa e
documentata per local-part. Non eliminare punti o suffissi +, né fondere caselle
distinte con euristiche Gmail. Duplicati con lo stesso indirizzo condividono storico,
pausa ed esclusioni anche se provengono da Place ID diversi.

L'assenza di nome non autorizza un nuovo recupero Places: lasciare il dato sconosciuto
o usare dati già disponibili. Ogni nuovo arricchimento è un'attività distinta.

### Campagne

Campi minimi: campaign_id immutabile, nome, attiva, mittente, versione template,
quota giornaliera richiesta, quota iniziale, data attivazione reale, rampa approvata,
intervallo minimo della campagna, prossimo invio consentito, peso/priorità,
finestra e ultimo esito. Quote modificabili solo nei campi dichiarati manuali.

Le regole dei settori hanno una fonte unica nel codice, con versione; il foglio
ne mostra una copia in sola lettura. Evitare configurazioni concorrenti foglio/codice.
Quote e interruttori hanno invece origine dichiarata nel foglio, validata prima
dell'applicazione: valori negativi, testo o incoerenti fermano la campagna.

### Invii

Campi: dispatch_id, chiave di deduplicazione, contact_id, campaign_id, step_id,
template_version, mittente, snapshot settore/criterio, timestamp UTC, data locale,
stato, ID messaggio se disponibile, codice errore classificato, Scheduler execution_id,
provenienza legacy e attendibilità della ricostruzione.

Gli indirizzi completi sono consultabili solo nell'area operativa protetta; nei
log generali usare contact_id. Gli eventi sono append-only e deduplicati con un ID.
Una singola cella ultimo contatto è un riepilogo, non sostituisce questo storico.

### Esclusioni

Campi: identificativo, email normalizzata, ambito globale/campagna, motivo, richiesta
ricevuta il, registrata il, operatore, riferimento richiesta, stato. Un rifiuto
generico blocca globalmente, non soltanto l'ultima campagna. Qualsiasi formula
chiara di opposizione vale, non solo la parola CANCELLAMI.

## 3. Settori e abbinamenti iniziali

Settori attuali nel codice: Ristorazione; Studi Professionali; Centri e Servizi;
Hospitality; Boutique e Retail; Automotive; Fitness e Sport; Veterinaria e Pet Care.

Matrice proposta commerciale, da rivedere sul contenuto delle offerte. Un abbinamento
non è una prova di consenso o di pertinenza alla singola attività.

| campaign_id | Nome | Settori iniziali proposti |
| --- | --- | --- |
| consulenza | Consulenza | Studi Professionali, Hospitality, Automotive |
| training | Training | Studi Professionali, Hospitality |
| nfc | Card NFC | Ristorazione, Centri e Servizi, Hospitality, Boutique e Retail, Automotive, Fitness e Sport, Veterinaria e Pet Care |
| sito | Sito | Ristorazione, Centri e Servizi, Hospitality, Boutique e Retail, Automotive, Fitness e Sport, Veterinaria e Pet Care |
| social | Social | Ristorazione, Centri e Servizi, Hospitality, Boutique e Retail, Fitness e Sport, Veterinaria e Pet Care |
| media | Slide e video | Studi Professionali, Hospitality, Boutique e Retail |

Le categorie sono ampie: Studi Professionali comprende avvocati, dentisti, notai
e commercialisti. Senza sottosettore non attribuire offerte specifiche a una
professione. Abilitare solo il testo compatibile con la categoria nota.

Nuovi settori: ID canonico stabile, etichetta e alias dichiarati, poi associazioni
esplicite alle campagne. Nessuna wildcard tutti i settori per i nuovi ingressi.
Un settore sconosciuto è in attesa di classificazione, non scartato né abilitato
automaticamente. Rinominare l'etichetta non perde storico o deduplicazione.

## 4. Quote e calendario

Il riferimento indicato è circa 50 per campagna, con valori indipendenti. Poiché
il proprietario ha citato anche 60, la specifica adotta 50 come tetto predefinito:
superarlo richiede una modifica esplicita, non deriva dal ritmo dello Scheduler.

Esempio a regime, non attivato: consulenza 40, training 35, NFC 50, sito 45,
social 45, media 40 = 255/giorno. Sei campagne da 50 equivalgono a 300/giorno.
La quota globale deve essere esplicita e può essere inferiore alla somma.

Finestra proposta: lunedì–venerdì 08:30 inclusa–18:30 esclusa, Europe/Rome.
Weekend esclusi nello Scheduler e nel codice. I festivi non sono esclusi per
implicito: aggiungere un calendario se richiesto. Nessun recupero concentrato il
lunedì per compensare il weekend. Giorno locale per quote, UTC per confronti temporali.

Il warm-up riguarda il mittente condiviso, non sei infrastrutture indipendenti.
Nuova campagna e nuova casella hanno parametri diversi. Proposta prudente iniziale:
quota globale 50 e piccoli tetti per campagna; incremento solo manuale dopo verifica
esiti. Nessuna rampa automatica verso 1.000 prevista da questa specifica.
Quota effettiva = minimo di tetto campagna, rampa campagna, quota residua mittente
e quota globale, usando contatori e prenotazioni persistenti.

### Sei Scheduler, un motore

Contratto proposto: POST `/send-emails/{campaign_id}`, autenticazione OIDC, ID
campagna convalidato; ID inesistente rifiutato. Il vecchio endpoint non resta una
settima sorgente attiva: migrazione esplicita e disattivazione dei vecchi trigger.

Gli Scheduler propongono lavoro, non sono il limite giornaliero. Esempi di polling
distinto: 5, 6, 7, 8, 9, 10 minuti, offset minuti distinti, ore 8–18, lunedì–venerdì,
timezone Europe/Rome. Il controllo orario nel codice elimina le chiamate prima
delle 08:30 e dalle 18:30. Verificare le occorrenze reali di ogni cron: gli step
del campo minuti ripartono a ogni ora e non sono sempre intervalli uniformi.

La cadenza di invio per campagna vive in `next_send_at`: ad esempio in 600 minuti,
50 invii richiedono mediamente 12 minuti, 40 ne richiedono 15. Il polling deve
offrire abbastanza occasioni; non promettere che la quota venga sempre raggiunta.
Proposta intervallo globale minimo due minuti: al massimo circa 300 opportunità
in dieci ore; le quote effettive e i conflitti possono ridurle. Le pause sono
scadenze persistenti, senza lunghi sleep dentro Cloud Run.

## 5. Pausa per destinatario e prevenzione dell'abbandono

Default proposto: almeno 30 giorni di calendario fra due campagne promozionali
verso la stessa email, massimo due invii in ogni finestra mobile di 90 giorni.
Sono parametri editoriali configurabili, non soglie legali o garanzie di recapito.
Un'eventuale richiesta specifica si gestisce separatamente, con ambito documentato.

Una coppia contatto-campagna ha un solo step introduttivo per default. Un nuovo
template non abilita a rispedire la stessa campagna. Eventuali follow-up sono
nuovi step espliciti, con proprie condizioni, non riavvii impliciti.

Per ogni coppia ammissibile mantenere: first_eligible_at, next_eligible_at,
last_considered_at, stato e motivo. In pausa significa rinviata, mai inviata o
esclusa definitivamente. Il motivo e la data devono essere visibili.

Calcolo della prossima data: massimo di pausa dopo ultimo invio, scadenza del
limite mobile, eventuale retry consentito e altre condizioni temporali; poi prima
finestra lavorativa utile. Non calcolare `oggi + 30` a ogni controllo, altrimenti
la data slitta per sempre. Il riferimento è l'evento che ha causato la pausa.

Esempio senza altri eventi: NFC il 2 novembre 2026 → altra campagna non prima
del 2 dicembre; se parte il 2 dicembre, una terza attende anche l'uscita del primo
invio dalla finestra mobile di 90 giorni. Nessuna promessa di sei proposte in sei mesi.

### Equità fra campagne

Se più campagne possono scrivere allo stesso contatto, assegnare prima della
spedizione una sola campagna vincente per il prossimo slot. Ordine proposto:
campagna attesa da più tempo, priorità settoriale esplicita, minor avanzamento
rispetto alla quota giornaliera, ID come spareggio deterministico. Un'assegnazione
temporanea scade se la campagna è disattivata o non può lavorare entro la finestra
prevista; l'anzianità delle altre non si azzera.

Non far vincere sempre lo Scheduler che scatta per primo. Per distribuire anche
la quota globale usare slot assegnati secondo deficit rispetto ai pesi/quote delle
campagne attive, con prestito degli slot inutilizzati a quelle che hanno candidati.
La transazione verifica il diritto allo slot globale prima della prenotazione.

Se una coda non avanza, mostrare motivo: nessun settore corrispondente, contatti
in pausa, esaurimento coppie non contattate, quote insufficienti o errori. Non
accorciare automaticamente le pause per riempire una quota.

Non si può garantire che tutti ricevano tutte le campagne con risorse finite.
Si può garantire che un rinvio mantenga la sua data e anzianità e sia rivalutato.

## 6. Filtro indirizzi prima dell'invio

Il filtro del sender è condiviso da tutte le campagne, anche per righe vecchie e
inserite manualmente; non occorre cambiare subito lo scraper.

- Validazione strutturale con libreria dedicata, rifiuto caratteri di controllo,
  liste di più destinatari in una cella e indirizzi ambigui da revisionare.
- Blocco ruoli, con local-part tokenizzata su separatori noti e regole ancorate:
  support, supporto, assistenza, helpdesk, privacy, dpo, gdpr, dataprotection,
  noreply/no-reply/do-not-reply, abuse, postmaster, security, webmaster.
- PEC: domini e indicatori espliciti noti; i casi dubbi richiedono revisione.
  Non affermare di riconoscere tutte le PEC dalla sola stringa.
- Evitare regex che bloccano nomi innocui contenenti parole simili, o qualunque
  dominio con la stringa pec. Conservare regola e motivo dell'esclusione.
- hello, info, contatti, commerciale non sono automaticamente scarti tecnici;
  non diventano per questo destinatari autorizzati o migliori per ogni campagna.
- Verifica DNS/MX, se prevista, distinta da esistenza della casella: niente
  probing SMTP massivo né promessa di bounce zero dalla sintassi.
- Lista globale opposizioni prevale sempre su regole settoriali e permessi precedenti.

## 7. Sheets come interfaccia, registro GCP per la concorrenza

Sei processi concorrenti non possono affidare prenotazioni e quote a una sequenza
lettura/scrittura di celle. Proposta: Firestore per stato transazionale e Sheets
come archivio operativo e vista. La cronologia originale rimane conservata.

Documenti/collezioni concettuali: contacts, campaign_contacts, dispatches,
daily_campaign_counters, daily_sender_counters, global_daily_counter,
global_dispatch_gate, suppressions, sync_operations, migration_runs.
Indici per campagna/stato/data utile e per contatto/campagna; niente scansioni
complete di 15.000 righe sei volte per ogni giro. Preparare solo le coppie ammesse,
con un percorso indicizzato che non si fermi ai primi candidati non disponibili.

Flusso di una richiesta:

1. Autenticazione, campagna, finestra, interruttori e configurazione valida.
2. Sincronizzazione dei comandi manuali, soprattutto esclusioni; se indisponibili,
   nessun nuovo invio. Versione e data dell'ultima sincronizzazione visibili.
3. Ricerca indicizzata dei candidati dovuti, filtro indirizzo/idoneità/settore,
   assegnazione equa. Se i primi sono rinviati, proseguire con pagina/cursore.
4. Transazione: verificare esclusioni, deduplicazione contatto-campagna-step,
   pausa, finestra mobile, lock destinatario, turnazione e quote. Prenotare quote,
   avanzamento temporale e dispatch ID stabile nello stesso stato condiviso.
5. Prima di inviare, rileggere gli eventuali blocchi urgenti e l'orario; se fuori
   finestra annullare la prenotazione secondo regole esplicite.
6. Registrare invio iniziato, trasmettere una volta, classificare l'esito.
7. Aggiornare stato persistente e coda di sincronizzazione del foglio.
8. Restituire risultato sintetico e ragione; nessuna eccezione trasformata in un
   generico completed se il lavoro è fallito.

Successo = accettato dal trasporto, non consegnato. Accettato o esito incerto
consumano prudenzialmente la quota; rifiuto certo prima dell'accettazione può
liberarla in transazione. Per esito incerto il destinatario resta bloccato fino a
riconciliazione, senza retry cieco. Se SMTP è mantenuto, ID e segnali disponibili
sono più limitati rispetto a un provider con eventi: dichiararlo nella vista.

Un lock scaduto prima dell'invio può essere recuperato; un invio già iniziato non
va rispedito automaticamente solo perché è scaduto il lock. Il vecchio invio
non può essere reso idempotente dal solo ID dello Scheduler.

Gli edit manuali su Sheets non sono una transazione con la spedizione: per un
blocco urgente usare interruttore globale, registrare opposizione, attendere esito
di sincronizzazione e assenza di invii in corso, poi riattivare. Il motore non legge
Gmail: il tempo fra ricezione del rifiuto e registrazione resta responsabilità operativa.

Se il provider ha accettato e l'aggiornamento Sheets fallisce, riconciliare dal
registro: non inviare una seconda volta. Aggiornare le righe per ID stabile e
verificare la chiave immediatamente prima della scrittura; preferire viste protette
e filter view, perché indice di riga e posizione non sono identità permanenti.

## 8. Migrazione dell'intero storico

Non far ripartire le sei campagne azzerando H/I. Migrazione automatizzabile,
eseguibile una tantum da un job amministrativo separato e riprendibile per blocchi:

1. Backup protetto e fotografia dei valori, formule, intestazioni e schede reali.
2. Anteprima senza modifiche: conteggi per stato/settore, email uniche, duplicati,
   indirizzi filtrati, date valide/mancanti/future, nuovi campi già presenti.
3. Verifica dell'origine delle spedizioni legacy: il template locale è NFC, ma
   questo non prova che tutti gli invii storici fossero NFC. Richiedere conferma
   o evidenze, mantenendo il grado di certezza.
4. Inviato con prova NFC: importare un evento NFC legacy per destinatario e step.
   Duplicati dello stesso evento non creano più spedizioni; eventi differenti con
   prova restano distinti. NFC introduttivo non riparte con il nuovo template.
5. Inviato di campagna incerta: evento legacy_unknown, conservare data e bloccare
   il primo step NFC come precauzione finché chiarito; sospendere le assegnazioni
   incompatibili, senza attribuire falsamente la campagna.
6. Inviato con data mancante/non interpretabile: storico incompleto, revisione
   prima di assegnare una nuova data. Non trattare come mai contattato.
7. Errore Invio: possibile esito ambiguo (il trasporto o Sheets potrebbero avere
   fallito dopo l'accettazione). Non reimmettere automaticamente come nuovo.
8. Duplicato Email: collegare all'indirizzo canonico e relativo storico, non
   interpretare la riga come invio effettuato.
9. Email Supporto/Nessuna email/opposizioni presenti: conservare stato e applicare
   i nuovi filtri globali. Stati sconosciuti richiedono mappatura esplicita.
10. Da inviare: candidato da classificare, non consenso automatico né garanzia
    di assenza di contatti effettuati fuori da questo sistema.
11. Importare Contatti/Invii e registro; confrontare totali e differenze con la
    fotografia iniziale, usando migration_id e ID eventi ripetibili per evitare duplicati.
12. Pausa dei soli sender legacy per il passaggio finale, riconciliazione del delta
    delle spedizioni avvenute durante l'analisi, verifica quote di oggi e attivazione
    progressiva delle nuove campagne. Nessun job vecchio lasciato a inviare in parallelo.

Scraper può restare attivo salvo breve coordinamento del delta: nuovi record
vengono importati a parte senza sovrascrivere note manuali. Migrazione strutturale
non ripete API Places, non rigenera contenuti AI e non ricontatta i destinatari.

## 9. Panoramica e gestione quotidiana

Per campagna: quota richiesta/effettiva, prenotati, accettati, incerti, errori,
bloccati, rinviati, candidati disponibili, prossimo slot e ultimo avvio Scheduler.
Mostrare anche totali globali/mittente e contatti unici, per non confondere numero
spedizioni e numero attività. Zero dati non è zero invii: indicare sincronizzazione
fallita o vista non aggiornata. Configurare avviso su nessun progresso persistente,
non generare allarme per una coda legittimamente vuota o in pausa.

Il proprietario modifica quote/interruttori e registra opposizioni, risposte,
richieste e acquisizioni clienti. Un contatto acquisito o in trattativa viene
sospeso dalle nuove proposte automatiche secondo la politica concordata.
Il resto del riepilogo deriva dal registro, senza formule manuali su ogni riga.

## 10. File da implementare e verifiche

Proposta di separazione: catalogo campagne/regole settori, filtro destinatari,
servizio contatti/migrazione, registro transazionale, selettore con equità,
dispatcher, sincronizzazione Sheets e renderer template. Modificare endpoint e
time filter solo per l'invio; tenere separata la finestra dello scraper.

Test significativi, senza email o API a pagamento reali:

- Due Scheduler sullo stesso indirizzo e stesso mittente: una sola prenotazione.
- Retry duplicato, timeout dopo invio, fallimento aggiornamento foglio, lock scaduto.
- Pause a 30 giorni e due invii/90 giorni, confini esatti e calcolo non scorrevole.
- Weekend, 08:29/08:30/18:29/18:30, cambio giorno Roma e ora legale.
- Candidato iniziale rinviato ma successivi disponibili, equità tra sei campagne,
  campagna disattivata e nuovi settori sconosciuti.
- Opposizione con duplicati/reimportazione, sincronizzazione indisponibile,
  esclusione inserita fra prenotazione e invio.
- Support/privacy/DPO/no-reply, falsi positivi di parole simili, PEC dubbia.
- Migrazione rieseguita due volte, date mancanti, stati sconosciuti, errore legacy
  ambiguo, contatti inviati durante il delta e aggiornamento righe ordinate.

Prima modalità anteprima, poi soli indirizzi propri, poi attivazione operativa.

## 11. Attività manuali che restano

Non soltanto gli Scheduler: serviranno la verifica/export del foglio reale,
conferma della campagna legacy e delle offerte/settori, provisioning Firestore
e indici, IAM e Secret Manager, eventuale configurazione mittente/DNS, autenticazione
OIDC, esecuzione migrazione e collaudo. Il codice potrà fornire strumenti e istruzioni
per ridurre questi passaggi, senza richiedere chiavi in chat.

Ordine lavori: ricognizione dati reali → importazione/migrazione in anteprima →
registro e filtri → dispatcher e test → sei template → collaudo → Scheduler.
Il legame mittente/provider resta configurabile; la progettazione non attesta
che il primo invio ai contatti raccolti sia autorizzato.

Riferimenti tecnici: [Scheduler consegna almeno una volta](https://docs.cloud.google.com/scheduler/docs/overview),
[cron e timezone](https://docs.cloud.google.com/scheduler/docs/configuring/cron-job-schedules),
[quote Sheets](https://developers.google.com/workspace/sheets/api/limits).
