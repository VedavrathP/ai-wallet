# Deployment Guide

This guide covers deploying the Agent Wallet service to various cloud platforms.

## Quick Start: Railway (Recommended for Testing)

Railway offers a generous free tier and one-click PostgreSQL.

### 1. Prerequisites
- GitHub account
- Railway account (https://railway.app)

### 2. Deploy Steps

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Initialize project (from agent-wallet directory)
cd agent-wallet
railway init

# Add PostgreSQL database
railway add --database postgres

# Set environment variables
railway variables set DATABASE_URL='${{Postgres.DATABASE_URL}}'
railway variables set SECRET_KEY='your-secret-key-change-in-production'
railway variables set ENVIRONMENT='production'

# Deploy
railway up
```

### 3. Get Your URL
After deployment, Railway provides a URL like:
```
https://agent-wallet-production-xxxx.up.railway.app
```

### 4. Test It
```bash
# Check health
curl https://your-railway-url.up.railway.app/health

# Use the SDK
from agent_wallet import WalletClient
client = WalletClient(
    api_key="your_api_key",
    base_url="https://your-railway-url.up.railway.app"
)
```

---

## Production: AWS (ECS + RDS)

For production workloads with high availability.

### Architecture
```
Internet → ALB → ECS Fargate → RDS PostgreSQL
                     ↓
              CloudWatch Logs
```

### 1. Create RDS PostgreSQL
```bash
aws rds create-db-instance \
  --db-instance-identifier agent-wallet-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --master-username postgres \
  --master-user-password <secure-password> \
  --allocated-storage 20
```

### 2. Build and Push Docker Image
```bash
# Create ECR repository
aws ecr create-repository --repository-name agent-wallet

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build and push
docker build -t agent-wallet -f service/Dockerfile .
docker tag agent-wallet:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/agent-wallet:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/agent-wallet:latest
```

### 3. Create ECS Task Definition
```json
{
  "family": "agent-wallet",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "containerDefinitions": [
    {
      "name": "agent-wallet",
      "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/agent-wallet:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "DATABASE_URL", "value": "postgresql://..."},
        {"name": "ENVIRONMENT", "value": "production"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/agent-wallet",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

### 4. Create ECS Service with ALB
Use AWS Console or Terraform to create:
- Application Load Balancer
- Target Group (port 8000)
- ECS Service with desired count

---

## Production: Google Cloud (Cloud Run + Cloud SQL)

Serverless option with automatic scaling.

### 1. Create Cloud SQL PostgreSQL
```bash
gcloud sql instances create agent-wallet-db \
  --database-version=POSTGRES_14 \
  --tier=db-f1-micro \
  --region=us-central1

gcloud sql databases create agent_wallet --instance=agent-wallet-db
```

### 2. Deploy to Cloud Run
```bash
# Build with Cloud Build
gcloud builds submit --tag gcr.io/PROJECT_ID/agent-wallet

# Deploy
gcloud run deploy agent-wallet \
  --image gcr.io/PROJECT_ID/agent-wallet \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --add-cloudsql-instances PROJECT_ID:us-central1:agent-wallet-db \
  --set-env-vars "DATABASE_URL=postgresql://..." \
  --set-env-vars "ENVIRONMENT=production"
```

---

## Production: Kubernetes (Any Cloud)

For maximum control and multi-cloud portability.

### Helm Chart Structure
```
helm/
├── Chart.yaml
├── values.yaml
└── templates/
    ├── deployment.yaml
    ├── service.yaml
    ├── ingress.yaml
    ├── configmap.yaml
    └── secret.yaml
```

### Example values.yaml
```yaml
replicaCount: 2

image:
  repository: your-registry/agent-wallet
  tag: latest
  pullPolicy: Always

service:
  type: ClusterIP
  port: 8000

ingress:
  enabled: true
  className: nginx
  hosts:
    - host: api.yourwallet.com
      paths:
        - path: /
          pathType: Prefix

resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 100m
    memory: 256Mi

env:
  DATABASE_URL: "postgresql://..."
  ENVIRONMENT: "production"

postgresql:
  enabled: true  # Use subchart or external
```

### Deploy
```bash
helm install agent-wallet ./helm -f values.yaml
```

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `SECRET_KEY` | Secret for signing (change in prod!) | Yes |
| `ENVIRONMENT` | `development` or `production` | No |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | No |

---

## Post-Deployment Checklist

- [ ] Run database migrations: `alembic upgrade head`
- [ ] Run seed script (if needed): `python -m agent_wallet_service.scripts.seed`
- [ ] Verify health endpoint: `curl https://your-url/health`
- [ ] Test API with SDK
- [ ] Set up monitoring/alerting
- [ ] Configure SSL/TLS (most platforms do this automatically)
- [ ] Set up database backups
- [ ] Review security groups/firewall rules

---

## Quick Comparison

| Platform | Ease | Cost | Scalability | Best For |
|----------|------|------|-------------|----------|
| Railway | ⭐⭐⭐⭐⭐ | Free tier | Auto | Testing, small projects |
| Render | ⭐⭐⭐⭐⭐ | Free tier | Auto | Testing, small projects |
| Fly.io | ⭐⭐⭐⭐ | Free tier | Auto | Edge deployment |
| AWS ECS | ⭐⭐⭐ | Pay-as-you-go | Manual/Auto | Production |
| GCP Cloud Run | ⭐⭐⭐⭐ | Pay-per-request | Auto | Serverless production |
| Kubernetes | ⭐⭐ | Varies | Full control | Enterprise, multi-cloud |
