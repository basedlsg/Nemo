# Implementation Plan

This implementation plan converts the geo-adaptive energy assistant design into discrete, manageable coding tasks that build incrementally toward a complete system. Each task focuses on writing, modifying, or testing code components, with early validation of core functionality through automated tests.

## Core Infrastructure and Data Layer

- [x] 1. Set up project structure and environment configuration

  - Create monorepo structure with apps/, services/, data/, infra/, docs/, tests/ directories
  - Configure .env file with API keys (Perplexity, Google CSE, Google Cloud)
  - Set up Python virtual environment with requirements.txt for core dependencies
  - Create Docker base images for microservices with Python 3.11 and required packages

  - _Requirements: Non-negotiables, API Contracts_

- [x] 2. Implement database schemas and connection utilities

  - Write AlloyDB connection management with pgvector extension setup

  - Create SQL migration scripts for citations, packs, and sources tables with proper indexes
  - Implement database connection pooling and health check endpoints
  - Write unit tests for database connection and basic CRUD operations
  - _Requirements: 2.4, Data Contracts_

- [x] 3. Create core data models and validation

  - Implement Citation, Pack, and Source Pydantic models with validation rules
  - Write UUID generation utilities and checksum validation functions
  - Create effective date parsing and conflict resolution logic (latest effective_date <= now())
  - Implement unit tests for data model validation and serialization

  - _Requirements: 1.3, 2.4, Effective Date Semantics_

## Source Registry and Discovery Pipeline

- [x] 4. Implement source registry management

  - Create YAML-based source registry parser that loads into sources table
  - Write source validation logic (domain allowlists, robots.txt checking)
  - Implement CRUD operations for source registry with owner tracking
  - Create unit tests for source registry loading and validation
  - _Requirements: 2.1, 2.5_

- [x] 5. Build Perplexity discovery service

  - Implement Perplexity API client with domain allowlist filtering
  - Create discovery request/response models with candidate URL extraction

  - Write retry logic with exponential backoff for API rate limits
  - Implement unit tests for Perplexity integration with mock responses

  - _Requirements: 2.1, Research Orchestrator APIs_

- [x] 6. Build Google CSE verification service

  - Implement Google Programmable Search CSE JSON API client
  - Create verification logic that confirms URLs against allowlisted domains
  - Write canonical URL extraction and deduplication logic
  - Implement unit tests for CSE verification with mock Google API responses
  - _Requirements: 2.2, Research Orchestrator APIs_

## Document Processing and Ingestion


- [ ] 7. Implement document fetching and snapshot storage

  - Create GCS client wrapper with WORM (Write Once Read Many) bucket configuration
  - Write document fetcher that respects robots.txt and logs trace_id
  - Implement SHA256 checksum calculation and metadata extraction
  - Create unit tests for document fetching and GCS storage operations
  - _Requirements: 2.3, 2.5_

- [x] 8. Build OCR and text extraction service

  - Integrate Google Document AI for Chinese PDF and HTML text extraction
  - Implement table structure recognition and text normalization for CJK characters
  - Create effective date extraction logic using regex patterns and metadata
  - Write unit tests for OCR processing with sample Chinese energy documents
  - _Requirements: 2.4, Chunking Policy_

- [x] 9. Implement text chunking and normalization

  - Create text chunking logic with 800 token max and 100 token overlap
  - Write ontology mapping service (jurisdiction → market/code → asset → lifecycle → requirement → parameter → citation)
  - Implement chunk_id generation and parent_citation_id tracking for traceability
  - Create unit tests for chunking and ontology mapping with energy regulation samples
  - _Requirements: 2.4, Chunking Policy, Data Models_

- [x] 10. Build embedding generation service

  - Integrate Google Cloud Vertex AI for text embedding generation
  - Implement batch processing for efficient embedding computation
  - Create vector storage logic for AlloyDB pgvector integration

  - Write unit tests for embedding generation and vector storage operations
  - _Requirements: 2.4, Data Models_

## NeMo Integration and RAG Services


- [ ] 11. Set up NeMo Retriever microservice

  - Configure NVIDIA NeMo Retriever with geo-sharded indexes (shandong, guangdong, inner_mongolia)
  - Implement BM25 + vector similarity reranking for citation retrieval
  - Create province-specific index management and query routing

  - Write integration tests for retriever service with sample citations

  - _Requirements: 3.1, NeMo Integration_

- [ ] 12. Implement NeMo Guardrails service

  - Configure NeMo Guardrails with citations_required, zh_first, and unsafe_scope policies
  - Write policy validation logic that checks citation metadata completeness

  - Implement refusal exception handling with specific error codes
  - Create unit tests for each guardrail policy with positive and negative test cases
  - _Requirements: 1.4, 4.4, Guardrails Policy, Refusal Taxonomy_

- [x] 13. Build NeMo Evaluator service

  - Set up NeMo Evaluator for offline quality assessment with nightly batch jobs
  - Implement groundedness, citation precision, and refusal accuracy metrics calculation
  - Create evaluation job scheduling and results storage in BigQuery
  - Write unit tests for evaluation metrics with golden Q/A datasets
  - _Requirements: 4.1, 4.3, Evaluator Gold Sets_


## API Gateway and Request Processing

- [ ] 14. Create FastAPI gateway with request routing

  - Implement FastAPI application with request validation using Pydantic models
  - Create province/asset/doc_class validation middleware

  - Write request logging with structured JSON format (service, trace_id, user, province, etc.)
  - Implement unit tests for API request validation and routing
  - _Requirements: 6.1, API Contracts, Structured Logging_

- [ ] 15. Implement query processing pipeline

  - Create end-to-end query handler that orchestrates Retriever → Guardrails → response formatting

  - Write citation metadata enrichment logic for response assembly
  - Implement query fingerprinting for pack generation and caching
  - Create integration tests for complete query processing with mock NeMo services
  - _Requirements: 1.1, 1.2, 1.3_

- [ ] 16. Build refusal handling and error responses
  - Implement RefusalException class with specific error codes (no_first_party_citation, stale_citation, etc.)
  - Create 422 error response formatting with policy information
  - Write refusal logging and metrics collection
  - Implement unit tests for each refusal scenario and error response format
  - _Requirements: 1.2, 4.4, Refusal Taxonomy, Error Handling_

## User Interface Development

- [x] 17. Create Explorer UI with Chinese-first interface

  - Build Next.js 14 application with TypeScript and Chinese localization
  - Implement province/asset/doc_class selector components with validation
  - Create query input form with real-time validation and submission
  - Write unit tests for UI components using React Testing Library
  - _Requirements: 6.1, 6.2_

- [x] 18. Implement citation display and pack generation




  - Create citation display components showing title, effective_date, and verification links
  - Implement Chinese PDF generation using headless Chrome/Puppeteer with Noto CJK fonts
  - Write CSS styling with line-break:anywhere and word-break:break-word for Hanzi text
  - Create unit tests for citation rendering and PDF generation
  - _Requirements: 6.2, 6.4_



- [ ] 19. Build refusal UI and ingestion request flow

  - Implement refusal badge component with clear explanation display
  - Create "request ingestion" action button that queues manual review

  - Write refusal reason display logic for each error code type




  - Implement unit tests for refusal UI states and user interactions
  - _Requirements: 6.3, Refusal Taxonomy_

- [ ] 20. Create Radar UI for market signals
  - Build market signals dashboard with province and asset filtering



  - Implement official tender/notice feed display with CSV export functionality
  - Create BigQuery integration for analytics data storage and retrieval
  - Write unit tests for Radar UI components and data export features
  - _Requirements: 8.1, 8.2, 8.4_

## Research Orchestrator and Pipeline Integration

- [ ] 21. Build research orchestrator service

  - Create orchestration service that coordinates discovery → verification → ingestion workflow
  - Implement Pub/Sub integration for asynchronous pipeline processing
  - Write job queue management with retry logic and failure handling
  - Create integration tests for complete research pipeline with mock external APIs
  - _Requirements: 2.1, 2.2, Research Orchestrator APIs_

- [ ] 22. Implement ingestion job processing

  - Create ingestion worker that processes verified URLs through fetch → OCR → normalize → embed → store
  - Write job status tracking and progress reporting
  - Implement error handling and dead letter queue for failed ingestions
  - Create integration tests for ingestion job processing with sample documents
  - _Requirements: 2.3, 2.4, 2.5_

- [ ] 23. Build pipeline monitoring and alerting
  - Implement ingestion freshness tracking (T+48h ≥ 95% target)
  - Create crawl failure monitoring and alerting logic
  - Write pipeline health check endpoints and status dashboards
  - Implement unit tests for monitoring metrics and alert conditions
  - _Requirements: SLO Targets, Observability_

## Testing and Quality Assurance

- [ ] 24. Create RAG evaluation test suite

  - Implement golden Q/A dataset management (10 per province × doc_class)
  - Write groundedness evaluation using exact-span matching in cited text
  - Create citation precision testing that validates relevance and completeness
  - Implement automated test execution with threshold validation (≥90% groundedness, ≥95% precision)
  - _Requirements: 4.1, 4.2, Evaluator Gold Sets_

- [ ] 25. Build refusal accuracy testing

  - Create test cases for each refusal scenario (no citation, stale citation, province mismatch, etc.)
  - Implement refusal accuracy measurement (≥99% target)
  - Write red-team test suite for prompt injection and cross-province leakage
  - Create automated refusal testing with comprehensive edge case coverage
  - _Requirements: 4.3, 4.4, Red-Team Testing_

- [ ] 26. Implement performance and load testing
  - Create k6 load testing scripts targeting p95 < 1000ms end-to-end latency
  - Write retriever-specific performance tests with p95 < 600ms target
  - Implement chaos testing for pod failures and network jitter scenarios
  - Create automated performance regression detection and alerting
  - _Requirements: SLO Targets, Load and Chaos Testing_

## Infrastructure and Deployment

- [ ] 27. Create Kubernetes deployment manifests

  - Write Helm charts for all microservices with configurable resource limits
  - Implement HPA (Horizontal Pod Autoscaler) configuration for auto-scaling
  - Create service mesh configuration for inter-service communication
  - Write deployment scripts and CI/CD pipeline integration
  - _Requirements: 5.1, 5.2, Cloud-Agnostic Architecture_

- [ ] 28. Implement observability and monitoring stack

  - Set up structured logging with JSON format and required fields
  - Create Prometheus metrics collection for all SLO targets
  - Implement Grafana dashboards for real-time monitoring and alerting
  - Write log aggregation and search functionality for debugging
  - _Requirements: Observability, Structured Logging, Required Metrics_

- [ ] 29. Build security and compliance features
  - Implement CMEK (Customer-Managed Encryption Keys) with Google Cloud KMS
  - Create VPC Service Controls configuration to prevent data exfiltration
  - Write Binary Authorization policies for signed container images only
  - Implement Secret Manager integration with GKE Workload Identity
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

## Integration and End-to-End Testing

- [ ] 30. Create end-to-end integration tests

  - Write complete user journey tests from query submission to pack generation
  - Implement cross-service integration testing with real NeMo services
  - Create data pipeline integration tests with sample official documents
  - Write automated acceptance tests that validate all requirements
  - _Requirements: All requirements integration_

- [ ] 31. Build committee approval and enablement workflow

  - Implement province enablement feature flags with committee approval tracking
  - Create evaluation threshold validation before province activation
  - Write spot-check workflow for Consulting Committee document review (10% sample)
  - Implement automated enablement criteria validation and reporting
  - _Requirements: 4.3, 2.5, Committee Ownership_

- [ ] 32. Create deployment and rollback procedures
  - Write blue-green deployment scripts for zero-downtime updates
  - Implement database migration procedures with rollback capabilities
  - Create disaster recovery procedures and backup validation
  - Write production readiness checklist and go-live procedures
  - _Requirements: Production deployment readiness_
