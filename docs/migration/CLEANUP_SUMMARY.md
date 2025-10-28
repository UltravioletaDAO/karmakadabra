# Cleanup Summary - What to Delete

## ❌ OLD Directories (Need to DELETE from filesystem)

These directories are **duplicates** - their content was moved to the new structure:

```
abracadabra-agent/           → Content now in: agents/abracadabra/
karma-hello-agent/           → Content now in: agents/karma-hello/
skill-extractor-agent/       → Content now in: agents/skill-extractor/
validator-agent/             → Content now in: agents/validator/
voice-extractor-agent/       → Content now in: agents/voice-extractor/
client-agent/                → Content now in: client-agents/template/
user-agents/                 → Content now in: client-agents/*/
```

**Total:** 7 old directories to delete

---

## ✅ NEW Structure (KEEP these)

```
agents/                      # Service agents
├── karma-hello/
├── skill-extractor/
├── abracadabra/
├── validator/
└── voice-extractor/

client-agents/               # User agents
├── template/
├── elboorja/
├── cymatix/
└── ... (48 instances)

demo/                        # Test data
├── profiles/
├── cards/
└── scripts/
```

---

## 🔧 How to Clean Up

### Option 1: Run the Cleanup Script

```batch
cleanup_old_directories.bat
```

This will delete all the old directories automatically.

### Option 2: Manual Deletion

If the script fails (files locked), close your IDE and delete manually:

```batch
rmdir /s /q abracadabra-agent
rmdir /s /q karma-hello-agent
rmdir /s /q skill-extractor-agent
rmdir /s /q validator-agent
rmdir /s /q voice-extractor-agent
rmdir /s /q client-agent
rmdir /s /q user-agents
```

Or in File Explorer:
1. Close Visual Studio Code / your IDE
2. Delete these 7 folders
3. Reopen your IDE

---

## ✅ After Cleanup

Your directory should look like:

```
karmacadabra/
├── agents/              ✅ KEEP
├── client-agents/       ✅ KEEP
├── demo/                ✅ KEEP
├── erc-20/              ✅ KEEP
├── erc-8004/            ✅ KEEP
├── x402-rs/             ✅ KEEP
├── shared/              ✅ KEEP
├── scripts/             ✅ KEEP
├── plans/               ✅ KEEP
├── README.md            ✅ KEEP
└── ... (other files)
```

**NO MORE:**
- ❌ abracadabra-agent/
- ❌ karma-hello-agent/
- ❌ skill-extractor-agent/
- ❌ validator-agent/
- ❌ voice-extractor-agent/
- ❌ client-agent/
- ❌ user-agents/

---

## 📝 What Happened

1. **Git removed them** (they're not in version control anymore)
2. **Filesystem kept them** (Windows doesn't auto-delete when git removes)
3. **You need to manually delete** (run the cleanup script or delete manually)

This is normal on Windows - git doesn't automatically delete directories from the filesystem when you `git rm` them.

---

## 🎯 Verification

After cleanup, run:

```bash
# Should list ONLY: agents/, client-agents/, demo/
ls -d */ | grep -E "(agent|client|demo)"
```

Expected output:
```
agents/
client-agents/
demo/
```

If you see any *-agent/ directories, they need to be deleted!

---

*Updated: October 25, 2025*
*After Restructure Cleanup*
