# Ubicación de las Claves Solana del Facilitator

**Fecha**: 2025-11-01
**Status**: ⚠️ Solo mainnet en AWS Secrets Manager, testnet falta

---

## Estado Actual

### ✅ Solana Mainnet - ENCONTRADO

**Address**: `F742C4VfFLQ9zRQyithoj5229ZgtX2WqKCSFKgH2EThq`

**Ubicación**: AWS Secrets Manager
- **Secret Name**: `karmacadabra-solana-keypair`
- **Region**: us-east-1
- **Description**: "Solana keypair for facilitator (mainnet)"
- **Last Changed**: 2025-10-29 19:01:55

**Estructura del Secret**:
```json
{
  "private_key": "[base64 or array]",
  "public_key": "F742C4VfFLQ9zRQyithoj5229ZgtX2WqKCSFKgH2EThq"
}
```

**Cómo se usa**:
```terraform
# terraform/ecs-fargate/main.tf
data "aws_secretsmanager_secret" "solana_keypair" {
  name = "karmacadabra-solana-keypair"
}

# En el task definition:
secrets = [
  {
    name      = "SOLANA_PRIVATE_KEY"
    valueFrom = "${data.aws_secretsmanager_secret.solana_keypair.arn}:private_key::"
  }
]
```

**Verificar**:
```bash
aws secretsmanager get-secret-value \
  --secret-id karmacadabra-solana-keypair \
  --region us-east-1 \
  --query 'SecretString' \
  | jq -r '.public_key'
# Output: F742C4VfFLQ9zRQyithoj5229ZgtX2WqKCSFKgH2EThq
```

---

### ❌ Solana Devnet/Testnet - NO ENCONTRADO EN AWS

**Address**: `6xNPewUdKRbEZDReQdpyfNUdgNg8QRc8Mt263T5GZSRv`

**Ubicación**: ⚠️ **NO ESTÁ EN AWS SECRETS MANAGER**

**Dónde está documentado**:
- `.unused/notes.txt`: Mencionado como "solana testnet wallet"
- `docs/FACILITATOR_WALLET_ROTATION.md`: Listado como Solana Devnet
- `MASTER_PLAN.md`: Listado como dirección de devnet
- `x402-rs/static/index.html`: Mostrado en la landing page

**Problema**: La clave privada de este wallet **NO ESTÁ** en:
- ❌ AWS Secrets Manager (ningún secret con esta clave)
- ❌ x402-rs/.env (archivo vacío o solo RPC URLs)
- ❌ Terraform configuration

**Implicación**: El facilitator actual probablemente **NO puede hacer pagos en Solana Devnet**, solo en Mainnet.

---

## Investigación Completa

### Secrets en AWS Secrets Manager (todos)

```bash
aws secretsmanager list-secrets --region us-east-1 \
  --query 'SecretList[?contains(Name, `facilitator`) || contains(Name, `solana`)].Name'
```

**Resultado**:
- `karmacadabra-facilitator-mainnet` - EVM chains mainnet (Base, Avalanche, etc.)
- `karmacadabra-facilitator-testnet` - EVM chains testnet (Base Sepolia, Fuji, etc.)
- `karmacadabra-solana-keypair` - **SOLO Solana Mainnet**

**Conclusión**: No hay secret para Solana testnet/devnet.

---

## ¿Por qué funciona Solana en producción?

El facilitator en `https://facilitator.ultravioletadao.xyz/supported` muestra Solana porque:

1. **Solana Mainnet está configurado** ✅
   - Private key en AWS Secrets Manager
   - RPC URL: `https://api.mainnet-beta.solana.com`
   - Funciona para pagos en mainnet

2. **Solana Devnet probablemente NO funciona** ❌
   - No hay private key en AWS
   - Si alguien intenta pagar en devnet, fallará con "missing private key"

**Test rápido**:
```bash
# Check logs del facilitator
aws logs tail /ecs/karmacadabra-prod/facilitator --follow | grep -i "solana\|devnet"

# Si ves errores como "SOLANA_PRIVATE_KEY_DEVNET not found" o similar, confirma que devnet no funciona
```

---

## Solución: Agregar Solana Devnet a AWS Secrets Manager

### Opción 1: Crear nuevo secret separado (RECOMENDADO)

```bash
# Crear secret para devnet
aws secretsmanager create-secret \
  --name karmacadabra-solana-devnet-keypair \
  --description "Solana devnet keypair for facilitator (testnet)" \
  --secret-string '{
    "private_key": "[PRIVATE_KEY_AQUI]",
    "public_key": "6xNPewUdKRbEZDReQdpyfNUdgNg8QRc8Mt263T5GZSRv"
  }' \
  --region us-east-1

# Actualizar terraform para usar este secret en devnet
# (agregar conditional logic para usar mainnet key en mainnet, devnet key en devnet)
```

### Opción 2: Agregar campo devnet al secret existente

```bash
# Actualizar secret existente para tener ambos
aws secretsmanager update-secret \
  --secret-id karmacadabra-solana-keypair \
  --secret-string '{
    "mainnet_private_key": "[MAINNET_KEY]",
    "mainnet_public_key": "F742C4VfFLQ9zRQyithoj5229ZgtX2WqKCSFKgH2EThq",
    "devnet_private_key": "[DEVNET_KEY]",
    "devnet_public_key": "6xNPewUdKRbEZDReQdpyfNUdgNg8QRc8Mt263T5GZSRv"
  }' \
  --region us-east-1

# Actualizar task definition para leer ambos campos
```

### Opción 3: Usar mismo keypair para ambos (NO RECOMENDADO)

Reutilizar el mainnet keypair para devnet. **NO es buena práctica de seguridad**.

---

## Para el Nuevo Facilitator Standalone

Cuando migres a `facilitator.prod.ultravioletadao.xyz`, necesitas:

### 1. Migrar Mainnet Key

```bash
# Exportar mainnet key (SECURE WORKSTATION ONLY!)
aws secretsmanager get-secret-value \
  --secret-id karmacadabra-solana-keypair \
  --region us-east-1 \
  --query 'SecretString' \
  --output text > /tmp/solana-mainnet.json

# Crear en nuevo secret
aws secretsmanager create-secret \
  --name facilitator-solana-mainnet-keypair \
  --description "Facilitator Solana mainnet keypair" \
  --secret-string file:///tmp/solana-mainnet.json \
  --region us-east-1

# Secure delete
shred -vfz -n 10 /tmp/solana-mainnet.json
```

### 2. Agregar Devnet Key (si existe)

**Si encuentras la private key de devnet en algún lado**:

```bash
# Crear secret para devnet
aws secretsmanager create-secret \
  --name facilitator-solana-devnet-keypair \
  --description "Facilitator Solana devnet keypair" \
  --secret-string '{
    "private_key": "[DEVNET_PRIVATE_KEY]",
    "public_key": "6xNPewUdKRbEZDReQdpyfNUdgNg8QRc8Mt263T5GZSRv"
  }' \
  --region us-east-1
```

**Si NO encuentras la private key de devnet**:

Necesitas generar un nuevo keypair o recuperar el original:

```bash
# Opción A: Si tienes la frase semilla (seed phrase)
solana-keygen recover -o devnet-keypair.json

# Opción B: Generar nuevo keypair (NUEVA ADDRESS)
solana-keygen new -o devnet-keypair.json

# Opción C: Si está en un archivo local en algún lado
find ~ -name "*solana*" -name "*.json" 2>/dev/null
```

### 3. Actualizar Terraform del Nuevo Facilitator

```hcl
# facilitator/terraform/environments/production/main.tf

# Mainnet secret
data "aws_secretsmanager_secret" "solana_mainnet" {
  name = "facilitator-solana-mainnet-keypair"
}

# Devnet secret (opcional)
data "aws_secretsmanager_secret" "solana_devnet" {
  name = "facilitator-solana-devnet-keypair"
}

# En task definition:
secrets = [
  {
    name      = "SOLANA_MAINNET_PRIVATE_KEY"
    valueFrom = "${data.aws_secretsmanager_secret.solana_mainnet.arn}:private_key::"
  },
  {
    name      = "SOLANA_DEVNET_PRIVATE_KEY"
    valueFrom = "${data.aws_secretsmanager_secret.solana_devnet.arn}:private_key::"
  }
]
```

### 4. Actualizar Código del Facilitator

El código x402-rs necesitará lógica para elegir qué key usar según la network:

```rust
// src/network.rs o similar
fn get_solana_private_key(network: &SolanaNetwork) -> Result<Keypair> {
    match network {
        SolanaNetwork::Mainnet => {
            env::var("SOLANA_MAINNET_PRIVATE_KEY")
                .expect("SOLANA_MAINNET_PRIVATE_KEY required")
        }
        SolanaNetwork::Devnet => {
            env::var("SOLANA_DEVNET_PRIVATE_KEY")
                .expect("SOLANA_DEVNET_PRIVATE_KEY required")
        }
    }
}
```

---

## Verificación Rápida

```bash
# Ver todos los secrets de Solana
aws secretsmanager list-secrets --region us-east-1 \
  | jq '.SecretList[] | select(.Name | contains("solana")) | {Name, Description}'

# Verificar mainnet key
aws secretsmanager get-secret-value \
  --secret-id karmacadabra-solana-keypair \
  --region us-east-1 \
  --query 'SecretString' \
  | jq -r '.public_key'
# Debe mostrar: F742C4VfFLQ9zRQyithoj5229ZgtX2WqKCSFKgH2EThq

# Buscar devnet key en repo
grep -r "6xNPewUdKRbEZDReQdpyfNUdgNg8QRc8Mt263T5GZSRv" z:/ultravioleta/dao/karmacadabra/ \
  | grep -v ".git" | grep -v "static/index.html" | grep -v "MASTER_PLAN"
# Si solo aparece en docs, la key privada NO ESTÁ en el repo
```

---

## Resumen

| Keypair | Address | Ubicación | Status |
|---------|---------|-----------|--------|
| **Solana Mainnet** | `F742C4VfFLQ9zRQyithoj5229ZgtX2WqKCSFKgH2EThq` | AWS Secrets Manager (`karmacadabra-solana-keypair`) | ✅ ENCONTRADO |
| **Solana Devnet** | `6xNPewUdKRbEZDReQdpyfNUdgNg8QRc8Mt263T5GZSRv` | ⚠️ NO ENCONTRADO | ❌ FALTA |

**Acción Requerida**:
1. Localizar la private key de devnet `6xNPewUdKRbEZDReQdpyfNUdgNg8QRc8Mt263T5GZSRv`
2. Crear secret en AWS: `karmacadabra-solana-devnet-keypair` (o `facilitator-solana-devnet-keypair` para el nuevo)
3. Actualizar terraform y código para usar la key correcta según la network

---

**Última actualización**: 2025-11-01
