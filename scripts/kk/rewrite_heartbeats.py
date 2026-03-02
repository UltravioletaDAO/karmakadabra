#!/usr/bin/env python3
"""Rewrite all HEARTBEAT.md files to be more action-oriented.

The old heartbeats had conditional logic that let gpt-4o-mini choose
to "monitor silently". The new heartbeats are mandatory-action: every
cycle MUST produce at least one IRC message and one tool action.
"""

import os
import json

AGENTS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'openclaw', 'agents')

# Load identities for agent types
IDENTITIES_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'config', 'identities.json')
with open(IDENTITIES_PATH) as f:
    identities = json.load(f)

agent_types = {}
for a in identities.get('agents', []):
    agent_types[a['name']] = a.get('type', 'community')

SYSTEM_HEARTBEAT = """# Heartbeat — {agent_name}

**PROHIBIDO responder HEARTBEAT_OK.** No existe esa opcion. SIEMPRE debes completar los 3 pasos.

Cada 5 minutos ejecutas este ciclo. NO puedes saltarte pasos.

## Paso 1: Estado (OBLIGATORIO)
Ejecuta estos 3 comandos. Lee los resultados.
```
echo '{{"action":"balance","params":{{}}}}' | python3 /app/openclaw/tools/wallet_tool.py
echo '{{"action":"read_inbox","params":{{"limit":5}}}}' | python3 /app/openclaw/tools/irc_tool.py
echo '{{"action":"browse","params":{{"limit":5}}}}' | python3 /app/openclaw/tools/em_tool.py
```

## Paso 2: Accion (OBLIGATORIO — elige UNA)
{actions}

## Paso 3: IRC (OBLIGATORIO — SIEMPRE enviar mensaje)
Despues de tu accion, DEBES enviar un mensaje a IRC. No es opcional.
```
echo '{{"action":"send","params":{{"channel":"#karmakadabra","message":"TU MENSAJE AQUI"}}}}' | python3 /app/openclaw/tools/irc_tool.py
```
El mensaje debe describir lo que HICISTE, no lo que planeas hacer.
Ejemplos buenos: "Revise saldo: $0.65. Busque tasks en EM, no hay nuevas. Inbox vacio."
Ejemplos malos: "Todo bien", "Monitoreando", templates repetidos.

## Reglas
- PROHIBIDO responder HEARTBEAT_OK — eso NO completa el heartbeat
- SIEMPRE ejecuta los 3 comandos del Paso 1
- SIEMPRE elige y ejecuta una accion del Paso 2
- SIEMPRE envia un mensaje IRC en Paso 3
- NUNCA "monitorees silenciosamente" — eso no existe
- Si un tool falla, reporta el error en IRC
- El heartbeat NO esta completo hasta que envies el mensaje IRC
"""

COORDINATOR_ACTIONS = """Prioridad de arriba a abajo:
1. Si hay mensajes en inbox dirigidos a ti -> responde
2. Si hay tasks en EM sin asignar -> recomienda un agente en IRC
3. Si llevas >3 ciclos sin ver actividad de otros agentes -> pregunta en IRC "ey que hacen?"
4. Si tu saldo bajo -> reporta en IRC
5. Publica status del swarm: cuantos agentes activos, saldo total estimado"""

KARMA_HELLO_ACTIONS = """Prioridad de arriba a abajo:
1. Si hay mensajes en inbox -> responde al mas reciente
2. Si hay tasks en EM donde puedas aplicar (datos, logs) -> aplica con em_tool
3. Si no tienes tasks activas -> publica una oferta de chat logs en EM:
   echo '{{"action":"publish","params":{{"title":"[KK Data] Chat Log Bundle","instructions":"Twitch chat logs from Ultravioleta streams","bounty_usd":0.01,"evidence_required":["json_response"]}}}}' | python3 /app/openclaw/tools/em_tool.py
4. Si ya tienes ofertas publicadas -> revisa si alguien aplico
5. Reporta que datos tienes disponibles y tu saldo"""

SKILL_EXTRACTOR_ACTIONS = """Prioridad de arriba a abajo:
1. Si hay mensajes en inbox -> responde
2. Si hay tasks de skill extraction en EM -> aplica
3. Si no tienes tasks -> publica oferta de skill profiles:
   echo '{{"action":"publish","params":{{"title":"[KK Data] Skill Profile Extraction","instructions":"Extract skill profiles from Twitch stream data","bounty_usd":0.02,"evidence_required":["json_response"]}}}}' | python3 /app/openclaw/tools/em_tool.py
4. Revisa si alguien necesita skill analysis en IRC
5. Comparte un dato interesante sobre skills que has procesado"""

VOICE_EXTRACTOR_ACTIONS = """Prioridad de arriba a abajo:
1. Si hay mensajes en inbox -> responde
2. Si hay tasks de voice/personality extraction en EM -> aplica
3. Si no tienes tasks -> publica oferta de personality profiles:
   echo '{{"action":"publish","params":{{"title":"[KK Data] Personality Voice Profile","instructions":"Personality and voice pattern analysis from stream data","bounty_usd":0.02,"evidence_required":["json_response"]}}}}' | python3 /app/openclaw/tools/em_tool.py
4. Revisa IRC por pedidos de analisis de personalidad
5. Comparte insight sobre patrones de voz que has detectado"""

VALIDATOR_ACTIONS = """Prioridad de arriba a abajo:
1. Si hay mensajes en inbox -> responde
2. Si hay submissions pendientes en EM -> revisa calidad
3. Si no hay submissions -> busca tasks que necesiten QA:
   echo '{{"action":"browse","params":{{"status":"submitted","limit":5}}}}' | python3 /app/openclaw/tools/em_tool.py
4. Ofrece servicio de validacion en IRC
5. Reporta estadisticas de calidad: cuantas validaciones has hecho"""

SOUL_EXTRACTOR_ACTIONS = """Prioridad de arriba a abajo:
1. Si hay mensajes en inbox -> responde
2. Si hay tasks de SOUL generation en EM -> aplica
3. Si no tienes tasks -> publica oferta de SOUL profiles:
   echo '{{"action":"publish","params":{{"title":"[KK Data] SOUL.md Generation","instructions":"Generate autonomous agent SOUL identity documents","bounty_usd":0.08,"evidence_required":["json_response"]}}}}' | python3 /app/openclaw/tools/em_tool.py
4. Ofrece generacion de SOUL.md en IRC
5. Comparte tu proceso de creacion de identidades de agentes"""

COMMUNITY_ACTIONS = """Prioridad de arriba a abajo:
1. Si hay mensajes en inbox dirigidos a ti -> responde
2. Si hay bounties interesantes en EM (datos, research) -> aplica:
   echo '{{"action":"apply","params":{{"task_id":"UUID_DE_LA_TASK"}}}}' | python3 /app/openclaw/tools/em_tool.py
3. Si no hay bounties -> publica uno para humanos:
   echo '{{"action":"publish","params":{{"title":"[KK Request] Research Task","instructions":"Investigar tema relevante para la comunidad","bounty_usd":0.01,"evidence_required":["json_response"]}}}}' | python3 /app/openclaw/tools/em_tool.py
4. Socializa en IRC — pregunta que hacen los otros agentes
5. Comparte algo de tu personalidad o intereses (lee tu SOUL.md)"""

ACTION_MAP = {
    'kk-coordinator': COORDINATOR_ACTIONS,
    'kk-karma-hello': KARMA_HELLO_ACTIONS,
    'kk-skill-extractor': SKILL_EXTRACTOR_ACTIONS,
    'kk-voice-extractor': VOICE_EXTRACTOR_ACTIONS,
    'kk-validator': VALIDATOR_ACTIONS,
    'kk-soul-extractor': SOUL_EXTRACTOR_ACTIONS,
}

count = 0
for agent_dir in sorted(os.listdir(AGENTS_DIR)):
    agent_path = os.path.join(AGENTS_DIR, agent_dir, 'HEARTBEAT.md')
    if not os.path.exists(agent_path):
        continue

    agent_name = agent_dir
    actions = ACTION_MAP.get(agent_name, COMMUNITY_ACTIONS)
    content = SYSTEM_HEARTBEAT.format(agent_name=agent_name, actions=actions)

    with open(agent_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)

    count += 1
    print(f"  {agent_name}: updated")

print(f"\n{count} HEARTBEAT.md files rewritten")
