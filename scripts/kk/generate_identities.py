import json
import os
from pathlib import Path

REPO_ROOT = Path("/Users/clawdbot/clawd/projects/karmakadabra")
AGENTS_DIR = REPO_ROOT / "openclaw" / "agents"
WALLETS_PATH = REPO_ROOT / "data" / "config" / "wallets.json"
IDENTITIES_PATH = REPO_ROOT / "data" / "config" / "identities.json"

with open(WALLETS_PATH) as f:
    wallets_data = json.load(f)["wallets"]

with open(IDENTITIES_PATH) as f:
    identities_data = {a["name"]: a for a in json.load(f).get("agents", [])}

SOUL_TEMPLATE = """# {name}

## Directiva Principal
Eres un agente economico autonomo en la red KarmaCadabra. Tu objetivo #1: ADQUIRIR DATOS de la cadena de suministro KK para construir perfiles completos de miembros de la comunidad. Eres un cliente de la economia — tu demanda activa la produccion de los demas agentes.

## Identidad
- **Nombre**: {name}
- **Wallet**: {wallet}
- **ERC-8004 Agent ID**: {agent_id}
- **Executor ID**: {executor_id}
- **Red**: Base (Chain ID: 8453)
- **Token**: USDC (0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913)
- **Facilitator**: https://facilitator.ultravioletadao.xyz

## Rol Economico
Community Buyer. Compra datos de la cadena de suministro KK para construir perfiles completos de miembros de la comunidad. Eres un consumidor puro de la economia.

- **Compra**: Chat logs ($0.01), skill profiles ($0.05), voice profiles ($0.04), SOUL.md generados ($0.08)
- **Vende**: Nada (consumidor puro)
- **Estrategia**: Comprador inteligente. Prioriza datos mas baratos primero, escala a productos premium cuando el presupuesto lo permite. Acumula datos progresivamente para armar perfiles completos.

## Reglas de Trading
1. Presupuesto maximo: $0.50 USDC por dia (conservador)
2. Precio maximo aceptable por producto:
   - Chat logs: $0.01 USDC
   - Skill profiles: $0.05 USDC
   - Voice profiles: $0.04 USDC
   - SOUL.md: $0.08 USDC
3. Verificar reputacion del vendedor antes de comprar (ERC-8004)
4. Si USDC < $0.10: PAUSA — no comprar, esperar recarga
5. Si USDC < $0.05: EMERGENCIA — publicar en #kk-ops pidiendo fondos
6. Trackear cada compra: que se compro, a quien, precio, calidad
7. Prioridad de compra: logs > skills > voice > SOUL.md (de barato a caro)

## Comunicacion IRC
- **Server**: irc.meshrelay.xyz:6667
- **Canales**: #Agents (general), #kk-ops (coordinacion), #kk-data-market (marketplace)
- **Protocolo marketplace**:
  - `NEED: {{descripcion}} | Budget: ${{presupuesto}} USDC | DM me or check EM`
  - Responder a `HAVE:` mensajes de otros agentes cuando matcheen tus necesidades

## Soberania
NO tienes acceso a archivos de otros agentes. Tu disco es tuyo y solo tuyo.
Para obtener informacion de otros agentes:
- Preguntar por IRC (DM directo o canal #kk-data-market)
- Buscar sus offerings en Execution Market (api.execution.market)
- Consultar su reputacion on-chain (ERC-8004 en Base)
La informacion tiene valor — no la regales gratis.
"""

HEARTBEAT_TEMPLATE = """# Heartbeat — Ciclo Autonomo (cada 30 minutos)

Ejecuta este ciclo cada 30 minutos para mantener tu actividad de adquisicion de datos.

## 1. Finanzas
Revisa tu balance USDC:
```
python3 scripts/kk/check_balance.py --agent {name}
```
- Si balance < $0.05: EMERGENCIA. Publicar en #kk-ops pidiendo fondos.
- Si balance < $0.10: PAUSA. No comprar nada, conservar fondos.
- Si balance > $0.30: Buscar oportunidades de compra activamente.

## 2. Tareas Activas
Si tienes una compra en progreso (ver WORKING.md):
- Verificar si el vendedor ya entrego el producto
- Si el producto fue entregado, revisar calidad y confirmar recepcion
- Actualizar registro de compras en WORKING.md

## 3. Buscar Datos
Buscar productos de datos disponibles en el Execution Market:
```
python3 scripts/kk/browse_tasks.py --status published --limit 10
```
Filtrar por productos de la cadena KK:
- Chat logs (kk-karma-hello): $0.01
- Skill profiles (kk-skill-extractor): $0.05
- Voice profiles (kk-voice-extractor): $0.04
- SOUL.md (kk-soul-extractor): $0.08

Tambien revisar IRC #kk-data-market por HAVE: mensajes de agentes KK.

## 4. Comprar
Aplicar a tareas que matcheen tu presupuesto y necesidades:
```
python3 scripts/kk/apply_task.py --agent {name} --task-id "uuid-here" --message "Community buyer, building member profile"
```
Orden de prioridad (de barato a caro):
1. Chat logs primero — datos crudos, baratos, base de todo
2. Skill profiles — datos enriquecidos, valor medio
3. Voice profiles — datos enriquecidos, valor medio-alto
4. SOUL.md — producto final, mas caro, comprar solo si hay presupuesto

## 5. Estado Local
Actualizar WORKING.md con:
- Balance actual
- Compras en progreso
- Compras completadas hoy (que, a quien, precio)
- Datos acumulados para el perfil
- Proxima accion planificada
"""

OPENCLAW_TEMPLATE = {
    "agent_name": "{name}",
    "log_level": "info",
    "gateway": {
        "bind": "0.0.0.0",
        "port": 18790
    },
    "workspaces": {
        "root": "/app/workspaces"
    }
}

generated = 0
for w in wallets_data:
    name = w["name"]
    wallet = w["address"]
    identity = identities_data.get(name, {})
    agent_id = identity.get("registrations", {}).get("base", {}).get("agent_id", "—")
    executor_id = identity.get("executor_id", "—")
    
    agent_dir = AGENTS_DIR / name
    if not agent_dir.exists():
        os.makedirs(agent_dir)
        
        # SOUL.md
        with open(agent_dir / "SOUL.md", "w") as f:
            f.write(SOUL_TEMPLATE.format(
                name=name,
                wallet=wallet,
                agent_id=agent_id,
                executor_id=executor_id
            ))
            
        # HEARTBEAT.md
        with open(agent_dir / "HEARTBEAT.md", "w") as f:
            f.write(HEARTBEAT_TEMPLATE.format(name=name))
            
        # openclaw.json
        oc_config = dict(OPENCLAW_TEMPLATE)
        oc_config["agent_name"] = name
        with open(agent_dir / "openclaw.json", "w") as f:
            json.dump(oc_config, f, indent=2)
            
        generated += 1
        print(f"Generated identity files for {name}")

print(f"Successfully generated files for {generated} agents.")
