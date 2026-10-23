# Piano operativo a moduli — domini, posta e contatti

23 ottobre 2026. Solo pianificazione: nessun invio, configurazione cloud, foglio o
pagina pubblica modificati. Questo documento aggiorna le scelte del precedente
PIANO_MIGRAZIONE_EMAIL.md dove divergono.

## Vincoli e perimetro aggiornati

- IONOS: acquisto domini e DNS. Il piano del proprietario non comprende caselle;
  non presumere disponibilità di Mail Basic/Business o SMTP.
- GCP: mantenere motore, configurazioni, segreti e registro degli invii.
- Le risposte devono essere leggibili in Gmail; non è richiesta lettura automatica
  delle conversazioni né interpretazione AI delle opposizioni.
- Preferenza per esclusioni registrate manualmente nel foglio e applicate poi
  automaticamente dal dispatcher a tutti i mittenti e campagne.
- Il proprietario riferisce circa 15.000 contatti già raccolti. Numero, contenuti e
  idoneità non verificati sul foglio live: è stato letto solo il codice locale.
- Scraping esistente da non modificare in questa fase. La verifica della fonte
  rimane comunque necessaria prima di presentare il flusso come conforme.
- Sei campagne: consulenza, training, NFC, sito, social, slide/video; demo OS esclusa.

## Distinzioni che governano il progetto

GCP e Google Workspace sono servizi distinti: Cloud Run e Cloud DNS non danno una
casella Gmail. Il provider di invio via API non crea necessariamente una inbox.
Non occorre costruire un server di posta su GCP per ricevere tre indirizzi.

Il Registro pubblico delle opposizioni riguarda telefonate e posta cartacea nei
limiti previsti, non una lista di email consultabile per autorizzare il marketing.
L'eventuale modulo RPO serve solo al percorso telefonico, con registrazione
operatore, verifica liste e condizioni della fonte; non abilita l'invio email.
Esiste un servizio automatico autenticato, non una blacklist pubblica scaricabile.
Fonti: [FAQ RPO](https://registrodelleopposizioni.it/operatore/domande-frequenti-operatore/),
[servizio REST](https://api.operatore.registrodelleopposizioni.it/rest/v1/schema/swagger-ui/).

Il trasferimento dei server fuori dall'Italia non sottrae automaticamente un'attività
italiana al GDPR: l'art. 3 considera lo stabilimento del titolare, non soltanto il
luogo del server. La ditta individuale e il regime forfettario non costituiscono
un'esenzione. Fonte: [testo GDPR, artt. 3 e 58](https://www.garanteprivacy.it/il-testo-del-regolamento).

Inviare una vetrina con link WhatsApp è comunque promozione se serve a proporre
servizi; una richiesta successiva su WhatsApp non autorizza retroattivamente la
prima email. Il sito senza cookie non risolve la base dell'email iniziale.
Fonte: [Garante, 14 maggio 2026](https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/10262105).

## Modulo 0 — Ricognizione e decisione sul percorso ammesso

Output: inventario effettivo di Cloud Run, Scheduler, IAM, costi, dati e fonti.
Esportazione protetta del foglio e conteggi di righe, email uniche, invii, opposizioni
e provenienza. Non confondere 15.000 righe con 15.000 destinatari autorizzati.
Contatti raccolti, autorizzati e bloccati devono essere distinguibili.

Raccogliere le condizioni applicabili alla fonte e al provider e ottenere una
valutazione mirata sul preciso messaggio e sui destinatari italiani. Un documento
privacy non sostituisce un presupposto valido. Il percorso automatico pubblico
→ email pubblicitaria resta non giustificato dalle fonti verificate.

Criterio di completamento: quantità e origine note, criticità documentate e regola
di ammissione agli invii definita; nessuna attestazione inventata di consenso.

## Modulo 1 — Domini e ricezione in Gmail

Acquistare i domini e mantenere i DNS su IONOS. Verificare che i nomi siano coerenti
con il marchio e identificare sempre la stessa attività nei messaggi.

Opzione A, da valutare per prima: aggiungere i domini al Workspace già posseduto,
con alias per la stessa persona o utenti con caselle proprie se necessari. Gli
alias non sono caselle indipendenti; verificare piano, indirizzi ottenibili e
eventuali licenze. Ricezione in Gmail, invio campagne separato tramite provider API.
La condivisione dell'organizzazione Workspace non garantisce isolamento dal rischio.

Opzione B: servizio esterno di ricezione/inoltro verso Gmail. Verificare costi per
tre domini, copie dei messaggi, affidabilità e come rispondere dal nuovo indirizzo.
Non presupporre la disponibilità futura di “Invia come” per account esterni.

Fonti: [domini Workspace](https://support.google.com/a/answer/7502379?hl=it),
[cambiamenti Gmail](https://support.google.com/mail/answer/17101213).

Criterio di completamento: prova da account esterno, risposta manuale col From
corretto e verifica dell'autenticazione. Nessuna modifica agli MX del dominio principale.

## Modulo 2 — Invio e autenticazione

Scegliere provider API in base a condizioni compatibili con il traffico ammesso,
eventi disponibili, costi e gestione dei dati. SendGrid non è ancora scelto né
collegato. SMTP IONOS è una possibilità tecnica solo acquistando/possedendo un
prodotto di posta idoneo; non è incluso per ipotesi e non aggira i requisiti di invio.
Fonte tecnica: [server IONOS](https://www.ionos.it/aiuto/e-mail/temi-generali/e-mail-ionos-dati-del-server-per-imap-pop3-e-smtp/).

Record su IONOS: verifica dominio, DKIM del provider, SPF coerente (uno per nome),
DMARC inizialmente di monitoraggio, eventuale Return-Path dedicato. MX secondo il
servizio ricevente, evitando conflitti con gli host di bounce. Chiavi solo in Secret Manager.

Criterio di completamento: invio a caselle proprie, verifica header e allineamento,
nessun ripiego automatico sulla casella Workspace principale.

## Modulo 3 — Sheets e opposizioni manuali

Non alterare inizialmente le posizioni delle undici colonne lette dal codice attuale.
Progettare nuove schede senza applicare la migrazione ora:

- Contatti: ID stabile, email normalizzata, azienda, fonte/data, canale utilizzabile,
  stato di autorizzazione e riferimento alla relativa evidenza.
- Campagne: servizio, versione template, mittenti ammessi, attivazione e limiti.
- Invii: contatto, campagna, versione, mittente, data, provider ID ed esito.
- Esclusioni: email normalizzata, stato bloccato, data, motivo, richiesta originale
  o suo riferimento, operatore che ha registrato la modifica.

Alla risposta CANCELLAMI, il proprietario registra manualmente l'opposizione;
qualsiasi espressione chiara di rifiuto vale, non soltanto la parola esatta.
Il dispatcher verifica la lista globale subito prima di inviare. Se non riesce a
leggerla, non invia. Una nuova raccolta non deve riattivare il destinatario.
Conservare soltanto il minimo necessario per rispettare l'opposizione, separato
dall'uso promozionale; definire conservazione e sicurezza. Eliminare soltanto la
riga di origine non protegge da una nuova importazione.

Le richieste vanno gestite tempestivamente: prima di nuove spedizioni al contatto.
Nessun sistema di lettura automatica Gmail richiesto in questo modulo. L'assenza
di lettura automatica non elimina la necessità di controllare regolarmente la posta.
Se il provider richiede disiscrizione tramite link, la sola risposta manuale non basta.

Criterio di completamento: una modifica manuale blocca tutte le campagne/domìni,
anche con duplicati e reimportazioni. Nessun invio reale nei test.

## Modulo 4 — Dispatcher affidabile e limiti

Contatori persistenti e prenotazioni transazionali; protezione dalle chiamate
concorrenti e gestione degli esiti incerti; tetto giornaliero globale e per mittente,
limite di frequenza anche fra campagne verso lo stesso destinatario, interruttore
globale e per campagna. Finestra Europe/Rome e giorni lavorativi configurabili.
Non usare rotazione e pause per aggirare controlli antispam.

La crescita di volume è subordinata a contatti utilizzabili ed esiti, non alla
sola età del dominio. Prevedere bounce/reclami del provider separatamente dalla
lettura delle risposte: i primi possono richiedere webhook o gestione specifica.

Criterio di completamento: quote rispettate fra istanze e retry; registro indisponibile
o esito ambiguo non producono reinvii automatici indiscriminati.

## Modulo 5 — Sei template e creatività

Una proposta per servizio, testo semplice, HTML accessibile e responsive, immagini
ottimizzate, identità completa, privacy e opposizione coerenti con il provider.
Nessun pixel individuale di apertura per default. La CTA può portare a WhatsApp;
tenere distinta la risposta a quella richiesta da future campagne marketing.
Anteprime e approvazione di offerte/prezzi prima del caricamento operativo.

## Modulo 6 — Documenti del sito e fascicolo di conformità

Esaminato il codice locale di CSD Station, non verificato il sito distribuito.
`src/pages/Legal.tsx` dichiara a riga 30 uso promozionale di recapiti da fonti
pubbliche e a riga 37 legittimo interesse per le proposte B2B. Rivedere questa
formulazione rispetto al canale email; non ripubblicarla come copertura generica.

Verificare informativa art. 14 quando applicabile, fonti, finalità e basi distinte,
provider effettivi (anche GCP, ricezione e invio), conservazione di lead/prove/
opposizioni/log, trasferimenti, accessi, diritti e modalità di disiscrizione.
Verificare hosting reale: il testo cita GitHub, ma il repository contiene anche
un server Express con Firestore e conteggi dei redirect NFC. Non è prova che il
server sia pubblicato, né di profilazione individuale: riconciliare testo e ambiente reale.

Tenere un fascicolo con versione delle informative e messaggi, prove di autorizzazione,
fonti/condizioni, contratti/DPA, registro opposizioni e invii, misure di sicurezza
e procedura per richieste o reclami. Non retrodatare documenti, inventare telefonate
o cancellare prove per sottrarle a un controllo. Validazione legale sul flusso concreto.

## Chi può intervenire e in quali casi

| Soggetto | Evento tipico | Possibili effetti |
| --- | --- | --- |
| Destinatario | Email indesiderata o richiesta sulla fonte | Opposizione, richiesta di informazioni, reclamo o azione secondo il caso |
| Garante | Reclamo, segnalazione o iniziativa d'ufficio | Richieste di documenti, accertamenti, prescrizioni, limiti/divieti, sanzioni ove applicabili |
| Guardia di Finanza | Accertamenti delegati | Verifica di archivi, procedure e documentazione nei limiti dei poteri previsti |
| Google/GCP/Workspace | Traffico vietato o violazioni contrattuali | Limitazione o sospensione secondo contratto |
| Provider email/IONOS | Reclami, abusi o violazioni delle condizioni | Blocchi, limitazioni o sospensione del servizio interessato |
| Giudice | Azione del soggetto che ne ha titolo | Rimedi civili e risarcimento se ne ricorrono i presupposti |

Non occorre ipotizzare un accesso permanente del Garante alla console GCP: un'email
ricevuta e le successive richieste al titolare possono già documentare l'attività.
Non è stata stimata la probabilità di controllo o una specifica esposizione economica.
Fonte sui controlli anche d'ufficio: [Garante, piano ispettivo luglio 2026](https://www.garanteprivacy.it/home/docweb/-/docweb-display/docweb/10296923).

## Modulo 7 — Collaudo e attivazione

Prima anteprime e test con propri indirizzi. Poi prova di ricezione e risposta,
esclusione manuale, reimportazione, errori, limiti, fuso orario e arresto.
Distribuire inizialmente con invio disabilitato. Avvio su lista ammessa e
monitoraggio separato di costi API, spedizioni ed esiti.

Sequenza suggerita: 0 → 1 → 2 → 3 → 4 → 5 → 6 → 7, con revisione documentale
in parallelo alla progettazione e completata prima dell'attivazione. Modulo RPO
eventuale e separato solo se si sceglie il contatto telefonico.

Nessuna configurazione tecnica o dicitura “B2B”, nessun volume basso e nessuna
pagina privacy rendono automaticamente conforme il primo invio non autorizzato.
Il piano permette di costruire i moduli senza dichiarare risolto quel presupposto.
