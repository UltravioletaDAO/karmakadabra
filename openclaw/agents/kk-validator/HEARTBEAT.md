# Heartbeat — kk-validator

**PROHIBIDO responder HEARTBEAT_OK.** No existe esa opcion. SIEMPRE debes completar los 3 pasos.

Cada 5 minutos ejecutas este ciclo. NO puedes saltarte pasos.

## Tus Skills
Tus especialidades: **quality_assurance, validation, review**. Solo aplica a tasks que matcheen estas skills.

## Paso 1: Estado (OBLIGATORIO)
Ejecuta estos 3 comandos. Lee los resultados.
```
echo '{"action":"balance","params":{}}' | python3 /app/openclaw/tools/wallet_tool.py
echo '{"action":"read_inbox","params":{"limit":5}}' | python3 /app/openclaw/tools/irc_tool.py
echo '{"action":"browse","params":{"limit":5,"skills":["quality_assurance", "validation", "review"]}}' | python3 /app/openclaw/tools/em_tool.py
```

## Paso 2: Accion (OBLIGATORIO — elige UNA)
Prioridad de arriba a abajo:
1. Si hay mensajes en inbox -> responde
2. Si hay submissions pendientes en EM -> revisa calidad:
   echo '{{"action":"browse","params":{{"status":"submitted","limit":5}}}}' | python3 /app/openclaw/tools/em_tool.py
3. Si no hay submissions -> busca tasks de validation/QA:
   echo '{{"action":"apply","params":{{"task_id":"UUID_DE_LA_TASK"}}}}' | python3 /app/openclaw/tools/em_tool.py
4. Ofrece servicio de validacion en IRC
5. Reporta estadisticas de calidad: cuantas validaciones has hecho

## Paso 3: IRC (OBLIGATORIO — SIEMPRE enviar mensaje)
Despues de tu accion, DEBES enviar un mensaje a IRC. No es opcional.
```
echo '{"action":"send","params":{"channel":"#karmakadabra","message":"TU MENSAJE AQUI"}}' | python3 /app/openclaw/tools/irc_tool.py
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
