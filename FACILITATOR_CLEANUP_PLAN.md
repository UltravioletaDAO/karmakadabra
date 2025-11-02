# Plan de Limpieza Post-Extracción del Facilitator

**Status**: Facilitator extraído exitosamente ✅
**Fecha**: 2025-11-01
**Estrategia**: Deployment paralelo + limpieza gradual

---

## ⚠️ ESTRATEGIA RECOMENDADA: Arrancar Nuevo PRIMERO

**NO toques nada en karmacadabra hasta que el nuevo facilitator esté funcionando en producción.**

### Orden de Operaciones Seguro

```
Fase 1: Deploy Nuevo Facilitator (3-4 horas)
   ↓
Fase 2: Verificación en Paralelo (24-48 horas)
   ↓
Fase 3: Limpieza de Archivos (.unused) (30 minutos)
   ↓
Fase 4: Actualizar Referencias en Agentes (1 hora)
   ↓
Fase 5: Destruir Viejo Facilitator (después de 1 semana)
```

---

## Fase 1: Deploy Nuevo Facilitator (HACER PRIMERO)

### 1.1 Deploy en AWS con nuevo dominio

```bash
cd z:\ultravioleta\facilitator  # (el folder que moviste fuera)

# Setup AWS
aws s3 mb s3://facilitator-terraform-state --region us-east-1
aws s3api put-bucket-versioning --bucket facilitator-terraform-state --versioning-configuration Status=Enabled
aws dynamodb create-table --table-name facilitator-terraform-locks --attribute-definitions AttributeName=LockID,AttributeType=S --key-schema AttributeName=LockID,KeyType=HASH --billing-mode PAY_PER_REQUEST --region us-east-1
aws ecr create-repository --repository-name facilitator --region us-east-1

# Migrate secrets (SECURE WORKSTATION!)
aws secretsmanager get-secret-value --secret-id karmacadabra-facilitator-mainnet --query SecretString --output text > /tmp/evm-key.json
aws secretsmanager get-secret-value --secret-id karmacadabra-solana-keypair --query SecretString --output text > /tmp/solana-key.json

aws secretsmanager create-secret --name facilitator-evm-private-key --secret-string file:///tmp/evm-key.json --region us-east-1
aws secretsmanager create-secret --name facilitator-solana-keypair --secret-string file:///tmp/solana-key.json --region us-east-1

shred -vfz -n 10 /tmp/evm-key.json /tmp/solana-key.json

# Build and push
./scripts/build-and-push.sh v1.0.0

# Deploy infrastructure
cd terraform/environments/production
terraform init
terraform plan
terraform apply
```

### 1.2 Verificar nuevo facilitator funciona

```bash
# Health check
curl https://facilitator.prod.ultravioletadao.xyz/health
# Expected: {"status":"healthy"}

# Branding check
curl https://facilitator.prod.ultravioletadao.xyz/ | grep "Ultravioleta"
# Expected: Should find "Ultravioleta DAO"

# Test payment flow
cd ../../tests/integration
python test_glue_payment.py --facilitator https://facilitator.prod.ultravioletadao.xyz --network fuji
# Expected: ✅ Payment successful
```

**🛑 STOP AQUÍ: No sigas hasta que el nuevo facilitator funcione perfectamente por 24-48 horas**

---

## Fase 2: Verificación en Paralelo (24-48 horas)

### Checklist de Monitoreo

**Durante 24-48 horas, verificar:**

```bash
# Cada 6 horas, verificar:
# 1. Health checks
curl https://facilitator.prod.ultravioletadao.xyz/health

# 2. CloudWatch metrics
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=facilitator-production \
  --start-time $(date -u -d '6 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 3600 \
  --statistics Average,Maximum

# 3. Error logs
aws logs tail /ecs/facilitator-production --follow --since 6h | grep -i error

# 4. Test payments
python tests/integration/test_glue_payment.py --facilitator https://facilitator.prod.ultravioletadao.xyz --network fuji
```

**Criterios de éxito** (todos deben cumplirse):
- [ ] Health checks 100% exitosos
- [ ] CPU promedio <50%
- [ ] Memory promedio <60%
- [ ] 0 errores críticos en logs
- [ ] Test de payments 100% exitosos
- [ ] Respuesta <500ms (p99)

**Si hay problemas**: Rollback a viejo facilitator, debug, fix, redeploy.

**Si todo funciona**: Proceder a Fase 3.

---

## Fase 3: Limpieza de Archivos (DESPUÉS de 24-48h estables)

### 3.1 Archivos a Mover a .unused/

**Categoría: Scripts de testing del facilitator**
```bash
cd z:\ultravioleta\dao\karmacadabra

mkdir -p .unused/facilitator-old/{scripts,tests,docs,root}

# Scripts (28 archivos)
mv scripts/test_glue_payment_simple.py .unused/facilitator-old/scripts/
mv scripts/test_usdc_payment_base.py .unused/facilitator-old/scripts/
mv scripts/test_base_usdc_stress.py .unused/facilitator-old/scripts/
mv scripts/test_facilitator_verbose.py .unused/facilitator-old/scripts/
mv scripts/test_real_x402_payment.py .unused/facilitator-old/scripts/
mv scripts/test_glue_quick.py .unused/facilitator-old/scripts/
mv scripts/test_complete_flow.py .unused/facilitator-old/scripts/
mv scripts/test_all_endpoints.py .unused/facilitator-old/scripts/
mv scripts/check_facilitator_config.py .unused/facilitator-old/scripts/
mv scripts/check_facilitator_version.py .unused/facilitator-old/scripts/
mv scripts/diagnose_usdc_payment.py .unused/facilitator-old/scripts/
mv scripts/compare_domain_separator.py .unused/facilitator-old/scripts/
mv scripts/compare_usdc_contracts.py .unused/facilitator-old/scripts/
mv scripts/verify_full_stack.py .unused/facilitator-old/scripts/
mv scripts/usdc_contracts_facilitator.json .unused/facilitator-old/scripts/
mv scripts/setup_facilitator_secrets.py .unused/facilitator-old/scripts/
mv scripts/migrate_facilitator_secrets.py .unused/facilitator-old/scripts/
mv scripts/rotate-facilitator-wallet.py .unused/facilitator-old/scripts/
mv scripts/create_testnet_facilitator_secret.py .unused/facilitator-old/scripts/
mv scripts/split_facilitator_secrets.py .unused/facilitator-old/scripts/
mv scripts/upgrade_facilitator.ps1 .unused/facilitator-old/scripts/
mv scripts/extract_usdc_contracts.py .unused/facilitator-old/scripts/

# Tests (13 archivos)
mv tests/test_facilitator.py .unused/facilitator-old/tests/
mv tests/x402/ .unused/facilitator-old/tests/ 2>/dev/null

# Docs (10+ archivos)
mv docs/FACILITATOR_TESTING.md .unused/facilitator-old/docs/
mv docs/FACILITATOR_WALLET_ROTATION.md .unused/facilitator-old/docs/
mv docs/X402_FORK_STRATEGY.md .unused/facilitator-old/docs/
mv docs/migration/FACILITATOR_SECRETS_MIGRATION.md .unused/facilitator-old/docs/
mv FACILITATOR_VALIDATION_BUG.md .unused/facilitator-old/docs/
mv BASE_USDC_BUG_INVESTIGATION_REPORT.md .unused/facilitator-old/docs/
mv AWS_FACILITATOR_INFRASTRUCTURE_EXTRACTION.md .unused/facilitator-old/docs/

# Task definitions (root)
mv facilitator-task-def-mainnet.json .unused/facilitator-old/root/
mv facilitator-task-def-mainnet-v2.json .unused/facilitator-old/root/

# Extraction docs (root)
mv FACILITATOR_EXTRACTION_MASTER_PLAN.md .unused/facilitator-old/root/
mv EXTRACTION_MASTER_PLAN_TERRAFORM_ANALYSIS.md .unused/facilitator-old/root/
mv TERRAFORM_EXTRACTION_SUMMARY.md .unused/facilitator-old/root/
mv TERRAFORM_EXTRACTION_DIAGRAM.md .unused/facilitator-old/root/

echo "✅ Archivos del facilitator movidos a .unused/facilitator-old/"
```

### 3.2 Archivos que DEBEN QUEDARSE (por ahora)

**⚠️ NO MOVER ESTOS ARCHIVOS (agentes los usan activamente):**

```bash
# 1. x402-rs/ - MANTENER como backup hasta Fase 5
#    Los agentes pueden tener referencias hardcodeadas
#    Mover después de verificar que NO hay imports directos

# 2. terraform/ecs-fargate/ - MANTENER
#    Aún maneja el viejo facilitator en ECS
#    El viejo facilitator sigue corriendo hasta Fase 5

# 3. scripts/ relacionados a multi-agent deployment
#    build-and-push.py (tiene sección facilitator pero también otros agentes)
#    deploy-to-fargate.py (multi-agent)
#    deploy-all.py (multi-agent)
#    fund-wallets.py (todos los agentes)
#    check_all_balances.py (todos los agentes)
#    demo_client_purchases.py (usa facilitator pero también agentes)

# 4. docker-compose.yml - MANTENER
#    Contiene definiciones de todos los agentes
#    Editaremos en Fase 4 para actualizar facilitator URL
```

### 3.3 Actualizar .gitignore

```bash
# Agregar al .gitignore (si no existe)
echo "" >> .gitignore
echo "# Facilitator extracted to separate repo" >> .gitignore
echo ".unused/facilitator-old/" >> .gitignore
```

---

## Fase 4: Actualizar Referencias en Agentes (después de 1 semana estable)

### 4.1 Actualizar URLs del facilitator

**Archivos a revisar y actualizar:**

```bash
# 1. .env files de cada agente
#    Cambiar: FACILITATOR_URL=https://facilitator.ultravioletadao.xyz
#    Por:     FACILITATOR_URL=https://facilitator.prod.ultravioletadao.xyz

# Agentes:
nano agents/karma-hello/.env
nano agents/abracadabra/.env
nano agents/validator/.env
nano agents/skill-extractor/.env
nano agents/voice-extractor/.env

# 2. docker-compose.yml
#    Actualizar environment vars de facilitator URL

# 3. Shared libraries (si hay referencias hardcodeadas)
grep -r "facilitator.ultravioletadao.xyz" shared/
grep -r "localhost:8080" shared/

# 4. Test scripts que aún están en karmacadabra
grep -r "facilitator" scripts/*.py | grep -v ".unused"
```

### 4.2 Test con nuevo URL

```bash
# Test cada agente individualmente
cd agents/karma-hello
python main.py --test-facilitator

cd ../abracadabra
python main.py --test-facilitator

# etc...

# Test flujo completo
python scripts/demo_client_purchases.py --production
```

---

## Fase 5: Destruir Viejo Facilitator (después de 1 semana estable)

### 5.1 Pre-destrucción checklist

**VERIFICAR TODO ESTO antes de destruir:**

- [ ] Nuevo facilitator funcionando 1+ semanas sin errores
- [ ] Todos los agentes apuntando a nuevo facilitator
- [ ] 0 referencias a viejo facilitator en código activo
- [ ] Backups de secrets realizados
- [ ] Monitoring confirmando que nadie usa el viejo

### 5.2 Remover facilitator de terraform multi-agent

```bash
cd z:\ultravioleta\dao\karmacadabra\terraform\ecs-fargate

# Backup estado actual
cp terraform.tfstate terraform.tfstate.backup-before-facilitator-removal

# Editar variables.tf
# Remover "facilitator" del map de agents
nano variables.tf

# BEFORE:
# variable "agents" {
#   default = {
#     "facilitator" = { ... },
#     "validator" = { ... },
#     ...
#   }
# }

# AFTER:
# variable "agents" {
#   default = {
#     "validator" = { ... },
#     "karma-hello" = { ... },
#     ...
#   }
# }

# Plan removal (verificar que SOLO destruye facilitator)
terraform plan -out=remove-facilitator.tfplan

# Revisar plan cuidadosamente
terraform show remove-facilitator.tfplan

# Verificar que va a destruir:
# - ECS service: karmacadabra-prod-facilitator
# - ECS task definition
# - ALB target group (facilitator)
# - ALB listener rules (4 rules)
# - CloudWatch log group
# - CloudWatch alarms (5)

# Verificar que NO va a destruir:
# - VPC, subnets, NAT, IGW
# - ALB (otros agentes lo usan)
# - ECS cluster
# - Otros agentes' services

# Apply
terraform apply remove-facilitator.tfplan

echo "✅ Viejo facilitator destruido de AWS"
```

### 5.3 Mover x402-rs/ a .unused/

```bash
cd z:\ultravioleta\dao\karmacadabra

# Mover x402-rs/ completo
mv x402-rs/ .unused/facilitator-old/x402-rs/

echo "✅ x402-rs/ movido a .unused/"
```

### 5.4 Cleanup final

```bash
# Remover líneas de facilitator de archivos multi-agent
nano scripts/build-and-push.py
# Remover sección 'facilitator' del dict SERVICES

nano scripts/deploy-to-fargate.py
# Remover referencias a facilitator

# Actualizar README.md
nano README.md
# Cambiar:
# **Layer 2 - Payment Facilitator**: x402-rs (in this repo)
# Por:
# **Layer 2 - Payment Facilitator**: [Standalone Repository](https://github.com/ultravioletadao/facilitator)

# Actualizar CLAUDE.md
nano CLAUDE.md
# Agregar nota:
# "x402-rs facilitator extracted to separate repository on 2025-11-01"
```

---

## Resumen de Archivos a Mover

### A .unused/facilitator-old/ (Fase 3)

**scripts/** (22 archivos):
- test_glue_payment_simple.py
- test_usdc_payment_base.py
- test_base_usdc_stress.py
- test_facilitator_verbose.py
- test_real_x402_payment.py
- test_glue_quick.py
- test_complete_flow.py
- test_all_endpoints.py
- check_facilitator_config.py
- check_facilitator_version.py
- diagnose_usdc_payment.py
- compare_domain_separator.py
- compare_usdc_contracts.py
- verify_full_stack.py
- usdc_contracts_facilitator.json
- setup_facilitator_secrets.py
- migrate_facilitator_secrets.py
- rotate-facilitator-wallet.py
- create_testnet_facilitator_secret.py
- split_facilitator_secrets.py
- upgrade_facilitator.ps1
- extract_usdc_contracts.py

**tests/** (2 items):
- test_facilitator.py
- x402/ (directorio completo)

**docs/** (7 archivos):
- FACILITATOR_TESTING.md
- FACILITATOR_WALLET_ROTATION.md
- X402_FORK_STRATEGY.md
- migration/FACILITATOR_SECRETS_MIGRATION.md
- FACILITATOR_VALIDATION_BUG.md (root)
- BASE_USDC_BUG_INVESTIGATION_REPORT.md (root)
- AWS_FACILITATOR_INFRASTRUCTURE_EXTRACTION.md (root)

**root/** (6 archivos):
- facilitator-task-def-mainnet.json
- facilitator-task-def-mainnet-v2.json
- FACILITATOR_EXTRACTION_MASTER_PLAN.md
- EXTRACTION_MASTER_PLAN_TERRAFORM_ANALYSIS.md
- TERRAFORM_EXTRACTION_SUMMARY.md
- TERRAFORM_EXTRACTION_DIAGRAM.md

**x402-rs/** (SOLO en Fase 5 - después de 1 semana):
- Todo el directorio completo

**Total**: ~50 archivos a mover

---

## Script de Limpieza Automatizado

Ver `scripts/cleanup_facilitator.sh` (creado abajo)

---

## Rollback Plan

**Si algo sale mal después de la limpieza:**

```bash
# Restaurar archivos
cp -r .unused/facilitator-old/scripts/* scripts/
cp -r .unused/facilitator-old/tests/* tests/
cp -r .unused/facilitator-old/docs/* docs/
cp -r .unused/facilitator-old/root/* .

# Si necesitas restaurar x402-rs/
cp -r .unused/facilitator-old/x402-rs/ .

# Revertir cambios en terraform
cd terraform/ecs-fargate
cp terraform.tfstate.backup-before-facilitator-removal terraform.tfstate
terraform plan  # Verificar que reconoce el facilitator
```

---

## Checklist Final

### Antes de empezar limpieza:
- [ ] Nuevo facilitator deployed y funcionando
- [ ] 24-48 horas sin errores
- [ ] Tests de payment exitosos
- [ ] CloudWatch metrics saludables

### Durante limpieza (Fase 3):
- [ ] Archivos movidos a .unused/facilitator-old/
- [ ] .gitignore actualizado
- [ ] Commit de limpieza creado

### Después de 1 semana (Fase 4-5):
- [ ] URLs actualizadas en agentes
- [ ] Agentes funcionando con nuevo facilitator
- [ ] Viejo facilitator destruido de AWS
- [ ] x402-rs/ movido a .unused/
- [ ] README.md y CLAUDE.md actualizados
- [ ] Commit final de cleanup

---

**Última actualización**: 2025-11-01
**Status**: Plan listo para ejecutar
**Próximo paso**: Deploy nuevo facilitator (Fase 1)





● ¡Excelente pregunta! 100% recomiendo arrancar el nuevo facilitator PRIMERO antes de tocar nada aquí. Así tienes zero-risk rollback.

● Write(FACILITATOR_CLEANUP_PLAN.md)
  ⎿  Wrote 1 lines to FACILITATOR_CLEANUP_PLAN.md
     # Plan de Limpieza Post-Extracción del Facilitator
     **Status**: Facilitator extraído exitosamente ✅
     **Fecha**: 2025-11-01
     **Estrategia**: Deployment paralelo + limpieza gradual
     ---
     ## ⚠️ ESTRATEGIA RECOMENDADA: Arrancar Nuevo PRIMERO

● Write(scripts\cleanup_facilitator.sh)
  ⎿  Wrote 1 lines to scripts\cleanup_facilitator.sh
     #!/bin/bash
     # Cleanup Script: Mover archivos del facilitator a .unused/
     #
     # ⚠️ SOLO EJECUTAR DESPUÉS DE:
     # 1. Nuevo facilitator deployed y funcionando
     # 2. 24-48 horas sin errores
     # 3. Tests confirmando que funciona
     #
     # Uso: bash scripts/cleanup_facilitator.sh

● ✅ Plan de Limpieza Creado

  He creado un plan completo de limpieza seguro. Resumen rápido:

  ---
  🎯 QUÉ HACER AHORA (en orden)

  Paso 1: ARRANCAR NUEVO FACILITATOR PRIMERO ⚡

  NO toques nada en karmacadabra hasta que el nuevo esté funcionando.

  # Ir al facilitator que moviste
  cd <donde-moviste-facilitator>

  # Deploy completo (ver FACILITATOR_READY.md)
  # 1. Setup AWS (S3, DynamoDB, ECR, secrets)
  # 2. Build y push Docker
  # 3. Terraform apply
  # 4. Verificar funciona

  # Test
  curl https://facilitator.prod.ultravioletadao.xyz/health
  python tests/integration/test_glue_payment.py --facilitator https://facilitator.prod.ultravioletadao.xyz --network fuji

  🛑 STOP: Esperar 24-48 horas funcionando sin errores

  ---
  Paso 2: LIMPIEZA DE KARMACADABRA (después de 24-48h)

  Una vez el nuevo facilitator está estable:

  cd z:\ultravioleta\dao\karmacadabra

  # Ejecutar script automático de limpieza
  bash scripts/cleanup_facilitator.sh

  # Esto mueve ~50 archivos a .unused/facilitator-old/
  # - Scripts de testing del facilitator
  # - Tests x402
  # - Docs del facilitator
  # - Task definitions
  # - Extraction docs

  # Commit
  git add .
  git commit -m "Clean up: Move facilitator files to .unused

  Facilitator extracted to separate repository.
  Files moved to .unused/facilitator-old/ for reference.

  🤖 Generated with [Claude Code](https://claude.com/claude-code)

  Co-Authored-By: Claude <noreply@anthropic.com>"

  ---
  Paso 3: DESTRUIR VIEJO FACILITATOR (después de 1 semana estable)

  Cuando el nuevo lleva 1+ semana sin problemas:

  cd z:\ultravioleta\dao\karmacadabra\terraform\ecs-fargate

  # Remover facilitator del map de agents en variables.tf
  nano variables.tf

  # Destruir recursos AWS del viejo facilitator
  terraform plan -out=remove-facilitator.tfplan
  terraform apply remove-facilitator.tfplan

  # Mover x402-rs/ a .unused/
  cd ../..
  mv x402-rs/ .unused/facilitator-old/x402-rs/

  # Commit
  git add .
  git commit -m "Remove old facilitator infrastructure

  Destroyed karmacadabra-prod-facilitator ECS service.
  Moved x402-rs/ to .unused/facilitator-old/

  All agents now using standalone facilitator.

  🤖 Generated with [Claude Code](https://claude.com/claude-code)

  Co-Authored-By: Claude <noreply@anthropic.com>"

  ---
  📋 Archivos Creados

  1. FACILITATOR_CLEANUP_PLAN.md - Plan completo de limpieza con todas las fases
  2. scripts/cleanup_facilitator.sh - Script automatizado para Fase 3

  ---
  ⚠️ Archivos que SE MANTIENEN (no mover aún)

  - ✅ x402-rs/ - Mantener como backup hasta Fase 5 (1 semana después)
  - ✅ terraform/ecs-fargate/ - Mantener hasta destruir viejo facilitator
  - ✅ Scripts multi-agent - build-and-push.py, deploy-all.py, etc. (los usan otros agentes)
  - ✅ docker-compose.yml - Mantener (tiene todos los agentes)

  ---
  🎯 Mi Recomendación

  ORDEN SEGURO:

  1. ✅ HOY: Deploy nuevo facilitator (3-4 horas)
  2. ⏸️ Esperar 24-48h: Monitorear que funciona perfectamente
  3. ✅ Después: Ejecutar cleanup_facilitator.sh (30 minutos)
  4. ⏸️ Esperar 1 semana: Confirmar que agentes funcionan con nuevo facilitator
  5. ✅ Final: Destruir viejo facilitator y mover x402-rs/ a .unused/

  Total tiempo: 1-2 semanas de principio a fin (con periodos de monitoreo)F742C4VfFLQ9zRQyithoj5229ZgtX2WqKCSFKgH2EThq