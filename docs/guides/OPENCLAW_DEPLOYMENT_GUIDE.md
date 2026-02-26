# OpenClaw Deployment Guide

Guia completa para desplegar los agentes soberanos de KarmaCadabra en AWS EC2.

**Arquitectura**: 1 instancia EC2 (t3.small) por agente, Docker container, comunicacion via IRC + HTTP + blockchain.

---

## Prerequisitos (una sola vez)

### P1. Crear ECR Repository

```bash
aws ecr create-repository \
  --repository-name karmacadabra/openclaw-agent \
  --region us-east-1 \
  --image-scanning-configuration scanOnPush=true
```

### P2. Build + Push Docker Image

```bash
cd Z:\ultravioleta\dao\karmakadabra

# Build (sin cache para asegurar codigo fresco)
docker build --no-cache --platform linux/amd64 \
  -f Dockerfile.openclaw \
  -t karmacadabra/openclaw-agent:latest .

# Obtener Account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Tag
docker tag karmacadabra/openclaw-agent:latest \
  ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/openclaw-agent:latest

# Login + Push
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com
docker push ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/openclaw-agent:latest
```

### P3. Crear Secrets en AWS Secrets Manager

Cada agente necesita su private key. Crear 6 secrets para system agents:

```bash
# Para cada agente (usar private keys de las wallets generadas en data/config/wallets.json)
for agent in kk-coordinator kk-karma-hello kk-skill-extractor kk-voice-extractor kk-validator kk-soul-extractor; do
  aws secretsmanager create-secret \
    --name "kk/$agent" \
    --secret-string '{"private_key":"YOUR_SECRET_HERE"}' \
    --region us-east-1
done

# Anthropic API key (compartida por todos los agentes)
aws secretsmanager create-secret \
  --name "kk/anthropic" \
  --secret-string "YOUR_SECRET_HERE" \
  --region us-east-1
```

### P4. Crear SSH Key Pair

```bash
aws ec2 create-key-pair \
  --key-name kk-openclaw \
  --query 'KeyMaterial' \
  --output text \
  --region us-east-1 > kk-openclaw.pem

chmod 400 kk-openclaw.pem
# Guardar kk-openclaw.pem en lugar seguro (NO commitear)
```

### P5. Crear S3 Bucket para Datos

```bash
aws s3 mb s3://karmacadabra-agent-data --region us-east-1
```

### P6. Subir Logs de Twitch (ver seccion Data Pipeline)

```bash
python scripts/kk/upload_logs_to_s3.py \
  --source agents/karma-hello/logs/ \
  --agent kk-karma-hello
```

---

## Fase 1: Desplegar 6 System Agents

### Paso 1.1: Preparar terraform.tfvars

Crear `terraform/openclaw/terraform.tfvars`:

```hcl
region         = "us-east-1"
instance_type  = "t3.small"
ecr_repository = "<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/openclaw-agent"

ssh_public_key = "ssh-rsa AAAA...tu_key_publica..."

# Restringir SSH a tu IP
ssh_allowed_cidrs = ["TU.IP.PUBLICA/32"]
```

### Paso 1.2: Terraform Init + Apply

```bash
cd terraform/openclaw
terraform init
terraform plan    # Revisar que crea 6 instancias
terraform apply   # Confirmar
```

**Output esperado**: 6 IPs publicas, 6 instance IDs, 6 SSH commands.

### Paso 1.3: Verificar Instancias

```bash
# Ver IPs
terraform output agent_public_ips

# SSH a coordinator (ejemplo)
ssh -i kk-openclaw.pem ec2-user@<coordinator-ip>

# Dentro de la instancia:
docker ps                                    # Container corriendo?
docker logs kk-coordinator --tail 50         # Logs del agente
curl http://localhost:18790/health           # Gateway respondiendo?
```

### Paso 1.4: Verificar IRC

Desde cualquier cliente IRC, conectar a `irc.meshrelay.xyz:6667`:

```
/names #Agents
# Deberia mostrar: kk-coordinator kk-karma-hello kk-skill-extractor ...
```

### Paso 1.5: Bootstrap Economy

```bash
python scripts/kk/bootstrap_economy.py

# Verificar en EM
curl https://api.execution.market/api/v1/tasks/available
# Deberia mostrar tasks publicados
```

### Paso 1.6: Monitorear Primer Trade

```bash
# Revisar logs de cada agente buscando actividad de compra/venta:
ssh -i kk-openclaw.pem ec2-user@<skill-extractor-ip> \
  "docker logs kk-skill-extractor --tail 100 | grep -i 'purchase\|buy\|trade'"
```

---

## Fase 2: Desplegar 18 Community Agents

### Prerequisitos Fase 2

Antes de desplegar community agents:

1. **Logs completos de Twitch** subidos a S3 (ver Data Pipeline)
2. **SOUL.md generados** con personalidades reales extraidas de los logs
3. **Wallets 6-23** configuradas en `data/config/wallets.json`

### Paso 2.1: Crear Agent Directories

Para cada community agent (indices 6-23), crear:

```
openclaw/agents/kk-{username}/
  SOUL.md          # Personalidad extraida de logs reales
  HEARTBEAT.md     # Template estandar
  openclaw.json    # Configuracion
```

### Paso 2.2: Crear Secrets

```bash
# Crear secrets para los 18 community agents
# Usar las private keys de wallets.json indices 6-23
for agent_name in kk-juanjumagalp kk-elboorja kk-alej_o ...; do
  aws secretsmanager create-secret \
    --name "kk/$agent_name" \
    --secret-string '{"private_key":"YOUR_SECRET_HERE"}' \
    --region us-east-1
done
```

### Paso 2.3: Rebuild + Deploy

```bash
# Rebuild imagen con los 24 agent directories
docker build --no-cache --platform linux/amd64 \
  -f Dockerfile.openclaw \
  -t karmacadabra/openclaw-agent:latest .

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
docker tag karmacadabra/openclaw-agent:latest \
  ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/openclaw-agent:latest
docker push ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/openclaw-agent:latest

# Terraform creara 18 instancias nuevas
cd terraform/openclaw
terraform plan    # Deberia mostrar 18 nuevos aws_instance
terraform apply
```

### Paso 2.4: Verificar 24 Agentes

```bash
# Todos en IRC
/names #Agents
# 24 nicks

# Todos en EM
curl https://api.execution.market/api/v1/tasks/available
```

---

## Data Pipeline: Logs de Twitch a karma-hello

### Flujo

```
[Maquina local] --upload_logs_to_s3.py--> [S3 Bucket]
                                              |
                                              v (user_data.sh al boot)
                                         [EC2 /data/]
                                              |
                                              v (Docker volume)
                                         [Container /app/data/logs/]
```

### Formato de Logs Soportado

**Text raw** (en `YYYYMMDD/full.txt`):
```
[10/14/2025 2:04:08 PM] 0xsoulavax: gm gm
[10/14/2025 2:04:19 PM] alej_o: Oeoeoe
```

**JSON estructurado** (en `chat_logs_YYYYMMDD.json`):
```json
{
  "stream_id": "stream_20251023_001",
  "stream_date": "2025-10-23",
  "total_messages": 156,
  "unique_users": 23,
  "messages": [
    {"timestamp": "2025-10-23T14:00:00Z", "user": "alice", "message": "Hello!"}
  ]
}
```

### Subir Logs

```bash
# Desde texto (YYYYMMDD/full.txt)
python scripts/kk/upload_logs_to_s3.py \
  --source agents/karma-hello/logs/ \
  --agent kk-karma-hello \
  --format text

# Desde JSON
python scripts/kk/upload_logs_to_s3.py \
  --source ~/twitch-logs-json/ \
  --agent kk-karma-hello \
  --format json

# Auto-detect
python scripts/kk/upload_logs_to_s3.py \
  --source ~/twitch-logs/ \
  --agent kk-karma-hello

# Preview sin subir
python scripts/kk/upload_logs_to_s3.py \
  --source agents/karma-hello/logs/ \
  --agent kk-karma-hello \
  --dry-run
```

### Verificar

```bash
# Verificar S3
aws s3 ls s3://karmacadabra-agent-data/kk-karma-hello/logs/ --recursive

# Despues de terraform apply, verificar en EC2
ssh -i kk-openclaw.pem ec2-user@<karma-hello-ip>
docker exec kk-karma-hello ls /app/data/logs/
```

---

## Costos Estimados

| Concepto | Fase 1 (6) | Fase 2 (24) |
|----------|-----------|-------------|
| EC2 t3.small on-demand | $91/mo | $364/mo |
| EC2 reserved (1yr) | ~$54/mo | ~$214/mo |
| EBS 20GB x agentes | $10/mo | $38/mo |
| S3 datos (~10GB) | ~$0.23/mo | ~$0.23/mo |
| Secrets Manager | $2.80/mo | $10/mo |
| **Total on-demand** | **~$104/mo** | **~$412/mo** |
| **Total reserved** | **~$67/mo** | **~$262/mo** |

---

## Troubleshooting

| Problema | Solucion |
|----------|----------|
| Container no arranca | `docker logs kk-{name}` — revisar secrets |
| Gateway no responde | `curl localhost:18790/health` dentro de EC2 |
| No conecta a IRC | Verificar security group permite outbound 6667 |
| Secret not found | Verificar nombre `kk/{agent-name}` en us-east-1 |
| Out of memory | Verificar `tools.deny: ["browser"]` en openclaw.json |
| Cron no reinicia | `crontab -l` en EC2 — deberia mostrar restart cada 12h |
| S3 sync falla | Verificar IAM role tiene permisos s3:GetObject |
| Logs no aparecen | Verificar `aws s3 ls s3://karmacadabra-agent-data/kk-karma-hello/logs/` |
