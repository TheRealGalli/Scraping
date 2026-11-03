# Segmenti per NFC e Video & Slide

Aggiornamento del 3 novembre 2026. Il proprietario ha scelto di includere subito
tutti gli otto segmenti nelle campagne indicate per ciascuno. Grossisti e
amministratori di condominio entrano solo in campagne oggi spente (forecasting e
consulenza): vengono raccolti, ma non ricevono email finché quelle campagne restano
FALSE e a quota 0. Quote 75 NFC + 75 Video & Slide, orari e pausa globale invariati.

## Segmenti, campagne e aggancio

| Settore scritto in Italy | Campagne | Aggancio concreto |
|---|---|---|
| Tatuaggi e Piercing | media, nfc | Portfolio degli artisti, recensione dopo il servizio |
| Serramenti e Pergole | media | Installazioni, finiture e soluzioni dalle foto dei lavori |
| Artigiani su Misura | media, sito | Falegnamerie, marmisti, restauratori: lavori su misura come catalogo |
| Cantine e Frantoi | media, nfc | Prodotti, lavorazioni, degustazioni; recensione dopo la visita |
| Autoscuole e Scuole di Lingue | media, nfc | Corsi, ambienti e metodo; recensione a fine percorso |
| Noleggio Barche ed Escursioni | media | Mezzi, itinerari ed esperienza proposta |
| Grossisti e Distributori | media, forecasting | Assortimento leggibile; previsioni solo con storico adatto |
| Amministratori di Condominio | consulenza | Ricerca in verbali e documenti, richieste e scadenze |

I nomi non contengono virgole: la scheda Contatti separa i settori con `;`.
Le regole sono in `services/campaign_catalog.py` (`SEGMENT_RULES_V4`, versione
`2026-11-03-v4`). I testi approvati delle email restano invariati; quelli di NFC,
Video & Slide e consulenza sono generici e adatti anche a questi settori.

## Parole chiave

Una parola chiave casuale per ricerca, come per gli altri settori.

- **Tatuaggi e Piercing**: studio tatuaggi; tatuatore; tattoo shop; studio piercing; tatuaggi e piercing; studio tattoo artistico.
- **Serramenti e Pergole**: serramentista; infissi e serramenti; porte e finestre; installazione pergole; pergole bioclimatiche; tende da sole; zanzariere e tapparelle.
- **Artigiani su Misura**: falegnameria; falegname mobili su misura; marmista; lavorazione marmo e pietra; restauro mobili; laboratorio di restauro; arredamento su misura artigianale.
- **Cantine e Frantoi**: cantina vinicola; cantina con degustazione; azienda vinicola vendita diretta; frantoio; frantoio oleario; oleificio vendita diretta.
- **Autoscuole e Scuole di Lingue**: autoscuola; scuola guida; scuola di lingue; scuola di inglese; corsi di lingue; centro linguistico.
- **Noleggio Barche ed Escursioni**: noleggio barche; noleggio gommoni; escursioni in barca; tour in barca; organizzazione escursioni; guide escursionistiche.
- **Grossisti e Distributori**: grossista alimentare; ingrosso bevande; distributore prodotti horeca; commercio all'ingrosso; cash and carry; grossista ferramenta.
- **Amministratori di Condominio**: amministratore di condominio; studio amministrazione condomini; amministrazioni condominiali; gestione condomini.

Nelle località lontane da mare e laghi le ricerche sulle barche possono restituire
pochi risultati pertinenti; le varianti sulle escursioni compensano in parte.

## Segnali nelle colonne L:P di Italy

| Colonna | Contenuto |
|---|---|
| L Categoria Google | Categoria principale della scheda, per esempio "Studio di tatuaggi" |
| M Foto Google | Foto restituite dalla ricerca: l'API ne fornisce al massimo 10 |
| N Segnali sito | Social collegati, galleria/portfolio, video, immagini in homepage |
| O Aggancio | `foto da valorizzare` e/o `senza sito` |
| P Google Maps | Link alla scheda, per controllare a mano i casi scelti |

`foto da valorizzare` corrisponde al criterio del test Video & Slide: almeno 5 foto
su Google e nessun sito, oppure un sito senza galleria e senza video. Un sito non
raggiungibile non viene considerato povero: risulta `sito non raggiungibile`.
Sono fatti verificabili, non probabilità di acquisto, e il sender non li usa.

Costo invariato: è la stessa ricerca Text Search. I nuovi campi sono di livello Pro,
mentre websiteUri, rating e userRatingCount fanno già fatturare la richiesta come
Enterprise; Google fattura il livello più alto richiesto. I segnali del sito vengono
dalla homepage già scaricata per cercare l'email. Le righe storiche non vengono
arricchite, perché richiederebbe nuove chiamate.

Le intestazioni L1:P1 vengono scritte una sola volta, dopo i controlli del cursore,
solo se quelle celle sono vuote. Se contengono già colonne manuali, lo scraper
continua a scrivere righe di 11 colonne senza segnali. Le attività che Google
indica come chiuse, definitivamente o temporaneamente, non vengono salvate: se
riaprono possono essere raccolte da una ricerca successiva.

## Ritmo di raccolta

Profilo `expanded_v4`: 21 settori su 243 località, sempre una ricerca per giro.
Con 30 giri al giorno ogni settore riceve circa 1,4 ricerche al giorno, fino a 20
risultati ciascuna. Il giro completo dell'Italia passa da circa 105 a circa 170
giorni; i nuovi settori entrano già nella città in corso, dopo i 13 precedenti.

Molti artigiani hanno solo la scheda Google. Se Custom Search è configurato, ogni
attività senza sito usa una richiesta di fallback: un'API distinta da Places.

## Lettura del test

Il piano proposto prevede 10 attività per ciascuno dei primi tre segmenti: tatuaggi,
serramenti, artigiani su misura. Con le campagne automatiche, i nuovi contatti
hanno la stessa precedenza degli altri mai contattati e nessuna quota aggiuntiva.

1. In Italy filtrare Settore e Aggancio `foto da valorizzare` per vedere gli esempi
   più adatti a Video & Slide; il link in P apre la scheda.
2. In Contatti filtrare Settori per segmento: "Campagne inviate" mostra chi ha già
   ricevuto nfc o media.
3. Annotare per segmento le richieste di esempi e di preventivi. Il sistema non
   legge le risposte. Confrontare i segmenti dopo almeno 10 invii ciascuno.

Per fermare un segmento: Esclusioni per i singoli indirizzi, oppure rimuoverlo da
`SEGMENT_RULES_V4` e aumentare `RULE_VERSION` con un nuovo rilascio.

## Attivazione dopo il push su main

Il push avvia il deploy automatico del servizio. Il job campaign-admin resta sulla
vecchia immagine finché non viene aggiornato: fino ad allora i contatti dei nuovi
settori non entrano nelle code. In Cloud Shell:

```bash
gcloud scheduler jobs pause Scraper --project=scraping-505816 --location=europe-west8
```

Attendere la fine del giro in corso, poi eseguire lo script del commit distribuito:

```bash
bash scripts/activate_scraper.sh COMMIT_COMPLETO
```

Lo script attende la revisione pronta e aggiorna campaign-admin alla stessa
immagine, conservando gli argomenti sync. Il controllo scraper-check converte
ConfigState in `expanded_v4` mantenendo la stessa prossima città e lo stesso settore,
e scrive L1:P1 se vuote. Solo dopo riprende lo Scheduler. Se lo Scraper fosse
rimasto attivo, il primo giro avrebbe già fatto la stessa conversione una sola
volta; lo script serve comunque per l'immagine del job.

Al sync successivo RegoleSettori viene riscritta una volta con la versione
`2026-11-03-v4` e i contatti dei nuovi settori ricevono le associazioni. Verificare:
ConfigState riga 3 `expanded_v4`, Italy L1:P1, RegoleSettori nuova versione,
Campagne ancora nfc/media TRUE e 75. SENDER_MODE, SENDING_ENABLED e la pausa
globale non vengono modificati.
