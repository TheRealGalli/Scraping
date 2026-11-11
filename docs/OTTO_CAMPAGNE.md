# Otto campagne, massimo globale 150

Configurazione richiesta l'11 novembre 2026: consulenza 35, training 15, NFC 20,
sito 15, social 15, Video & Slide 15, forecasting 15, Archivio AI 20.
Tutte attive, quota iniziale uguale alla finale, rampa costante, intervallo
per campagna 720 secondi. Il limite condiviso resta 150 e comprende i tentativi
già registrati oggi: l'attivazione non azzera i contatori o lo storico.
Le quote sono massimi; destinatari insufficienti possono lasciare invii inutilizzati.

## Pertinenza

Dentisti e studi professionali escono da Video & Slide. Entrambe le categorie
ricevono consulenza, training e Archivio AI; per i dentisti restano compatibili
anche NFC, sito e social. Consulenza precede gli altri servizi per questi studi;
per gli amministratori di condominio precede Archivio. Per gioiellerie e
artigiani precedono i servizi visivi, per ristorazione, hospitality e grossisti
il forecasting. Le preferenze si applicano alle campagne compatibili e disponibili:
quote, pause e invii precedenti possono rendere disponibile un'altra proposta.
L'import aggiorna anche l'ordine dei contatti esistenti senza cancellare lo storico.
Resta la priorità a chi non è mai stato raggiunto e la distribuzione geografica.

Il forecasting attuale parla di scorte, ordini e vendite: non viene abilitato per
studi notarili o dentistici. Archivio propone una valutazione sui documenti dello
studio, anche in locale, senza chiedere allegati riservati nel primo messaggio.
Riutilizza l'immagine documentale della consulenza; testo e collegamento sono dedicati.
I segnali L:P di Italy restano descrittivi: il motore non deduce bisogni dall'assenza
di una galleria o dalle recensioni. RegoleSettori è una copia delle regole del codice.

## Pubblicazione e attivazione da Cloud Shell

Il push aggiorna il servizio scraping, non campaign-admin. Dopo il deploy usare
scripts/activate_all_campaigns.sh con il commit completo del rilascio.

Lo script attende la revisione pronta del commit, sospende temporaneamente gli
Scheduler email e sync se attivi, attende la fine degli amministrativi precedenti,
conserva gli argomenti permanenti del job e allinea l'immagine a quella del servizio.
Imposta GLOBAL_DAILY_LIMIT=150 su entrambi e SMART_SELECTION_ENABLED=True sul servizio.
Non modifica lo Scheduler Scraper o le sue quote API.

Esegue con override della sola esecuzione:

```
python scripts/campaign_admin.py activate150 --backup-bucket scraping-505816-campaign-backups-707079344561
```

activate150 salva un backup, imposta le otto righe in Campagne mantenendo la pausa,
esegue un sync completo degli abbinamenti e delle liste, poi toglie la pausa in
ControlloInvii e aggiorna Panoramica. L'operazione è esplicitamente autorizzata a
riattivare tutte le campagne. Gli argomenti ricorrenti restano:

```
python scripts/campaign_admin.py sync --legacy-campaign nfc --backup-bucket scraping-505816-campaign-backups-707079344561
```

Se riesce stampa OTTO_CAMPAGNE_ATTIVE; riprende gli Scheduler che erano attivi.
Se fallisce, lo Scheduler email sospeso dallo script resta in pausa e il messaggio
lo segnala: correggere il problema e ripetere. Se viene interrotta una precedente
esecuzione e lo Scheduler email era già in pausa al nuovo tentativo, dopo il successo
riprenderlo esplicitamente solo se si desiderano gli invii automatici.
Una pausa email preesistente viene conservata.
Il servizio mantiene SENDING_ENABLED e SENDER_MODE correnti: lo script non converte
un ambiente di prova in invii reali. Non esegue invii forzati per il collaudo.
