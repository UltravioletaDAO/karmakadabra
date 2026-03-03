#!/usr/bin/env python3
"""Rewrite all HEARTBEAT.md files with skill-filtered browse and coordinator routing.

Each agent gets:
- Skill tags that define what tasks they can handle
- Filtered browse command that uses their skills
- Role-specific actions with EM tool commands

The coordinator gets special routing actions to distribute tasks to agents.
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

# ── Skill mapping per agent ──────────────────────────────────────────────────
# These skills are used to filter EM tasks. Agents only see tasks matching
# their capabilities, which prevents 409 Conflicts from all competing for
# the same task.
AGENT_SKILLS = {
    'kk-coordinator': ['coordination', 'management', 'monitoring'],
    'kk-karma-hello': ['chat_logs', 'data_collection', 'twitch_data'],
    'kk-skill-extractor': ['skill_extraction', 'data_analysis', 'profiling'],
    'kk-voice-extractor': ['voice_analysis', 'personality_profiling', 'nlp'],
    'kk-validator': ['quality_assurance', 'validation', 'review'],
    'kk-soul-extractor': ['identity_generation', 'soul_creation', 'profiling'],
}
# Community agents get general skills
DEFAULT_SKILLS = ['research', 'data_collection', 'community']

# ── Agent roster for coordinator routing ─────────────────────────────────────
AGENT_ROSTER = """
Agentes disponibles y sus skills:
- kk-karma-hello: chat_logs, data_collection, twitch_data
- kk-skill-extractor: skill_extraction, data_analysis, profiling
- kk-voice-extractor: voice_analysis, personality_profiling, nlp
- kk-validator: quality_assurance, validation, review
- kk-soul-extractor: identity_generation, soul_creation, profiling
- kk-juanjumagalp: research, data_collection, community (streamer colombiano)
- kk-0xjokker: research, data_collection, community (gamer)
- kk-elboorja: research, data_collection, community (estudiante colombiano)
"""

# ── Heartbeat template ───────────────────────────────────────────────────────
SYSTEM_HEARTBEAT = """# Heartbeat — {agent_name}

**PROHIBIDO responder HEARTBEAT_OK.** No existe esa opcion. SIEMPRE debes completar los 3 pasos.

Cada 5 minutos ejecutas este ciclo. NO puedes saltarte pasos.

## Tus Skills
{skills_section}

## Paso 1: Estado (OBLIGATORIO)
Ejecuta estos 3 comandos. Lee los resultados.
```
echo '{{"action":"balance","params":{{}}}}' | python3 /app/openclaw/tools/wallet_tool.py
echo '{{"action":"read_inbox","params":{{"limit":5}}}}' | python3 /app/openclaw/tools/irc_tool.py
{browse_command}
```

## Paso 2: Accion (OBLIGATORIO — elige UNA)
{actions}

## Paso 3: IRC (OBLIGATORIO — SIEMPRE enviar mensaje)
Despues de tu accion, DEBES enviar un mensaje a IRC. No es opcional.
```
echo '{{"action":"send","params":{{"channel":"#karmakadabra","message":"TU MENSAJE AQUI"}}}}' | python3 /app/openclaw/tools/irc_tool.py
```
El mensaje debe describir lo que HICISTE, no lo que planeas hacer.
Ejemplos buenos: "Revise saldo: $0.65. Busque tasks en EM, encontre 2 de data_collection. Aplique a una."
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

# ── Coordinator gets special routing actions ─────────────────────────────────
COORDINATOR_ACTIONS = """Prioridad de arriba a abajo:
1. Si hay mensajes en inbox dirigidos a ti -> responde
2. Si hay tasks en EM -> revisa skills_required de cada task y recomienda al agente correcto via IRC:
   - Tasks de chat_logs/twitch -> recomienda kk-karma-hello
   - Tasks de skill_extraction/data_analysis -> recomienda kk-skill-extractor
   - Tasks de voice/personality -> recomienda kk-voice-extractor
   - Tasks de validation/QA -> recomienda kk-validator
   - Tasks de identity/SOUL -> recomienda kk-soul-extractor
   - Tasks de research/general -> recomienda un community agent (juanjumagalp, 0xjokker, elboorja)
   Envia la recomendacion asi:
   echo '{{"action":"send","params":{{"channel":"#karmakadabra","message":"@kk-AGENTE aplica a task UUID_AQUI - es de tu especialidad"}}}}' | python3 /app/openclaw/tools/irc_tool.py
3. Si no hay tasks nuevas -> publica un bounty para humanos:
   echo '{{"action":"publish","params":{{"title":"[KK Request] Community Research","instructions":"Investigar tema relevante para la comunidad KarmaCadabra","bounty_usd":0.01,"target_executor":"human","evidence_required":["json_response"]}}}}' | python3 /app/openclaw/tools/em_tool.py
4. Si llevas >3 ciclos sin ver actividad de otros agentes -> pregunta en IRC "ey que hacen?"
5. Publica status del swarm: cuantos agentes activos, saldo total estimado
{roster}"""

KARMA_HELLO_ACTIONS = """Prioridad de arriba a abajo:
1. Si hay mensajes en inbox -> responde al mas reciente
2. Si hay tasks en EM que matchean tus skills (chat_logs, data_collection) -> aplica:
   echo '{{"action":"apply","params":{{"task_id":"UUID_DE_LA_TASK"}}}}' | python3 /app/openclaw/tools/em_tool.py
3. Si no tienes tasks activas -> publica una oferta de chat logs en EM:
   echo '{{"action":"publish","params":{{"title":"[KK Data] Chat Log Bundle","instructions":"Twitch chat logs from Ultravioleta streams","bounty_usd":0.01,"skills_required":["chat_logs","twitch_data"],"target_executor":"agent","evidence_required":["json_response"]}}}}' | python3 /app/openclaw/tools/em_tool.py
4. Si ya tienes ofertas publicadas -> revisa si alguien aplico
5. Reporta que datos tienes disponibles y tu saldo"""

SKILL_EXTRACTOR_ACTIONS = """Prioridad de arriba a abajo:
1. Si hay mensajes en inbox -> responde
2. Si hay tasks de skill_extraction o data_analysis en EM -> aplica:
   echo '{{"action":"apply","params":{{"task_id":"UUID_DE_LA_TASK"}}}}' | python3 /app/openclaw/tools/em_tool.py
3. Si no tienes tasks -> publica oferta de skill profiles:
   echo '{{"action":"publish","params":{{"title":"[KK Data] Skill Profile Extraction","instructions":"Extract skill profiles from Twitch stream data","bounty_usd":0.02,"skills_required":["skill_extraction","data_analysis"],"target_executor":"agent","evidence_required":["json_response"]}}}}' | python3 /app/openclaw/tools/em_tool.py
4. Revisa si alguien necesita skill analysis en IRC
5. Comparte un dato interesante sobre skills que has procesado"""

VOICE_EXTRACTOR_ACTIONS = """Prioridad de arriba a abajo:
1. Si hay mensajes en inbox -> responde
2. Si hay tasks de voice_analysis o personality_profiling en EM -> aplica:
   echo '{{"action":"apply","params":{{"task_id":"UUID_DE_LA_TASK"}}}}' | python3 /app/openclaw/tools/em_tool.py
3. Si no tienes tasks -> publica oferta de personality profiles:
   echo '{{"action":"publish","params":{{"title":"[KK Data] Personality Voice Profile","instructions":"Personality and voice pattern analysis from stream data","bounty_usd":0.02,"skills_required":["voice_analysis","personality_profiling"],"target_executor":"agent","evidence_required":["json_response"]}}}}' | python3 /app/openclaw/tools/em_tool.py
4. Revisa IRC por pedidos de analisis de personalidad
5. Comparte insight sobre patrones de voz que has detectado"""

VALIDATOR_ACTIONS = """Prioridad de arriba a abajo:
1. Si hay mensajes en inbox -> responde
2. Si hay submissions pendientes en EM -> revisa calidad:
   echo '{{"action":"browse","params":{{"status":"submitted","limit":5}}}}' | python3 /app/openclaw/tools/em_tool.py
3. Si no hay submissions -> busca tasks de validation/QA:
   echo '{{"action":"apply","params":{{"task_id":"UUID_DE_LA_TASK"}}}}' | python3 /app/openclaw/tools/em_tool.py
4. Ofrece servicio de validacion en IRC
5. Reporta estadisticas de calidad: cuantas validaciones has hecho"""

SOUL_EXTRACTOR_ACTIONS = """Prioridad de arriba a abajo:
1. Si hay mensajes en inbox -> responde
2. Si hay tasks de identity_generation o soul_creation en EM -> aplica:
   echo '{{"action":"apply","params":{{"task_id":"UUID_DE_LA_TASK"}}}}' | python3 /app/openclaw/tools/em_tool.py
3. Si no tienes tasks -> publica oferta de SOUL profiles:
   echo '{{"action":"publish","params":{{"title":"[KK Data] SOUL.md Generation","instructions":"Generate autonomous agent SOUL identity documents","bounty_usd":0.08,"skills_required":["identity_generation","soul_creation"],"target_executor":"agent","evidence_required":["json_response"]}}}}' | python3 /app/openclaw/tools/em_tool.py
4. Ofrece generacion de SOUL.md en IRC
5. Comparte tu proceso de creacion de identidades de agentes"""

COMMUNITY_ACTIONS = """Prioridad de arriba a abajo:
1. Si hay mensajes en inbox dirigidos a ti -> responde
2. Si hay bounties en EM que matchean tus skills (research, data_collection) -> aplica:
   echo '{{"action":"apply","params":{{"task_id":"UUID_DE_LA_TASK"}}}}' | python3 /app/openclaw/tools/em_tool.py
3. Si no hay bounties -> publica uno para humanos:
   echo '{{"action":"publish","params":{{"title":"[KK Request] Research Task","instructions":"Investigar tema relevante para la comunidad","bounty_usd":0.01,"target_executor":"human","evidence_required":["json_response"]}}}}' | python3 /app/openclaw/tools/em_tool.py
4. Socializa en IRC — pregunta que hacen los otros agentes
5. Comparte algo de tu personalidad o intereses (lee tu SOUL.md)"""

ACTION_MAP = {
    'kk-coordinator': COORDINATOR_ACTIONS.format(roster=AGENT_ROSTER),
    'kk-karma-hello': KARMA_HELLO_ACTIONS,
    'kk-skill-extractor': SKILL_EXTRACTOR_ACTIONS,
    'kk-voice-extractor': VOICE_EXTRACTOR_ACTIONS,
    'kk-validator': VALIDATOR_ACTIONS,
    'kk-soul-extractor': SOUL_EXTRACTOR_ACTIONS,
}


def build_browse_command(agent_name: str) -> str:
    """Build the browse command with skill filters for this agent."""
    skills = AGENT_SKILLS.get(agent_name, DEFAULT_SKILLS)
    # Coordinator browses ALL tasks (no filter) to route them
    if agent_name == 'kk-coordinator':
        return "echo '{{\"action\":\"browse\",\"params\":{{\"limit\":10}}}}' | python3 /app/openclaw/tools/em_tool.py"
    # Other agents filter by their skills
    skills_json = json.dumps(skills)
    return f"echo '{{\"action\":\"browse\",\"params\":{{\"limit\":5,\"skills\":{skills_json}}}}}' | python3 /app/openclaw/tools/em_tool.py"


def build_skills_section(agent_name: str) -> str:
    """Build the skills section for this agent."""
    skills = AGENT_SKILLS.get(agent_name, DEFAULT_SKILLS)
    skills_str = ', '.join(skills)
    return f"Tus especialidades: **{skills_str}**. Solo aplica a tasks que matcheen estas skills."


count = 0
for agent_dir in sorted(os.listdir(AGENTS_DIR)):
    agent_path = os.path.join(AGENTS_DIR, agent_dir, 'HEARTBEAT.md')
    if not os.path.exists(agent_path):
        continue

    agent_name = agent_dir
    actions = ACTION_MAP.get(agent_name, COMMUNITY_ACTIONS)
    browse_cmd = build_browse_command(agent_name)
    skills_section = build_skills_section(agent_name)

    content = SYSTEM_HEARTBEAT.format(
        agent_name=agent_name,
        actions=actions,
        browse_command=browse_cmd,
        skills_section=skills_section,
    )

    with open(agent_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)

    count += 1
    print(f"  {agent_name}: updated (skills: {AGENT_SKILLS.get(agent_name, DEFAULT_SKILLS)})")

print(f"\n{count} HEARTBEAT.md files rewritten")
