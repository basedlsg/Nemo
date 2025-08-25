# ⚡ QUICK RESTORE REFERENCE

## 🎯 **Save Point Details**
- **Commit**: `abb6b5d` (original working state)
- **Tag**: `v1.0.0-working-with-restore` (includes restore guide)
- **Status**: ✅ FULLY WORKING

## 🚀 **One-Command Restore**
```bash
git reset --hard abb6b5d
```

## 🔗 **Working URLs**
- **API**: https://gaea-gateway-783449213067.us-central1.run.app
- **Frontend**: https://n-sandy-ten.vercel.app
- **Local Test**: http://localhost:8080/test-frontend.html

## 📋 **What Works**
✅ Real Chinese government documents  
✅ Proper citations with URLs  
✅ CORS fixed for all domains  
✅ Full bilingual interface  
✅ Production deployment  

## 🛠️ **If Something Breaks**
1. Run: `git reset --hard abb6b5d`
2. Test API: `curl https://gaea-gateway-783449213067.us-central1.run.app/_health`
3. Redeploy if needed: `gcloud run deploy gaea-gateway --source . --region us-central1 --allow-unauthenticated --env-vars-file=env.yaml`

## 📖 **Full Guide**
See `RESTORE.md` for complete restoration instructions.

---
**Emergency**: Always return to commit `abb6b5d` for working state.
