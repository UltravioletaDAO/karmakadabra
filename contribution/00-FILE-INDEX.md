# Contribution Files Index

> Quick reference guide for all files in the contribution process

**Created:** October 27, 2025
**Status:** Setup Complete
**Start Here:** Read files in numerical order (0.x → 1.x → 2.x)

---

## 📚 Core Documentation (Read First)

| File | Purpose | When to Read | Time | Status |
|------|---------|--------------|------|--------|
| **README.md** | Overview, quick start | NOW | 10 min | ✓ |
| **00-FILE-INDEX.md** | This file | NOW | 2 min | ✓ |
| **0-MASTER-PLAN.md** | Complete 16-week roadmap | Before Week 1 | 30 min | ✓ |
| **0.1-GETTING-STARTED.md** | Setup instructions | Before Week 1 | 5 min | ✓ |
| **0.2-PROGRESS-TRACKER.md** | Daily progress log | EVERY DAY | 5 min/day | ✓ |

**Action:** Read README.md → 0-MASTER-PLAN.md → Start Week 1

---

## 📅 Week 1: Implementation & Testing (20 hours)

| File | Purpose | When to Use | Status |
|------|---------|-------------|--------|
| **week1/0-verification-report.md** | Current state | Day 0 (done) | ✓ Generated |
| **week1/1.0-CHECKLIST.md** | Week 1 tasks | Days 1-5 | ⏳ Start now |
| **week1/1.1-implementation.md** | Code guide | Day 1 | 🔜 Create when needed |
| **week1/1.2-test-results.md** | Test output | Day 2 | 🔜 Auto-generated |
| **week1/1.3-integration-test-results.md** | Integration tests | Day 4 | 🔜 Auto-generated |
| **week1/1.4-testnet-transactions.csv** | Transaction data | Day 5 | 🔜 Auto-generated |
| **week1/1.4-testnet-transaction-hashes.txt** | TX hashes | Day 5 | 🔜 Auto-generated |
| **week1/1.5-WEEK-SUMMARY.md** | Week recap | End of Week 1 | 🔜 Write at end |

**Current Task:** Open `week1/1.0-CHECKLIST.md` and start Day 1

---

## 📅 Week 2: Data Collection (15 hours)

| File | Purpose | Status |
|------|---------|--------|
| **week2/2.0-CHECKLIST.md** | Week 2 tasks | 🔒 Locked until Week 1 complete |
| **week2/2.1-marketplace-simulation.py** | Test script | 🔜 Create in Week 2 |
| **week2/2.2-rating-analysis.json** | Data analysis | 🔜 Auto-generated |
| **week2/2.3-WEEK-SUMMARY.md** | Week recap | 🔜 Write at end |

**Unlock:** Complete Week 1 deliverables first

---

## 📅 Week 3: Security Analysis (20 hours)

| File | Purpose | Status |
|------|---------|--------|
| **week3/3.0-CHECKLIST.md** | Week 3 tasks | 🔒 Locked |
| **security/sybil-attack-analysis.md** | Sybil defense | 🔜 |
| **security/rating-manipulation-analysis.md** | Manipulation defense | 🔜 |
| **security/collusion-attack-analysis.md** | Collusion defense | 🔜 |
| **security/code-audit-report.md** | Audit report | 🔜 |
| **week3/3.5-WEEK-SUMMARY.md** | Week recap | 🔜 |

**Unlock:** Complete Week 2 first

---

## 📅 Week 4: Comparative Analysis (20 hours)

| File | Purpose | Status |
|------|---------|--------|
| **week4/4.0-CHECKLIST.md** | Week 4 tasks | 🔒 Locked |
| **docs/comparison/uber-lyft-analysis.md** | Uber comparison | 🔜 |
| **docs/comparison/airbnb-analysis.md** | Airbnb comparison | 🔜 |
| **docs/comparison/marketplace-analysis.md** | eBay comparison | 🔜 |
| **docs/comparison/eip8004-base-vs-bidirectional.md** | Base spec comparison | 🔜 |
| **week4/4.5-WEEK-SUMMARY.md** | Week recap | 🔜 |

**Unlock:** Complete Week 3 first

---

## 📅 Weeks 5-16: Documentation, Outreach, Submission

Files will be created as needed during those weeks. Focus on Phase 1 (Weeks 1-4) first.

---

## 🛠️ Scripts (in scripts/)

| Script | Purpose | When to Run |
|--------|---------|-------------|
| **verify_bidirectional_state.py** | Check implementation status | Week 0 (done) ✓ |
| **execute_bidirectional_testnet_transactions.py** | Test transactions | Week 1 Day 5 🔜 |
| **simulate_marketplace.py** | 100+ transactions | Week 2 🔜 |
| **analyze_bidirectional_ratings.py** | Statistical analysis | Week 2 🔜 |

**Location:** `scripts/` (all new scripts go here)

---

## 🧪 Tests (in tests/)

| Test File | Purpose | Status |
|-----------|---------|--------|
| **test_bidirectional_transactions.py** | Integration tests | ✓ Exists |
| **test_bidirectional_e2e.py** | End-to-end tests | 🔜 Create Week 1 |

**Location:** `tests/` (all new tests go here)

---

## 📊 Generated Output Folders

| Folder | Contains | When Created |
|--------|----------|--------------|
| **week1/** | Week 1 deliverables | Days 1-5 |
| **week2/** | Week 2 deliverables | Days 6-10 |
| **docs/** | Documentation | Weeks 5+ |
| **security/** | Security analyses | Week 3 |
| **community/** | Outreach materials | Weeks 8-9 |
| **templates/** | Email/post templates | Week 8 |

---

## 🎯 Reading Order by Day

### **Day 0 (Setup) - TODAY**
1. ✓ `README.md` (10 min)
2. ✓ `00-FILE-INDEX.md` (2 min) - You're here!
3. ✓ `0-MASTER-PLAN.md` (30 min) - Read sections relevant to Week 1
4. ✓ `0.1-GETTING-STARTED.md` (5 min)
5. ✓ Run `scripts/verify_bidirectional_state.py`
6. ✓ Review `week1/0-verification-report.md` (10 min)
7. ⏳ Open `week1/1.0-CHECKLIST.md` and START Week 1!

**Total time today:** ~1 hour reading + start coding

### **Days 1-5 (Week 1)**
- Morning: Open `week1/1.0-CHECKLIST.md`
- Follow Day X tasks
- Evening: Update `0.2-PROGRESS-TRACKER.md`

### **Sunday (End of Week 1)**
- Write `week1/1.5-WEEK-SUMMARY.md`
- Complete Week 1 retrospective in progress tracker
- Prepare for Week 2

---

## 📈 Progress Tracking

**Update these files DAILY:**
- `0.2-PROGRESS-TRACKER.md` - Log hours, tasks, notes

**Update these files WEEKLY:**
- `0.2-PROGRESS-TRACKER.md` - Weekly retrospective
- `weekX/X.5-WEEK-SUMMARY.md` - Week summary

**Commit frequency:**
- Commit after completing each major task
- Push at end of each day

---

## 🎓 Quick Reference

### File Naming Convention

```
0.X  = Setup files (read first)
X.0  = Weekly checklist (start here each week)
X.1  = Implementation guides
X.2  = Test results
X.3  = Analysis results
X.4  = Data exports
X.5  = Week summary (write at end)
```

### Status Icons

- ✓ = Complete
- ⏳ = In progress
- 🔜 = Will be created when needed
- 🔒 = Locked until prerequisites complete
- ❌ = Blocked/issues

---

## 🚦 Current Status

**Phase:** 1 - Implementation & Validation
**Week:** 0 (Setup) → Moving to Week 1
**Day:** 0 → Moving to Day 1
**Progress:** 38% of Week 1 code already done
**Estimated remaining work:** 10 hours for Week 1

**Next file to open:** `week1/1.0-CHECKLIST.md`

---

## 🎯 Success Criteria

**You're ready for Week 2 when:**
- [ ] All Week 1 checklist items complete
- [ ] 10+ testnet transactions executed
- [ ] `week1/1.5-WEEK-SUMMARY.md` written
- [ ] `0.2-PROGRESS-TRACKER.md` updated
- [ ] All code committed and pushed

**Don't skip ahead!** Each week builds on the previous week.

---

**Now go open: `week1/1.0-CHECKLIST.md` and start Day 1! 🚀**
