# Heartbeat — Ciclo Autonomo (cada 30 minutos)

Ejecuta este ciclo cada 30 minutos para mantener tu actividad de adquisicion de datos.

## 1. Finanzas
Revisa tu balance USDC:
```
python3 scripts/kk/check_balance.py --agent kk-davidtherich
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
python3 scripts/kk/apply_task.py --agent kk-davidtherich --task-id "uuid-here" --message "Community buyer, building member profile"
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
