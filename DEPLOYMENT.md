# Deployment Guide

This guide covers deploying the Context-Aware AI System using Docker (local development) and Kubernetes (production).

---

## Docker Deployment (Local Development)

### Prerequisites

- Docker 20.10+ and Docker Compose 2.0+
- Git repository you want to analyze
- (Optional) OpenAI API key for multimodal features

### Quick Start

```bash
# 1. Clone or navigate to the project
cd luminescent-cluster

# 2. Set environment variables (optional)
export REPO_PATH=/path/to/your/git/repo
export OPENAI_API_KEY=your-key-here

# 3. Build and start services
docker-compose up -d

# 4. View logs
docker-compose logs -f

# 5. Check status
docker-compose ps
```

### Configuration

Create a `.env` file in the project root:

```bash
# Path to your git repository
REPO_PATH=./

# OpenAI API key (optional, for meeting transcription)
OPENAI_API_KEY=sk-...
```

### Docker Compose Services

**session-memory**:
- Fast git context access
- Mounts your repository read-only
- Resource limits: 512MB RAM, 0.5 CPU

**pixeltable-memory**:
- Persistent knowledge base
- Volume: `pixeltable-data` (survives restarts)
- Resource limits: 4GB RAM, 2 CPU

### Common Commands

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f session-memory
docker-compose logs -f pixeltable-memory

# Restart a service
docker-compose restart session-memory

# Stop all services
docker-compose down

# Stop and remove volumes (⚠️ deletes data)
docker-compose down -v

# Execute commands in container
docker-compose exec pixeltable-memory python pixeltable_setup.py
```

### Volume Management

**Backup Pixeltable data:**
```bash
docker run --rm \
  -v luminescent-cluster_pixeltable-data:/data \
  -v $(pwd)/backups:/backups \
  alpine tar czf /backups/pixeltable-$(date +%Y%m%d).tar.gz /data
```

**Restore Pixeltable data:**
```bash
docker run --rm \
  -v luminescent-cluster_pixeltable-data:/data \
  -v $(pwd)/backups:/backups \
  alpine tar xzf /backups/pixeltable-20241125.tar.gz -C /
```

### Troubleshooting

**Containers won't start:**
```bash
# Check logs
docker-compose logs

# Rebuild without cache
docker-compose build --no-cache

# Check resource usage
docker stats
```

**Permission errors:**
```bash
# Ensure volumes have correct permissions
docker-compose down
docker volume rm luminescent-cluster_pixeltable-data
docker-compose up -d
```

---

## Kubernetes Deployment (Production)

### Prerequisites

- Kubernetes 1.24+ cluster (EKS, GKE, AKS, or self-hosted)
- `kubectl` configured to access your cluster
- Container registry (Docker Hub, ECR, GCR, etc.)
- Persistent storage provider (EBS, GCE PD, etc.)

### Architecture

```
┌─────────────────────────────────────┐
│      Kubernetes Cluster             │
│                                     │
│  ┌───────────────────────────────┐ │
│  │  Namespace: context-aware-ai  │ │
│  │                               │ │
│  │  ┌─────────────────────────┐  │ │
│  │  │ session-memory          │  │ │
│  │  │ - Deployment (1 pod)    │  │ │
│  │  │ - PVC: git-repos (RO)   │  │ │
│  │  └─────────────────────────┘  │ │
│  │                               │ │
│  │  ┌─────────────────────────┐  │ │
│  │  │ pixeltable-memory       │  │ │
│  │  │ - Deployment (1 pod)    │  │ │
│  │  │ - PVC: pixeltable-data  │  │ │
│  │  │ - Secret: openai-key    │  │ │
│  │  └─────────────────────────┘  │ │
│  └───────────────────────────────┘ │
└─────────────────────────────────────┘
```

### Step 1: Build and Push Images

```bash
# Build images
docker build -f Dockerfile.session-memory -t your-registry/session-memory:1.0.0 .
docker build -f Dockerfile.pixeltable -t your-registry/pixeltable-memory:1.0.0 .

# Push to registry
docker push your-registry/session-memory:1.0.0
docker push your-registry/pixeltable-memory:1.0.0

# Update deployment YAMLs with your image names
sed -i 's|context-aware-ai/session-memory:latest|your-registry/session-memory:1.0.0|g' \
  k8s/deployment-session-memory.yaml

sed -i 's|context-aware-ai/pixeltable-memory:latest|your-registry/pixeltable-memory:1.0.0|g' \
  k8s/deployment-pixeltable.yaml
```

### Step 2: Configure Secrets

```bash
# Create OpenAI API key secret
export OPENAI_API_KEY=sk-your-key-here

kubectl create secret generic openai-api-key \
  --from-literal=OPENAI_API_KEY=$OPENAI_API_KEY \
  -n context-aware-ai
```

### Step 3: Deploy

```bash
# Option A: Use deployment script
cd k8s
./deploy.sh

# Option B: Manual deployment
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmaps.yaml
kubectl apply -f k8s/persistent-volumes.yaml
kubectl apply -f k8s/deployment-session-memory.yaml
kubectl apply -f k8s/deployment-pixeltable.yaml
kubectl apply -f k8s/services.yaml
```

### Step 4: Verify Deployment

```bash
# Check namespace
kubectl get all -n context-aware-ai

# Check pods
kubectl get pods -n context-aware-ai -w

# Check logs
kubectl logs -f deployment/session-memory -n context-aware-ai
kubectl logs -f deployment/pixeltable-memory -n context-aware-ai

# Check persistent volumes
kubectl get pvc -n context-aware-ai
```

### Resource Configuration

**Session Memory:**
- Requests: 256MB RAM, 0.1 CPU
- Limits: 512MB RAM, 0.5 CPU
- Storage: 10GB (git repos)

**Pixeltable Memory:**
- Requests: 2GB RAM, 0.5 CPU
- Limits: 4GB RAM, 2 CPU
- Storage: 20GB (knowledge base)

**Adjust in deployment YAMLs as needed for your workload.**

### Storage Classes

By default, PVCs use the default storage class. To specify:

```yaml
# k8s/persistent-volumes.yaml
spec:
  storageClassName: fast-ssd  # or 'gp3', 'pd-ssd', etc.
```

### High Availability (Optional)

MCP servers are typically single-instance, but you can add redundancy:

```yaml
# k8s/deployment-pixeltable.yaml
spec:
  replicas: 2  # Multiple replicas
  
  # Add anti-affinity to spread across nodes
  affinity:
    podAntiAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
      - labelSelector:
          matchLabels:
            app.kubernetes.io/name: pixeltable-memory
        topologyKey: kubernetes.io/hostname
```

### Ingress (Optional)

If you need external access (not typical for MCP servers):

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mcp-ingress
  namespace: context-aware-ai
spec:
  rules:
  - host: mcp.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: pixeltable-memory
            port:
              number: 8080
```

### Monitoring

**Prometheus ServiceMonitor:**

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: mcp-servers
  namespace: context-aware-ai
spec:
  selector:
    matchLabels:
      app.kubernetes.io/component: mcp-server
  endpoints:
  - port: metrics
    interval: 30s
```

### Backup Strategy

**Automated Pixeltable backups:**

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: pixeltable-backup
  namespace: context-aware-ai
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: alpine:latest
            command:
            - /bin/sh
            - -c
            - tar czf /backups/pixeltable-$(date +\%Y\%m\%d).tar.gz /data
            volumeMounts:
            - name: data
              mountPath: /data
            - name: backups
              mountPath: /backups
          volumes:
          - name: data
            persistentVolumeClaim:
              claimName: pixeltable-data
          - name: backups
            persistentVolumeClaim:
              claimName: backup-storage
          restartPolicy: OnFailure
```

### Scaling Considerations

**Vertical Scaling** (increase resources):
```bash
kubectl patch deployment pixeltable-memory -n context-aware-ai \
  --patch '{"spec":{"template":{"spec":{"containers":[{"name":"pixeltable-memory","resources":{"requests":{"memory":"4Gi"},"limits":{"memory":"8Gi"}}}]}}}}'
```

**Horizontal Scaling** (not recommended for MCP):
- MCP servers maintain state via stdio
- Multiple instances may conflict
- Use vertical scaling instead

### Updates and Rollbacks

```bash
# Update image
kubectl set image deployment/pixeltable-memory \
  pixeltable-memory=your-registry/pixeltable-memory:1.1.0 \
  -n context-aware-ai

# Check rollout status
kubectl rollout status deployment/pixeltable-memory -n context-aware-ai

# Rollback if needed
kubectl rollout undo deployment/pixeltable-memory -n context-aware-ai

# View rollout history
kubectl rollout history deployment/pixeltable-memory -n context-aware-ai
```

### Cleanup

```bash
# Delete all resources
kubectl delete namespace context-aware-ai

# Or use individual manifests
kubectl delete -f k8s/
```

---

## Connecting Claude Code

### Docker Setup

Update your Claude MCP configuration:

```json
{
  "mcpServers": {
    "session-memory": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "session-memory-mcp",
        "python",
        "session_memory_server.py"
      ]
    },
    "pixeltable-memory": {
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "pixeltable-memory-mcp",
        "python",
        "pixeltable_mcp_server.py"
      ]
    }
  }
}
```

### Kubernetes Setup

Port-forward to access from local machine:

```bash
# In separate terminals
kubectl port-forward -n context-aware-ai deployment/session-memory 8081:8080
kubectl port-forward -n context-aware-ai deployment/pixeltable-memory 8082:8080
```

Then configure Claude Code to connect via localhost:8081 and localhost:8082.

---

## Production Checklist

- [ ] Images built and pushed to registry
- [ ] Secrets created (OpenAI API key)
- [ ] Storage classes configured
- [ ] Resource limits appropriate for workload
- [ ] PVCs sized correctly
- [ ] Health checks tested
- [ ] Backup strategy in place
- [ ] Monitoring configured
- [ ] Logs aggregated (ELK, CloudWatch, etc.)
- [ ] Claude Code MCP configuration updated
- [ ] Team access documented

---

## Cost Optimization

**Docker:**
- Use multi-stage builds ✅ (already implemented)
- Minimize image layers ✅ (already implemented)
- Use Alpine base images (consider for smaller size)

**Kubernetes:**
- Right-size resource requests/limits
- Use spot/preemptible instances for non-critical workloads
- Enable cluster autoscaling
- Use storage classes with lower IOPS for cold data
- Consider managed Pixeltable service if available

**OpenAI API:**
- Monitor embedding generation costs
- Use local sentence-transformers (free) ✅ (default)
- Enable summarization only when needed
- Cache results aggressively

---

## Support

For issues:
1. Check logs: `kubectl logs -f deployment/<name> -n context-aware-ai`
2. Verify resources: `kubectl describe pod <pod-name> -n context-aware-ai`
3. Check events: `kubectl get events -n context-aware-ai`
4. Review documentation in `README.md`
