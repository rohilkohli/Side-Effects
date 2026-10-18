#!/usr/bin/env bash
# Deploy SIDE EFFECTS to Cloud Run, calling Gemini through Vertex AI with the
# service's own identity (no API key stored anywhere).
#   PROJECT_ID=my-project ./deploy.sh
set -euo pipefail
: "${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-asia-southeast1}"          # Cloud Run region (Singapore)
VERTEX_LOCATION="${VERTEX_LOCATION:-global}"  # where Gemini is called
MODEL="${GEMINI_MODEL:-gemini-3.8-flash}"
SA="side-effects@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com bigquery.googleapis.com cloudscheduler.googleapis.com
gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 || \
  gcloud iam service-accounts create side-effects --display-name "SIDE EFFECTS app"
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:$SA" --role roles/aiplatform.user --condition=None >/dev/null

# BigQuery: live complaint lookups on the public CFPB table, and an audit table of every gate decision.
for ROLE in roles/bigquery.jobUser roles/bigquery.dataEditor; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:$SA" --role "$ROLE" --condition=None >/dev/null
done
bq --location="$REGION" show "${PROJECT_ID}:side_effects" >/dev/null 2>&1 || bq --location="$REGION" mk --dataset "${PROJECT_ID}:side_effects"
bq show "${PROJECT_ID}:side_effects.gate_decisions" >/dev/null 2>&1 || \
  bq mk --table --time_partitioning_field ts "${PROJECT_ID}:side_effects.gate_decisions" pipeline/bigquery/gate_decisions.schema.json
bq show "${PROJECT_ID}:side_effects.safety_alerts" >/dev/null 2>&1 || \
  bq mk --table --time_partitioning_field ts "${PROJECT_ID}:side_effects.safety_alerts" pipeline/bigquery/safety_alerts.schema.json

# New projects: let the default compute service account build from source.
PN=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:${PN}-compute@developer.gserviceaccount.com" \
  --role roles/run.builder --condition=None >/dev/null

# Leaflets live in memory, so one instance keeps the pharmacist next to its leaflet.
gcloud run deploy side-effects \
  --source . \
  --region "$REGION" \
  --service-account "$SA" \
  --allow-unauthenticated \
  --memory 1Gi --timeout 900 --max-instances 1 --cpu-boost \
  --set-env-vars "GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${VERTEX_LOCATION},GEMINI_MODEL=${MODEL},BIGQUERY_ENABLED=true"

# Safety alerts: Cloud Scheduler runs the scan every morning (Singapore time). The endpoint runs at most
# hourly whoever calls it, so it needs no secret.
URL=$(gcloud run services describe side-effects --region "$REGION" --format 'value(status.url)')
JOB_ARGS=(--location "$REGION" --schedule "0 7 * * *" --time-zone "Asia/Singapore" --http-method POST
  --uri "${URL}/api/alerts/scan?wait=true" --attempt-deadline 600s)
if gcloud scheduler jobs describe side-effects-safety-scan --location "$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update http side-effects-safety-scan "${JOB_ARGS[@]}"
else
  gcloud scheduler jobs create http side-effects-safety-scan "${JOB_ARGS[@]}"
fi
echo "Live at ${URL}"
