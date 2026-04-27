# 🧪 CommitGuard — Test Projects & Penetration Testing Targets

This document serves as a catalog of vulnerable applications and datasets used to benchmark, train, and penetration-test the CommitGuard agent. These projects provide the ground-truth "exploit targets" required to verify the agent's detection accuracy across various CWE categories.

---

## Tier 1 — Purpose-Built Vulnerable Python Apps
*Best for: Controlled training, unit testing, and reward model validation.*

These projects are intentionally designed with security loopholes, making them ideal for verifying that CommitGuard’s reward model correctly identifies specific CWEs.

### 1. Checkmarx c{api}tal
- **GitHub:** [Checkmarx/capital](https://github.com/Checkmarx/capital)
- **Tech Stack:** FastAPI, Pydantic, Alembic, React.
- **Vulnerabilities:** 10 challenges mapping to OWASP Top 10 API risks.
- **CWEs Covered:** Broken Object Level Auth (BOLA), Mass Assignment, Broken Authentication, SSRF.
- **CommitGuard Fit:** Matches the modern Python backend stack (FastAPI + Pydantic) that the agent is optimized to audit.

### 2. vulnpy by Contrast Security
- **GitHub:** [Contrast-Security-OSS/vulnpy](https://github.com/Contrast-Security-OSS/vulnpy)
- **Tech Stack:** FastAPI, Flask, Django support.
- **Vulnerabilities:** Purposely-vulnerable functions that can be mounted as routes.
- **CWEs Covered:** SQLi, Path Traversal, Command Injection, XSS, SSRF, Deserialization.
- **CommitGuard Fit:** Isolated, clean diff-level code units—perfect for the granularity of the RL environment.

### 3. OWASP BenchmarkPython
- **GitHub:** [OWASP-Benchmark/BenchmarkPython](https://github.com/OWASP-Benchmark/BenchmarkPython)
- **Purpose:** Verifying SAST/DAST/IAST accuracy.
- **CommitGuard Fit:** Provides a standardized scorecard to measure CommitGuard's accuracy against established tools like Bandit or ZAP.

### 4. python-insecure-app by trottomv
- **GitHub:** [trottomv/python-insecure-app](https://github.com/trottomv/python-insecure-app)
- **CWEs Covered:** CWE-798 (Hardcoded Credentials), CWE-94 (SSTI/Code Injection), CWE-937 (Vulnerable Dependencies).
- **CommitGuard Fit:** Demonstrates "shift-left" security by targeting insecure dependencies and secrets in FastAPI.

### 5. Intentionally-Vulnerable-Python-Application
- **GitHub:** [mukxl/Intentionally-Vulnerable-Python-Application](https://github.com/mukxl/Intentionally-Vulnerable-Python-Application)
- **Purpose:** Designed for SCA, SAST, and DAST analysis.
- **CommitGuard Fit:** Excellent regression test target to confirm the agent catches what conventional scanners catch—and identifies what they miss.

### 6. Vulnerable-API by michealkeines
- **GitHub:** [michealkeines/Vulnerable-API](https://github.com/michealkeines/Vulnerable-API)
- **Tech Stack:** Flask, Jinja, SQLite3.
- **CWEs Covered:** CWE-89 (SQLi), CWE-79 (XSS), CWE-73 (LFI/RFI), CWE-94 (SSTI).
- **CommitGuard Fit:** Specifically designed to test automated API scanners with injection-heavy payloads.

---

## Tier 2 — Real-World Projects with Known CVEs
*Best for: Advanced agent training and "In-the-Wild" performance testing.*

These production-grade projects provide non-synthetic, complex commit diffs derived from the National Vulnerability Database (NVD).

| Project | Stack | CWE / Vulnerability Type | Relevance |
| :--- | :--- | :--- | :--- |
| **Django** | Django + ORM | SQL Injection (CWE-89), Open Redirect (CWE-601), ReDoS (CWE-400) | High-signal real-world diffs |
| **Pillow** | Python Imaging | Buffer overflows, Path Traversal, ACE | Tests non-web CWE detection |
| **Requests** | Python HTTP | SSRF, Header Injection | Header-level vuln detection |
| **Paramiko** | SSH/Crypto | Auth bypass (CVE-2018-7750), Weak crypto | Crypto CWE training data |
| **PyYAML** | Config Parsing | Deserialization ACE (CWE-502) | Classic commit-diff CWE |

**Recommended Dataset:** [CVEFixes (ZeoVan/CVEfixes)](https://github.com/ZeoVan/CVEfixes)
A multi-language dataset providing the exact fixing commits for vulnerabilities, annotated at function and file levels. Directly usable for CommitGuard's diff-based pipeline.

---

## Tier 3 — Pydantic & Type-Safety Specific Targets
*Best for: Specialized auditing of type-driven Python applications.*

1. **Pydantic v1 Model Misuse Patterns:** Common vulnerabilities involving `model.dict()`, validator skipping, or internal field exposure. The **Checkmarx c{api}tal** project is the primary reference for this.
2. **Type-Safety "Escape Hatches":** Targets projects with complex type annotations, union types, and `Any` usage where type-safety bugs often hide. 
   - **Targets:** Django REST Framework and FastAPI projects with permissive `Optional` fields or loose Pydantic validation.

---

## 📈 Benchmarking Strategy
To verify CommitGuard's performance on these projects:
1. **Extraction:** Use `scratch/extract_sample.py` to pull vulnerable diffs from the projects above.
2. **Evaluation:** Run `scripts/evaluate.py` using these samples as the test set.
3. **Comparison:** Compare results against the `eval_baseline.json` to visualize the delta in detection capabilities.
