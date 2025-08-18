# 🚀 Deploy GAEA to Google Cloud - Execute Now

## ⚡ **Quick Deploy (5 minutes)**

### 1. Set Your Project ID
```powershell
# Replace with your actual GCP project ID
$PROJECT_ID = "your-actual-project-id"
```

### 2. Run Deployment Script
```powershell
# Execute the deployment
.\scripts\deploy-cloud.ps1 -ProjectId $PROJECT_ID -Region "us-central1"
```

### 3. Wait for Completion (15-20 minutes)
The script will:
- ✅ Enable required GCP APIs
- ✅ Deploy infrastructure with Terraform
- ✅ Create AlloyDB cluster with pgvector
- ✅ Set up Secret Manager with your API keys
- ✅ Build and deploy all services
- ✅ Configure auto-scaling and monitoring

### 4. Get Your URLs
After deployment completes, you'll see:
```
✅ Deployment complete!

🌐 Service URLs:
  Gateway API: https://gaea-gateway-xxx.run.app
  Web UI: https://gaea-ui-xxx.run.app

🧪 Test the deployment:
  curl -X POST https://gaea-gateway-xxx.run.app/query \
    -H 'Content-Type: application/json' \
    -d '{"province":"guangdong","doc_class":"grid_connection","asset":"solar","question":"并网验收需要哪些资料？","lang":"zh"}'

🎯 Open the UI: https://gaea-ui-xxx.run.app
```

## 🧪 **Test Your Deployment**

### Health Check
```bash
curl https://gaea-gateway-xxx.run.app/health
```

### Chinese Query Test
```bash
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

### Expected Response (with placeholder protection)
```json
{
  "status": "refused",
  "reason": "placeholder_url_detected",
  "message": "Citation contains placeholder domain: gzpec.cn",
  "policy": "no_placeholder_citations"
}
```

This refusal is **correct** - it means the guardrails are working!

## 🔄 **Next Steps After Deployment**

### 1. Replace Placeholder Registry
```bash
# Update the registry with real domains
gsutil cp updated-sources.yaml gs://$PROJECT_ID-gaea-registry/sources.yaml
```

### 2. Run Content Ingestion
```bash
# Trigger discovery and ingestion pipeline
curl -X POST https://gaea-gateway-xxx.run.app/admin/trigger-ingestion \
  -H 'Authorization: Bearer YOUR_ADMIN_TOKEN'
```

### 3. Verify Real Citations
Once real content is ingested, queries should return actual citations instead of refusals.

## 🛡️ **Security Features Active**

- ✅ **Placeholder Detection**: Refuses `gzpec.cn`, `sdpxc.cn`, `impex.org.cn`
- ✅ **Secret Manager**: All API keys secured
- ✅ **Workload Identity**: Secure K8s → GCP access
- ✅ **Citation Requirements**: First-party sources only
- ✅ **Auto-scaling**: Handles traffic spikes
- ✅ **Health Monitoring**: Automatic failure detection

## 📊 **What's Running**

### Cloud Run (Public)
- **Gateway API**: Main query endpoint
- **Explorer UI**: Web interface with Chinese/English support

### GKE Autopilot (Private)
- **Retriever**: Vector similarity search
- **Composer**: Chinese answer generation
- **Guardrails**: Policy enforcement
- **Discovery**: Content discovery
- **Verification**: Fact checking

### AlloyDB
- **Vector Database**: pgvector for embeddings
- **Citation Storage**: Structured document metadata
- **Query Logging**: Analytics and monitoring

## 🎯 **Ready to Go Live!**

Your GAEA Energy Assistant is now:
- 🌐 **Deployed to production**
- 🔒 **Secured with best practices**
- 📈 **Auto-scaling enabled**
- 🛡️ **Protected against test data leakage**
- 📊 **Monitored and observable**

**Just run the deployment script and you're live in the cloud!**