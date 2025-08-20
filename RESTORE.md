# 🔄 RESTORE GUIDE - Chinese Energy Compliance Assistant

## 📋 **Save Point Information**

**Commit Hash**: `abb6b5d`  
**Tag**: `v1.0.0-working`  
**Date**: August 20, 2025  
**Status**: ✅ FULLY WORKING DEPLOYMENT

## 🎯 **What This Save Point Contains**

### **✅ Working Components**
- **API Backend**: Cloud Run deployment at `https://gaea-gateway-783449213067.us-central1.run.app`
- **Frontend**: Vercel deployment at `https://n-sandy-ten.vercel.app`
- **CORS Configuration**: Fixed for all domains including Vercel
- **Real Data**: Chinese government documents with proper citations
- **Environment Variables**: Properly configured for production
- **Full End-to-End Functionality**: Query → API → Real Documents → Citations

### **✅ Key Features Working**
- Chinese energy compliance document queries
- Real-time Google CSE integration
- Proper citation formatting
- Bilingual interface (Chinese/English)
- Error handling and validation
- Production-ready deployment

## 🚀 **How to Restore This Save Point**

### **Method 1: Git Reset (Recommended)**
```bash
# Navigate to project directory
cd C:\Users\Flare\Nemo_Test

# Reset to the working commit
git reset --hard abb6b5d

# Verify you're at the right commit
git log --oneline -1
```

### **Method 2: Git Checkout Tag**
```bash
# Checkout the tagged version
git checkout v1.0.0-working

# Create a new branch from this point (optional)
git checkout -b restore-working-deployment
```

### **Method 3: Create New Branch from Save Point**
```bash
# Create and switch to new branch from working commit
git checkout -b backup-working abb6b5d
```

## 🔧 **Post-Restore Steps**

### **1. Verify Environment Variables**
Ensure these files exist and are correct:
- `env.yaml` - Contains API keys and configuration
- `apps/explorer-ui/.env.local` - Contains Vercel API base URL

### **2. Test API Endpoints**
```bash
# Test health endpoint
curl https://gaea-gateway-783449213067.us-central1.run.app/_health

# Test query endpoint
curl -X POST https://gaea-gateway-783449213067.us-central1.run.app/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"province":"广东","doc_class":"光伏","asset":"分布式","question":"并网接入需要什么手续","lang":"zh-CN"}'
```

### **3. Redeploy if Needed**
```bash
# Redeploy API to Cloud Run
gcloud run deploy gaea-gateway --source . --region us-central1 --allow-unauthenticated --env-vars-file=env.yaml

# Redeploy frontend to Vercel
cd apps/explorer-ui
vercel --prod
```

## 🛡️ **Why This Save Point is Important**

### **1. Production Stability**
- All systems are tested and working
- Real data integration verified
- No mock responses or test data
- Production-ready configuration

### **2. CORS Issues Resolved**
- Dynamic Vercel domain handling
- Proper cross-origin request configuration
- Tested with multiple deployment URLs

### **3. Complete Functionality**
- Full query pipeline working
- Chinese government document retrieval
- Proper citation formatting
- Error handling implemented

### **4. Deployment Infrastructure**
- Cloud Run API deployment
- Vercel frontend deployment
- Environment variables configured
- CORS properly set up

## 📊 **Current Working URLs**

| Component | URL | Status |
|-----------|-----|--------|
| API Backend | https://gaea-gateway-783449213067.us-central1.run.app | ✅ Working |
| API Health | https://gaea-gateway-783449213067.us-central1.run.app/_health | ✅ Working |
| Vercel Frontend | https://n-sandy-ten.vercel.app | ✅ Working |
| Local Test | http://localhost:8080/test-frontend.html | ✅ Working |

## 🔍 **Troubleshooting**

### **If API is Down**
```bash
# Check Cloud Run status
gcloud run services describe gaea-gateway --region us-central1

# Redeploy API
gcloud run deploy gaea-gateway --source . --region us-central1 --allow-unauthenticated --env-vars-file=env.yaml
```

### **If Frontend is Down**
```bash
# Check Vercel deployment
cd apps/explorer-ui
vercel ls

# Redeploy frontend
vercel --prod
```

### **If CORS Issues Return**
```bash
# Check current CORS configuration
curl -H "Origin: https://n-sandy-ten.vercel.app" https://gaea-gateway-783449213067.us-central1.run.app/_health

# Redeploy with updated CORS
gcloud run deploy gaea-gateway --source . --region us-central1 --allow-unauthenticated --env-vars-file=env.yaml
```

## 📝 **Environment Variables Reference**

### **API Environment (env.yaml)**
```yaml
QUERY_MODE: "web_only"
PPLX_API_KEY: "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"
GOOGLE_API_KEY: "AIzaSyAM6Ko33ubRd_d8tkr6b4rocOqRXgyAy0Q"
GOOGLE_CSE_ID: "c2902a74ad3664d41"
ALLOWLIST_DOMAINS: "gov.cn,gd.gov.cn,gz.gov.cn,zfcxjst.gd.gov.cn"
ALLOWED_ORIGINS: "https://n-k76s89hm2-basedlsgs-projects.vercel.app,https://n-27cd508ag-basedlsgs-projects.vercel.app,https://n-sandy-ten.vercel.app,http://localhost:3000,http://localhost:8080,file://"
```

### **Frontend Environment (.env.local)**
```
NEXT_PUBLIC_API_BASE=https://gaea-gateway-783449213067.us-central1.run.app
```

## 🎯 **Success Criteria**

After restoration, you should be able to:
1. ✅ Access the API at the Cloud Run URL
2. ✅ Access the frontend at the Vercel URL
3. ✅ Submit queries and receive real Chinese government documents
4. ✅ See proper citations with URLs
5. ✅ No CORS errors in browser console
6. ✅ Full bilingual interface working

## 📞 **Emergency Contacts**

- **Cloud Run**: Google Cloud Console
- **Vercel**: Vercel Dashboard
- **API Keys**: Check env.yaml for current keys
- **Domain Issues**: Verify ALLOWED_ORIGINS in env.yaml

---

**Last Updated**: August 20, 2025  
**Save Point ID**: `abb6b5d`  
**Tag**: `v1.0.0-working`  
**Status**: ✅ PRODUCTION READY
