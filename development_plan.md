# Comprehensive Development Plan

This document outlines a phased approach to enhancing the document retrieval system while adhering to all safety and stability guidelines.

## Phase 1: Safe Enhancements (1 week)

This phase focuses on implementing immediate, low-risk improvements to the query building and scoring mechanisms.

### 1.1. Enhanced Query Building

-   **Objective:** Improve the relevance of search results by adding intent-specific keywords to the search query.
-   **File to Modify:** `services/online/query_online.py`
-   **Function to Create:** `_build_enhanced_query_text(payload: Query) -> str`
-   **Implementation:**
    -   Create a new function, `_build_enhanced_query_text`, that incorporates the logic from the "Safe Enhancement Example" in the development instructions.
    -   This function will add keywords like "规定," "办法," and "运输" to the query based on the user's question.
    -   The original `_build_query_text` function will be preserved to maintain backward compatibility.

### 1.2. Enhanced Scoring

-   **Objective:** Improve the accuracy of document ranking by introducing an intent-aware scoring algorithm.
-   **File to Modify:** `services/online/query_online.py`
-   **Function to Create:** `enhanced_score(doc_text: str, q: Query) -> float`
-   **Implementation:**
    -   Create a new function, `enhanced_score`, that implements the logic from the "Safe Enhancement Example."
    -   This function will boost the scores of regulatory documents and penalize procurement documents when the user's intent is regulatory.
    -   It will also incorporate weight-specific scoring to handle queries that specify a particular weight (e.g., "5吨煤炭").

### 1.3. Integration and Testing

-   **Objective:** Integrate the new functions into the main query processing loop and ensure that all changes are safe and effective.
-   **File to Modify:** `services/online/query_online.py`
-   **Implementation:**
    -   Modify the `query_online` function to use the new `_build_enhanced_query_text` and `enhanced_score` functions.
    -   The results will be sorted by the new, more accurate score.
    -   Comprehensive unit and integration tests will be developed in a separate `test_enhancements.py` file to verify that the changes work as expected and do not break the existing system.

## Phase 2: Comprehensive Logging (1 week)

This phase focuses on introducing a structured logging framework to improve the observability and maintainability of the system.

### 2.1. Structured Logging

-   **Objective:** Implement a JSON-based logging format to make logs easier to parse, search, and analyze.
-   **Files to Modify:** `services/gateway/api.py`, `services/online/query_online.py`
-   **Implementation:**
    -   Configure the logging module to output logs in a structured JSON format.
    -   Each log entry will include a timestamp, log level, message, and relevant context (e.g., query parameters, function name).

### 2.2. Key Metrics Logging

-   **Objective:** Log key performance indicators (KPIs) to monitor the health and performance of the system.
-   **File to Modify:** `services/online/query_online.py`
-   **Implementation:**
    -   Log the response time for each query.
    -   Log the scores assigned to each document.
    -   Log any errors that occur during the query processing pipeline.

## Phase 3: Future-Proofing (1 week)

This phase focuses on preparing the codebase for a future transition to a more advanced architecture, such as the Vector Search model.

### 3.1. Feature Flagging

-   **Objective:** Introduce a feature-flagging mechanism to allow for the safe and gradual rollout of new features.
-   **File to Modify:** `services/gateway/api.py`
-   **Implementation:**
    -   Implement a simple feature-flagging system using environment variables.
    -   This will allow us to enable or disable the enhanced query building and scoring features without redeploying the application.

### 3.2. Code Refactoring

-   **Objective:** Refactor the `query_online` function to make it more modular and easier to maintain.
-   **File to Modify:** `services/online/query_online.py`
-   **Implementation:**
    -   Break down the `query_online` function into smaller, more manageable functions.
    -   This will make the code easier to read, test, and modify in the future.

This phased approach will allow us to deliver significant improvements to the document retrieval system while minimizing risk and ensuring the continued stability of the production environment.