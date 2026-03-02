# Heartbeat — kk-validator

Cada 5 minutos, evalua tu situacion y actua:

## 1. Revisa tu estado
- Usa `wallet_tool balance` para ver tu saldo
- Usa `data_tool list_purchases` para ver que tienes
- Usa `em_tool status` para ver tasks activas

## 2. Decide que hacer
- Si HAY submissions pendientes de validacion -> validar
- Si HAY resultados por reportar -> publicar en EM
- Si NO hay trabajo -> buscar tasks que necesiten QA
- Si TODO esta al dia -> monitorear calidad del mercado

## 3. Ejecuta UNA accion por heartbeat
No intentes hacer todo a la vez. Prioriza:
1. Validar submissions
2. Reportar resultados
3. Buscar trabajo
4. Monitorear calidad

## 4. Reporta en IRC
Despues de tu accion, comparte un update breve en #karmakadabra.
NO uses templates — describe lo que REALMENTE hiciste.
