#!/usr/bin/env bash
# Run in Cloud Shell after the Git-triggered deployment. No source upload needed.
set -euo pipefail

if [[ $# != 1 || ! "$1" =~ ^[a-f0-9]{40}$ ]]; then
  printf '%s\n' 'Uso: bash activate_smart_selection.sh COMMIT_COMPLETO' >&2
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
selection_cleanup() {
  selection_exit=$?
  trap - EXIT
  if [[ "$selection_scheduler_paused" = 1 ]]; then
    if ! gcloud scheduler jobs resume campaign-registry-sync --project=scraping-505816 --location=europe-west1 --quiet; then
      printf '%s\n' 'Riprendere campaign-registry-sync: il riavvio dello Scheduler non e riuscito.' >&2
      selection_exit=1
    fi
  fi
  exit "$selection_exit"
}
trap selection_cleanup EXIT
if [[ "$selection_scheduler_state" = ENABLED ]]; then
  gcloud scheduler jobs pause campaign-registry-sync --project=scraping-505816 --location=europe-west1 --quiet
  selection_scheduler_paused=1
fi

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

gcloud run jobs update campaign-admin --project=scraping-505816 --region=europe-west1 --image="$selection_image" --quiet
gcloud run jobs execute campaign-admin --project=scraping-505816 --region=europe-west1 --wait
gcloud run services update scraping --project=scraping-505816 --region=europe-west1 --update-env-vars=SMART_SELECTION_ENABLED=True --quiet
printf '%s\n' 'PRIORITA_CONTATTI_ATTIVA: nuovi contatti in target prima, rotazione fra localita.'
