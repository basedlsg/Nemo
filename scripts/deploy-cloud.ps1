# GAEA Cloud Deployment Script for PowerShell
# Run this from Cloud Shell or a machine with gcloud CLI configured

param(
    [string]$ProjectId = "nemo-test-project",
    [string]$Region = "us-central1"
)

$ErrorActionPreference = "Stop"

Write-Host "🚀 Starting GAEA cloud deployment..." -ForegroundColor Green
Write-Host "Project: $ProjectId" -ForegroundColor Cyan
Write-Host "Region: $Region" -ForegroundColor Cyan

$TfBucket = "$ProjectId-tf"

# Step 1: Enable required APIs
Write-Host "📋 Enabling required GCP APIs..." -ForegroundColor Yellow
gcloud config set project $ProjectId

$apis = @(
    "container.googleapis.com",
    "run.googleapis.com", 
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "cloudbuild.googleapis.com",
    "vpcaccess.googleapis.com",
    "documentai.googleapis.com",
    "workflows.googleapis.com",
    "pubsub.googleapis.com",
    "dataflow.googleapis.com",
    "alloydb.googleapis.com",
    "cloudkms.googleapis.com",
    "monitoring.googleapis.com",
    "logging.googleapis.com"
)

gcloud services enable $apis

# Step 2: Create Terraform state bucket
Write-Host "🪣 Creating Terraform state bucket..." -ForegroundColor Yellow
try {
    gsutil mb -l $Region gs://$TfBucket
} catch {
    Write-Host "Bucket already exists" -ForegroundColor Gray
}

# Step 3: Apply Terraform infrastructure
Write-Host "🏗️ Deploying infrastructure with Terraform..." -ForegroundColor Yellow
Set-Location infra/terraform

# Update project ID in tfvars
(Get-Content terraform.tfvars) -replace 'nemo-test-project', $ProjectId | Set-Content terraform.tfvars

terraform init
terraform apply -var-file=terraform.tfvars -auto-approve

# Get AlloyDB IP for database URL
$AlloyDbIp = terraform output -raw alloydb_ip
Write-Host "AlloyDB IP: $AlloyDbIp" -ForegroundColor Cyan

Set-Location ../..

# Step 4: Create secrets in Secret Manager
Write-Host "🔐 Creating secrets in Secret Manager..." -ForegroundColor Yellow

# Database URL
$DbUrl = "postgresql+asyncpg://gaea_admin:GaeaSecure2025!@$AlloyDbIp:5432/postgres"
try {
    echo $DbUrl | gcloud secrets create DATABASE_URL --data-file=-
} catch {
    echo $DbUrl | gcloud secrets versions add DATABASE_URL --data-file=-
}

# API Keys (using values from .env)
$PplxKey = (Get-Content .env | Where-Object { $_ -match "PPLX_API_KEY=" }) -replace "PPLX_API_KEY=", ""
$GoogleKey = (Get-Content .env | Where-Object { $_ -match "GOOGLE_API_KEY=" }) -replace "GOOGLE_API_KEY=", ""
$GoogleCse = (Get-Content .env | Where-Object { $_ -match "GOOGLE_CSE_ID=" }) -replace "GOOGLE_CSE_ID=", ""

try {
    echo $PplxKey | gcloud secrets create PPLX_API_KEY --data-file=-
} catch {
    echo $PplxKey | gcloud secrets versions add PPLX_API_KEY --data-file=-
}

try {
    echo $GoogleKey | gcloud secrets create GOOGLE_API_KEY --data-file=-
} catch {
    echo $GoogleKey | gcloud secrets versions add GOOGLE_API_KEY --data-file=-
}

try {
    echo $GoogleCse | gcloud secrets create GOOGLE_CSE_ID --data-file=-
} catch {
    echo $GoogleCse | gcloud secrets versions add GOOGLE_CSE_ID --data-file=-
}

# Step 5: Upload registry to GCS
Write-Host "📄 Uploading registry to GCS..." -ForegroundColor Yellow
gsutil cp data/registry/sources.yaml gs://$ProjectId-gaea-registry/sources.yaml

# Step 6: Trigger Cloud Build
Write-Host "🔨 Triggering Cloud Build deployment..." -ForegroundColor Yellow

# Manual build for immediate deployment
gcloud builds submit --config=cloudbuild.yaml .

# Step 7: Wait for deployment and get URLs
Write-Host "⏳ Waiting for deployment to complete..." -ForegroundColor Yellow
Start-Sleep 60

$GatewayUrl = gcloud run services describe gaea-gateway --region $Region --format="value(status.url)"
$UiUrl = gcloud run services describe gaea-ui --region $Region --format="value(status.url)"

Write-Host "✅ Deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "🌐 Service URLs:" -ForegroundColor Cyan
Write-Host "  Gateway API: $GatewayUrl" -ForegroundColor White
Write-Host "  Web UI: $UiUrl" -ForegroundColor White
Write-Host ""
Write-Host "🧪 Test the deployment:" -ForegroundColor Cyan
Write-Host "  curl -X POST $GatewayUrl/query \\" -ForegroundColor Gray
Write-Host "    -H 'Content-Type: application/json' \\" -ForegroundColor Gray
Write-Host "    -d '{\"province\":\"guangdong\",\"doc_class\":\"grid_connection\",\"asset\":\"solar\",\"question\":\"test query\",\"lang\":\"zh\"}'" -ForegroundColor Gray
Write-Host ""
Write-Host "🎯 Open the UI: $UiUrl" -ForegroundColor Green