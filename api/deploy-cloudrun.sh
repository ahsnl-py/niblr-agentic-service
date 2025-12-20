#!/bin/bash
# Deploy API to Cloud Run
# Usage: ./deploy-cloudrun.sh [service-name] [region]

set -e

# Load environment variables from .env file if it exists
load_env_file() {
    if [ -f "$1" ]; then
        echo "📋 Loading environment variables from $1..."
        # Use set -a to automatically export all variables
        set -a
        # Create a temporary file with filtered content (no comments, no empty lines)
        TEMP_ENV=$(mktemp)
        grep -v '^#' "$1" | grep -v '^$' > "$TEMP_ENV"
        # Source the filtered file
        source "$TEMP_ENV"
        rm -f "$TEMP_ENV"
        set +a
        return 0
    fi
    return 1
}

# Only load from api/.env (current directory when running from api/)
if [ -f ".env" ]; then
    load_env_file ".env"
else
    echo "⚠️  Warning: .env file not found in api/ directory"
    echo "   Expected location: api/.env"
fi

# Debug: Show if critical variables were loaded (mask sensitive values)
echo "📋 Environment variables loaded from api/.env:"
if [ -n "${JWT_SECRET_KEY}" ]; then
    echo "   ✅ JWT_SECRET_KEY loaded (length: ${#JWT_SECRET_KEY} chars)"
else
    echo "   ⚠️  JWT_SECRET_KEY not found"
fi

if [ -n "${DB_PASSWORD}" ]; then
    echo "   ✅ DB_PASSWORD loaded (length: ${#DB_PASSWORD} chars)"
else
    echo "   ⚠️  DB_PASSWORD not found"
fi

if [ -n "${AGENT_ENGINE_RESOURCE_NAME}" ]; then
    echo "   ✅ AGENT_ENGINE_RESOURCE_NAME loaded"
else
    echo "   ⚠️  AGENT_ENGINE_RESOURCE_NAME not found"
fi
echo ""

# Configuration (with defaults)
PROJECT_ID=${GOOGLE_CLOUD_PROJECT:-niblr-agentic-service}
REGION=${1:-${GOOGLE_CLOUD_LOCATION:-europe-west3}}
SERVICE_NAME=${2:-niblr-api}
INSTANCE_NAME=${CLOUD_SQL_INSTANCE:-niblr-db}
DB_NAME=${DB_NAME:-niblr_api}
DB_USER=${DB_USER:-postgres}

# Image configuration
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"
IMAGE_TAG="latest"

echo "🔍 Validating environment variables..."
echo ""

# Define required environment variables
REQUIRED_VARS=(
    "GOOGLE_CLOUD_PROJECT"
    "GOOGLE_CLOUD_LOCATION"
    "AGENT_ENGINE_RESOURCE_NAME"
    "JWT_SECRET_KEY"
    "DB_PASSWORD"
)

MISSING_VARS=()
WARNINGS=()

# Check each required variable
for var in "${REQUIRED_VARS[@]}"; do
    # Handle special cases
    if [ "$var" = "GOOGLE_CLOUD_PROJECT" ]; then
        if [ -z "${GOOGLE_CLOUD_PROJECT}" ]; then
            WARNINGS+=("GOOGLE_CLOUD_PROJECT not set, using default: ${PROJECT_ID}")
        fi
    elif [ "$var" = "GOOGLE_CLOUD_LOCATION" ]; then
        if [ -z "${GOOGLE_CLOUD_LOCATION}" ] && [ -z "$1" ]; then
            WARNINGS+=("GOOGLE_CLOUD_LOCATION not set, using default: ${REGION}")
        fi
    else
        if [ -z "${!var}" ]; then
            MISSING_VARS+=("$var")
        fi
    fi
done

# Show warnings (non-critical)
if [ ${#WARNINGS[@]} -ne 0 ]; then
    echo "⚠️  Warnings:"
    for warning in "${WARNINGS[@]}"; do
        echo "   - $warning"
    done
    echo ""
fi

# Check for missing required variables
if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    echo "❌ Error: Missing required environment variables:"
    for var in "${MISSING_VARS[@]}"; do
        echo "   - $var"
    done
    echo ""
    echo "Please set these in your api/.env file before running this script."
    echo ""
    echo "Example .env file:"
    echo "  GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"
    echo "  GOOGLE_CLOUD_LOCATION=${REGION}"
    echo "  AGENT_ENGINE_RESOURCE_NAME=your-agent-engine-resource-name"
    echo "  JWT_SECRET_KEY=your-secret-key"
    echo "  DB_PASSWORD=your-database-password"
    echo "  DB_USER=${DB_USER}"
    exit 1
fi

# Show loaded variables summary (mask sensitive ones)
echo "✅ All required environment variables are set:"
echo "   - GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"
echo "   - GOOGLE_CLOUD_LOCATION=${REGION}"
echo "   - AGENT_ENGINE_RESOURCE_NAME=${AGENT_ENGINE_RESOURCE_NAME}"
echo "   - JWT_SECRET_KEY=*** (length: ${#JWT_SECRET_KEY} chars)"
echo "   - DB_USER=${DB_USER}"
echo "   - DB_PASSWORD=*** (set)"
echo "   - CLOUD_SQL_INSTANCE=${INSTANCE_NAME}"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI is not installed"
    echo "Install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Build Cloud SQL connection name (needed for DATABASE_URL validation)
CLOUD_SQL_CONNECTION_NAME="${PROJECT_ID}:${REGION}:${INSTANCE_NAME}"

# Build DATABASE_URL for Cloud Run (Unix socket connection)
DATABASE_URL="postgresql://${DB_USER}:${DB_PASSWORD}@/niblr_api?host=/cloudsql/${CLOUD_SQL_CONNECTION_NAME}"

echo "🚀 Deploying ${SERVICE_NAME} to Cloud Run"
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo "Cloud SQL Instance: ${CLOUD_SQL_CONNECTION_NAME}"
echo ""

# Set project
echo "📋 Setting GCP project..."
gcloud config set project ${PROJECT_ID}

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    sqladmin.googleapis.com \
    secretmanager.googleapis.com \
    --project=${PROJECT_ID} 2>/dev/null || echo "APIs may already be enabled"

# Build and push Docker image
echo ""
echo "🏗️  Building Docker image..."
cd ..

# Use cloudbuild.yaml (builds from project root, uses api/Dockerfile)
echo "Using cloudbuild.yaml configuration..."
gcloud builds submit \
    --config=api/cloudbuild.yaml \
    --project=${PROJECT_ID} \
    --substitutions=_PROJECT_ID=${PROJECT_ID} \
    .

echo "📤 Image built and pushed successfully"
echo ""

# Build environment variables string
# Note: PORT is reserved by Cloud Run and set automatically - don't include it
ENV_VARS=(
    "GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"
    "GOOGLE_CLOUD_LOCATION=${REGION}"
    "GOOGLE_GENAI_USE_VERTEXAI=TRUE"
    "DATABASE_URL=${DATABASE_URL}"
    "API_PORT=8080"
)

# Add required environment variables (already validated above)
ENV_VARS+=("AGENT_ENGINE_RESOURCE_NAME=${AGENT_ENGINE_RESOURCE_NAME}")
ENV_VARS+=("JWT_SECRET_KEY=${JWT_SECRET_KEY}")

# Add optional environment variables if they exist
[ -n "${STAGING_BUCKET}" ] && ENV_VARS+=("STAGING_BUCKET=${STAGING_BUCKET}")
[ -n "${JOB_HUNTING_AGENT_URL}" ] && ENV_VARS+=("JOB_HUNTING_AGENT_URL=${JOB_HUNTING_AGENT_URL}")
[ -n "${PROPERTY_HUNTING_AGENT_URL}" ] && ENV_VARS+=("PROPERTY_HUNTING_AGENT_URL=${PROPERTY_HUNTING_AGENT_URL}")
[ -n "${CORS_ORIGINS}" ] && ENV_VARS+=("CORS_ORIGINS=${CORS_ORIGINS}")
[ -n "${ACCESS_TOKEN_EXPIRE_MINUTES}" ] && ENV_VARS+=("ACCESS_TOKEN_EXPIRE_MINUTES=${ACCESS_TOKEN_EXPIRE_MINUTES}")
[ -n "${SQL_ECHO}" ] && ENV_VARS+=("SQL_ECHO=${SQL_ECHO}")

# Convert array to --set-env-vars format
ENV_VARS_STRING=$(IFS=','; echo "${ENV_VARS[*]}")

echo "🚀 Deploying to Cloud Run..."
echo "Environment variables:"
for var in "${ENV_VARS[@]}"; do
    # Mask sensitive values
    if [[ "$var" == *"PASSWORD"* ]] || [[ "$var" == *"SECRET"* ]] || [[ "$var" == *"DATABASE_URL"* ]]; then
        echo "  ${var%%=*}=***"
    else
        echo "  $var"
    fi
done
echo ""

gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME}:${IMAGE_TAG} \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --port 8080 \
    --memory 2Gi \
    --cpu 2 \
    --timeout 300 \
    --max-instances 10 \
    --min-instances 0 \
    --set-env-vars "${ENV_VARS_STRING}" \
    --add-cloudsql-instances ${CLOUD_SQL_CONNECTION_NAME} \
    --project=${PROJECT_ID}

# Get service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
    --region=${REGION} \
    --project=${PROJECT_ID} \
    --format="value(status.url)")

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Service URL: ${SERVICE_URL}"
echo ""
echo "📝 Next steps:"
echo "1. Test the health endpoint: curl ${SERVICE_URL}/health"
echo "2. Check logs if there are issues:"
echo "   gcloud run services logs read ${SERVICE_NAME} --region=${REGION} --limit 50"
echo "3. Update CORS_ORIGINS if needed:"
echo "   gcloud run services update ${SERVICE_NAME} --region=${REGION} --set-env-vars CORS_ORIGINS=https://yourdomain.com"
echo ""
echo "🔍 Troubleshooting:"
echo "If the service fails to start, check:"
echo "  - All required env vars are set (AGENT_ENGINE_RESOURCE_NAME, JWT_SECRET_KEY, etc.)"
echo "  - Database connection string is correct"
echo "  - Cloud SQL instance is accessible"
echo "  - Agent engine resource name is valid and accessible"
echo ""
echo "View logs:"
echo "  gcloud run services logs read ${SERVICE_NAME} --region=${REGION} --limit 100"
echo ""
echo "🔐 To use secrets instead of env vars:"
echo "   gcloud secrets create JWT_SECRET_KEY --data-file=-"
echo "   gcloud run services update ${SERVICE_NAME} --region=${REGION} --set-secrets JWT_SECRET_KEY=JWT_SECRET_KEY:latest"

