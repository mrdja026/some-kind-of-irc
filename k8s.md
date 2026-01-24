# K8s Architecture (Redis-Orchestrated)

This document describes the minimal Kubernetes deployment shape for the IRC chat system with Redis as the
coordination layer (Pub/Sub + small ephemeral state) and a relational database as the source of truth.
It follows the agreed design: frontend never talks to Redis; only backend/services do.

## Goals

- Scale backend pods horizontally without losing real-time chat.
- Keep durability in the database; Redis is best-effort fan-out and ephemeral state.
- Allow media uploads via a dedicated storage service.

## Components

1. Backend API (FastAPI + WebSocket)
2. Frontend (static Nginx)
3. Redis (Pub/Sub + cache/presence)
4. Postgres (durable data)
5. Media Storage Service (Flask)
6. MinIO (object storage)
7. Worker (optional, for long-running tasks)

## Data Flow (Chat)

1. Client sends message to Backend (HTTP).
2. Backend writes message to Postgres and gets `message_id`.
3. Backend publishes `{channel_id, message_id}` to Redis Pub/Sub.
4. Each backend pod with WS clients for that channel pushes the message.
5. Client reconnects -> Backend provides REST catch-up using last seen `message_id`.

## Data Flow (Uploads)

1. Client uploads to Storage Service (HTTP multipart).
2. Storage Service stores object in MinIO.
3. Storage Service writes metadata in Postgres.
4. Storage Service writes progress to Redis (`upload:{id}` hash, TTL).
5. Client polls Backend every ~4s for progress; Backend reads Redis.

## Redis Usage

- Pub/Sub channels:
  - `channel:{channel_id}` for global channels and DMs (DMs are just channels).
- Ephemeral state:
  - `presence:{user_id}` -> online/idle with TTL
  - `channel_members:{channel_id}` -> set of user_ids with TTL
  - `upload:{upload_id}` -> hash: `status`, `bytes`, `total`, `updated_at`

## Expected Guarantees

- Live delivery is best-effort (Redis Pub/Sub).
- Durability is guaranteed by Postgres.
- Client catch-up via REST on reconnect is required.

## Kubernetes Topology (Minimum)

Namespaces:
- `irc` (all workloads)

Deployments:
- `backend` (2+ replicas)
- `frontend` (1+ replicas)
- `storage` (1+ replicas)
- `worker` (0-1 replicas, optional)
- `redis` (1 replica for dev; use HA in prod)
- `postgres` (1 replica for dev; use managed/HA in prod)
- `minio` (1 replica for dev; use managed/HA in prod)

Services:
- `backend` (ClusterIP)
- `frontend` (ClusterIP)
- `storage` (ClusterIP)
- `redis` (ClusterIP)
- `postgres` (ClusterIP)
- `minio` (ClusterIP)

Ingress:
- `/` -> frontend
- `/api` -> backend
- `/ws` -> backend (WebSocket)
- `/media` -> storage

## Environment Variables (Key)

Backend:
- `DATABASE_URL=postgresql://...`
- `REDIS_URL=redis://redis:6379/0`
- `JWT_SECRET=...`

Storage:
- `MINIO_ENDPOINT=http://minio:9000`
- `MINIO_PUBLIC_ENDPOINT=http://minio:9000`
- `MINIO_BUCKET=media`
- `MINIO_ACCESS_KEY=...`
- `MINIO_SECRET_KEY=...`
- `BACKEND_VERIFY_URL=http://backend:8002/auth/me`
- `PUBLIC_BASE_URL=https://your-domain/media`
- `REDIS_URL=redis://redis:6379/0`

Frontend:
- `VITE_API_BASE_URL=https://your-domain/api`
- `VITE_WS_URL=wss://your-domain/ws`

## Notes / Future Upgrades

- If stronger delivery guarantees are required, replace Pub/Sub with Redis Streams or NATS JetStream.
- For multi-region or high scale, move Redis/Postgres/MinIO to managed services.

## Example Manifests (Minimal, Not Production-Ready)

These are intentionally small. Replace hardcoded values with Secrets and tune resources,
storage classes, and ingress rules for your cluster.

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: irc
```

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: irc
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          ports:
            - containerPort: 6379
```

```yaml
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: irc
spec:
  selector:
    app: redis
  ports:
    - name: redis
      port: 6379
      targetPort: 6379
```

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: irc
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
        - name: postgres
          image: postgres:16-alpine
          ports:
            - containerPort: 5432
          env:
            - name: POSTGRES_DB
              value: irc
            - name: POSTGRES_USER
              value: irc
            - name: POSTGRES_PASSWORD
              value: irc
```

```yaml
apiVersion: v1
kind: Service
metadata:
  name: postgres
  namespace: irc
spec:
  selector:
    app: postgres
  ports:
    - name: postgres
      port: 5432
      targetPort: 5432
```

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: minio
  namespace: irc
spec:
  replicas: 1
  selector:
    matchLabels:
      app: minio
  template:
    metadata:
      labels:
        app: minio
    spec:
      containers:
        - name: minio
          image: minio/minio:RELEASE.2024-10-13T13-34-11Z
          args: ["server", "/data", "--console-address", ":9001"]
          ports:
            - containerPort: 9000
            - containerPort: 9001
          env:
            - name: MINIO_ROOT_USER
              value: minio
            - name: MINIO_ROOT_PASSWORD
              value: minio123
```

```yaml
apiVersion: v1
kind: Service
metadata:
  name: minio
  namespace: irc
spec:
  selector:
    app: minio
  ports:
    - name: api
      port: 9000
      targetPort: 9000
    - name: console
      port: 9001
      targetPort: 9001
```

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  namespace: irc
spec:
  replicas: 2
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
        - name: backend
          image: your-registry/irc-backend:latest
          ports:
            - containerPort: 8002
          env:
            - name: DATABASE_URL
              value: postgresql://irc:irc@postgres:5432/irc
            - name: REDIS_URL
              value: redis://redis:6379/0
            - name: JWT_SECRET
              value: change-me
          readinessProbe:
            httpGet:
              path: /health
              port: 8002
            initialDelaySeconds: 5
            periodSeconds: 10
```

```yaml
apiVersion: v1
kind: Service
metadata:
  name: backend
  namespace: irc
spec:
  selector:
    app: backend
  ports:
    - name: http
      port: 8002
      targetPort: 8002
```

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: storage
  namespace: irc
spec:
  replicas: 1
  selector:
    matchLabels:
      app: storage
  template:
    metadata:
      labels:
        app: storage
    spec:
      containers:
        - name: storage
          image: your-registry/irc-storage:latest
          ports:
            - containerPort: 9101
          env:
            - name: MINIO_ENDPOINT
              value: http://minio:9000
            - name: MINIO_PUBLIC_ENDPOINT
              value: http://minio:9000
            - name: MINIO_BUCKET
              value: media
            - name: MINIO_ACCESS_KEY
              value: minio
            - name: MINIO_SECRET_KEY
              value: minio123
            - name: BACKEND_VERIFY_URL
              value: http://backend:8002/auth/me
            - name: PUBLIC_BASE_URL
              value: https://your-domain/media
            - name: REDIS_URL
              value: redis://redis:6379/0
```

```yaml
apiVersion: v1
kind: Service
metadata:
  name: storage
  namespace: irc
spec:
  selector:
    app: storage
  ports:
    - name: http
      port: 9101
      targetPort: 9101
```

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: irc
spec:
  replicas: 1
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
        - name: frontend
          image: your-registry/irc-frontend:latest
          ports:
            - containerPort: 80
```

```yaml
apiVersion: v1
kind: Service
metadata:
  name: frontend
  namespace: irc
spec:
  selector:
    app: frontend
  ports:
    - name: http
      port: 80
      targetPort: 80
```

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: irc-ingress
  namespace: irc
spec:
  rules:
    - host: your-domain
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: frontend
                port:
                  number: 80
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: backend
                port:
                  number: 8002
          - path: /ws
            pathType: Prefix
            backend:
              service:
                name: backend
                port:
                  number: 8002
          - path: /media
            pathType: Prefix
            backend:
              service:
                name: storage
                port:
                  number: 9101
```
