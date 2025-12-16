#!/bin/bash

# Deployment script for job-hunting-agent Cloud Run service
# Reads environment variables from .env file in the same directory

set -e  # Exit on error

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

# Check if .env file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ Error: .env file not found at $ENV_FILE"
    exit 1
fi

echo "📄 Loading environment variables from $ENV_FILE"

# Source the .env file
set -a  # Automatically export all variables
source "$ENV_FILE"
set +a  # Stop automatically exporting

# Required variables
REQUIRED_VARS=("GOOGLE_CLOUD_PROJECT" "GOOGLE_CLOUD_LOCATION" "TOOLBOX_URL")

# Check if required variables are set
MISSING_VARS=()
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    echo "❌ Error: Missing required environment variables:"
    printf '   - %s\n' "${MISSING_VARS[@]}"
    exit 1
fi

# Set defaults for optional variables
REGION="${GOOGLE_CLOUD_LOCATION:-europe-west3}"
PROJECT_ID="${GOOGLE_CLOUD_PROJECT}"
TOOLBOX_URL="${TOOLBOX_URL}"
TOOLBOX_AUDIENCE="${TOOLBOX_AUDIENCE:-$TOOLBOX_URL}"  # Default to TOOLBOX_URL if not set
GOOGLE_API_KEY="${GOOGLE_API_KEY:-}"
HOST_OVERRIDE="${HOST_OVERRIDE:-}"
MEMORY="${MEMORY:-1Gi}"
MIN_INSTANCES="${MIN_INSTANCES:-1}"

# Display configuration
echo ""
echo "🚀 Deploying job-hunting-agent to Cloud Run"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   Project ID:     $PROJECT_ID"
echo "   Region:         $REGION"
echo "   Toolbox URL:    $TOOLBOX_URL"
echo "   Memory:         $MEMORY"
echo "   Min Instances:  $MIN_INSTANCES"
if [ -n "$HOST_OVERRIDE" ]; then
    echo "   Host Override:  $HOST_OVERRIDE"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Build the gcloud command
GCLOUD_CMD="gcloud run deploy job-hunting-agent \
    --source $SCRIPT_DIR \
    --port=8080 \
    --allow-unauthenticated \
    --min-instances=$MIN_INSTANCES \
    --region=$REGION \
    --project=$PROJECT_ID \
    --update-env-vars GOOGLE_CLOUD_LOCATION=$REGION \
    --update-env-vars GOOGLE_CLOUD_PROJECT=$PROJECT_ID \
    --update-env-vars TOOLBOX_AUDIENCE=$TOOLBOX_AUDIENCE \
    --update-env-vars TOOLBOX_URL=$TOOLBOX_URL \
    --memory=$MEMORY"

# Add optional environment variables
if [ -n "$GOOGLE_API_KEY" ]; then
    GCLOUD_CMD="$GCLOUD_CMD --update-env-vars GOOGLE_API_KEY=$GOOGLE_API_KEY"
fi

if [ -n "$HOST_OVERRIDE" ]; then
    GCLOUD_CMD="$GCLOUD_CMD --update-env-vars HOST_OVERRIDE=$HOST_OVERRIDE"
fi

# Add GOOGLE_GENAI_USE_VERTEXAI if GOOGLE_API_KEY is not set
if [ -z "$GOOGLE_API_KEY" ]; then
    GCLOUD_CMD="$GCLOUD_CMD --update-env-vars GOOGLE_GENAI_USE_VERTEXAI=TRUE"
    echo "ℹ️  Using Vertex AI (GOOGLE_API_KEY not set)"
else
    echo "ℹ️  Using Google AI API Key"
fi

echo "📦 Executing deployment command..."
echo ""

# Execute the command
eval $GCLOUD_CMD

# Check if deployment was successful
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Deployment successful!"
    echo ""
    echo "🔗 Service URL:"
    gcloud run services describe job-hunting-agent \
        --region=$REGION \
        --project=$PROJECT_ID \
        --format="value(status.url)"
else
    echo ""
    echo "❌ Deployment failed!"
    exit 1
fi

