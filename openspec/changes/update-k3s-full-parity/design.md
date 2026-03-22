## Context

The K3s local development setup was created to test the Strangler Pattern migration from monolith to microservices. Since then, docker-compose has evolved with several new services that K8s manifests don't include. This change brings K3s to full parity with docker-compose.

## Goals / Non-Goals

**Goals:**
- Full service parity between `deploy-local.sh` and `run_locally_k3s.sh`
- VPS-ready deployment (ANTHROPIC_API_KEY from environment)
- Database migrations run automatically
- All health endpoints accessible

**Non-Goals:**
- Production hardening (HA replicas, autoscaling, network policies)
- External secrets management (Vault, Sealed Secrets)
- Helm chart update (known tech debt)
- CI/CD pipeline integration

## Decisions

### Decision 1: MinIO as K8s Pod
- **What**: Deploy MinIO as a Deployment with PVC in irc-app namespace
- **Why**: Full parity with docker-compose, works offline, enables media upload testing
- **Alternatives**: External S3 (requires internet, breaks offline dev)

### Decision 2: Migration Jobs vs Init Containers
- **What**: Use Kubernetes Jobs for database migrations
- **Why**: Jobs can be re-run independently, easier debugging, clear completion status
- **Alternatives**: Init containers (auto-run but harder to debug failures)

### Decision 3: ANTHROPIC_API_KEY Injection
- **What**: Script reads from environment variable and patches K8s secret
- **Why**: User runs on VPS with API key set, matches existing workflow
- **Alternatives**: Manual kubectl (error-prone), file-based (like docker-compose secrets)

### Decision 4: NGINX Ingress for All Routes
- **What**: Extend existing NGINX ingress with /adk/*, /media/*, /minio/* routes
- **Why**: Consistent with existing K3s setup, NGINX handles path rewriting
- **Alternatives**: Deploy Caddy in K8s (adds complexity, duplicates routing)

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| MinIO PVC data loss on node failure | Document backup procedure, use emptyDir for local dev |
| Migration job failure blocks deployment | Add retry logic, clear error messages |
| ANTHROPIC_API_KEY exposed in secret | Document secure secret management for production |
| local vLLM `host.docker.internal` won't work in K3s | Add hostAliases or document skip for VPS |

## Migration Plan

1. Create new manifests (non-breaking, additive)
2. Update configmap with new env vars (backward compatible)
3. Update scripts (run new script versions on VPS)
4. Test on local K3s first (optional)
5. Test on VPS with ANTHROPIC_API_KEY set
6. Rollback: Previous manifests still work, just missing new services

## Open Questions

1. Should we add a "minimal mode" flag to skip optional services (audit-logger, adk)?
2. Should MinIO data persist across `k3s-uninstall.sh`?
3. Is the Helm chart worth updating or should we deprecate it?
