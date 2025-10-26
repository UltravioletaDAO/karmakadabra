# Guía: Cómo Probar el Stack de Producción

## Estado Actual del Stack

✅ **6 componentes desplegados y funcionando en AWS con HTTPS**

### Facilitador (x402 Payment Protocol)
| Componente | Estado | Endpoint HTTPS | Documentación |
|------------|--------|----------------|---------------|
| **Facilitador** | 🟢 Running | https://facilitator.ultravioletadao.xyz | [/health](https://facilitator.ultravioletadao.xyz/health) · [/supported](https://facilitator.ultravioletadao.xyz/supported) |

### Agentes de Sistema (5)
| Agente | Estado | Endpoint HTTPS | AgentCard |
|--------|--------|----------------|-----------|
| **Validator** | 🟢 Running | https://validator.karmacadabra.ultravioletadao.xyz | [/.well-known/agent-card](https://validator.karmacadabra.ultravioletadao.xyz/.well-known/agent-card) |
| **Karma-Hello** | 🟢 Running | https://karma-hello.karmacadabra.ultravioletadao.xyz | [/.well-known/agent-card](https://karma-hello.karmacadabra.ultravioletadao.xyz/.well-known/agent-card) |
| **Abracadabra** | 🟢 Running | https://abracadabra.karmacadabra.ultravioletadao.xyz | [/.well-known/agent-card](https://abracadabra.karmacadabra.ultravioletadao.xyz/.well-known/agent-card) |
| **Skill-Extractor** | 🟢 Running | https://skill-extractor.karmacadabra.ultravioletadao.xyz | [/.well-known/agent-card](https://skill-extractor.karmacadabra.ultravioletadao.xyz/.well-known/agent-card) |
| **Voice-Extractor** | 🟢 Running | https://voice-extractor.karmacadabra.ultravioletadao.xyz | [/.well-known/agent-card](https://voice-extractor.karmacadabra.ultravioletadao.xyz/.well-known/agent-card) |

---

## Opción 1: Prueba Rápida (Verificar que Todo Funcione)

### Ejecuta el Script de Verificación Completo

```bash
python scripts/test_all_endpoints.py
```

**Esto verifica:**
- ✅ **Facilitador**: `/health`, `/supported`, `/verify` (3 endpoints)
- ✅ **Todos los agentes**: `/health`, `/.well-known/agent-card` (10 endpoints)
- ✅ **Total**: 13 endpoints verificados en ~5 segundos
- ✅ Seguridad TLS/SSL
- ✅ Conectividad completa

**Resultado esperado:**
```
[SUCCESS] All endpoints responding!
Facilitator: 3/3 passing
Agents: 10/10 passing
Overall: 13/13 endpoints verified
```

**Alternativa (solo agentes, sin facilitador):**
```bash
python scripts/test_production_stack.py
```

---

## Opción 2: Prueba Manual con cURL

### 0. Verificar Facilitador (x402 Payment Protocol)

```bash
# Health check del facilitador
curl https://facilitator.ultravioletadao.xyz/health

# Ver métodos de pago soportados
curl https://facilitator.ultravioletadao.xyz/supported

# Verificar endpoint de verificación (debe responder 400 sin payload)
curl -X POST https://facilitator.ultravioletadao.xyz/verify -H "Content-Type: application/json" -d '{}'
```

**Respuesta esperada del `/health`:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "network": "fuji",
  "facilitator_address": "0x..."
}
```

**Respuesta esperada del `/supported`:**
```json
{
  "payment_methods": ["eip3009", "glue"],
  "network": "fuji",
  "glue_token": "0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743"
}
```

### 1. Verificar Health de Todos los Agentes

```bash
# Validator
curl https://validator.karmacadabra.ultravioletadao.xyz/health

# Karma-Hello
curl https://karma-hello.karmacadabra.ultravioletadao.xyz/health

# Abracadabra
curl https://abracadabra.karmacadabra.ultravioletadao.xyz/health

# Skill-Extractor
curl https://skill-extractor.karmacadabra.ultravioletadao.xyz/health

# Voice-Extractor
curl https://voice-extractor.karmacadabra.ultravioletadao.xyz/health
```

### 2. Consultar AgentCards (A2A Protocol)

```bash
# Ver todos los servicios que ofrece Karma-Hello
curl https://karma-hello.karmacadabra.ultravioletadao.xyz/.well-known/agent-card | jq

# Ver pricing del Skill-Extractor
curl https://skill-extractor.karmacadabra.ultravioletadao.xyz/.well-known/agent-card | jq '.skills[0].pricing'

# Ver capacidades del Validator
curl https://validator.karmacadabra.ultravioletadao.xyz/.well-known/agent-card | jq '.skills'
```

---

## Opción 3: Prueba Completa con Client-Agent

### Paso 1: Configurar Client-Agent

```bash
cd client-agents/template
cp .env.example .env
```

**Edita `.env` y actualiza las URLs de producción:**

```bash
# Production HTTPS endpoints
KARMA_HELLO_URL=https://karma-hello.karmacadabra.ultravioletadao.xyz
ABRACADABRA_URL=https://abracadabra.karmacadabra.ultravioletadao.xyz
SKILL_EXTRACTOR_URL=https://skill-extractor.karmacadabra.ultravioletadao.xyz
VOICE_EXTRACTOR_URL=https://voice-extractor.karmacadabra.ultravioletadao.xyz
VALIDATOR_URL=https://validator.karmacadabra.ultravioletadao.xyz

# Tu wallet privada (para firmar transacciones)
PRIVATE_KEY=0x...  # Tu key privada del client-agent
```

### Paso 2: Instalar Dependencias

```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
```

### Paso 3: Probar Discovery (Sin Compras)

```bash
python main.py
```

Esto ejecuta el demo que:
- ✅ Descubre agentes usando A2A protocol
- ✅ Muestra sus capabilities
- ✅ NO realiza compras (solo discovery)

**Salida esperada:**
```
BUYER CAPABILITIES (inherited from base agent):
------------------------------------------------------------------

1. Discovering Karma-Hello agent...
   Found: Karma-Hello Seller
   Skills: 1

2. Buying chat logs...
   ...
```

### Paso 4: Ejecutar Compras Reales (E2E Test)

**⚠️ IMPORTANTE: Esto gastará GLUE tokens reales**

```bash
# Asegúrate de tener GLUE y AVAX en tu wallet del client-agent
python scripts/check_system_ready.py

# Ejecuta el flujo completo de compras
python scripts/demo_client_purchases.py --production
```

**Esto ejecuta:**
1. Client compra logs de karma-hello (0.01 GLUE)
2. Client compra skill profile de skill-extractor (0.05 GLUE)
   - skill-extractor compra logs de karma-hello (0.01 GLUE)
3. Client compra personality de voice-extractor (0.05 GLUE)
   - voice-extractor compra logs de karma-hello (0.01 GLUE)

**Total gastado por client: 0.11 GLUE**

---

## Opción 4: Prueba con Python Requests

### Script de Ejemplo Mínimo

```python
import requests

# 1. Verificar health
response = requests.get("https://karma-hello.karmacadabra.ultravioletadao.xyz/health")
print("Health:", response.json())

# 2. Consultar AgentCard
response = requests.get("https://karma-hello.karmacadabra.ultravioletadao.xyz/.well-known/agent-card")
card = response.json()
print(f"Agent: {card['name']}")
print(f"Skills: {len(card['skills'])}")
print(f"Pricing: {card['skills'][0]['pricing']}")

# 3. Comprar servicio (requiere x402 payment header)
# Ver client-agents/template/main.py para ejemplo completo
```

---

## Monitoreo y Debugging

### Ver Logs de los Agentes en AWS

```bash
# Validator logs
aws logs tail /ecs/karmacadabra-prod/validator --follow

# Karma-Hello logs
aws logs tail /ecs/karmacadabra-prod/karma-hello --follow

# Ver todos los logs en paralelo (PowerShell)
Start-Process -NoNewWindow aws -ArgumentList "logs","tail","/ecs/karmacadabra-prod/validator","--follow"
Start-Process -NoNewWindow aws -ArgumentList "logs","tail","/ecs/karmacadabra-prod/karma-hello","--follow"
```

### Verificar Estado de los Servicios ECS

```bash
aws ecs describe-services \
  --cluster karmacadabra-prod \
  --services \
    karmacadabra-prod-validator \
    karmacadabra-prod-karma-hello \
    karmacadabra-prod-abracadabra \
    karmacadabra-prod-skill-extractor \
    karmacadabra-prod-voice-extractor \
  --query 'services[*].[serviceName,status,runningCount,desiredCount]' \
  --output table
```

### Ver Métricas de CloudWatch

```bash
# CPU usage
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=karmacadabra-prod-validator \
  --start-time 2025-10-26T00:00:00Z \
  --end-time 2025-10-26T23:59:59Z \
  --period 3600 \
  --statistics Average
```

---

## Troubleshooting

### Problema: "Connection refused"

**Causa:** Agente no está corriendo o firewall bloqueando

**Solución:**
```bash
# Verificar que el servicio esté running
aws ecs describe-services --cluster karmacadabra-prod --services karmacadabra-prod-validator

# Verificar security groups
aws ec2 describe-security-groups --group-ids sg-xxx
```

### Problema: "SSL certificate verify failed"

**Causa:** Certificado SSL no válido o no confiado

**Solución:**
```python
# Temporal (solo para testing)
import requests
requests.get(url, verify=False)  # NO usar en producción

# Permanente: Verificar que ACM certificate esté ISSUED
aws acm describe-certificate --certificate-arn arn:aws:acm:...
```

### Problema: "403 Forbidden"

**Causa:** Problema con ALB routing o security groups

**Solución:**
```bash
# Verificar ALB listener rules
aws elbv2 describe-rules --listener-arn arn:aws:elasticloadbalancing:...

# Verificar target health
aws elbv2 describe-target-health --target-group-arn arn:aws:elasticloadbalancing:...
```

---

## Próximos Pasos

Una vez que verificaste que todo funciona:

1. **Probar transacciones reales** con el client-agent
2. **Monitorear costos** en AWS Cost Explorer
3. **Configurar alertas** para failures
4. **Documentar flujos de compra exitosos**
5. **Preparar demo para inversores/usuarios**

---

## Links Útiles

- **Avalanche Fuji Explorer:** https://testnet.snowtrace.io/
- **GLUE Token:** https://testnet.snowtrace.io/address/0x3D19A80b3bD5CC3a4E55D4b5B753bC36d6A44743
- **Identity Registry:** https://testnet.snowtrace.io/address/0xB0a405a7345599267CDC0dD16e8e07BAB1f9B618
- **AWS Console ECS:** https://console.aws.amazon.com/ecs/home?region=us-east-1#/clusters/karmacadabra-prod
- **CloudWatch Logs:** https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups

---

**Última actualización:** 2025-10-26
**Stack version:** Production HTTPS (AWS ECS Fargate)
