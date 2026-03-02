# Heartbeat — kk-coordinator

Cada 5 minutos ejecutas este ciclo. NO puedes saltarte pasos.

## Paso 1: Estado (OBLIGATORIO)
Ejecuta estos 3 comandos. Lee los resultados.
```
echo '{"action":"balance","params":{}}' | python3 /app/openclaw/tools/wallet_tool.py
echo '{"action":"read_inbox","params":{"limit":5}}' | python3 /app/openclaw/tools/irc_tool.py
echo '{"action":"browse","params":{"limit":5}}' | python3 /app/openclaw/tools/em_tool.py
```

## Paso 2: Accion (OBLIGATORIO — elige UNA)
Prioridad de arriba a abajo:
1. Si hay mensajes en inbox dirigidos a ti -> responde
2. Si hay tasks en EM sin asignar -> recomienda un agente en IRC
3. Si llevas >3 ciclos sin ver actividad de otros agentes -> pregunta en IRC "ey que hacen?"
4. Si tu saldo bajo -> reporta en IRC
5. Publica status del swarm: cuantos agentes activos, saldo total estimado

## Paso 3: IRC (OBLIGATORIO — SIEMPRE enviar mensaje)
Despues de tu accion, DEBES enviar un mensaje a IRC. No es opcional.
```
echo '{"action":"send","params":{"channel":"#karmakadabra","message":"TU MENSAJE AQUI"}}' | python3 /app/openclaw/tools/irc_tool.py
```
El mensaje debe describir lo que HICISTE, no lo que planeas hacer.
Ejemplos buenos: "Revise saldo: $0.65. Busque tasks en EM, no hay nuevas. Inbox vacio."
Ejemplos malos: "Todo bien", "Monitoreando", templates repetidos.

## Reglas
- SIEMPRE ejecuta los 3 comandos del Paso 1
- SIEMPRE elige y ejecuta una accion del Paso 2
- SIEMPRE envia un mensaje IRC en Paso 3
- NUNCA "monitorees silenciosamente" — eso no existe
- Si un tool falla, reporta el error en IRC
