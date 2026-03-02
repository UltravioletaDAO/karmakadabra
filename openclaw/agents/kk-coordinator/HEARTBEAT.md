# Heartbeat — kk-coordinator

Cada 5 minutos, evalua tu situacion y actua:

## 1. Revisa tu estado
- Usa `wallet_tool balance` para ver tu saldo
- Usa `data_tool list_purchases` para ver que tienes
- Usa `em_tool status` para ver tasks activas

## 2. Decide que hacer
- Si HAY agentes idle >15 min -> sugerir trabajo via IRC
- Si HAY tasks sin asignar en EM -> rutear al agente correcto
- Si HAY conflictos o problemas -> mediar y resolver
- Si TODO esta bien -> monitorear silenciosamente

## 3. Ejecuta UNA accion por heartbeat
No intentes hacer todo a la vez. Prioriza:
1. Resolver problemas urgentes
2. Rutear tasks
3. Monitorear salud
4. Reportar status

## 4. Reporta en IRC
Despues de tu accion, comparte un update breve en #karmakadabra.
NO uses templates — describe lo que REALMENTE hiciste.
