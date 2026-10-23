# Anteprime delle sei campagne

Sei proposte grafiche approvate, integrate nel nuovo dispatcher SMTP con immagini CID.
Il nuovo invio resta disattivato di default; guida operativa in
`docs/GUIDA_GCP_SEI_CAMPAGNE.md`. Il vecchio endpoint d'invio è stato ritirato.

## Consultazione

Aprire `index.html` tramite un server locale per la galleria con selettore desktop
e mobile. Ogni campagna è anche un HTML autonomo e ha una versione `.txt` e un
oggetto/preheader nel catalogo `campaigns.json`.

Screenshot desktop e mobile nella cartella `screenshots/`. Le anteprime sono state
controllate in Chrome a 760 px e 390 px: immagini caricate, nessuno scorrimento
orizzontale, selezione delle sei campagne e commutazione della galleria funzionanti.
Questo controllo browser non equivale a un collaudo dei client di posta.

## Scelte editoriali

- Palette avorio/lime, titoli neri e mascotte Otto dai caroselli del sito.
- Immagini consulenza, training e NFC riprese dagli asset esistenti.
- Tre nuove scene coordinate per sito, social e slide/video, generate per queste email.
- Testo HTML leggibile anche quando le immagini sono bloccate.
- Un pulsante principale alla sezione del sito, link secondario WhatsApp con testo
  dedicato e possibilità di rispondere per chiedere l'esclusione.
- Nessun prezzo provvisorio, promessa di risultati o affermazione che il contatto
  abbia prestato consenso. Demo OS escluse.
- Nessun pixel individuale, JavaScript o animazione dentro gli HTML email.
  Solo la galleria usa JavaScript per navigare fra le anteprime.

## Prima dell'invio reale

1. Confermare testi, offerte e recapiti del mittente.
2. Il dispatcher sostituisce i percorsi relativi con CID e incorpora solo
   l'immagine della campagna selezionata. Le anteprime conservano i percorsi locali.
3. Oggetto, HTML e testo sono caricati dal catalogo dedicato; il template NFC
   precedente non viene riutilizzato dal nuovo motore.
4. Collegare le esclusioni globali al flusso manuale concordato. Verificare che
   la disiscrizione soddisfi i requisiti del provider effettivamente usato.
5. Allineare l'informativa privacy al trattamento realmente approvato: il link
   attuale è presente, ma il testo della pagina richiede la revisione già segnalata.
6. Collaudare su indirizzi propri in Gmail, Outlook e mobile, anche con immagini
   bloccate e dark mode. Nessun invio reale eseguito per produrre queste anteprime.

## Continuità dell'infrastruttura

Il progetto GCP già collegato a Sheets non deve essere ricollegato solo perché
aggiungiamo campagne. Conservare identità di servizio e ID del foglio, verificando
i permessi già esistenti. Il registro condiviso e gli Scheduler saranno descritti
nella guida di implementazione; queste pagine non li attivano.
