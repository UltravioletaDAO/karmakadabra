# Plan: LLM Self-Hosted para KarmaCadabra Swarm

> Documento de investigacion y plan de implementacion para migrar los 9 agentes
> KK de OpenRouter (GPT-4o-mini) a un servidor de inferencia local con Qwen 3.5.
>
> Fecha: 2026-03-03
> Estado: INVESTIGACION / NO IMPLEMENTAR AUN

---

## Tabla de Contenidos

1. [Qwen 3.5 Overview](#1-qwen-35-overview)
2. [Opciones de Hosting en AWS](#2-opciones-de-hosting-en-aws)
3. [Arquitectura Propuesta](#3-arquitectura-propuesta-para-karmacadabra)
4. [Analisis de Costos](#4-analisis-de-costos)
5. [Servidor de Inferencia Recomendado](#5-servidor-de-inferencia-recomendado)
6. [Plan de Implementacion](#6-plan-de-implementacion-paso-a-paso)
7. [Riesgos y Mitigacion](#7-riesgos-y-mitigacion)
8. [Conclusion y Recomendacion](#8-conclusion-y-recomendacion)

---

## 1. Qwen 3.5 Overview

### Que es Qwen 3.5

Qwen 3.5 es la familia de modelos de lenguaje de Alibaba Cloud (equipo Qwen), lanzada en
febrero-marzo 2026. Es completamente open-weight bajo licencia **Apache 2.0**, lo que
permite uso comercial sin restricciones. Soporta 201 idiomas y hasta 256K tokens de contexto.

### Cronologia de Lanzamiento

| Fecha | Serie | Modelos |
|-------|-------|---------|
| 16 Feb 2026 | Flagship | 397B-A17B (MoE: 397B total, 17B activos) |
| 24 Feb 2026 | Medium | 27B (dense), 35B-A3B (MoE), 122B-A10B (MoE) |
| 02 Mar 2026 | Small | 0.8B, 2B, 4B, 9B (dense, para on-device) |

### Benchmarks vs GPT-4o-mini

GPT-4o-mini es un modelo closed-source de OpenAI que cuesta $0.15/M input tokens y $0.60/M
output tokens via API. No se puede auto-hospedar. Los benchmarks de Qwen 3.5 muestran
resultados competitivos o superiores:

| Benchmark | Qwen3.5-9B | Qwen3.5-35B-A3B | Qwen3.5-27B | GPT-4o-mini* |
|-----------|-----------|-----------------|-------------|-------------|
| MMLU | ~82+ | ~84+ | ~85+ | 82.0 |
| GPQA Diamond | 81.7 | ~78 | ~80 | ~55** |
| MMMU-Pro | 70.1 | ~65 | ~68 | ~59** |
| BFCL-V4 (tool use) | ~60 | 67.3 | ~65 | ~55*** |
| Context Window | 256K | 1M | 256K | 128K |
| Licencia | Apache 2.0 | Apache 2.0 | Apache 2.0 | Closed |

(*) GPT-4o-mini benchmarks de julio 2024; modelos mas recientes pueden variar.
(**) Comparacion indirecta; GPT-5-mini score usado como proxy.
(***) BFCL-V4: GPT-5-mini obtuvo 55.5; GPT-4o-mini probablemente inferior.

**Hallazgo clave para KK**: El Qwen3.5-35B-A3B (MoE) obtiene 67.3 en BFCL-V4 (tool use/
function calling), superando significativamente a GPT-5-mini (55.5). Dado que los agentes KK
dependen fuertemente de tool calling (em_tool, wallet_tool, data_tool, reputation_tool,
irc_guard), este modelo es un candidato excelente.

### Tamanos de Modelo y Requisitos de Hardware

#### Serie Small (para CPU o GPU basica)

| Modelo | Parametros | VRAM BF16 | VRAM Q4 | GPU Minima |
|--------|-----------|----------|---------|------------|
| Qwen3.5-0.8B | 0.8B | ~1.6 GB | ~0.5 GB | Cualquier GPU / solo CPU |
| Qwen3.5-2B | 2B | ~4 GB | ~1.5 GB | GTX 1060 6GB |
| Qwen3.5-4B | 4B | ~8 GB | ~2.5 GB | RTX 3060 8GB |
| Qwen3.5-9B | 9B | ~18 GB | ~5 GB | RTX 3060 12GB |

#### Serie Medium (requiere GPU dedicada)

| Modelo | Total Params | Activos/Token | VRAM BF16 | VRAM Q4_K_M | GPU Recomendada |
|--------|-------------|--------------|----------|------------|----------------|
| Qwen3.5-27B (dense) | 27B | 27B | ~54 GB | ~17 GB | A10G 24GB (Q4) |
| Qwen3.5-35B-A3B (MoE) | 35B | 3B | ~22 GB (Q8) | ~12 GB | A10G 24GB |
| Qwen3.5-122B-A10B (MoE) | 122B | 10B | ~244 GB | ~60-70 GB | Multi-GPU |

#### Serie Flagship

| Modelo | Total Params | Activos/Token | VRAM BF16 | Infraestructura |
|--------|-------------|--------------|----------|----------------|
| Qwen3.5-397B-A17B | 397B | 17B | ~794 GB | 8x H100 80GB |

### Modelos Candidatos para KK

**RECOMENDADO: Qwen3.5-35B-A3B (MoE)**
- Solo 3B parametros activos por token = rapido y eficiente
- 35B parametros totales = conocimiento extenso
- Tool calling superior (BFCL-V4: 67.3)
- Cabe en 1x A10G 24GB con quantizacion Q4/Q5
- Contexto de 1M tokens
- Arquitectura MoE ideal para inferencia multi-tenant

**ALTERNATIVA ECONOMICA: Qwen3.5-9B**
- Cabe completo en BF16 en 24GB GPU
- Benchmarks sorprendentemente buenos para su tamano
- Ideal si el presupuesto es prioridad maxima
- Contexto de 256K tokens

**ALTERNATIVA PREMIUM: Qwen3.5-27B (dense)**
- Mejor calidad que el 35B-A3B en razonamiento puro
- Requiere quantizacion Q4 para caber en 24GB (ajustado)
- Mas lento que el MoE por activar todos los parametros

---

## 2. Opciones de Hosting en AWS

### Opcion A: EC2 con GPU (Recomendado)

#### Instancias Disponibles en us-east-1

| Instancia | GPU | VRAM | vCPUs | RAM | On-Demand/hr | Reservada 1yr/hr | Spot/hr | Mensual OD |
|-----------|-----|------|-------|-----|-------------|-----------------|---------|-----------|
| **g6.xlarge** | 1x L4 | 24 GB | 4 | 16 GB | $0.805 | $0.524 | $0.381 | **$580** |
| **g6.2xlarge** | 1x L4 | 24 GB | 8 | 32 GB | $0.978 | $0.636 | $0.501 | **$704** |
| **g5.xlarge** | 1x A10G | 24 GB | 4 | 16 GB | $1.006 | $0.435 | $0.431 | **$724** |
| **g5.2xlarge** | 1x A10G | 24 GB | 8 | 32 GB | $1.212 | $0.764 | $0.440 | **$873** |
| g6e.xlarge | 1x L40S | 45 GB | 4 | 32 GB | $1.861 | ~$1.21 | ~$0.74 | $1,340 |
| g6e.2xlarge | 1x L40S | 45 GB | 8 | 64 GB | $2.242 | ~$1.46 | ~$0.90 | $1,614 |

**Nota sobre GPUs:**
- **NVIDIA L4** (g6): Arquitectura Ada Lovelace, 24GB, buena para inferencia, mas nueva y barata
- **NVIDIA A10G** (g5): Arquitectura Ampere, 24GB, buena para inferencia, mas madura
- **NVIDIA L40S** (g6e): 45GB VRAM, para modelos que no caben en 24GB

#### Recomendacion GPU

Para el Qwen3.5-35B-A3B (MoE) con quantizacion Q4/Q5:
- **Primera opcion**: `g6.xlarge` ($580/mes OD) o `g5.xlarge` ($724/mes OD)
- La VRAM de 24GB es suficiente para el modelo quantizado (~12-15 GB)
- Sobra VRAM para KV cache y requests concurrentes

Para el Qwen3.5-9B en BF16 (sin quantizar):
- **Suficiente con**: `g6.xlarge` ($580/mes OD)
- El modelo ocupa ~18GB, dejando ~6GB para KV cache

Para el Qwen3.5-27B (dense) en Q4:
- **Minimo**: `g5.xlarge` ($724/mes OD) - ajustado, ~17GB modelo + ~7GB KV cache
- **Recomendado**: `g6e.xlarge` ($1,340/mes OD) si necesitas contexto largo

### Opcion B: EC2 con CPU-Only (Quantizacion GGUF)

Funciona para modelos pequenos usando llama.cpp con GGUF:

| Instancia | vCPUs | RAM | Modelo Compatible | Velocidad | Costo/mes |
|-----------|-------|-----|------------------|-----------|----------|
| c6i.2xlarge | 8 | 16 GB | Qwen3.5-9B Q4 | ~5-8 tok/s | ~$245 |
| c6i.4xlarge | 16 | 32 GB | Qwen3.5-9B Q5 | ~8-12 tok/s | ~$490 |
| r6i.2xlarge | 8 | 64 GB | Qwen3.5-27B Q4 | ~3-5 tok/s | ~$403 |

**Veredicto CPU-only**: NO RECOMENDADO para produccion. A 5-10 tokens/segundo, un solo
request de 500 tokens tarda 50-100 segundos. Con 9 agentes haciendo heartbeats cada 5
minutos, se genera un cuello de botella inaceptable. Los agentes necesarian esperar en cola
y los heartbeats se acumularian.

### Opcion C: Amazon Bedrock

**Estado actual**: Bedrock tiene Qwen3 (serie anterior), pero **NO Qwen 3.5 aun**.
Modelos Qwen disponibles en Bedrock a marzo 2026:
- Qwen3-Coder-480B-A35B-Instruct
- Qwen3-Coder-30B-A3B-Instruct
- Qwen3-235B-A22B-Instruct-2507
- Qwen3-32B (Dense)

**Pricing Bedrock** (Qwen3-32B referencia):
- Input: ~$0.20/M tokens
- Output: ~$0.60/M tokens

**Veredicto Bedrock**: Los precios son similares a OpenRouter y no ahorrarias
significativamente. Ademas, no tiene Qwen 3.5. Util como fallback pero no como solucion
principal. Cuando agreguen Qwen 3.5, podria ser interesante como alternativa serverless.

### Opcion D: Amazon SageMaker Inference Endpoints

SageMaker permite desplegar modelos custom en endpoints dedicados:
- Usaria instancias ml.g5.xlarge (~$1.20/hr) o ml.g6.xlarge
- Incluye auto-scaling, monitores, A/B testing
- Overhead de gestion de SageMaker (~20-30% mas caro que EC2 directo)
- Ventaja: Integrado con CloudWatch, auto-scaling nativo

**Veredicto SageMaker**: Excesivo para 9 agentes. El overhead no se justifica cuando una
sola instancia EC2 puede servir toda la carga. Considerar solo si se escala a 50+ agentes.

---

## 3. Arquitectura Propuesta para KarmaCadabra

### Estado Actual

```
                    Internet
                       |
            +----------+-----------+
            |    OpenRouter API    |
            | (openai/gpt-4o-mini) |
            +----------+-----------+
                       |
    +------------------+------------------+
    |          |          |          |    ...
 Agent 1   Agent 2   Agent 3   Agent 4   (x9)
 t3.small  t3.small  t3.small  t3.small
 $15/mo    $15/mo    $15/mo    $15/mo
```

- 9 agentes en EC2 t3.small (~$106/mes total infra)
- Cada agente usa `openrouter/openai/gpt-4o-mini` via OpenClaw
- API key: `OPENROUTER_API_KEY` inyectada desde AWS Secrets Manager
- Heartbeat cada 5 minutos = ~288 llamadas LLM por agente por dia

### Arquitectura Propuesta

```
                  +----------------------------+
                  |   GPU Instance (g6.xlarge)  |
                  |   NVIDIA L4 - 24GB VRAM     |
                  |                              |
                  |  +------------------------+  |
                  |  |    vLLM Server          |  |
                  |  |    Puerto 8000          |  |
                  |  |    Qwen3.5-35B-A3B Q4   |  |
                  |  |    OpenAI-compatible     |  |
                  |  +------------------------+  |
                  |            |                  |
                  +------------|------------------+
                               | VPC interno
          +--------------------+--------------------+
          |          |         |         |          |
       Agent 1   Agent 2   Agent 3   Agent 4   ... (x9)
       t3.small  t3.small  t3.small  t3.small
```

### Cambios Necesarios en OpenClaw

#### Actual: openclaw.json de cada agente

```json
{
  "agent": {
    "model": "openrouter/openai/gpt-4o-mini",
    "name": "kk-coordinator",
    ...
  }
}
```

#### Nuevo: openclaw.json con endpoint local

```json
{
  "agent": {
    "model": "kk-local/qwen3.5-35b-a3b",
    "name": "kk-coordinator",
    ...
  }
}
```

#### Configuracion del Provider en OpenClaw

Cada agente necesita la configuracion del provider en su config de OpenClaw. Hay dos
maneras de hacerlo:

**Opcion 1: Variable de entorno + modelo (minimo cambio)**

En el `entrypoint.sh`, agregar deteccion del endpoint local:

```bash
if [ -n "$KK_LLM_BASE_URL" ]; then
    export VLLM_API_KEY="kk-local-key"
    openclaw models set "vllm/qwen3.5-35b-a3b" 2>/dev/null || true
    echo "[entrypoint] Model: vllm/qwen3.5-35b-a3b (local: $KK_LLM_BASE_URL)"
elif [ -n "$OPENROUTER_API_KEY" ]; then
    openclaw models set "openrouter/openai/gpt-4o-mini" 2>/dev/null || true
    ...
fi
```

**Opcion 2: Provider custom en openclaw.json (mas control)**

```json
{
  "models": {
    "providers": {
      "kk-local": {
        "baseUrl": "http://10.0.1.100:8000/v1",
        "apiKey": "kk-local-key",
        "api": "openai-completions",
        "models": [
          {
            "id": "qwen3.5-35b-a3b",
            "name": "Qwen 3.5 35B-A3B (Local)",
            "reasoning": false,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 131072,
            "maxTokens": 8192
          }
        ]
      }
    }
  }
}
```

### Entrypoint.sh: Logica de Fallback

```bash
# Prioridad: Local GPU > OpenRouter > OpenAI > Anthropic
if [ -n "$KK_LLM_BASE_URL" ]; then
    # Verificar que el servidor local responde
    if curl -sf "$KK_LLM_BASE_URL/health" > /dev/null 2>&1; then
        export VLLM_API_KEY="${KK_LLM_API_KEY:-kk-local}"
        openclaw models set "vllm/qwen3.5-35b-a3b" 2>/dev/null || true
        echo "[entrypoint] Model: Qwen3.5-35B-A3B (local GPU server)"
    else
        echo "[WARN] Local LLM server not responding, falling back to OpenRouter"
        if [ -n "$OPENROUTER_API_KEY" ]; then
            openclaw models set "openrouter/openai/gpt-4o-mini" 2>/dev/null || true
        fi
    fi
elif [ -n "$OPENROUTER_API_KEY" ]; then
    openclaw models set "openrouter/openai/gpt-4o-mini" 2>/dev/null || true
fi
```

---

## 4. Analisis de Costos

### Costo Actual: OpenRouter

**Estimacion de uso por agente (heartbeat cada 5 min):**

| Metrica | Valor |
|---------|-------|
| Heartbeats/dia | 288 (60/5 * 24) |
| Tokens promedio por request (input) | ~2,000 (SOUL.md + HEARTBEAT.md + context) |
| Tokens promedio por request (output) | ~500 (respuesta + tool calls) |
| Tokens input/dia/agente | ~576,000 |
| Tokens output/dia/agente | ~144,000 |

**Costo por agente/dia:**
- Input: 576K tokens * $0.15/M = $0.0864
- Output: 144K tokens * $0.60/M = $0.0864
- Total/dia/agente: **$0.1728**

**Costo mensual total (9 agentes):**
- 9 * $0.1728 * 30 = **$46.66/mes**

**Nota**: Este es un estimado conservador. Si los agentes hacen tool calls que generan
multiples requests por heartbeat, el costo real podria ser 2-3x mayor:
- Escenario realista (2 requests/heartbeat): ~$93/mes
- Escenario pesado (3 requests/heartbeat): ~$140/mes

### Costo Propuesto: GPU Self-Hosted

#### Opcion 1: g6.xlarge On-Demand

| Concepto | Costo/mes |
|----------|----------|
| g6.xlarge (1x L4, 24GB) | $580 |
| Storage EBS (100GB gp3) | $8 |
| Data transfer | ~$5 |
| **Total** | **$593/mes** |

#### Opcion 2: g6.xlarge Reservada 1 ano

| Concepto | Costo/mes |
|----------|----------|
| g6.xlarge reservada 1yr all-upfront | $377 |
| Storage EBS (100GB gp3) | $8 |
| Data transfer | ~$5 |
| **Total** | **$390/mes** |

#### Opcion 3: g5.xlarge Spot (mas riesgo, mas ahorro)

| Concepto | Costo/mes |
|----------|----------|
| g5.xlarge spot (promedio) | $310 |
| Storage EBS (100GB gp3) | $8 |
| Data transfer | ~$5 |
| **Total** | **$323/mes** |

**Nota Spot**: Instancias spot pueden ser reclamadas por AWS con 2 minutos de aviso.
Necesita fallback automatico a OpenRouter.

### Analisis de Break-Even

| Escenario OpenRouter | Costo/mes OR | Costo/mes GPU (OD) | Costo/mes GPU (RI) | Break-even? |
|---------------------|-------------|-------------------|-------------------|-------------|
| Conservador (1 req/hb) | $47 | $593 | $390 | NO - GPU 8-12x mas caro |
| Realista (2 req/hb) | $93 | $593 | $390 | NO - GPU 4-6x mas caro |
| Pesado (3 req/hb) | $140 | $593 | $390 | NO - GPU 3-4x mas caro |
| 24 agentes desplegados | $249-$373 | $593 | $390 | CASI - GPU 1-2x mas caro |
| 24 agentes + alto uso | $560-$840 | $593 | $390 | SI - GPU mas barato |

**Conclusion de costos**: Con 9 agentes, el self-hosting es significativamente mas caro
que OpenRouter. El break-even se alcanza con ~20-24 agentes activos con uso moderado-alto,
o cuando se escale a los 24 agentes registrados que actualmente estan sin desplegar.

### Pero hay beneficios no-monetarios...

| Beneficio | Valor |
|-----------|-------|
| **Sin rate limits** | OpenRouter puede throttlear; local = ilimitado |
| **Latencia reducida** | VPC interno vs internet = ~50-100ms vs ~200-500ms |
| **Privacidad total** | Datos de agentes no salen de AWS |
| **Sin dependencia externa** | Si OpenRouter cae, los agentes siguen funcionando |
| **Modelo personalizable** | Fine-tuning futuro con datos de KK |
| **Tool calling superior** | Qwen3.5-35B-A3B > GPT-4o-mini en BFCL-V4 |
| **Contexto mayor** | 1M tokens vs 128K de GPT-4o-mini |
| **Sin costos por token** | Costo fijo mensual, uso ilimitado |

---

## 5. Servidor de Inferencia Recomendado

### Comparativa de Servidores

| Criterio | vLLM | TGI | Ollama | LocalAI |
|----------|------|-----|--------|---------|
| **OpenAI-compatible API** | Excelente | Buena | Buena | Excelente |
| **Throughput concurrente** | 793 tok/s | ~500 tok/s | 41 tok/s | ~300 tok/s |
| **Continuous Batching** | Si (PagedAttention) | Si | No | Parcial |
| **Multi-request handling** | Excelente | Bueno | Pobre | Bueno |
| **Qwen 3.5 soporte** | Nativo (nightly) | Parcial | Via GGUF | Via GGUF |
| **Docker oficial** | Si | Si | Si | Si |
| **Quantizacion** | AWQ, GPTQ, FP8 | GPTQ, AWQ | GGUF | GGUF |
| **Estado del proyecto** | Activo, recomendado | Mantenimiento* | Activo | Activo |
| **GPU memory optimization** | PagedAttention v2 | Flash Attention | Basica | Basica |

(*) Hugging Face puso TGI en modo mantenimiento en diciembre 2025 y recomienda vLLM o SGLang.

### Recomendacion: vLLM

**vLLM es la eleccion clara** por las siguientes razones:

1. **Throughput 19x mayor que Ollama** en requests concurrentes (793 vs 41 tok/s)
2. **PagedAttention**: Optimiza memoria del KV cache, permite mas requests simultaneos
3. **Continuous batching**: Los 9 agentes pueden hacer requests simultaneos sin cola
4. **Soporte nativo Qwen 3.5**: El equipo vLLM tiene recetas especificas para Qwen3.5
5. **API OpenAI-compatible completa**: Drop-in replacement, logprobs, structured output
6. **Docker image oficial**: `vllm/vllm-openai:nightly` lista para produccion
7. **Chunked prefill**: Optimiza GPU para prompts largos (SOUL.md + HEARTBEAT.md)
8. **Recomendado por Qwen y HuggingFace**

### Configuracion vLLM para KK

```bash
# Docker command para Qwen3.5-35B-A3B (MoE) quantizado
docker run -d \
  --gpus all \
  --name kk-inference \
  -p 8000:8000 \
  --ipc=host \
  -v /data/models:/root/.cache/huggingface \
  -e VLLM_API_KEY=kk-local-key \
  vllm/vllm-openai:nightly \
  --model Qwen/Qwen3.5-35B-A3B \
  --quantization awq \
  --max-model-len 32768 \
  --enable-prefix-caching \
  --gpu-memory-utilization 0.90 \
  --max-num-seqs 16 \
  --api-key kk-local-key
```

**Parametros explicados:**
- `--quantization awq`: Quantizacion AWQ para caber en 24GB con buena calidad
- `--max-model-len 32768`: Limita contexto a 32K (suficiente para heartbeats)
- `--enable-prefix-caching`: Reutiliza KV cache de SOUL.md/HEARTBEAT.md (comun entre requests)
- `--gpu-memory-utilization 0.90`: Usa 90% de VRAM (deja margen para picos)
- `--max-num-seqs 16`: Hasta 16 requests concurrentes (sobra para 9 agentes)

### Alternativa: Qwen3.5-9B (si el presupuesto es critico)

```bash
docker run -d \
  --gpus all \
  --name kk-inference \
  -p 8000:8000 \
  --ipc=host \
  -v /data/models:/root/.cache/huggingface \
  -e VLLM_API_KEY=kk-local-key \
  vllm/vllm-openai:nightly \
  --model Qwen/Qwen3.5-9B \
  --dtype bfloat16 \
  --max-model-len 65536 \
  --enable-prefix-caching \
  --gpu-memory-utilization 0.90 \
  --max-num-seqs 32 \
  --api-key kk-local-key
```

Con el 9B en BF16 (~18GB), sobran ~6GB para KV cache, permitiendo mas requests concurrentes
y contexto mas largo.

---

## 6. Plan de Implementacion Paso a Paso

### Fase 0: Preparacion (1 dia)

#### 0.1 Descargar modelo y testear localmente

```bash
# Si tienes GPU local, probar primero
pip install vllm
vllm serve Qwen/Qwen3.5-35B-A3B --quantization awq --max-model-len 8192

# Test rapido
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3.5-35B-A3B",
    "messages": [{"role": "user", "content": "Hello, who are you?"}]
  }'
```

### Fase 1: Infraestructura Terraform (1 dia)

#### 1.1 Crear archivo Terraform para instancia GPU

Archivo: `terraform/gpu-inference/main.tf`

```hcl
# ============================================================
# KK Self-Hosted LLM Inference Server
# ============================================================

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "karmacadabra-terraform-state"
    key    = "gpu-inference/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = "us-east-1"
}

# ---- Data Sources ----

data "aws_vpc" "main" {
  filter {
    name   = "tag:Name"
    values = ["kk-openclaw-vpc"]
  }
}

data "aws_subnet" "private" {
  filter {
    name   = "tag:Name"
    values = ["kk-openclaw-private-*"]
  }
}

# ---- Security Group ----

resource "aws_security_group" "inference" {
  name_prefix = "kk-inference-"
  vpc_id      = data.aws_vpc.main.id

  # vLLM API - only from agent instances
  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [var.agent_security_group_id]
    description     = "vLLM API from KK agents"
  }

  # SSH for management
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
    description = "SSH admin access"
  }

  # Health check from monitoring
  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    cidr_blocks     = ["10.0.0.0/16"]
    description     = "Health check from VPC"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name    = "kk-inference-sg"
    Project = "karmacadabra"
  }
}

# ---- EC2 Instance ----

resource "aws_instance" "inference" {
  ami           = var.gpu_ami_id  # Deep Learning AMI (Ubuntu) con drivers NVIDIA
  instance_type = var.instance_type
  key_name      = "kk-openclaw"
  subnet_id     = data.aws_subnet.private.id

  vpc_security_group_ids = [aws_security_group.inference.id]

  iam_instance_profile = aws_iam_instance_profile.inference.name

  root_block_device {
    volume_size = 150  # Espacio para modelo + Docker images
    volume_type = "gp3"
    throughput  = 250
    iops        = 3000
  }

  user_data = templatefile("${path.module}/user_data.sh.tpl", {
    model_name     = var.model_name
    quantization   = var.quantization
    max_model_len  = var.max_model_len
    api_key_secret = var.api_key_secret_arn
  })

  tags = {
    Name    = "kk-inference-server"
    Project = "karmacadabra"
    Role    = "llm-inference"
  }
}

# ---- IAM Role ----

resource "aws_iam_role" "inference" {
  name_prefix = "kk-inference-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.inference.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "inference" {
  name_prefix = "kk-inference-"
  role        = aws_iam_role.inference.name
}

# ---- CloudWatch Alarms ----

resource "aws_cloudwatch_metric_alarm" "gpu_health" {
  alarm_name          = "kk-inference-gpu-unhealthy"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 3
  metric_name         = "GPUUtilization"
  namespace           = "KK/Inference"
  period              = 300
  statistic           = "Average"
  threshold           = 1
  alarm_description   = "GPU inference server not responding"
  alarm_actions       = [var.sns_topic_arn]

  dimensions = {
    InstanceId = aws_instance.inference.id
  }
}
```

#### 1.2 Variables

Archivo: `terraform/gpu-inference/variables.tf`

```hcl
variable "instance_type" {
  description = "EC2 instance type for GPU inference"
  type        = string
  default     = "g6.xlarge"  # NVIDIA L4 24GB - $580/mes
}

variable "model_name" {
  description = "HuggingFace model ID"
  type        = string
  default     = "Qwen/Qwen3.5-35B-A3B"
}

variable "quantization" {
  description = "Quantization method (awq, gptq, none)"
  type        = string
  default     = "awq"
}

variable "max_model_len" {
  description = "Maximum context length"
  type        = number
  default     = 32768
}

variable "agent_security_group_id" {
  description = "Security group ID of KK agent instances"
  type        = string
}

variable "admin_cidr" {
  description = "CIDR for SSH admin access"
  type        = string
  default     = "0.0.0.0/0"  # Restringir en produccion
}

variable "gpu_ami_id" {
  description = "AMI ID for Deep Learning AMI with NVIDIA drivers"
  type        = string
  # Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 22.04)
  default = "ami-0a0c8eebcdd6dcbd0"
}

variable "api_key_secret_arn" {
  description = "ARN of the API key secret in Secrets Manager"
  type        = string
  default     = ""
}

variable "sns_topic_arn" {
  description = "SNS topic for alerts"
  type        = string
  default     = ""
}
```

#### 1.3 User Data Script

Archivo: `terraform/gpu-inference/user_data.sh.tpl`

```bash
#!/bin/bash
set -euo pipefail

echo "[user_data] Starting KK inference server setup..."

# ---- Install Docker + NVIDIA Container Toolkit ----
apt-get update
apt-get install -y docker.io nvidia-container-toolkit

# Configure NVIDIA runtime
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker

# ---- Pre-download model ----
mkdir -p /data/models
export HF_HOME=/data/models

# ---- Create systemd service for vLLM ----
cat > /etc/systemd/system/kk-inference.service <<'UNIT'
[Unit]
Description=KK vLLM Inference Server
After=docker.service
Requires=docker.service

[Service]
Restart=always
RestartSec=30
TimeoutStartSec=600

ExecStartPre=-/usr/bin/docker rm -f kk-inference
ExecStart=/usr/bin/docker run \
  --gpus all \
  --name kk-inference \
  -p 8000:8000 \
  --ipc=host \
  -v /data/models:/root/.cache/huggingface \
  vllm/vllm-openai:nightly \
  --model ${model_name} \
  --quantization ${quantization} \
  --max-model-len ${max_model_len} \
  --enable-prefix-caching \
  --gpu-memory-utilization 0.90 \
  --max-num-seqs 16 \
  --api-key kk-inference-key

ExecStop=/usr/bin/docker stop kk-inference

[Install]
WantedBy=multi-user.target
UNIT

# ---- Enable and start ----
systemctl daemon-reload
systemctl enable kk-inference
systemctl start kk-inference

# ---- Health check script ----
cat > /usr/local/bin/kk-health-check.sh <<'HEALTH'
#!/bin/bash
RESPONSE=$(curl -sf http://localhost:8000/health 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "healthy"
    exit 0
else
    echo "unhealthy"
    exit 1
fi
HEALTH
chmod +x /usr/local/bin/kk-health-check.sh

# ---- CloudWatch agent for GPU metrics ----
cat > /opt/gpu-metrics.sh <<'METRICS'
#!/bin/bash
GPU_UTIL=$(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits 2>/dev/null || echo "0")
GPU_MEM=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null || echo "0")
GPU_TEMP=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null || echo "0")

INSTANCE_ID=$(curl -sf http://169.254.169.254/latest/meta-data/instance-id)

aws cloudwatch put-metric-data \
  --namespace "KK/Inference" \
  --metric-name "GPUUtilization" \
  --value "$GPU_UTIL" \
  --unit Percent \
  --dimensions InstanceId=$INSTANCE_ID \
  --region us-east-1

aws cloudwatch put-metric-data \
  --namespace "KK/Inference" \
  --metric-name "GPUMemoryUsed" \
  --value "$GPU_MEM" \
  --unit Megabytes \
  --dimensions InstanceId=$INSTANCE_ID \
  --region us-east-1

aws cloudwatch put-metric-data \
  --namespace "KK/Inference" \
  --metric-name "GPUTemperature" \
  --value "$GPU_TEMP" \
  --unit None \
  --dimensions InstanceId=$INSTANCE_ID \
  --region us-east-1
METRICS
chmod +x /opt/gpu-metrics.sh

# Cron: GPU metrics every 5 minutes
echo "*/5 * * * * root /opt/gpu-metrics.sh" > /etc/cron.d/gpu-metrics

echo "[user_data] Setup complete. vLLM server starting..."
```

### Fase 2: Deploy del Servidor de Inferencia (1 dia)

```bash
# 2.1 Inicializar Terraform
cd terraform/gpu-inference
terraform init

# 2.2 Plan
terraform plan -out=gpu.plan

# 2.3 Apply
terraform apply gpu.plan

# 2.4 Esperar que el servidor arranque (~5-10 min para descargar modelo)
INFERENCE_IP=$(terraform output -raw inference_private_ip)
echo "Inference server IP: $INFERENCE_IP"

# 2.5 Verificar desde un agente existente (SSH)
ssh -i ~/.ssh/kk-openclaw.pem ec2-user@<AGENT_IP> \
  "curl -sf http://$INFERENCE_IP:8000/health"

# 2.6 Test de inferencia
ssh -i ~/.ssh/kk-openclaw.pem ec2-user@<AGENT_IP> \
  "curl http://$INFERENCE_IP:8000/v1/chat/completions \
    -H 'Content-Type: application/json' \
    -H 'Authorization: Bearer kk-inference-key' \
    -d '{
      \"model\": \"Qwen/Qwen3.5-35B-A3B\",
      \"messages\": [{\"role\": \"user\", \"content\": \"Hello\"}],
      \"max_tokens\": 100
    }'"
```

### Fase 3: Actualizar Agentes (1 dia)

#### 3.1 Actualizar openclaw.json de cada agente

Para cada agente, agregar la configuracion del provider local:

```json
{
  "agent": {
    "model": "kk-local/qwen3.5-35b-a3b",
    "name": "kk-coordinator",
    "soul": "/app/openclaw/agents/kk-coordinator/SOUL.md",
    "heartbeat": "/app/openclaw/agents/kk-coordinator/HEARTBEAT.md",
    "heartbeat_interval": 300
  },
  "models": {
    "providers": {
      "kk-local": {
        "baseUrl": "http://<INFERENCE_PRIVATE_IP>:8000/v1",
        "apiKey": "kk-inference-key",
        "api": "openai-completions",
        "models": [
          {
            "id": "qwen3.5-35b-a3b",
            "name": "Qwen 3.5 35B-A3B (KK Local)",
            "reasoning": false,
            "input": ["text"],
            "cost": { "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0 },
            "contextWindow": 32768,
            "maxTokens": 8192
          }
        ]
      }
    }
  },
  "irc": { "..." },
  "tools": { "..." }
}
```

#### 3.2 Actualizar entrypoint.sh

Agregar la variable `KK_LLM_BASE_URL` y la logica de fallback (ver Seccion 3).

#### 3.3 Actualizar variables de Terraform de los agentes

En `terraform/openclaw/variables.tf`, agregar:

```hcl
variable "inference_endpoint" {
  description = "URL del servidor de inferencia local"
  type        = string
  default     = ""  # Vacio = usar OpenRouter
}
```

Pasar como env var al container:
```hcl
environment = [
  { name = "KK_LLM_BASE_URL", value = var.inference_endpoint }
]
```

#### 3.4 Rebuild y Deploy

```bash
# Build nueva imagen Docker
docker build --no-cache -f Dockerfile.openclaw -t openclaw-agent:latest .

# Push a ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 518898403364.dkr.ecr.us-east-1.amazonaws.com
docker tag openclaw-agent:latest 518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/openclaw-agent:latest
docker push 518898403364.dkr.ecr.us-east-1.amazonaws.com/karmacadabra/openclaw-agent:latest

# Deploy a todos los agentes (usar kk-deploy skill)
# O manualmente:
for agent_ip in 44.211.242.65 13.218.119.234 100.53.60.94 100.52.188.43 44.203.23.11 3.234.249.61 3.235.151.197 13.218.189.187; do
  ssh -i ~/.ssh/kk-openclaw.pem ec2-user@$agent_ip "docker pull <ECR_IMAGE> && docker restart kk-agent"
done
```

### Fase 4: Monitoreo y Fallback (continuo)

#### 4.1 Health Check del Servidor de Inferencia

Script en cada agente que verifica el servidor antes de cada heartbeat:

```python
# En openclaw/tools/inference_health.py
import requests
import os

def check_inference_health():
    """Verifica si el servidor de inferencia local responde."""
    base_url = os.environ.get("KK_LLM_BASE_URL", "")
    if not base_url:
        return {"status": "not_configured", "fallback": "openrouter"}

    try:
        resp = requests.get(f"{base_url}/health", timeout=5)
        if resp.status_code == 200:
            return {"status": "healthy", "provider": "kk-local"}
    except Exception:
        pass

    return {"status": "unhealthy", "fallback": "openrouter"}
```

#### 4.2 Metricas CloudWatch

El user_data script ya configura metricas cada 5 minutos:
- `KK/Inference/GPUUtilization` - Uso de GPU (%)
- `KK/Inference/GPUMemoryUsed` - VRAM usada (MB)
- `KK/Inference/GPUTemperature` - Temperatura GPU

#### 4.3 Alarmas

- GPU utilization = 0% por 15 min: Servidor caido, notificar
- GPU temperature > 90C: Throttling inminente, notificar
- VRAM > 95%: Riesgo de OOM, notificar

#### 4.4 Fallback Automatico

Si el servidor local no responde:
1. Los agentes detectan en el health check pre-heartbeat
2. Cambian automaticamente a OpenRouter
3. Se envia alerta via SNS
4. Cuando el servidor se recupera, se vuelve a usar automaticamente

---

## 7. Riesgos y Mitigacion

| Riesgo | Probabilidad | Impacto | Mitigacion |
|--------|-------------|---------|-----------|
| **GPU OOM con 9 requests simultaneos** | Media | Alto | `--max-num-seqs 16`, limitar contexto a 32K |
| **Spot instance reclamada** | Alta | Alto | Fallback a OpenRouter, alarma automatica |
| **Modelo inferior a GPT-4o-mini en KK tasks** | Baja | Alto | Probar extensivamente antes de migrar |
| **vLLM crash/memory leak** | Baja | Medio | Systemd restart automatico, health checks |
| **NVIDIA driver issues** | Baja | Alto | Usar Deep Learning AMI preconfigurada |
| **Modelo no soporta tool calling bien** | Baja | Critico | Qwen3.5-35B-A3B tiene 67.3 en BFCL-V4 |
| **Costo mayor que OpenRouter** | Certeza | Medio | Aceptar el premium por autonomia/privacidad |
| **Qwen 3.5 no en vLLM stable** | Media | Medio | Usar nightly, upgrade cuando salga stable |

### Estrategia de Rollback

Si algo falla despues de migrar:

1. Cambiar `KK_LLM_BASE_URL=""` en variables de Terraform
2. `terraform apply` para propagar cambio
3. Agentes automaticamente caen a OpenRouter en siguiente heartbeat
4. No necesita rebuild de Docker image

---

## 8. Conclusion y Recomendacion

### Resumen Ejecutivo

| Aspecto | OpenRouter (actual) | Self-Hosted GPU |
|---------|-------------------|-----------------|
| Costo 9 agentes | $47-140/mes | $390-593/mes |
| Costo 24 agentes | $125-373/mes | $390-593/mes (mismo) |
| Latencia | ~200-500ms | ~50-100ms (VPC) |
| Rate limits | Si (OpenRouter) | No |
| Privacidad | Datos van a OpenAI | Todo en AWS VPC |
| Dependencia | OpenRouter + OpenAI | Solo AWS |
| Tool calling | GPT-4o-mini (~55) | Qwen3.5 (67.3 BFCL-V4) |
| Contexto max | 128K tokens | 1M tokens (35B-A3B) |
| Fine-tuning | No | Si, futuro |
| Disponibilidad | 99.9% (OpenRouter) | Depende de nosotros |

### Recomendacion por Fase

**FASE INMEDIATA (Ahora)**: NO migrar. Con 9 agentes, OpenRouter cuesta $47-140/mes.
Un GPU server cuesta minimo $390/mes. El ROI no se justifica.

**FASE MEDIA (Cuando despliegues 15-20+ agentes)**: Comenzar con una instancia g6.xlarge
reservada 1 ano ($390/mes) con Qwen3.5-35B-A3B. El break-even se alcanza con ~20 agentes
con uso moderado.

**FASE AVANZADA (24 agentes + fine-tuning)**: Migrar completamente a self-hosted.
Considerar g5.2xlarge para mas CPU/RAM, o g6e.xlarge para modelos mas grandes.

### Recomendacion Final

**Esperar a desplegar mas agentes antes de invertir en GPU.** Mientras tanto:

1. Hacer un **proof of concept** en una instancia spot g5.xlarge (~$310/mes) durante 1 semana
2. Probar Qwen3.5-35B-A3B con los tool calls reales de KK (em_tool, wallet_tool, etc.)
3. Comparar calidad de respuestas vs GPT-4o-mini
4. Si la calidad es igual o mejor, mantener el servidor listo para cuando se escale
5. Implementar el fallback a OpenRouter desde el dia 1

El valor real del self-hosting no esta en el ahorro de costos (que no existe con 9 agentes),
sino en la **autonomia, privacidad, latencia reducida, y capacidad de fine-tuning futuro**.

---

## Fuentes

- [Qwen 3.5 Official Blog](https://qwen.ai/blog?id=qwen3.5)
- [Qwen 3.5 GitHub](https://github.com/QwenLM/Qwen3.5)
- [Qwen 3.5 Medium Models Benchmarks](https://www.digitalapplied.com/blog/qwen-3-5-medium-model-series-benchmarks-pricing-guide)
- [Qwen 3.5 Small Models (MarkTechPost)](https://www.marktechpost.com/2026/03/02/alibaba-just-released-qwen-3-5-small-models-a-family-of-0-8b-to-9b-parameters-built-for-on-device-applications/)
- [Qwen 3.5 Complete Guide](https://techie007.substack.com/p/qwen-35-the-complete-guide-benchmarks)
- [Qwen 3.5 Local AI Guide (InsiderLLM)](https://insiderllm.com/guides/qwen-3-5-local-ai-guide/)
- [Qwen 3.5 Hardware Requirements](https://apxml.com/posts/gpu-system-requirements-qwen-models)
- [vLLM Qwen3.5 Usage Guide](https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3.5.html)
- [vLLM Docker Deployment](https://docs.vllm.ai/en/stable/deployment/docker/)
- [vLLM vs TGI vs Ollama Comparison (Hivenet)](https://compute.hivenet.com/post/vllm-vs-tgi-vs-tensorrt-llm-vs-ollama)
- [Token Throughput: vLLM vs Ollama vs TGI](https://dasroot.net/posts/2026/02/token-throughput-comparison-vllm-ollama-tgi/)
- [Ollama vs vLLM 2026 (Particula)](https://particula.tech/blog/ollama-vs-vllm-comparison)
- [AWS EC2 G5 Instances](https://aws.amazon.com/ec2/instance-types/g5/)
- [AWS EC2 G6 Instances](https://aws.amazon.com/ec2/instance-types/g6/)
- [AWS EC2 On-Demand Pricing](https://aws.amazon.com/ec2/pricing/on-demand/)
- [g5.xlarge Pricing (Vantage)](https://instances.vantage.sh/aws/ec2/g5.xlarge)
- [g6.xlarge Pricing (Vantage)](https://instances.vantage.sh/aws/ec2/g6.xlarge)
- [OpenRouter GPT-4o-mini Pricing](https://openrouter.ai/openai/gpt-4o-mini)
- [Amazon Bedrock Qwen Models](https://aws.amazon.com/bedrock/qwen/)
- [OpenClaw Model Providers Docs](https://docs.openclaw.ai/concepts/model-providers)
- [OpenClaw with vLLM (AMD)](https://www.amd.com/en/developer/resources/technical-articles/2026/openclaw-with-vllm-running-for-free-on-amd-developer-cloud-.html)
- [Qwen3.5-35B-A3B DGX Spark Benchmarks](https://github.com/adadrag/qwen3.5-dgx-spark)
- [Qwen3.5-122B-A10B Specs](https://apxml.com/models/qwen35-122b-a10b)
