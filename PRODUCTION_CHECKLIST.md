# GAEA Production Readiness Checklist

## 🎯 **Pre-Deployment**

### Infrastructure
- [ ] GCP Project with billing enabled
- [ ] Required APIs enabled (see `scripts/deploy-cloud.ps1`)
- [ ] Terraform state bucket created
- [ ] AlloyDB cluster provisioned with pgvector
- [ ] GKE Autopilot cluster ready
- [ ] Artifact Registry repository created

### Security
- [ ] All secrets stored in Secret Manager
- [ ] Service account permissions configured
- [ ] Workload Identity enabled for GKE
- [ ] Network security policies applied
- [ ] Database access restricted to services only

### Configuration
- [ ] Real API keys added to Secret Manager:
  - [ ] `PPLX_API_KEY` (Perplexity)
  - [ ] `GOOGLE_API_KEY` (Google Cloud)
  - [ ] `GOOGLE_CSE_ID` (Custom Search Engine)
- [ ] Database URL configured in Secret Manager
- [ ] Registry sources updated with real domains (not placeholders)

## 🚀 **Deployment**

### Initial Deployment
- [ ] Run `./scripts/deploy-cloud.ps1 -ProjectId "your-project"`
- [ ] Verify Terraform infrastructure deployment
- [ ] Confirm Cloud Build successful
- [ ] Check all services are healthy

### Database Setup
- [ ] Run database migration: `scripts/setup-database.sql`
- [ ] Verify vector extension enabled
- [ ] Confirm tables created with proper indexes
- [ ] Test database connectivity from services

### Service Verification
- [ ] Gateway API responding: `/health` endpoint
- [ ] All microservices healthy in GKE
- [ ] UI accessible and loading
- [ ] API rewrites working (`/api/v1/*` → gateway)

## 🧪 **Testing**

### Functional Testing
- [ ] Health checks pass for all services
- [ ] Chinese query processing works
- [ ] Guardrails properly refuse placeholder domains
- [ ] Citation formatting correct
- [ ] Error handling works (invalid queries)

### Performance Testing
- [ ] Load test with concurrent queries
- [ ] Verify auto-scaling triggers
- [ ] Database query performance acceptable
- [ ] Memory usage within limits

### Security Testing
- [ ] Placeholder domain detection working
- [ ] Unauthorized domain rejection
- [ ] Secret access properly restricted
- [ ] No sensitive data in logs

## 📊 **Monitoring**

### Observability Setup
- [ ] Prometheus metrics collection
- [ ] Cloud Logging configured
- [ ] Error tracking enabled
- [ ] Performance monitoring active

### Alerting
- [ ] Service health alerts
- [ ] Database connection alerts
- [ ] High error rate alerts
- [ ] Resource usage alerts

### Dashboards
- [ ] Service health dashboard
- [ ] Query volume and latency
- [ ] Error rate and refusal reasons
- [ ] Resource utilization

## 🔄 **Operations**

### CI/CD Pipeline
- [ ] Cloud Build trigger configured
- [ ] Automatic deployment on main branch
- [ ] Rollback procedure tested
- [ ] Blue-green deployment strategy

### Backup and Recovery
- [ ] Database backup schedule
- [ ] Configuration backup
- [ ] Disaster recovery plan
- [ ] RTO/RPO defined

### Scaling
- [ ] Horizontal Pod Autoscaler configured
- [ ] Cloud Run auto-scaling enabled
- [ ] Database scaling strategy
- [ ] Cost optimization reviewed

## 📋 **Go-Live**

### Final Checks
- [ ] All placeholder domains replaced
- [ ] Real content ingested into database
- [ ] End-to-end testing complete
- [ ] Performance benchmarks met
- [ ] Security review passed

### Launch Preparation
- [ ] Monitoring dashboards ready
- [ ] Support team trained
- [ ] Documentation updated
- [ ] Rollback plan prepared
- [ ] Communication plan ready

### Post-Launch
- [ ] Monitor initial traffic
- [ ] Verify all metrics normal
- [ ] Check error rates
- [ ] Validate user experience
- [ ] Document any issues

## 🛡️ **Security Compliance**

### Data Protection
- [ ] PII handling compliant
- [ ] Data retention policies
- [ ] Encryption at rest and in transit
- [ ] Access logging enabled

### Compliance
- [ ] Security policies enforced
- [ ] Audit trail complete
- [ ] Vulnerability scanning
- [ ] Penetration testing

## 📈 **Performance Targets**

### Response Times
- [ ] Gateway API: < 2s for queries
- [ ] UI loading: < 3s initial load
- [ ] Database queries: < 500ms
- [ ] Service-to-service: < 100ms

### Availability
- [ ] 99.9% uptime target
- [ ] < 1% error rate
- [ ] Auto-recovery from failures
- [ ] Graceful degradation

### Scalability
- [ ] Handle 100 concurrent users
- [ ] Support 1000 queries/hour
- [ ] Auto-scale to demand
- [ ] Cost-effective scaling

## ✅ **Sign-off**

- [ ] **Technical Lead**: Infrastructure and code review complete
- [ ] **Security Team**: Security review and approval
- [ ] **Operations Team**: Monitoring and alerting ready
- [ ] **Product Owner**: Functional requirements met
- [ ] **Compliance**: Regulatory requirements satisfied

---

**Deployment Date**: ___________
**Deployed By**: ___________
**Version**: ___________
**Environment**: Production