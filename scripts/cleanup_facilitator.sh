#!/bin/bash
# Cleanup Script: Mover archivos del facilitator a .unused/
#
# ⚠️ SOLO EJECUTAR DESPUÉS DE:
# 1. Nuevo facilitator deployed y funcionando
# 2. 24-48 horas sin errores
# 3. Tests confirmando que funciona
#
# Uso: bash scripts/cleanup_facilitator.sh

set -e

REPO_ROOT="z:/ultravioleta/dao/karmacadabra"
UNUSED_DIR=".unused/facilitator-old"

echo "=========================================="
echo "Facilitator Cleanup Script"
echo "=========================================="
echo ""
echo "⚠️  WARNING: Este script moverá archivos del facilitator a .unused/"
echo ""
echo "Presiona ENTER para continuar, o Ctrl+C para cancelar..."
read

cd "$REPO_ROOT"

# Crear directorios
echo "📁 Creando directorios en .unused/..."
mkdir -p "$UNUSED_DIR"/{scripts,tests,docs,root}

# Mover scripts
echo "📦 Moviendo scripts de testing..."
mv scripts/test_glue_payment_simple.py "$UNUSED_DIR/scripts/" 2>/dev/null || echo "  - test_glue_payment_simple.py ya movido"
mv scripts/test_usdc_payment_base.py "$UNUSED_DIR/scripts/" 2>/dev/null || echo "  - test_usdc_payment_base.py ya movido"
mv scripts/test_base_usdc_stress.py "$UNUSED_DIR/scripts/" 2>/dev/null || echo "  - test_base_usdc_stress.py ya movido"
mv scripts/test_facilitator_verbose.py "$UNUSED_DIR/scripts/" 2>/dev/null || echo "  - test_facilitator_verbose.py ya movido"
mv scripts/test_real_x402_payment.py "$UNUSED_DIR/scripts/" 2>/dev/null || echo "  - test_real_x402_payment.py ya movido"
mv scripts/test_glue_quick.py "$UNUSED_DIR/scripts/" 2>/dev/null || echo "  - test_glue_quick.py ya movido"
mv scripts/test_complete_flow.py "$UNUSED_DIR/scripts/" 2>/dev/null || echo "  - test_complete_flow.py ya movido"
mv scripts/test_all_endpoints.py "$UNUSED_DIR/scripts/" 2>/dev/null || echo "  - test_all_endpoints.py ya movido"

echo "📦 Moviendo scripts de diagnóstico..."
mv scripts/check_facilitator_config.py "$UNUSED_DIR/scripts/" 2>/dev/null || echo "  - check_facilitator_config.py ya movido"
mv scripts/check_facilitator_version.py "$UNUSED_DIR/scripts/" 2>/dev/null || echo "  - check_facilitator_version.py ya movido"
mv scripts/diagnose_usdc_payment.py "$UNUSED_DIR/scripts/" 2>/dev/null || echo "  - diagnose_usdc_payment.py ya movido"
mv scripts/compare_domain_separator.py "$UNUSED_DIR/scripts/" 2>/dev/null || echo "  - compare_domain_separator.py ya movido"
mv scripts/compare_usdc_contracts.py "$UNUSED_DIR/scripts/" 2>/dev/null || echo "  - compare_usdc_contracts.py ya movido"
mv scripts/verify_full_stack.py "$UNUSED_DIR/scripts/" 2>/dev/null || echo "  - verify_full_stack.py ya movido"
mv scripts/usdc_contracts_facilitator.json "$UNUSED_DIR/scripts/" 2>/dev/null || echo "  - usdc_contracts_facilitator.json ya movido"
mv scripts/extract_usdc_contracts.py "$UNUSED_DIR/scripts/" 2>/dev/null || echo "  - extract_usdc_contracts.py ya movido"

echo "📦 Moviendo scripts de secrets..."
mv scripts/setup_facilitator_secrets.py "$UNUSED_DIR/scripts/" 2>/dev/null || echo "  - setup_facilitator_secrets.py ya movido"
mv scripts/migrate_facilitator_secrets.py "$UNUSED_DIR/scripts/" 2>/dev/null || echo "  - migrate_facilitator_secrets.py ya movido"
mv scripts/rotate-facilitator-wallet.py "$UNUSED_DIR/scripts/" 2>/dev/null || echo "  - rotate-facilitator-wallet.py ya movido"
mv scripts/create_testnet_facilitator_secret.py "$UNUSED_DIR/scripts/" 2>/dev/null || echo "  - create_testnet_facilitator_secret.py ya movido"
mv scripts/split_facilitator_secrets.py "$UNUSED_DIR/scripts/" 2>/dev/null || echo "  - split_facilitator_secrets.py ya movido"
mv scripts/upgrade_facilitator.ps1 "$UNUSED_DIR/scripts/" 2>/dev/null || echo "  - upgrade_facilitator.ps1 ya movido"

# Mover tests
echo "📦 Moviendo tests..."
mv tests/test_facilitator.py "$UNUSED_DIR/tests/" 2>/dev/null || echo "  - test_facilitator.py ya movido"
mv tests/x402/ "$UNUSED_DIR/tests/" 2>/dev/null || echo "  - x402/ ya movido"

# Mover docs
echo "📦 Moviendo documentación..."
mv docs/FACILITATOR_TESTING.md "$UNUSED_DIR/docs/" 2>/dev/null || echo "  - FACILITATOR_TESTING.md ya movido"
mv docs/FACILITATOR_WALLET_ROTATION.md "$UNUSED_DIR/docs/" 2>/dev/null || echo "  - FACILITATOR_WALLET_ROTATION.md ya movido"
mv docs/X402_FORK_STRATEGY.md "$UNUSED_DIR/docs/" 2>/dev/null || echo "  - X402_FORK_STRATEGY.md ya movido"
mv docs/migration/FACILITATOR_SECRETS_MIGRATION.md "$UNUSED_DIR/docs/" 2>/dev/null || echo "  - FACILITATOR_SECRETS_MIGRATION.md ya movido"

# Mover archivos root
echo "📦 Moviendo archivos root..."
mv FACILITATOR_VALIDATION_BUG.md "$UNUSED_DIR/root/" 2>/dev/null || echo "  - FACILITATOR_VALIDATION_BUG.md ya movido"
mv BASE_USDC_BUG_INVESTIGATION_REPORT.md "$UNUSED_DIR/root/" 2>/dev/null || echo "  - BASE_USDC_BUG_INVESTIGATION_REPORT.md ya movido"
mv AWS_FACILITATOR_INFRASTRUCTURE_EXTRACTION.md "$UNUSED_DIR/root/" 2>/dev/null || echo "  - AWS_FACILITATOR_INFRASTRUCTURE_EXTRACTION.md ya movido"
mv facilitator-task-def-mainnet.json "$UNUSED_DIR/root/" 2>/dev/null || echo "  - facilitator-task-def-mainnet.json ya movido"
mv facilitator-task-def-mainnet-v2.json "$UNUSED_DIR/root/" 2>/dev/null || echo "  - facilitator-task-def-mainnet-v2.json ya movido"
mv FACILITATOR_EXTRACTION_MASTER_PLAN.md "$UNUSED_DIR/root/" 2>/dev/null || echo "  - FACILITATOR_EXTRACTION_MASTER_PLAN.md ya movido"
mv EXTRACTION_MASTER_PLAN_TERRAFORM_ANALYSIS.md "$UNUSED_DIR/root/" 2>/dev/null || echo "  - EXTRACTION_MASTER_PLAN_TERRAFORM_ANALYSIS.md ya movido"
mv TERRAFORM_EXTRACTION_SUMMARY.md "$UNUSED_DIR/root/" 2>/dev/null || echo "  - TERRAFORM_EXTRACTION_SUMMARY.md ya movido"
mv TERRAFORM_EXTRACTION_DIAGRAM.md "$UNUSED_DIR/root/" 2>/dev/null || echo "  - TERRAFORM_EXTRACTION_DIAGRAM.md ya movido"

# Actualizar .gitignore
echo "📝 Actualizando .gitignore..."
if ! grep -q ".unused/facilitator-old/" .gitignore 2>/dev/null; then
  echo "" >> .gitignore
  echo "# Facilitator extracted to separate repo" >> .gitignore
  echo ".unused/facilitator-old/" >> .gitignore
  echo "  - .gitignore actualizado"
else
  echo "  - .gitignore ya tiene la entrada"
fi

# Resumen
echo ""
echo "=========================================="
echo "✅ Limpieza completada"
echo "=========================================="
echo ""
echo "Archivos movidos a: $UNUSED_DIR/"
echo ""
echo "Próximos pasos:"
echo "1. Verificar que los agentes siguen funcionando"
echo "2. Hacer commit de la limpieza:"
echo "   git add ."
echo "   git commit -m \"Clean up: Move facilitator files to .unused\""
echo ""
echo "⚠️  RECORDATORIO: NO muevas x402-rs/ hasta Fase 5 (después de 1 semana)"
echo ""
