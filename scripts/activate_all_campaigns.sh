#!/usr/bin/env bash
# Run in Cloud Shell after the Git-triggered deployment. No source upload needed.
set -euo pipefail

if [[ $# != 1 || ! "$1" =~ ^[a-f0-9]{40}$ ]]; then
  printf '%s\n' 'Uso: bash activate_all_campaigns.sh COMMIT_COMPLETO' >&2
  exit 1
fi
selection_commit="$1"
selection_ready=0
for selection_attempt in {1..30}; do
  read -r selection_created_revision selection_ready_revision selection_image < <(
    gcloud run services describe scraping --project=scraping-505816 --region=europe-west1 \
      --format='value(status.latestCreatedRevisionName,status.latestReadyRevisionName,spec.template.spec.containers[0].image)'
  )
  if [[ "$selection_created_revision" = "$selection_ready_revision" && "$selection_image" = *"$selection_commit"* ]]; then
    selection_ready=1
    break
  fi
  printf '%s\n' 'Attendo che il deploy automatico del commit sia pronto...'
  sleep 10
done
if [[ "$selection_ready" != 1 ]]; then
  printf '%s\n' 'Deploy non ancora pronto: ripetere questo comando dopo il suo completamento.' >&2
  exit 1
fi
selection_job_command="$(gcloud run jobs describe campaign-admin --project=scraping-505816 --region=europe-west1 --format='value(spec.template.spec.template.spec.containers[0].args[1])')"
if [[ "$selection_job_command" != sync ]]; then
  printf '%s\n' 'campaign-admin non usa il normale comando sync: attivazione interrotta.' >&2
  exit 1
fi

selection_scheduler_state="$(gcloud scheduler jobs describe campaign-registry-sync --project=scraping-505816 --location=europe-west1 --format='value(state)')"
selection_scheduler_paused=0
selection_email_paused=0
selection_success=0
selection_cleanup() {
  selection_exit=$?
  trap - EXIT
  if [[ "$selection_scheduler_paused" = 1 ]]; then
    if ! gcloud scheduler jobs resume campaign-registry-sync --project=scraping-505816 --location=europe-west1 --quiet; then
      printf '%s\n' 'Riprendere campaign-registry-sync: il riavvio dello Scheduler non e riuscito.' >&2
      selection_exit=1
    fi
  fi
  if [[ "$selection_email_paused" = 1 && "$selection_success" = 1 ]]; then
    gcloud scheduler jobs resume campaign-email-dispatch --project=scraping-505816 --location=europe-west1 --quiet || selection_exit=1
  elif [[ "$selection_email_paused" = 1 ]]; then
    printf '%s\n' 'Attivazione non completata: campaign-email-dispatch resta in pausa. Correggere e ripetere lo script.' >&2
  fi
  exit "$selection_exit"
}
trap selection_cleanup EXIT
if [[ "$selection_scheduler_state" = ENABLED ]]; then
  gcloud scheduler jobs pause campaign-registry-sync --project=scraping-505816 --location=europe-west1 --quiet
  selection_scheduler_paused=1
fi

selection_email_state="$(gcloud scheduler jobs describe campaign-email-dispatch --project=scraping-505816 --location=europe-west1 --format='value(state)')"
if [[ "$selection_email_state" = ENABLED ]]; then
  gcloud scheduler jobs pause campaign-email-dispatch --project=scraping-505816 --location=europe-west1 --quiet
  selection_email_paused=1
fi
# Allow an already-started sender tick to finish before acquiring the admin lease.
sleep 60
selection_idle=0
for selection_attempt in {1..18}; do
  selection_running="$(gcloud run jobs executions list --job=campaign-admin --project=scraping-505816 --region=europe-west1 --limit=20 --format=json | python3 -c 'import json,sys; rows=json.load(sys.stdin); print(sum(not e.get("status",{}).get("completionTime") and not any(c.get("type")=="Completed" and c.get("status") in ("True","False") for c in e.get("status",{}).get("conditions",[])) for e in rows))')"
  if [[ "$selection_running" = 0 ]]; then
    selection_idle=1
    break
  fi
  printf '%s\n' 'Attendo la fine della sincronizzazione gia in corso...'
  sleep 5
done
if [[ "$selection_idle" != 1 ]]; then
  printf '%s\n' 'Sincronizzazione ancora in corso: ripetere il comando quando termina.' >&2
  exit 1
fi

gcloud run services update scraping --project=scraping-505816 --region=europe-west1 \
  --update-env-vars=GLOBAL_DAILY_LIMIT=150,SMART_SELECTION_ENABLED=True --quiet
gcloud run jobs update campaign-admin --project=scraping-505816 --region=europe-west1 \
  --image="$selection_image" --update-env-vars=GLOBAL_DAILY_LIMIT=150 --quiet
gcloud run jobs execute campaign-admin --project=scraping-505816 --region=europe-west1 \
  --args=scripts/campaign_admin.py,activate150,--backup-bucket,scraping-505816-campaign-backups-707079344561 --wait
selection_success=1
printf '%s\n' 'OTTO_CAMPAGNE_ATTIVE: quote 35/15/20/15/15/15/15/20, massimo globale 150. Argomenti ricorrenti sync conservati.'
