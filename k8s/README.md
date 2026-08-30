# GUSIP Kubernetes — production resource pack

City / state **intelligence** cluster (events, GIS, watchlist, evidence).  
Not the 80k-camera GPU farm — that is `gpu-worker.yaml` on regional nodes.

```bash
# Provision `gusip-secrets` through OpenBao + External Secrets first.
# The repository deliberately contains no deployable Secret values.
kubectl apply -k k8s/
# GPU farm (NVIDIA device plugin required)
kubectl apply -f k8s/gpu-worker.yaml
```

## Requests (scheduled) vs limits (capped)

| Workload | Replicas | CPU req → lim | Memory req → lim | Disk | Scale |
|---|---|---|---|---|---|
| **backend** | 3 | 500m → 2 | 512Mi → 2Gi | — | HPA 3–24 |
| **frontend** | 3 | 100m → 500m | 64Mi → 256Mi | — | HPA 3–12 |
| **worker** (CPU YOLO/ANPR) | 3 | 2 → 4 | 4Gi → 8Gi | — | HPA 3–20 |
| **worker-gpu** | 2 | 4 → 8 + 1 GPU | 8Gi → 16Gi | — | HPA 2–32 |
| **postgres** | 1 StatefulSet | 2 → 4 | 4Gi → 16Gi | 200Gi | PDB min=1 |
| **redis** | 1 StatefulSet | 500m → 2 | 1Gi → 4Gi | 20Gi | AOF, 3Gi maxmemory |
| **minio** | 1 StatefulSet | 1 → 4 | 2Gi → 8Gi | 500Gi | S3 evidence |

Namespace **ResourceQuota**: 48 CPU / 96Gi request, 96 CPU / 192Gi limit, 2Ti PVC, 80 pods.

Idle floor (all min replicas, no GPU overlay): **~14 CPU, ~22Gi RAM, 720Gi disk**.

## 80k-camera path (regional, not this YAML)

See `docs/scalability.md`: ~400–800 GPU workers, 12–24 API pods, Kafka RF=3. Add GPU nodes and raise `worker-gpu` HPA `maxReplicas`; keep this namespace for the intelligence plane.

## Must change before real prod

1. Create `gusip-secrets` with External Secrets/OpenBao. Required keys are `SECRET_KEY`, `ENCRYPTION_KEY`, `POSTGRES_PASSWORD`, `DATABASE_URL`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `ADAPTER_KEYS_JSON`, and `OIDC_CLIENT_SECRET`. Every adapter key must be unique and at least 32 characters.
2. Ingress host `gusip.example.in` + cert-manager issuer.
3. Set `MINIO_ENDPOINT` to a TLS S3/Object-Lock service and `MINIO_SECURE=true`. The production guard intentionally refuses the bundled cleartext MinIO settings.
4. Images `gusip-backend:prod` / `gusip-frontend:prod` from your registry.
5. Apply the migration Job before rolling application Deployments; production application startup never calls `create_all`.
