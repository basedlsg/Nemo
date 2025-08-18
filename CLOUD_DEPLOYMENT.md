# GAEA Cloud Deployment Guide

## 🎯 **Overview**

This guide deploys the complete GAEA Energy Assistant stack to Google Cloud Platform using infrastructure-as-code and CI/CD best practices.

## 🏗️ **Architecture**

- **AlloyDB**: Vector database with pgvector for embeddings
- **Cloud Run**: API Gateway (public HTTPS endpoint)
- **GKE Autopilot**: Microservices (retriever, composer, guardrails, discovery, verification)
- **Artifact Registry**: Container images
- **Secret Manager**: API keys and database credentials
- **Cloud Storage**: Document storage and registry
- **Pub/Sub**: Async processing pipelines

## 🚀 **Quick Deploy**

### Prerequisites
1. GCP Project with billing enabled
2. gcloud CLI installed and authenticated
3. Terraform installed (for infrastructure)

### Deploy Commands

**From Cloud Shell or local machine:**

```bash
# Set your project ID
export PROJECT_ID="your-project-id"
export REGION="us-central1"

# Run deployment script
./scripts/deploy-cloud.sh
```

**From Windows PowerShell:**

```powershell
# Run deployment script
.\scripts\deploy-cloud.ps1 -ProjectId "your-project-id" -Region "us-central1"
```

## 📋 **What Gets Deployed**

### Infrastructure (Terraform)
- AlloyDB cluster with pgvector support
- GKE Autopilot cluster
- Artifact Registry repository
- Secret Manager secrets
- GCS buckets for data storage
- Pub/Sub topics for async processing

### Services (Cloud Build)
- **Gateway API** → Cloud Run (public endpoint)
- **Retriever Service** → GKE (vector search)
- **Composer Service** → GKE (answer generation)
- **Guardrails Service** → GKE (policy enforcement)
- **Discovery Service** → GKE (content discovery)
- **Verification Service** → GKE (fact checking)
- **Explorer UI** → Cloud Run (Next.js frontend)

### Security
- All secrets managed via Secret Manager
- Workload Identity for secure K8s → GCP access
- Placeholder domain detection in guardrails
- First-party citation requirements

## 🔧 **Configuration**

### Environment Variables
All configuration is managed via Secret Manager:
- `DATABASE_URL`: AlloyDB connection string
- `PPLX_API_KEY`: Perplexity API key
- `GOOGLE_API_KEY`: Google Cloud API key
- `GOOGLE_CSE_ID`: Custom Search Engine ID

### Registry Sources
Registry configuration is stored in GCS at:
`gs://{project-id}-gaea-registry/sources.yaml`

Update this file to add new provinces or document sources.

## 🧪 **Testing**

### Health Checks
```bash
# Gateway health
curl https://gaea-gateway-xxx.run.app/health

# Service statistics
curl https://gaea-gateway-xxx.run.app/stats
```

### Query Testing
```bash
# Test Chinese query
curl -X POST https://gaea-gateway-xxx.run.app/query \
  -H 'Content-Type: application/json' \
  -d '{
    "province": "guangdong",
    "doc_class": "grid_connection", 
    "asset": "solar",
    "question": "并网验收需要哪些资料？",
    "lang": "zh"
  }'
```

### UI Testing
Open the UI URL in browser and submit queries through the web interface.

## 🔄 **CI/CD Pipeline**

### Automatic Deployment
- Push to `main` branch triggers Cloud Build
- Builds all container images
- Deploys to Cloud Run and GKE
- Updates service configurations

### Manual Deployment
```bash
# Trigger manual build
gcloud builds submit --config=cloudbuild.yaml .
```

## 📊 **Monitoring**

### Logs
```bash
# Gateway logs
gcloud logs read "resource.type=cloud_run_revision AND resource.labels.service_name=gaea-gateway"

# Service logs
kubectl logs -n gaea deployment/gaea-retriever
```

### Metrics
- Cloud Run metrics in GCP Console
- GKE workload metrics
- Custom application metrics via logging

## 🛡️ **Security Features**

### Guardrails
- **Placeholder Detection**: Refuses queries with test domains
- **Citation Requirements**: Ensures first-party sources
- **Province Validation**: Only supported regions
- **Domain Allowlisting**: Authorized sources only

### Access Control
- Service accounts with minimal permissions
- Workload Identity for K8s → GCP access
- Secret Manager for sensitive data
- Private GKE cluster networking

## 🔧 **Troubleshooting**

### Common Issues

**Database Connection Errors**
```bash
# Check AlloyDB status
gcloud alloydb instances describe gaea-primary --cluster=gaea-cluster --region=us-central1

# Verify database URL secret
gcloud secrets versions access latest --secret=DATABASE_URL
```

**Service Deployment Issues**
```bash
# Check Cloud Build logs
gcloud builds list --limit=5

# Check service status
kubectl get pods -n gaea
gcloud run services list
```

**API Key Issues**
```bash
# Verify secrets exist
gcloud secrets list

# Check secret values
gcloud secrets versions access latest --secret=PPLX_API_KEY
```

### Performance Tuning

**Scaling Configuration**
- Cloud Run: Auto-scales 0-10 instances
- GKE: Autopilot manages node scaling
- AlloyDB: 2 CPU baseline, auto-scaling storage

**Resource Limits**
- Gateway: 2 CPU, 2Gi memory
- Retriever: 500m CPU, 1Gi memory  
- Composer: 500m CPU, 1Gi memory
- Other services: 250m CPU, 512Mi memory

## 📈 **Next Steps**

1. **Add Real Registry Sources**: Replace placeholder domains with actual provincial exchange URLs
2. **Content Ingestion**: Run discovery → verification → ingestion pipeline
3. **Monitoring Setup**: Configure alerting and dashboards
4. **Load Testing**: Validate performance under load
5. **Security Audit**: Review access controls and secrets

## 🆘 **Support**

For deployment issues:
1. Check Cloud Build logs: `gcloud builds list`
2. Verify service health: `/health` endpoints
3. Review application logs in Cloud Logging
4. Check resource quotas and billing

## 📚 **References**

- [GCP AlloyDB Documentation](https://cloud.google.com/alloydb/docs)
- [GKE Autopilot Guide](https://cloud.google.com/kubernetes-engine/docs/concepts/autopilot-overview)
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Secret Manager Best Practices](https://cloud.google.com/secret-manager/docs/best-practices)