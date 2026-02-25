# OpenClaw Infrastructure Research — 2026-02-25

## Contexto

Investigacion de recursos necesarios para correr 24 agentes OpenClaw autonomos en AWS.
Cada agente es una instancia soberana de OpenClaw que participa en una economia agentica
comprando/vendiendo datos via Execution Market, IRC (MeshRelay), y pagos x402/USDC en Base.

## Hallazgos Clave

### OpenClaw Resource Footprint

| Modo | RAM Idle | RAM Peak | CPU | Docker Image |
|---|---|---|---|---|
| Sin browser (API + cron) | 300-500 MB | ~1 GB | 1 vCPU | 2-4 GB |
| Con Playwright/Chromium | 300-500 MB + browser | 4-8 GB | 2-4 vCPU | 6-8 GB |

- Gateway Node.js idle: ~300-500 MB (fuente: macaron.im, clawtrust.ai)
- Playwright/Chromium por instancia: 1-2 GB adicionales (fuente: GitHub playwright #15400)
- Nuestros agentes NO necesitan browser — usan CLI scripts (HTTP, IRC, crypto signing)
- Deshabilitar browser: `{ "tools": { "deny": ["browser"] } }` en openclaw.json

### Memory Leaks (Conocidos)

- Bug: cron jobs no limpian `seqByRun` map en `agent-events.ts` (GitHub openclaw #17820)
- Con heartbeats cada 30 min: gateway crece 1-2 GB en 10-12 horas
- Caso extremo: 6 GB en 26 minutos (GitHub openclaw #24689)
- Caso extremo: 28 GB en 3 dias con container de 32 GB
- Solucion: restart automatico cada 12 horas via cron del host

### Precios AWS EC2 (us-east-1, Feb 2026)

| Instancia | vCPU | RAM | On-Demand/mo | Reserved 1yr/mo |
|---|---|---|---|---|
| t3.micro | 2 | 1 GB | $7.50 | ~$4.40 |
| t3.small | 2 | 2 GB | $15.18 | ~$8.92 |
| t3.medium | 2 | 4 GB | $30.37 | ~$17.75 |
| t3.xlarge | 4 | 16 GB | $121.47 | ~$71 |
| t3.2xlarge | 8 | 32 GB | $242.94 | ~$143 |

Alternativa barata: Hetzner CPX31 (~$11/mo, 4 vCPU, 8 GB) — 87% mas barato que AWS
pero sin ecosistema AWS (Secrets Manager, CloudWatch, etc.)

## Opciones Evaluadas

### Opcion A: 24 Instancias Soberanas (t3.small) -- RECOMENDADA

- 24x t3.small (2 vCPU, 2 GB) = $364/mo on-demand, $214/mo reserved
- Cada agente es un servidor independiente con su propio EBS
- Comunicacion SOLO por IRC, HTTP (EM API), blockchain (x402)
- Verdadera soberania — prueba la economia agentica
- Arranque incremental: 6 system agents primero ($91/mo)

### Opcion B: 2 Maquinas Grandes (12 agentes c/u) -- DESCARTADA

- 2x t3.2xlarge = $486/mo on-demand
- MAS CARO que Opcion A
- Si una maquina muere, 12 agentes caen
- Monolito disfrazado de Docker containers
- Un container con memory leak puede matar a los demas (OOM killer)

### Opcion C: Hibrido (6 soberanos + 1 maquina community) -- ALTERNATIVA

- 6x t3.small + 1x t3.xlarge = $227/mo on-demand, $140/mo reserved
- System agents soberanos, community agents comparten infra
- Mas barato pero community agents no son autonomos

## Decision: Opcion A Incremental

### Fase 1: 6 System Agents ($91/mo)
- kk-coordinator, kk-karma-hello, kk-skill-extractor
- kk-voice-extractor, kk-validator, kk-soul-extractor
- Valida economia con cadena de valor completa
- Valida que OpenClaw cabe en 2 GB sin Playwright

### Fase 2: +18 Community Agents ($364/mo total)
- Solo si Fase 1 demuestra revenue
- Misma arquitectura, mismo Terraform launch template

## Configuracion OpenClaw Recomendada

```json
{
  "agent": {
    "model": "anthropic/claude-sonnet-4-6"
  },
  "tools": {
    "deny": ["browser"]
  }
}
```

- Deshabilitar Playwright/browser (ahorra 6 GB RAM)
- Usar modelo cloud (no local) — el agente es liviano, la IA esta en la nube
- Heartbeats cada 30 min (default OpenClaw)
- Restart gateway cada 12 horas (mitiga memory leaks)

## Restart Cron (en cada instancia)

```bash
0 */12 * * * docker restart openclaw-gateway
```

## Fuentes

- https://macaron.im/blog/openclaw-hardware-requirements
- https://clawtrust.ai/blog/openclaw-server-requirements
- https://github.com/microsoft/playwright/issues/15400
- https://github.com/openclaw/openclaw/issues/17820
- https://github.com/openclaw/openclaw/issues/24689
- https://medium.com/@onurmaciit/8gb-was-a-lie-playwright-in-production-c2bdbe4429d6
- https://kaxo.io/insights/openclaw-production-gotchas/
- https://gist.github.com/digitalknk/ec360aab27ca47cb4106a183b2c25a98
- https://www.economize.cloud/resources/aws/pricing/ec2/t3.small/
- https://instances.vantage.sh/
