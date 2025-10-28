@echo off
REM Cleanup script - Delete old duplicate directories
REM Run this to remove OLD agent directories that were replaced in restructure

echo ========================================
echo Cleaning up OLD duplicate directories
echo ========================================
echo.

echo Deleting OLD agent directories (content moved to agents/):
rmdir /s /q abracadabra-agent 2>nul && echo   ✓ Deleted abracadabra-agent || echo   ✗ Failed to delete abracadabra-agent (may be locked)
rmdir /s /q karma-hello-agent 2>nul && echo   ✓ Deleted karma-hello-agent || echo   ✗ Failed to delete karma-hello-agent (may be locked)
rmdir /s /q skill-extractor-agent 2>nul && echo   ✓ Deleted skill-extractor-agent || echo   ✗ Failed to delete skill-extractor-agent (may be locked)
rmdir /s /q validator-agent 2>nul && echo   ✓ Deleted validator-agent || echo   ✗ Failed to delete validator-agent (may be locked)
rmdir /s /q voice-extractor-agent 2>nul && echo   ✓ Deleted voice-extractor-agent || echo   ✗ Failed to delete voice-extractor-agent (may be locked)

echo.
echo Deleting OLD client directories (content moved to client-agents/):
rmdir /s /q client-agent 2>nul && echo   ✓ Deleted client-agent || echo   ✗ Failed to delete client-agent (may be locked)
rmdir /s /q user-agents 2>nul && echo   ✓ Deleted user-agents || echo   ✗ Failed to delete user-agents (may be locked)

echo.
echo ========================================
echo Cleanup complete!
echo ========================================
echo.
echo NEW structure (should be the only ones left):
echo   agents/              (service agents)
echo   client-agents/       (user agents)
echo   demo/                (test data)
echo.
echo If any deletions failed, close your IDE/editor and run this script again.
echo.
pause
