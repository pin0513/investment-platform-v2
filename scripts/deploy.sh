#!/usr/bin/env bash
set -euo pipefail

PROJECT_ID="paul-test-174403"
REGION="asia-east1"
SERVICE="investment-platform-v2"
IMAGE="asia-east1-docker.pkg.dev/${PROJECT_ID}/investment-platform-v2/app:latest"
SA="cr-investment-v2@${PROJECT_ID}.iam.gserviceaccount.com"

# DB_URL is plaintext for now (will move to Secret Manager in Task 30)
DB_URL_PLACEHOLDER="postgresql+psycopg://placeholder:placeholder@10.140.0.2:5432/investment_v2"

gcloud run deploy "${SERVICE}" \
  --image="${IMAGE}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --service-account="${SA}" \
  --allow-unauthenticated \
  --port=8080 \
  --min-instances=0 \
  --max-instances=3 \
  --cpu=1 \
  --memory=512Mi \
  --set-env-vars="ENVIRONMENT=prod,ALLOWED_ORIGINS=https://invest.paulfun.net,GOOGLE_OAUTH_CLIENT_ID=329908581117-0csnfufiij5h5oc6a8qah5uvnm447ppo.apps.googleusercontent.com,DB_URL=${DB_URL_PLACEHOLDER}" \
  --set-secrets="JWT_SECRET=JWT_SECRET:latest"

echo "Deployed. URL:"
gcloud run services describe "${SERVICE}" --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)'
