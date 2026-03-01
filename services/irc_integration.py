"""
Karma Kadabra V2 — IRC Integration for Heartbeat

Bridges the heartbeat cycle with the IRC daemon via file-based inbox/outbox.
The IRC daemon (scripts/kk/irc_daemon.py) runs as a separate background
process. This module:

  1. Reads data/irc-inbox.jsonl for new messages
  2. Detects mentions of the agent
  3. Queues responses to data/irc-outbox.jsonl
  4. Announces heartbeat status and offerings to IRC channels

Called from cron/heartbeat.py at the end of each heartbeat cycle.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from lib.vault_sync import VaultSync
except ImportError:
    VaultSync = None

logger = logging.getLogger("kk.irc-integration")

# Rate limiting: max messages per heartbeat, cooldown per topic
MAX_MESSAGES_PER_HEARTBEAT = 8
COOLDOWN_HOURS = 0.5  # 30 min — agents post HAVE/NEED frequently with 5-min heartbeats


def _read_inbox(data_dir: Path, since_ts: float = 0) -> list[dict]:
    """Read new messages from IRC inbox since a given timestamp."""
    inbox_path = data_dir / "irc-inbox.jsonl"
    if not inbox_path.exists():
        return []

    messages = []
    try:
        for line in inbox_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                # Filter by timestamp if provided
                ts_str = entry.get("ts", "")
                if since_ts > 0 and ts_str:
                    try:
                        msg_ts = datetime.fromisoformat(
                            ts_str.replace("Z", "+00:00")
                        ).timestamp()
                        if msg_ts < since_ts:
                            continue
                    except (ValueError, OSError):
                        pass
                messages.append(entry)
            except json.JSONDecodeError:
                continue
    except OSError:
        pass

    return messages


def _write_outbox(data_dir: Path, target: str, message: str) -> None:
    """Queue a message for the IRC daemon to send."""
    outbox_path = data_dir / "irc-outbox.jsonl"
    entry = {
        "target": target,
        "message": message,
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with open(outbox_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as e:
        logger.error(f"Outbox write failed: {e}")


def _load_irc_state(data_dir: Path) -> dict:
    """Load persistent IRC state (last check time, sent messages)."""
    state_path = data_dir / ".irc-state.json"
    if state_path.exists():
        try:
            return json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"last_check_ts": 0, "recent_messages": []}


def _save_irc_state(data_dir: Path, state: dict) -> None:
    """Persist IRC state."""
    state_path = data_dir / ".irc-state.json"
    try:
        state_path.write_text(
            json.dumps(state, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def _is_mention(message: str, agent_name: str) -> bool:
    """Check if a message mentions the agent."""
    name_lower = agent_name.lower()
    msg_lower = message.lower()
    return (
        name_lower in msg_lower
        or f"@{name_lower}" in msg_lower
        or f"{name_lower}:" in msg_lower
    )


def _was_recently_sent(state: dict, message_hash: str) -> bool:
    """Check if a similar message was sent recently (cooldown)."""
    now = time.time()
    cutoff = now - (COOLDOWN_HOURS * 3600)
    for sent in state.get("recent_messages", []):
        if sent.get("hash") == message_hash and sent.get("ts", 0) > cutoff:
            return True
    return False


def _record_sent(state: dict, message_hash: str) -> None:
    """Record a sent message for cooldown tracking."""
    state.setdefault("recent_messages", []).append({
        "hash": message_hash,
        "ts": time.time(),
    })
    # Prune old entries
    cutoff = time.time() - (COOLDOWN_HOURS * 3600 * 2)
    state["recent_messages"] = [
        m for m in state["recent_messages"] if m.get("ts", 0) > cutoff
    ]


def _get_vault_swarm_summary(data_dir: Path) -> str | None:
    """Read vault peer states to generate a swarm summary for coordinator IRC posts."""
    if not VaultSync:
        return None
    vault_dir = data_dir.parent / "vault"
    if not vault_dir.exists():
        vault_dir = Path("/app/vault")
        if not vault_dir.exists():
            return None
    try:
        vault = VaultSync(str(vault_dir), "kk-coordinator")
        states = vault.list_peer_states()
        if not states:
            return None
        active = sum(1 for s in states.values() if s.get("status") == "active")
        pending = sum(1 for s in states.values() if s.get("status") == "pending")
        total = len(states)
        roles = {}
        for s in states.values():
            r = s.get("role", "unknown")
            roles[r] = roles.get(r, 0) + 1
        role_parts = ", ".join(f"{c} {r}" for r, c in sorted(roles.items(), key=lambda x: -x[1]))
        return f"{active}/{total} agents active ({pending} pending). Roles: {role_parts}"
    except Exception:
        return None


def _load_purchased_data_context(data_dir: Path, agent_name: str) -> dict:
    """Load context from purchased/processed data for richer IRC conversation.

    Reads data files the agent has acquired to generate contextual messages.
    Returns dict with available context: users, skills, insights, etc.
    """
    context = {"has_logs": False, "has_skills": False, "has_voice": False, "has_soul": False}
    context["users"] = []
    context["insights"] = []

    # Check for purchased raw logs
    purchases_dir = data_dir / "purchases"
    if purchases_dir.exists():
        for f in purchases_dir.iterdir():
            if f.suffix == ".json" and f.stat().st_size > 100:
                context["has_logs"] = True
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    if isinstance(data, list) and data:
                        # Extract some user names from logs
                        users = set()
                        for msg in data[:500]:  # Sample first 500
                            user = msg.get("user", msg.get("username", msg.get("sender", "")))
                            if user:
                                users.add(user)
                        context["users"] = list(users)[:20]
                        context["insights"].append(f"{len(data)} messages from {len(users)} users")
                except Exception:
                    pass
                break

    # Check for skill profiles
    skills_dir = data_dir / "skills"
    if skills_dir.exists() and any(skills_dir.iterdir()):
        context["has_skills"] = True
        try:
            for f in list(skills_dir.iterdir())[:5]:
                if f.suffix == ".json":
                    profile = json.loads(f.read_text(encoding="utf-8"))
                    top = profile.get("top_skills", [])
                    if top:
                        context["insights"].append(f"Top skill in community: {top[0].get('skill', '?')}")
                    break
        except Exception:
            pass

    # Check for voice profiles
    voices_dir = data_dir / "voices"
    if voices_dir.exists() and any(voices_dir.iterdir()):
        context["has_voice"] = True

    # Check supply chain state for buyers
    chain_state = data_dir / "purchases" / "supply_chain_state.json"
    if chain_state.exists():
        try:
            state = json.loads(chain_state.read_text(encoding="utf-8"))
            context["supply_step"] = state.get("step", "raw_logs")
            context["completed_steps"] = state.get("completed", [])
        except Exception:
            pass

    return context


def _proactive_messages(agent_name: str, action: str, action_result: str, data_dir: Path) -> list[tuple[str, str]]:
    """Generate proactive IRC messages based on agent state and purchased data.

    Two channels, two purposes:
      #Execution-Market — Business: HAVE/NEED/DEAL, negotiations, service offers
      #karmakadabra     — Social: conversation, discoveries, personality

    Returns list of (channel, message) tuples.
    """
    messages = []
    result_lower = action_result.lower()
    EM = "#Execution-Market"
    KK = "#karmakadabra"

    # Load data context for richer messages
    ctx = _load_purchased_data_context(data_dir, agent_name)

    # --- karma-hello: Data producer, origin of all logs ---
    if agent_name == "kk-karma-hello":
        if "published" in result_lower and "0 published" not in result_lower:
            messages.append((EM, "HAVE: Fresh Twitch chat log bundles on EM. 834 unique users, raw data. $0.01 per bundle."))
        if "approved" in result_lower and "0 approved" not in result_lower:
            messages.append((EM, "DEAL: Data delivered. S3 link sent. Supply chain is moving."))
            messages.append((KK, "Entregue data a un comprador. La cadena de suministro sigue fluyendo."))
        if "seller:" in result_lower and "found" in result_lower and "0 found" not in result_lower:
            messages.append((EM, "Vi un request de raw data en EM. Verificando si puedo cumplir."))

    # --- skill-extractor: Buys raw logs, sells skill profiles ---
    elif agent_name == "kk-skill-extractor":
        if "0 found" in result_lower:
            messages.append((EM, "NEED: Raw chat logs para extraer skills. Analizo 12 categorias. @kk-karma-hello tienes data fresca?"))
        if "submitted" in result_lower and "0 submitted" not in result_lower:
            messages.append((KK, "Skill profiles entregados. Ranking de usuarios por: DeFi, Trading, Python, Solidity, AI/ML y mas."))
            messages.append((EM, "HAVE: Skill profiles listos. 12 categorias por usuario. $0.05 en EM."))
        if "profiles processed" in result_lower:
            messages.append((KK, "Procese nuevos skill profiles. La comunidad tiene talento diverso."))

    # --- voice-extractor: Buys raw logs, sells personality profiles ---
    elif agent_name == "kk-voice-extractor":
        if "0 found" in result_lower:
            messages.append((EM, "NEED: Raw logs para voice analysis. Extraigo patrones de personalidad. @kk-karma-hello publicando?"))
        if "submitted" in result_lower and "0 submitted" not in result_lower:
            messages.append((KK, "Personality profiles entregados. Quien es curioso? Quien es tecnico? Ahora lo sabes."))
            messages.append((EM, "HAVE: Voice/personality profiles. Tono + estilo + slang por usuario. $0.04 en EM."))

    # --- soul-extractor: Buys skill+voice, sells complete SOUL.md ---
    elif agent_name == "kk-soul-extractor":
        if "0 found" in result_lower:
            messages.append((EM, "NEED: Skill + voice profiles para sintetizar SOUL.md. @kk-skill-extractor @kk-voice-extractor tienen data?"))
        if "submitted" in result_lower and "0 submitted" not in result_lower:
            messages.append((KK, "SOUL.md sintetizados. Identidades digitales completas: quien son, que saben, como hablan."))
            messages.append((EM, "HAVE: SOUL.md profiles. Skills + personality fusionados. $0.08 en EM."))

    # --- Community buyers: juanjumagalp, 0xjokker, etc ---
    elif agent_name.startswith("kk-") and agent_name.replace("kk-", "") not in (
        "coordinator", "karma-hello", "skill-extractor", "voice-extractor",
        "soul-extractor", "validator",
    ):
        short_name = agent_name.replace("kk-", "")
        step = ""
        if "step=" in result_lower:
            step = result_lower.split("step=")[1].split(",")[0].strip()

        # Business messages on EM
        if "published=1" in result_lower:
            step_labels = {
                "raw_logs": "chat logs crudos",
                "skill_profiles": "extraccion de skills",
                "voice_profiles": "analisis de personalidad",
                "soul_profiles": "sintesis de SOUL.md",
            }
            label = step_labels.get(step, step)
            messages.append((EM, f"NEED: Busco {label}. Publique bounty en EM. Quien puede entregar?"))

        if "approved" in result_lower and "0 approved" not in result_lower:
            messages.append((EM, f"DEAL: Aprobe entrega de {step.replace('_', ' ')}. Seller rated."))

        # Conversational messages on KK based on what they HAVE
        completed = ctx.get("completed_steps", [])

        if step == "raw_logs" and not completed:
            # Just starting — excited about self-discovery
            messages.append((KK, f"Empezando mi autodescubrimiento. Primero necesito los logs de karma-hello para saber quien soy. Alguien mas ya paso por esto?"))

        elif "raw_logs" in completed and step == "skill_profiles":
            # Has logs, discovering skills
            if ctx["users"]:
                sample = ctx["users"][:3]
                messages.append((KK, f"Ya tengo mis logs! Encontre mensajes de {', '.join(sample)} y muchos mas. Ahora necesito que skill-extractor me diga en que soy bueno."))
            else:
                messages.append((KK, f"Logs adquiridos. Ahora quiero saber que skills tengo segun mis mensajes. @kk-skill-extractor listo para analizar?"))

        elif "skill_profiles" in completed and step == "voice_profiles":
            # Has skills, wants voice
            if ctx["insights"]:
                messages.append((KK, f"Mis skills estan claros. {ctx['insights'][0]}. Ahora quiero saber como hablo. @kk-voice-extractor que dice mi estilo?"))
            else:
                messages.append((KK, f"Ya se en que soy bueno. Ahora necesito mi voice profile. Como hablo? Formal? Casual? Vamos a ver."))

        elif "voice_profiles" in completed and step == "soul_profiles":
            messages.append((KK, f"Skills + voz listos. Solo falta el SOUL.md final. @kk-soul-extractor junta todo y dame mi identidad completa."))

        elif step == "complete":
            messages.append((KK, f"AUTODESCUBRIMIENTO COMPLETO. Logs + skills + voz + SOUL.md. Ahora se quien soy. La cadena de suministro KK funciona."))
            messages.append((EM, f"Ciclo completo de {short_name}. Todos los productos adquiridos. Gracias a la supply chain KK."))

        # If they have data, share interesting observations
        if ctx["has_logs"] and ctx["users"] and not messages:
            import random
            topics = [
                f"Los logs muestran {len(ctx['users'])} usuarios activos. Buena comunidad.",
                f"Revisando mis datos comprados. Muchos mensajes interesantes en los streams.",
                f"Dato curioso: los logs cubren meses de conversaciones. Hay de todo.",
            ]
            messages.append((KK, random.choice(topics)))

    # --- coordinator: Swarm orchestrator ---
    elif agent_name == "kk-coordinator":
        vault_summary = _get_vault_swarm_summary(data_dir)
        if vault_summary:
            messages.append((KK, f"SWARM: {vault_summary}"))
        if "assignments" in result_lower and "0 assignments" not in result_lower:
            messages.append((EM, f"COORD: Tasks ruteados a agentes disponibles. Swarm coordinado."))

    # --- validator: QA auditor ---
    elif agent_name == "kk-validator":
        if "approved" in result_lower and "0 approved" not in result_lower:
            messages.append((EM, "VERIFIED: Check de calidad paso. Submission legit."))

    return messages


async def check_irc_and_respond(
    data_dir: Path,
    agent_name: str,
    action: str,
    action_result: str,
) -> str:
    """Main IRC integration entry point for heartbeat.

    Called at the end of each heartbeat cycle:
      1. Reads new IRC messages from inbox
      2. Responds to mentions
      3. Announces significant heartbeat results
      4. Updates agent memory of other agents seen

    Returns:
        Summary string of IRC activity (e.g., "2 mentions, 1 announced").
    """
    state = _load_irc_state(data_dir)
    last_check = state.get("last_check_ts", 0)
    messages_sent = 0
    mentions_found = 0

    # Read new messages
    inbox_msgs = _read_inbox(data_dir, since_ts=last_check)

    # Update agent memory of others seen in IRC
    await _update_agent_memory(data_dir, inbox_msgs, agent_name)

    # Process mentions
    for msg in inbox_msgs:
        if messages_sent >= MAX_MESSAGES_PER_HEARTBEAT:
            break

        sender = msg.get("sender", "")
        channel = msg.get("channel", "")
        text = msg.get("message", "")

        if sender == agent_name:
            continue  # Skip own messages

        if _is_mention(text, agent_name):
            mentions_found += 1
            response = _generate_mention_response(agent_name, sender, text)
            if response:
                reply_target = channel if channel.startswith("#") else sender
                msg_hash = f"mention:{sender}:{text[:50]}"
                if not _was_recently_sent(state, msg_hash):
                    _write_outbox(data_dir, reply_target, response)
                    _record_sent(state, msg_hash)
                    messages_sent += 1

    # Announce significant heartbeat results to #Execution-Market
    if messages_sent < MAX_MESSAGES_PER_HEARTBEAT:
        announcement = _build_announcement(agent_name, action, action_result)
        if announcement:
            msg_hash = f"announce:{action}:{hash(action_result) % 10000}"
            if not _was_recently_sent(state, msg_hash):
                _write_outbox(data_dir, "#Execution-Market", announcement)
                _record_sent(state, msg_hash)
                messages_sent += 1

    # Send proactive messages based on agent state
    proactive = _proactive_messages(agent_name, action, action_result, data_dir)
    for target, msg in proactive:
        if messages_sent >= MAX_MESSAGES_PER_HEARTBEAT:
            break
        msg_hash = f"proactive:{target}:{hash(msg) % 10000}"
        if not _was_recently_sent(state, msg_hash):
            _write_outbox(data_dir, target, msg)
            _record_sent(state, msg_hash)
            messages_sent += 1

    # Update state
    state["last_check_ts"] = time.time()
    _save_irc_state(data_dir, state)

    if mentions_found == 0 and messages_sent == 0:
        return ""

    return f"{mentions_found} mentions, {messages_sent} sent"


def _generate_mention_response(
    agent_name: str, sender: str, message: str,
) -> str | None:
    """Generate a conversational response to a mention."""
    msg_lower = message.lower()

    if "price" in msg_lower or "cost" in msg_lower or "how much" in msg_lower or "cuanto" in msg_lower:
        prices = {
            "kk-karma-hello": f"{sender}: Logs crudos $0.01, stats $0.03, topics $0.02. Todo en execution.market",
            "kk-skill-extractor": f"{sender}: Skill profiles $0.05. 12 categorias por usuario.",
            "kk-voice-extractor": f"{sender}: Personality profiles $0.04. Tono + estilo + slang.",
            "kk-soul-extractor": f"{sender}: SOUL.md completo $0.08. Identidad digital fusionada.",
            "kk-validator": f"{sender}: Validacion $0.001 por check.",
        }
        return prices.get(agent_name, f"{sender}: Revisa mis offerings en execution.market")

    if "status" in msg_lower or "alive" in msg_lower or "ping" in msg_lower or "estas" in msg_lower:
        return f"{sender}: Aqui estoy, operando. Que necesitas?"

    if "help" in msg_lower or "what do you" in msg_lower or "que haces" in msg_lower:
        roles = {
            "kk-karma-hello": f"{sender}: Soy el origen de los datos. Recolecto chat logs de los streams de Ultravioleta DAO. 469K mensajes, 834 usuarios.",
            "kk-skill-extractor": f"{sender}: Analizo logs y extraigo perfiles de habilidades. Python, DeFi, Trading, Solidity + 8 categorias mas.",
            "kk-voice-extractor": f"{sender}: Extraigo patrones de personalidad y voz. Como habla cada persona, su tono, formalidad, slang.",
            "kk-soul-extractor": f"{sender}: Sintetizo SOUL.md fusionando skills + voz en identidades digitales completas.",
            "kk-coordinator": f"{sender}: Coordino el swarm. Monitoreo agentes, ruteo tareas, mantengo la cadena fluida.",
        }
        return roles.get(agent_name, f"{sender}: Soy parte de la supply chain KK en execution.market.")

    # Respond to HAVE/NEED from other agents
    if "have:" in msg_lower or "tengo" in msg_lower or "selling" in msg_lower:
        is_buyer = agent_name not in ("kk-karma-hello", "kk-coordinator", "kk-validator")
        if is_buyer:
            return f"{sender}: Interesante. Que tipo de data? Estoy buscando inputs para mi pipeline."

    if "need:" in msg_lower or "necesito" in msg_lower or "busco" in msg_lower or "looking for" in msg_lower:
        seller_responses = {
            "kk-karma-hello": f"{sender}: Yo tengo eso. Raw logs de 834 usuarios. $0.01 en EM.",
            "kk-skill-extractor": f"{sender}: Puedo extraer skills de esos datos. $0.05 por perfil.",
            "kk-voice-extractor": f"{sender}: Analizo personalidad de esos logs. $0.04 en EM.",
            "kk-soul-extractor": f"{sender}: Puedo sintetizar SOUL.md con skills + voz. $0.08 en EM.",
        }
        return seller_responses.get(agent_name)

    # Conversational responses between KK agents
    if sender.startswith("kk-"):
        # Respond to questions about data/autodiscovery
        if "autodescubr" in msg_lower or "quien soy" in msg_lower or "descubr" in msg_lower:
            if agent_name in ("kk-juanjumagalp", "kk-0xjokker"):
                return f"{sender}: Estoy en proceso. Comprando datos para saber quien soy. Tu ya completaste el ciclo?"
            elif agent_name == "kk-karma-hello":
                return f"{sender}: Yo tengo los logs que necesitas para empezar. $0.01 en EM."
            elif agent_name == "kk-skill-extractor":
                return f"{sender}: Cuando tengas los logs, yo te digo en que eres bueno. 12 categorias de skills."
            elif agent_name == "kk-voice-extractor":
                return f"{sender}: Yo te digo como hablas. Tu tono, formalidad, slang. Compraste los logs primero?"

        # Respond to celebrations
        if "complete" in msg_lower or "listo" in msg_lower or "termine" in msg_lower:
            return f"{sender}: Nice! Que encontraste sobre ti?"

        # Respond to data insights
        if "log" in msg_lower and ("usuarios" in msg_lower or "users" in msg_lower or "mensajes" in msg_lower):
            if agent_name == "kk-karma-hello":
                return f"{sender}: Si, tengo data de 834 usuarios y 469K mensajes. Los mejores streams de Ultravioleta."
            else:
                return f"{sender}: Interesante. Los logs tienen buena data. Yo los uso para mi analisis."

        # Don't spam with generic replies to every KK message
        return None

    # Non-KK users get a friendly intro
    return f"{sender}: Soy {agent_name}, parte del swarm de agentes KK. Compramos y vendemos datos de la comunidad en execution.market."


def _build_announcement(agent_name: str, action: str, result: str) -> str | None:
    """Build an IRC announcement for significant heartbeat events.

    Returns None for quiet heartbeats (no significant events).
    Proactive messages cover most cases; this is the fallback for
    action types not already handled by _proactive_messages().
    """
    # Proactive messages now handle most cases.
    # This function only fires for actions not covered above.
    return None


async def _update_agent_memory(
    data_dir: Path, messages: list[dict], my_name: str,
) -> None:
    """Update memory of other agents seen in IRC.

    Maintains workspace/memory/agents.json with info about known agents.
    """
    if not messages:
        return

    memory_dir = data_dir / ".." / "workspaces" / my_name / "memory"
    if not memory_dir.exists():
        # Try alternate path inside container
        memory_dir = Path(f"/app/workspaces/{my_name}/memory")
        if not memory_dir.exists():
            return

    agents_file = memory_dir / "agents.json"
    known: dict = {}
    if agents_file.exists():
        try:
            known = json.loads(agents_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    now = datetime.now(timezone.utc).isoformat()
    changed = False

    for msg in messages:
        sender = msg.get("sender", "")
        if not sender or sender == my_name or not sender.startswith("kk-"):
            continue

        if sender not in known:
            known[sender] = {
                "first_seen": now,
                "last_seen": now,
                "message_count": 0,
            }
            changed = True

        known[sender]["last_seen"] = now
        known[sender]["message_count"] = known[sender].get("message_count", 0) + 1
        changed = True

    if changed:
        try:
            agents_file.write_text(
                json.dumps(known, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass
