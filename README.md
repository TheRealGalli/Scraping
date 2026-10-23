# Scraper e campagne CSD Station

La raccolta `/worker` mantiene il collegamento esistente a Google Sheets.
Il nuovo invio offre sei campagne con targeting per settore, registro Firestore,
quote condivise, pause per destinatario ed esclusioni manuali su Sheets.

**Prima di distribuire:** leggere [la guida GCP](docs/GUIDA_GCP_SEI_CAMPAGNE.md).
Il vecchio endpoint `/send-emails` viene disattivato dal nuovo codice. Le nuove
campagne iniziano con invio spento; richiedono migrazione e collaudo espliciti.

- Guida operativa: `docs/GUIDA_GCP_SEI_CAMPAGNE.md`
- Specifica di riferimento: `docs/SPECIFICA_SEI_CAMPAGNE.md`
- Galleria delle email: `templates/campaigns/index.html`
- Anteprima migrazione: `python scripts/campaign_admin.py plan`
- Test locali senza invii reali: `python -m pytest tests/ -q`

Configurazione di esempio in `.env.example`. Credenziali in Secret Manager o
nell'ambiente locale, mai nel repository. Il default è `SENDING_ENABLED=False`.
