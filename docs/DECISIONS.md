# Architecture Decision Records (ADRs)

This document tracks the high-level technical, architectural, and AI-specific decisions made while building OpsPilot. It follows the standard ADR format to explain *why* the system is built the way it is, highlighting the trade-offs considered during development.

---

## ADR-001: Database Selection (PostgreSQL + pgvector)
**Status:** Accepted  
**Context:** The RAG pipeline requires a vector database to store and search document embeddings. We evaluated dedicated SaaS vector databases (Pinecone, Milvus) versus extending our primary relational database.  
**Decision:** We chose to use PostgreSQL with the `pgvector` extension.  
**Consequences:**  
- ✅ **Pros:** Operational simplicity (one database to manage and backup), ACID compliance, and seamless joining of vector similarity scores with relational metadata (e.g., `org_id` for strict multi-tenant isolation). Significantly more cost-effective than SaaS vector DBs.  
- ❌ **Cons:** May not scale to billions of vectors as efficiently as a dedicated, distributed vector database. However, it is more than sufficient for enterprise knowledge bases and keeps the MVP architecture lean.

---

## ADR-002: Backend Framework (FastAPI + Async SQLAlchemy)
**Status:** Accepted  
**Context:** OpsPilot is an I/O-heavy application that frequently calls AI models, queries vector databases, and hits external APIs. A synchronous framework would create severe bottlenecks.  
**Decision:** We selected FastAPI coupled with SQLAlchemy 2.0 (asyncio).  
**Consequences:**  
- ✅ **Pros:** Native async support provides vastly superior throughput. FastAPI offers excellent Pydantic validation and automatic OpenAPI documentation. SQLAlchemy 2.0 ensures strict type safety across all database interactions.  
- ❌ **Cons:** Async Python introduces complexity (e.g., managing event loops, avoiding blocking calls) and has a steeper learning curve than synchronous frameworks like Django.

---

## ADR-003: Frontend State Management (Zustand over Redux)
**Status:** Accepted  
**Context:** The frontend requires global state management for authentication tokens and user profiles, but traditional solutions introduce heavy boilerplate.  
**Decision:** We opted for Zustand instead of Redux.  
**Consequences:**  
- ✅ **Pros:** Zustand provides a simple, hook-based API that drastically reduces boilerplate. It handles our auth state perfectly without needing complex reducers or actions.  
- ❌ **Cons:** Lacks the massive middleware ecosystem and strict unidirectional data flow enforcement of Redux, though this is unnecessary for our application's scale.

---

## ADR-004: Styling (Tailwind CSS over Component Libraries)
**Status:** Accepted  
**Context:** OpsPilot requires a highly specific, premium "dark-mode glassmorphism" aesthetic. Traditional component libraries (MUI, AntD) are notoriously difficult to override for deeply custom designs.  
**Decision:** We built a custom design system using Tailwind CSS.  
**Consequences:**  
- ✅ **Pros:** Allows rapid iteration on utility classes, zero visual bloat, and complete control over micro-animations and glowing borders.  
- ❌ **Cons:** Results in verbose HTML and requires us to manually build and maintain our own reusable component library (e.g., `Button`, `Card`) rather than importing pre-built ones.

---

## ADR-005: Phased AI Implementation
**Status:** Accepted  
**Context:** Integrating LLMs on day one introduces massive complexity, latency, and unpredictability, which can stall core product development.  
**Decision:** We structured the project to build the traditional SaaS foundation (Auth, Tickets, UI, RBAC) first, mocking the AI components in early phases.  
**Consequences:**  
- ✅ **Pros:** Ensures the core application is robust, secure, and fully operational before AI integration. Frontend developers are never blocked by prompt engineering or API rate limits.  
- ❌ **Cons:** Delays the integration of "real" AI behavior, requiring strict interface mocking to ensure the transition to real LLMs is seamless later.

---

## ADR-006: AI Agent Orchestration (LangGraph over Sequential Chains)
**Status:** Accepted  
**Context:** Incident investigation requires conditional branching, retries, and persistent state (e.g., if RAG retrieval yields low confidence, the agent must loop and refine the query). Sequential LangChain chains cannot handle this.  
**Decision:** We adopted LangGraph to model the AI agent as a state machine.  
**Consequences:**  
- ✅ **Pros:** Provides explicit control flow, cyclical execution (loops for self-correction), persistent state across nodes, and highly observable execution traces.  
- ❌ **Cons:** Requires significantly more boilerplate code and a steeper learning curve compared to simple `chain.invoke()` patterns.

---

## ADR-007: AI Governance (Policy Engine + HITL over Direct Tool Execution)
**Status:** Accepted  
**Context:** Allowing an LLM to directly execute infrastructure tools (e.g., "restart production server") is a severe security and reliability risk due to hallucinations and prompt injection.  
**Decision:** The AI agent is strictly advisory. It outputs a `proposed_action`. A deterministic, rule-based Policy Engine intercepts this, assigns an authoritative risk level, and enforces Human-in-the-Loop (HITL) approval for MEDIUM/HIGH risk actions.  
**Consequences:**  
- ✅ **Pros:** Prevents catastrophic autonomous actions, provides a clear audit trail, and aligns with enterprise security compliance (SOC2).  
- ❌ **Cons:** Adds latency to the workflow and requires building a custom approval state machine rather than relying on out-of-the-box agent frameworks.

---

## ADR-008: AI Evaluation (Rule-Based over "LLM-as-a-Judge")
**Status:** Accepted  
**Context:** Measuring AI quality (groundedness, retrieval relevance) is critical. A common pattern is to use a second, powerful LLM to "judge" the first LLM's output.  
**Decision:** We implemented a deterministic, rule-based Evaluation Engine. For example, groundedness is measured by structurally comparing the `chunk_id`s cited in the AI's output against the actual `chunk_id`s returned by the RAG retriever.  
**Consequences:**  
- ✅ **Pros:** Zero additional LLM API costs, deterministic and reproducible results, no compounding hallucinations, and instant execution.  
- ❌ **Cons:** Cannot evaluate nuanced semantic correctness as well as a human or a highly tuned LLM judge. It strictly measures structural fidelity and evidence coverage.

---

## ADR-009: Multi-Tenant Isolation (Shared Schema with Application-Level Filtering)
**Status:** Accepted  
**Context:** OpsPilot is designed as a multi-tenant SaaS. We needed to ensure Organization A can never access Organization B's data. Options included database-per-tenant and schema-per-tenant.  
**Decision:** We chose a shared database, shared schema approach, enforcing isolation strictly at the application query layer. Every query explicitly includes `.where(Model.org_id == current_user.org_id)`.  
**Consequences:**  
- ✅ **Pros:** Simplest to deploy and maintain, easy to run global analytics, and avoids the complexity of multi-schema migrations.  
- ❌ **Cons:** Relies entirely on developer discipline. A single missing `org_id` filter in a new endpoint could cause a data leak. Mitigated by strict integration tests for cross-org prevention.

---

## ADR-010: Production Deployment (Multi-Stage Docker with Gunicorn + Nginx)
**Status:** Accepted  
**Context:** Initial development used `uvicorn main:app --reload` and the Vite development server. These are insecure and inefficient for production traffic.  
**Decision:** The production `Dockerfile` uses a multi-stage build. The backend runs via `gunicorn` with async `uvicorn` workers. The frontend is compiled to static assets and served via a minimal Nginx container. Containers run as non-root users.  
**Consequences:**  
- ✅ **Pros:** Production-grade performance, security hardening, and readiness for deployment to AWS ECS/Fargate or Kubernetes.  
- ❌ **Cons:** Slightly more complex Docker configuration and longer build times compared to dev environments.

---

## ADR-011: Observability (Structured JSON Logging with Distributed Request IDs)
**Status:** Accepted  
**Context:** Debugging an AI agent that spans RAG retrieval, LLM calls,