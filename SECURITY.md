# Security Policy

MCP-Sentry is an autonomous security, robustness, and fuzzing framework designed to stress-test Model Context Protocol (MCP) servers in sandboxed container environments. Because MCP-Sentry executes and probes potentially untrusted or vulnerable MCP server implementations, security is an architectural priority.

---

## Supported Versions

Only the latest release on the primary development branch is actively maintained and receives security updates.

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

---

## Architectural Security Model & Defense in Depth

MCP-Sentry enforces strict security boundaries to prevent target servers or untrusted input payloads from compromising the host system:

### 1. Isolated Docker Sandbox Execution
- **Container Isolation:** All target MCP servers run inside ephemeral, isolated Docker containers.
- **Resource Limits:** Hard caps are enforced on memory (e.g., `--memory=512m`) and CPU allocation to prevent Denial-of-Service (DoS) and runaway resource consumption on the host.
- **Auto-Removal & Clean Teardown:** Containers are launched with isolated networks where appropriate and cleaned up deterministically upon session completion or timeout.

### 2. Strict API Whitelisting & Input Validation
- **No Arbitrary Command Execution:** The FastAPI backend does not accept arbitrary shell commands, executable paths, or Docker parameters from API clients or the frontend.
- **Pre-Configured Target Registry:** The `POST /runs` endpoint strictly validates targets against the immutable internal `TARGET_CONFIGS` registry. Any unlisted target is rejected immediately with HTTP 400 Bad Request.

### 3. Concurrency & Race-Condition Controls
- **Single-Run Mutex:** An `asyncio.Lock` ensures that only one fuzzing session executes at any given time. Concurrent execution attempts are rejected with HTTP 409 Conflict to prevent container exhaustion and CPU saturation.

### 4. Leak Detection & Data Sanitization
- **Credential Leak Detection:** Output payloads from MCP tools are actively inspected against configured regex patterns (e.g., AWS access keys, database connection URIs, file system path leaks).
- **Log Sanitization:** Observer tail logs are truncated and sanitized to prevent terminal control injection or excessive log storage.

---

## Reporting a Vulnerability

We appreciate the security community's efforts in identifying and reporting vulnerabilities responsibly.

If you believe you have discovered a security vulnerability in MCP-Sentry:

1. **Do NOT open a public GitHub issue.**
2. Report the vulnerability privately via **GitHub Security Advisories** on the repository or email the maintainer directly at:
   - **Email:** `kennunes77@gmail.com`
3. Please include the following details in your report:
   - Description of the vulnerability and attack vector.
   - Proof of Concept (PoC) code or reproducible steps.
   - Potential impact (e.g., container breakout, host denial of service, privilege escalation).
   - Any suggested mitigations or fixes.

### Response Timeline
- **Initial Acknowledgment:** Within 48 hours of report receipt.
- **Assessment & Triage:** Within 5 business days, confirming whether the issue is accepted and its severity rating.
- **Fix & Advisory Release:** A coordinated security release and public advisory will be published once a fix is verified.

---

## Scope & Safe Harbor

### In Scope
- Vulnerabilities allowing container escape or host execution.
- Bypass of the target whitelisting mechanism leading to arbitrary command execution.
- Authentication/authorization bypasses (when auth layers are enabled).
- Unhandled crashes in MCP-Sentry core that leave orphan zombie containers or unreleased locks permanently locking the host.

### Out of Scope
- Intended fuzzing crashes in target test servers (e.g., `FragileTarget` crashing by design under invalid input).
- Attacks requiring root / administrative access on the host machine running Docker daemon.
- Social engineering attacks against maintainers or contributors.
