#!/usr/bin/env bash
# Deploy SIDE EFFECTS to Cloud Run, calling Gemini through Vertex AI with the
# service's own identity (no API key stored anywhere).
#   PROJECT_ID=my-project ./deploy.sh
set -euo pipefail
: "${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-asia-southeast1}"          # Cloud Run region (Singapore)
VERTEX_LOCATION="${VERTEX_LOCATION:-global}"  # where Gemini is called
MODEL="${GEMINI_MODEL:-gemini-2.5-flash}"
SA="side-effects@${PROJECT_ID}.iam.gserviceaccount.com"

gcloud config set project "$PROJECT_ID"
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com
gcloud iam service-accounts describe "$SA" >/dev/null 2>&1 || \
  gcloud iam service-accounts create side-effects --display-name "SIDE EFFECTS app"
gcloud projects add-iam-policy-binding "$PROJECT_ID" --member "serviceAccount:$SA" --role roles/aiplatform.user --condition=None >/dev/null

# Leaflets live in memory, so one instance keeps the pharmacist next to its leaflet.
gcloud run deploy side-effects \
  --source . \
  --region "$REGION" \
  --service-account "$SA" \
  --allow-unauthenticated \
  --memory 1Gi --timeout 300 --max-instances 1 \
  --set-env-vars "GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${VERTEX_LOCATION},GEMINI_MODEL=${MODEL}"
