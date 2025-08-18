#!/bin/bash

# GAEA Cloud Deployment Script
# Run this from Cloud Shell or a machine with gcloud CLI configured

set -e

# Configuration
PROJECT_ID="${PROJECT_ID:-nemo-test-project}"  # Set your project ID
REGION="${REGION:-us-central1}"
TF_BUCKET="${PROJECT_ID}-tf"

echo "🚀 Starting GAEA cloud deployment..."
echo "Project: $PROJECT_ID"
echo "Region: $REGION"

# Step 1: Enable required APIs
echo "📋 Enabling required GCP APIs..."
gcloud config set project $PROJECT_ID

gcloud services enable \
  container.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  vpcaccess.googleapis.com \
  documentai.googleapis.com \
  workflows.googleapis.com \
  pubsub.googleapis.com \
  dataflow.googleapis.com \
  alloydb.googleapis.com \
  cloudkms.googleapis.com \
  monitoring.googleapis.com \
  logging.googleapis.com

# Step 2: Create Terraform state bucket
echo "🪣 Creating Terraform state bucket..."
gsutil mb -l $REGION gs://$TF_BUCKET || echo "Bucket already exists"

# Step 3: Apply Terraform infrastructure
echo "🏗️ Deploying infrastructure with Terraform..."
cd infra/terraform

# Update project ID in tfvars
sed -i "s/nemo-test-project/$PROJECT_ID/g" terraform.tfvars

terraform init
terraform apply -var-file=terraform.tfvars -auto-approve

# Get AlloyDB IP for database URL
ALLOYDB_IP=$(terraform output -raw alloydb_ip)
echo "AlloyDB IP: $ALLOYDB_IP"

cd ../..

# Step 4: Create secrets in Secret Manager
echo "🔐 Creating secrets in Secret Manager..."

# Database URL
DB_URL="postgresql+asyncpg://gaea_admin:GaeaSecure2025!@$ALLOYDB_IP:5432/postgres"
echo -n "$DB_URL" | gcloud secrets create DATABASE_URL --data-file=- || \
echo -n "$DB_URL" | gcloud secrets versions add DATABASE_URL --data-file=-

# API Keys (using values from .env)
PPLX_KEY=$(grep PPLX_API_KEY .env | cut -d'=' -f2)
GOOGLE_KEY=$(grep GOOGLE_API_KEY .env | cut -d'=' -f2)
GOOGLE_CSE=$(grep GOOGLE_CSE_ID .env | cut -d'=' -f2)

echo -n "$PPLX_KEY" | gcloud secrets create PPLX_API_KEY --data-file=- || \
echo -n "$PPLX_KEY" | gcloud secrets versions add PPLX_API_KEY --data-file=-

echo -n "$GOOGLE_KEY" | gcloud secrets create GOOGLE_API_KEY --data-file=- || \
echo -n "$GOOGLE_KEY" | gcloud secrets versions add GOOGLE_API_KEY --data-file=-

echo -n "$GOOGLE_CSE" | gcloud secrets create GOOGLE_CSE_ID --data-file=- || \
echo -n "$GOOGLE_CSE" | gcloud secrets versions add GOOGLE_CSE_ID --data-file=-

# Step 5: Upload registry to GCS
echo "📄 Uploading registry to GCS..."
gsutil cp data/registry/sources.yaml gs://$PROJECT_ID-gaea-registry/sources.yaml

# Step 6: Trigger Cloud Build
echo "🔨 Triggering Cloud Build deployment..."

# Create Cloud Build trigger if it doesn't exist
gcloud builds triggers create github \
  --repo-name=gaea-energy-assistant \
  --repo-owner=your-github-username \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml \
  --name=gaea-deploy || echo "Trigger already exists"

# Manual build for immediate deployment
gcloud builds submit --config=cloudbuild.yaml .

# Step 7: Wait for deployment and get URLs
echo "⏳ Waiting for deployment to complete..."
sleep 60

GATEWAY_URL=$(gcloud run services describe gaea-gateway --region $REGION --format="value(status.url)")
UI_URL=$(gcloud run services describe gaea-ui --region $REGION --format="value(status.url)")

echo "✅ Deployment complete!"
echo ""
echo "🌐 Service URLs:"
echo "  Gateway API: $GATEWAY_URL"
echo "  Web UI: $UI_URL"
echo ""
echo "🧪 Test the deployment:"
echo "  curl -X POST $GATEWAY_URL/query \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"province\":\"guangdong\",\"doc_class\":\"grid_connection\",\"asset\":\"solar\",\"question\":\"并网验收需要哪些资料？\",\"lang\":\"zh\"}'"
echo ""
echo "🎯 Open the UI: $UI_URL"