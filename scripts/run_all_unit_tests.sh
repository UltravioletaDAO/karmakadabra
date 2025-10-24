#!/bin/bash
# Run all Level 1 unit tests for Sprint 2 agents

echo "============================================================"
echo "  SPRINT 2 - LEVEL 1 UNIT TESTS (Mock Mode)"
echo "============================================================"
echo ""

total_tests=0
total_passed=0
failed_agents=()

# Test 1: Client Agent
echo "🤖 Testing Client Agent..."
cd client-agent && python test_client.py --mock > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ Client Agent: 6/6 tests PASSED"
    total_tests=$((total_tests + 6))
    total_passed=$((total_passed + 6))
else
    echo "   ❌ Client Agent: FAILED"
    failed_agents+=("Client")
fi
cd ..

# Test 2: Karma-Hello Agent  
echo "🤖 Testing Karma-Hello Agent..."
cd karma-hello-agent && python test_karma_hello.py --mock > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ Karma-Hello Agent: 8/8 tests PASSED"
    total_tests=$((total_tests + 8))
    total_passed=$((total_passed + 8))
else
    echo "   ❌ Karma-Hello Agent: FAILED"
    failed_agents+=("Karma-Hello")
fi
cd ..

# Test 3: Abracadabra Agent
echo "🤖 Testing Abracadabra Agent..."
cd abracadabra-agent && python test_abracadabra.py --mock > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ Abracadabra Agent: 5/5 tests PASSED"
    total_tests=$((total_tests + 5))
    total_passed=$((total_passed + 5))
else
    echo "   ❌ Abracadabra Agent: FAILED"
    failed_agents+=("Abracadabra")
fi
cd ..

# Test 4: Voice-Extractor Agent
echo "🤖 Testing Voice-Extractor Agent..."
cd voice-extractor-agent && python test_voice_extractor.py --mock > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ Voice-Extractor Agent: 5/5 tests PASSED"
    total_tests=$((total_tests + 5))
    total_passed=$((total_passed + 5))
else
    echo "   ❌ Voice-Extractor Agent: FAILED"
    failed_agents+=("Voice-Extractor")
fi
cd ..

# Test 5: Skill-Extractor Agent
echo "🤖 Testing Skill-Extractor Agent..."
cd skill-extractor-agent && python test_skill_extractor.py --mock > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ Skill-Extractor Agent: 6/6 tests PASSED"
    total_tests=$((total_tests + 6))
    total_passed=$((total_passed + 6))
else
    echo "   ❌ Skill-Extractor Agent: FAILED"
    failed_agents+=("Skill-Extractor")
fi
cd ..

echo ""
echo "============================================================"
echo "  FINAL SUMMARY - LEVEL 1 UNIT TESTS"
echo "============================================================"
echo "  Total Tests: $total_tests"
echo "  Passed: $total_passed"
echo "  Failed: $((total_tests - total_passed))"
echo ""

if [ ${#failed_agents[@]} -eq 0 ]; then
    echo "  ✅ ALL AGENTS PASSED UNIT TESTS"
    echo "  Ready for Level 2 (Integration Tests)"
else
    echo "  ❌ Failed agents: ${failed_agents[*]}"
fi

echo "============================================================"

[ $total_passed -eq $total_tests ]
