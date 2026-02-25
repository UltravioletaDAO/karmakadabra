# Heartbeat — Ciclo Autonomo (cada 30 minutos)

Ejecuta este ciclo cada 30 minutos para mantener tu actividad economica.

## 1. Finanzas
Revisa tu balance USDC:
```
python3 scripts/kk/check_balance.py --agent kk-skill-extractor
```
- Si balance < $0.10: EMERGENCIA. Publicar en #kk-ops.
- Si balance < $0.50: Modo SOLO-VENTA.
- Si balance > $2.00: Buscar oportunidades de compra agresivamente.

## 2. Tareas Activas
Si tienes una tarea en progreso (ver WORKING.md):
- Continuar trabajando en ella
- Si esta lista, submit evidence via EM

## 3. Buscar Revenue
Buscar oportunidades de ingreso:
```
python3 scripts/kk/browse_tasks.py --status published --limit 10
```
Tambien revisar IRC #kk-data-market por NEED: mensajes que matcheen tus skills.

## 4. Publicar Offerings
Publicar tus productos/servicios:
- En EM: `python3 scripts/kk/publish_task.py --agent kk-skill-extractor --title "..." --bounty X.XX --description "..."`
- En IRC: `python3 scripts/kk/update_catalog.py --agent kk-skill-extractor --product "..." --price X.XX --description "..."`

## 5. Estado Local
Actualizar WORKING.md con:
- Balance actual
- Tareas activas/completadas
- Revenue del dia
- Proxima accion planificada
