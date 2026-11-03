#!/usr/bin/env bash
# Cloud Shell activation after the Git deploy. No application quota is added.
set -euo pipefail
if [[ $# != 1 || ! "$1" =~ ^[a-f0-9]{40}$ ]]; then
  printf '%s\n' 'Uso: bash activate_scraper.sh COMMIT_COMPLETO' >&2
  exit 1
fi
scraper_commit="$1"
scraper_state="$(gcloud scheduler jobs describe Scraper --project=scraping-505816 --location=europe-west8 --format='value(state)')"
if [[ "$scraper_state" != PAUSED ]]; then
  printf '%s\n' 'Prima metti Scraper in pausa e attendi la fine del giro in corso, poi ripeti questo comando.' >&2
  exit 1
fi
scraper_ready=0
for scraper_attempt in {1..30}; do
  read -r scraper_created_revision scraper_ready_revision scraper_image < <(
    gcloud run services describe scraping --project=scraping-505816 --region=europe-west1 \
      --format='value(status.latestCreatedRevisionName,status.latestReadyRevisionName,spec.template.spec.containers[0].image)'
  )
  if [[ "$scraper_created_revision" = "$scraper_ready_revision" && "$scraper_image" = *"$scraper_commit"* ]]; then
    scraper_ready=1
    break
  fi
  printf '%s\n' 'Attendo il deploy automatico del commit...'
  sleep 10
done
if [[ "$scraper_ready" != 1 ]]; then
  printf '%s\n' 'Deploy non ancora pronto: ripetere questo comando dopo il suo completamento.' >&2
  exit 1
fi
gcloud run services describe scraping --project=scraping-505816 --region=europe-west1 --format=json | python3 -c 'import json,sys; d=json.load(sys.stdin); env={v["name"]:v.get("value","") for v in d["spec"]["template"]["spec"]["containers"][0].get("env",[])}; assert env.get("SHEET_NAME","Italy")=="Italy", "SHEET_NAME deve essere Italy"; assert int(env.get("MAX_SEARCH_QUERIES_PER_RUN","1"))==1, "MAX_SEARCH_QUERIES_PER_RUN deve essere 1 per avere una ricerca per giro"; print("Configurazione del servizio verificata: Italy, una ricerca Maps per giro.")'
scraper_admin_command="$(gcloud run jobs describe campaign-admin --project=scraping-505816 --region=europe-west1 --format='value(spec.template.spec.template.spec.containers[0].args[1])')"
if [[ "$scraper_admin_command" != sync ]]; then
  printf '%s\n' 'campaign-admin non usa il normale comando sync: attivazione interrotta.' >&2
  exit 1
fi
gcloud run jobs update campaign-admin --project=scraping-505816 --region=europe-west1 --image="$scraper_image" --quiet
gcloud run jobs execute campaign-admin --project=scraping-505816 --region=europe-west1 \
  --args=scripts/campaign_admin.py,scraper-check --wait
gcloud logging read 'resource.type="cloud_run_job" AND resource.labels.job_name="campaign-admin" AND jsonPayload.event="scraper_check"' \
  --project=scraping-505816 --freshness=10m --limit=1 --format='json(timestamp,jsonPayload)'

# 09:00 through 18:40: 30 runs before the exclusive 19:00 end.
gcloud scheduler jobs update http Scraper --project=scraping-505816 --location=europe-west8 \
  --schedule='*/20 9-18 * * *' --time-zone=Europe/Rome --quiet --format='value(name,schedule,state)'
gcloud scheduler jobs resume Scraper --project=scraping-505816 --location=europe-west8 --quiet
printf '%s\n' 'SCRAPER_RIATTIVATO: Italy, 21 settori con segnali L:P, ogni 20 minuti dalle 09:00 alle 18:40 (30 avvii programmati/giorno).'
