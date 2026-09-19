#!/usr/bin/env bash
# ==============================================================================
# Universal Agentic Platform - Cloud Deployment Helper Script
# Supports: Google Cloud Run (Serverless), AWS EC2, DigitalOcean Droplet
# ==============================================================================

set -euo pipefail

echo "======================================================================"
echo " UNIVERSAL AGENTIC PLATFORM - CLOUD DEPLOYMENT"
echo "======================================================================"

TARGET="${1:-cloud-run}"

if [ "$TARGET" == "cloud-run" ]; then
    echo "Deploying to Google Cloud Run (Serverless)..."
    SERVICE_NAME="${2:-universal-agentic-system}"
    REGION="${3:-us-central1}"

    echo "Building and deploying '$SERVICE_NAME' in region '$REGION'..."
    gcloud run deploy "$SERVICE_NAME" \
        --source . \
        --platform managed \
        --region "$REGION" \
        --allow-unauthenticated \
        --port 8000 \
        --memory 1Gi \
        --cpu 1

    echo "Deployment to Google Cloud Run complete!"

elif [ "$TARGET" == "docker" ]; then
    echo "Deploying via Docker Compose (AWS EC2 / DigitalOcean Droplet)..."
    docker compose down --remove-orphans || true
    docker compose build --no-cache
    docker compose up -d

    echo "Container started! Check status with:"
    echo "  docker compose ps"
    echo "  docker compose logs -f"

else
    echo "Usage: ./scripts/deploy_cloud.sh [cloud-run|docker] [service-name] [region]"
    exit 1
fi
