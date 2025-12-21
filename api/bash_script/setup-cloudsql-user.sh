#!/bin/bash
# Script to create a database user for Cloud SQL
# Usage: ./setup-cloudsql-user.sh [username] [password]

set -e

PROJECT_ID=${GOOGLE_CLOUD_PROJECT:-niblr-agentic-service}
INSTANCE_NAME=${CLOUD_SQL_INSTANCE:-niblr-db}
DB_USER=${1:-niblr_user}
DB_PASSWORD=${2}

if [ -z "$DB_PASSWORD" ]; then
    echo "Usage: $0 [username] [password]"
    echo "Example: $0 niblr_user mySecurePassword123"
    exit 1
fi

echo "Creating database user: $DB_USER"
echo "Instance: $INSTANCE_NAME"
echo "Project: $PROJECT_ID"

gcloud sql users create "$DB_USER" \
    --instance="$INSTANCE_NAME" \
    --password="$DB_PASSWORD" \
    --project="$PROJECT_ID"

echo ""
echo "✅ User created successfully!"
echo ""
echo "Add these to your .env file:"
echo "DB_USER=$DB_USER"
echo "DB_PASSWORD=$DB_PASSWORD"
echo ""
echo "Or set them as environment variables:"
echo "export DB_USER=$DB_USER"
echo "export DB_PASSWORD=$DB_PASSWORD"

