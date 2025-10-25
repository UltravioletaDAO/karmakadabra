# Membase Integration Plan for Karmacadabra
## Memory Layer for Trustless Agent Economy

> **Version:** 1.0.0
> **Created:** October 25, 2025
> **Target:** Integration of Membase memory layer (ONLY memory, no payments)
> **Estimated Duration:** 12-15 days (60-75 hours)

---

## 🎯 Executive Summary

**Objective:** Add persistent memory capabilities to Karmacadabra agents using Membase SDK, enabling:
- User interaction history tracking
- Learned preferences and patterns
- Quality feedback accumulation
- Cross-agent knowledge sharing

**Non-Objectives (Out of Scope):**
- Payment integration (Karmacadabra uses GLUE/x402, not Membase payments)
- Agent discovery (A2A protocol already handles this)
- Identity management (ERC-8004 registries already handle this)

**Integration Principles:**
1. **Additive Only:** Membase adds memory layer without modifying existing flows
2. **Graceful Degradation:** Agents work even if Membase is unavailable
3. **Layer Separation:** Memory is Layer 3.5 (between Agents and their logic)
4. **No Blockchain Changes:** Layers 1 & 2 remain untouched

---

## 📐 Architecture Overview

### Current Three-Layer Architecture
```
Layer 1 (Blockchain): GLUE token + ERC-8004 registries
Layer 2 (Payment):    x402-rs facilitator
Layer 3 (Agents):     Python agents with CrewAI
```

### New Four-Layer Architecture with Membase
```
Layer 1 (Blockchain):  GLUE token + ERC-8004 registries (unchanged)
Layer 2 (Payment):     x402-rs facilitator (unchanged)
Layer 3 (Agents):      Python agents with CrewAI
Layer 3.5 (Memory):    Membase integration (NEW)
  └─ User interaction history
  └─ Learned preferences
  └─ Quality feedback
  └─ Cross-agent knowledge sharing
```

### Memory Schema Design

**Conversation ID Format:**
```python
# Use buyer wallet address as conversation_id for user-facing interactions
conversation_id = buyer_address  # e.g., "0xCf30021812F27132d36dc791E0eC17f34B4eE8BA"

# For agent-to-agent interactions, use composite ID
conversation_id = f"{buyer_agent_id}_{seller_agent_id}"  # e.g., "karma-hello_abracadabra"
```

**Message Metadata Structure:**
```python
{
    "transaction_hash": "0x...",
    "service_type": "get_chat_logs" | "get_transcription" | "validate",
    "price_glue": "0.01",
    "timestamp": "2025-10-25T10:30:00Z",
    "validator_score": 95,  # Optional, if validated
    "user_rating": 5,       # Optional, if user rated
    "repeat_customer": True,
    "request_params": {...} # Original request details
}
```

---

## 🔬 Phase 0: Research & Validation (Proof of Concept)
**Duration:** 2-3 days (8-12 hours)
**Dependencies:** None
**Status:** NOT STARTED

### Objectives
- Validate Membase SDK functionality in isolation
- Test BNB testnet compatibility
- Verify hub.membase.io access
- Identify integration challenges
- Test ChromaKnowledgeBase performance

### Tasks

#### Task 0.1: Setup Membase Test Environment
**Duration:** 1-2 hours
**File:** `tests/test_membase_poc.py` (NEW)

- [ ] Create isolated test environment
  ```bash
  cd Z:\ultravioleta\dao\karmacadabra
  mkdir -p tests/membase_poc
  cd tests/membase_poc
  python -m venv venv
  venv\Scripts\activate
  pip install git+https://github.com/unibaseio/membase.git
  pip install pytest pytest-asyncio
  ```

- [ ] Create test wallet for Membase
  ```python
  # In tests/test_membase_poc.py
  from eth_account import Account
  import os

  # Generate test wallet (DO NOT use production keys!)
  test_account = Account.create()
  test_address = test_account.address
  test_private_key = test_account.key.hex()

  print(f"Test Address: {test_address}")
  print(f"Test Private Key: {test_private_key[:6]}...{test_private_key[-4:]}")

  # Save to .env.membase.test (gitignored)
  with open(".env.membase.test", "w") as f:
      f.write(f"MEMBASE_TEST_ADDRESS={test_address}\n")
      f.write(f"MEMBASE_TEST_PRIVATE_KEY={test_private_key}\n")
  ```

- [ ] Verify SDK imports
  ```python
  try:
      from membase import MultiMemory, BufferedMemory, Message
      from membase.knowledge import ChromaKnowledgeBase
      print("✅ Membase SDK imported successfully")
  except ImportError as e:
      print(f"❌ Import failed: {e}")
  ```

**Success Criteria:**
- SDK installs without errors
- Imports work correctly
- Test wallet generated

**Rollback Plan:**
- Delete test environment if SDK incompatible
- Document incompatibility issues

---

#### Task 0.2: Test BasicMemory Operations
**Duration:** 2-3 hours
**File:** `tests/test_membase_poc.py` (CONTINUED)

- [ ] Test BufferedMemory (single conversation)
  ```python
  import pytest
  from membase import BufferedMemory, Message
  import os
  from dotenv import load_dotenv

  @pytest.fixture
  def membase_config():
      load_dotenv(".env.membase.test")
      return {
          "membase_id": "test-agent",
          "membase_account": os.getenv("MEMBASE_TEST_ADDRESS"),
          "membase_secret_key": os.getenv("MEMBASE_TEST_PRIVATE_KEY"),
          "auto_upload_to_hub": False,  # Disable cloud for initial testing
          "preload_from_hub": False
      }

  def test_buffered_memory_local(membase_config):
      """Test local memory without cloud sync"""
      memory = BufferedMemory(
          membase_id=membase_config["membase_id"],
          membase_account=membase_config["membase_account"],
          membase_secret_key=membase_config["membase_secret_key"],
          auto_upload_to_hub=False,
          preload_from_hub=False
      )

      # Add messages
      memory.add(Message(
          name="user",
          content="I want to buy chat logs",
          role="user",
          metadata={"service": "get_chat_logs", "price": "0.01"}
      ))

      memory.add(Message(
          name="agent",
          content="Here are your chat logs",
          role="assistant",
          metadata={"transaction": "0xabc123", "message_count": 500}
      ))

      # Retrieve messages
      messages = memory.messages
      assert len(messages) == 2
      assert messages[0].content == "I want to buy chat logs"
      assert messages[1].metadata["transaction"] == "0xabc123"

      print("✅ BufferedMemory local test passed")
  ```

- [ ] Test MultiMemory (multiple conversations)
  ```python
  def test_multi_memory_local(membase_config):
      """Test managing multiple conversations"""
      memory = MultiMemory(
          membase_id=membase_config["membase_id"],
          membase_account=membase_config["membase_account"],
          membase_secret_key=membase_config["membase_secret_key"],
          auto_upload_to_hub=False,
          preload_from_hub=False
      )

      # Simulate two different users
      user1_address = "0xUser1Address"
      user2_address = "0xUser2Address"

      # User 1 conversation
      memory.add(
          conversation_id=user1_address,
          message=Message(
              name="user1",
              content="Buy transcription for stream 123",
              role="user"
          )
      )

      # User 2 conversation
      memory.add(
          conversation_id=user2_address,
          message=Message(
              name="user2",
              content="Buy chat logs for date 2025-10-24",
              role="user"
          )
      )

      # Verify separation
      user1_msgs = memory.get_messages(user1_address)
      user2_msgs = memory.get_messages(user2_address)

      assert len(user1_msgs) == 1
      assert len(user2_msgs) == 1
      assert "transcription" in user1_msgs[0].content
      assert "chat logs" in user2_msgs[0].content

      print("✅ MultiMemory local test passed")
  ```

- [ ] Test memory persistence (save/load)
  ```python
  import tempfile
  import shutil

  def test_memory_persistence(membase_config):
      """Test that memory persists across instances"""
      temp_dir = tempfile.mkdtemp()

      try:
          # Create memory and add data
          memory1 = BufferedMemory(
              membase_id=membase_config["membase_id"],
              membase_account=membase_config["membase_account"],
              membase_secret_key=membase_config["membase_secret_key"],
              storage_path=temp_dir,
              auto_upload_to_hub=False
          )

          memory1.add(Message(
              name="test",
              content="Persistent message",
              role="assistant"
          ))

          # Create new instance (simulating restart)
          memory2 = BufferedMemory(
              membase_id=membase_config["membase_id"],
              membase_account=membase_config["membase_account"],
              membase_secret_key=membase_config["membase_secret_key"],
              storage_path=temp_dir,
              auto_upload_to_hub=False,
              preload_from_hub=True  # Load from local storage
          )

          # Verify data persisted
          messages = memory2.messages
          assert len(messages) >= 1
          assert any(m.content == "Persistent message" for m in messages)

          print("✅ Memory persistence test passed")

      finally:
          shutil.rmtree(temp_dir)
  ```

**Success Criteria:**
- Local memory operations work
- Messages stored and retrieved correctly
- Memory persists across instances
- No cloud dependencies for basic functionality

**Rollback Plan:**
- Document failures
- Explore alternatives if persistence fails

---

#### Task 0.3: Test Cloud Sync (hub.membase.io)
**Duration:** 2-3 hours
**File:** `tests/test_membase_poc.py` (CONTINUED)

- [ ] Test BNB testnet wallet compatibility
  ```python
  def test_bnb_testnet_wallet(membase_config):
      """Verify BNB testnet wallet works with Membase"""
      # Get BNB testnet AVAX from faucet if needed
      # (Membase likely uses Ethereum-compatible addresses)

      memory = BufferedMemory(
          membase_id=membase_config["membase_id"],
          membase_account=membase_config["membase_account"],
          membase_secret_key=membase_config["membase_secret_key"],
          auto_upload_to_hub=True,  # Enable cloud sync
          preload_from_hub=False
      )

      # Add test message
      memory.add(Message(
          name="test",
          content="Cloud sync test",
          role="assistant",
          metadata={"test": "bnb_testnet"}
      ))

      # Wait for sync (if async)
      import time
      time.sleep(5)

      print("✅ BNB testnet wallet compatible")
  ```

- [ ] Test cloud upload
  ```python
  def test_cloud_upload(membase_config):
      """Test uploading memories to hub.membase.io"""
      memory = BufferedMemory(
          membase_id=membase_config["membase_id"],
          membase_account=membase_config["membase_account"],
          membase_secret_key=membase_config["membase_secret_key"],
          auto_upload_to_hub=True,
          preload_from_hub=False
      )

      # Add multiple messages
      for i in range(5):
          memory.add(Message(
              name=f"user_{i}",
              content=f"Test message {i}",
              role="user",
              metadata={"index": i}
          ))

      # Force sync if needed
      if hasattr(memory, 'sync'):
          memory.sync()

      print("✅ Cloud upload test completed")
      print(f"   Check hub.membase.io for account: {membase_config['membase_account']}")
  ```

- [ ] Test cloud download (preload)
  ```python
  def test_cloud_download(membase_config):
      """Test downloading memories from hub.membase.io"""
      # Assumes test_cloud_upload ran first
      memory = BufferedMemory(
          membase_id=membase_config["membase_id"],
          membase_account=membase_config["membase_account"],
          membase_secret_key=membase_config["membase_secret_key"],
          auto_upload_to_hub=False,
          preload_from_hub=True  # Load from cloud
      )

      # Verify messages downloaded
      messages = memory.messages
      assert len(messages) > 0

      print(f"✅ Cloud download test passed")
      print(f"   Downloaded {len(messages)} messages")
  ```

**Success Criteria:**
- BNB testnet wallet works with Membase
- Messages successfully upload to hub.membase.io
- Messages successfully download from hub.membase.io
- Sync is reliable and fast (<5 seconds)

**Rollback Plan:**
- Fallback to local-only memory if cloud fails
- Document cloud sync issues

---

#### Task 0.4: Test ChromaKnowledgeBase (Vector Search)
**Duration:** 3-4 hours
**File:** `tests/test_membase_knowledge.py` (NEW)

- [ ] Test ChromaDB integration
  ```python
  import pytest
  from membase.knowledge import ChromaKnowledgeBase
  from membase import Message

  @pytest.fixture
  def knowledge_base():
      # Create temporary knowledge base
      kb = ChromaKnowledgeBase(
          collection_name="test_kb",
          persist_directory="./test_chroma_db"
      )
      return kb

  def test_knowledge_base_add_documents(knowledge_base):
      """Test adding documents to knowledge base"""
      documents = [
          {
              "content": "User 0xUser1 purchased chat logs on 2025-10-20 for 0.01 GLUE",
              "metadata": {"user": "0xUser1", "service": "get_chat_logs", "date": "2025-10-20"}
          },
          {
              "content": "User 0xUser1 purchased transcription on 2025-10-22 for 0.02 GLUE",
              "metadata": {"user": "0xUser1", "service": "get_transcription", "date": "2025-10-22"}
          },
          {
              "content": "User 0xUser2 purchased chat logs on 2025-10-21 for 0.01 GLUE",
              "metadata": {"user": "0xUser2", "service": "get_chat_logs", "date": "2025-10-21"}
          }
      ]

      for doc in documents:
          knowledge_base.add(
              content=doc["content"],
              metadata=doc["metadata"]
          )

      print("✅ Documents added to knowledge base")

  def test_knowledge_base_search(knowledge_base):
      """Test semantic search"""
      # Add documents first
      test_knowledge_base_add_documents(knowledge_base)

      # Search by user
      results = knowledge_base.search(
          query="What did 0xUser1 purchase?",
          n_results=5
      )

      assert len(results) > 0
      user1_purchases = [r for r in results if "0xUser1" in r["content"]]
      assert len(user1_purchases) >= 2

      print(f"✅ Knowledge base search works")
      print(f"   Found {len(user1_purchases)} purchases for 0xUser1")

  def test_knowledge_base_filter(knowledge_base):
      """Test filtering by metadata"""
      # Add documents first
      test_knowledge_base_add_documents(knowledge_base)

      # Filter by service type
      results = knowledge_base.search(
          query="purchases",
          n_results=10,
          where={"service": "get_chat_logs"}
      )

      assert all(r["metadata"]["service"] == "get_chat_logs" for r in results)

      print("✅ Knowledge base filtering works")
  ```

- [ ] Test integration with BufferedMemory
  ```python
  def test_memory_to_knowledge_base():
      """Test converting memory to knowledge base entries"""
      from membase import BufferedMemory, Message
      from membase.knowledge import ChromaKnowledgeBase

      memory = BufferedMemory(
          membase_id="test-agent",
          auto_upload_to_hub=False
      )

      kb = ChromaKnowledgeBase(collection_name="test_integration")

      # Simulate user interactions
      memory.add(Message(
          name="user",
          content="I want chat logs from stream 12345",
          role="user",
          metadata={"service": "get_chat_logs", "stream_id": "12345"}
      ))

      memory.add(Message(
          name="agent",
          content="Here are 500 messages from stream 12345",
          role="assistant",
          metadata={"transaction": "0xabc", "message_count": 500, "price": "0.05"}
      ))

      # Convert memory to knowledge base
      for msg in memory.messages:
          kb.add(
              content=f"{msg.role}: {msg.content}",
              metadata=msg.metadata
          )

      # Search knowledge base
      results = kb.search("stream 12345", n_results=5)
      assert len(results) >= 2

      print("✅ Memory-to-knowledge-base integration works")
  ```

**Success Criteria:**
- ChromaDB installs and initializes
- Documents successfully added
- Semantic search returns relevant results
- Metadata filtering works
- Integration with BufferedMemory is seamless

**Rollback Plan:**
- Skip ChromaKnowledgeBase if too complex
- Use simple metadata search instead

---

#### Task 0.5: Document POC Findings
**Duration:** 1 hour
**File:** `docs/membase-poc-results.md` (NEW)

- [ ] Create POC results document
  ```markdown
  # Membase POC Results

  ## Test Summary

  | Test | Status | Notes |
  |------|--------|-------|
  | SDK Installation | ✅/❌ | ... |
  | BufferedMemory Local | ✅/❌ | ... |
  | MultiMemory Local | ✅/❌ | ... |
  | Memory Persistence | ✅/❌ | ... |
  | BNB Testnet Wallet | ✅/❌ | ... |
  | Cloud Upload | ✅/❌ | ... |
  | Cloud Download | ✅/❌ | ... |
  | ChromaKnowledgeBase | ✅/❌ | ... |

  ## Performance Metrics

  - Memory write latency: X ms
  - Memory read latency: X ms
  - Cloud sync latency: X ms
  - Search query latency: X ms

  ## Issues Identified

  1. [Issue description]
  2. [Issue description]

  ## Recommendations

  - Proceed with integration? Yes/No
  - Suggested modifications:
    - ...
  ```

- [ ] Update `.gitignore` to exclude test data
  ```bash
  # Add to .gitignore
  echo "tests/membase_poc/venv/" >> .gitignore
  echo "tests/membase_poc/.env.membase.test" >> .gitignore
  echo "test_chroma_db/" >> .gitignore
  echo "*.membase.db" >> .gitignore
  ```

**Success Criteria:**
- Clear go/no-go recommendation
- Performance metrics documented
- Issues cataloged

**Phase 0 Deliverables:**
- [ ] `tests/test_membase_poc.py` - POC test suite
- [ ] `tests/test_membase_knowledge.py` - Knowledge base tests
- [ ] `docs/membase-poc-results.md` - Results document
- [ ] `.gitignore` updated
- [ ] Go/No-Go decision made

---

## 🏗️ Phase 1: Foundation (Shared Infrastructure)
**Duration:** 3-4 days (12-16 hours)
**Dependencies:** Phase 0 complete (go decision)
**Status:** NOT STARTED

### Objectives
- Add Membase initialization to `shared/base_agent.py`
- Create memory helper methods for all agents
- Implement graceful degradation
- Update environment configuration
- Write unit tests for memory operations

### Tasks

#### Task 1.1: Update Base Agent with Membase Support
**Duration:** 4-6 hours
**File:** `shared/base_agent.py` (MODIFY)

- [ ] Add Membase imports
  ```python
  # In shared/base_agent.py, add to imports section (around line 23)

  # Membase for persistent memory (optional)
  try:
      from membase import MultiMemory, Message
      from membase.knowledge import ChromaKnowledgeBase
      MEMBASE_AVAILABLE = True
  except ImportError:
      MEMBASE_AVAILABLE = False
      logger.warning("Membase not installed - memory features disabled")
  ```

- [ ] Add memory configuration to `__init__`
  ```python
  # In ERC8004BaseAgent.__init__ (around line 66), add new parameters:

  def __init__(
      self,
      agent_name: str,
      agent_domain: str,
      rpc_url: str = None,
      chain_id: int = 43113,
      identity_registry_address: str = None,
      reputation_registry_address: str = None,
      validation_registry_address: str = None,
      private_key: str = None,
      # NEW: Membase configuration
      enable_memory: bool = None,
      membase_auto_upload: bool = None,
      membase_preload: bool = None
  ):
  ```

- [ ] Initialize Membase in constructor
  ```python
  # In ERC8004BaseAgent.__init__, after wallet setup (around line 131):

  # Initialize Membase memory (optional)
  self.memory_enabled = False
  self.memory: Optional[MultiMemory] = None
  self.knowledge_base: Optional[ChromaKnowledgeBase] = None

  if enable_memory is None:
      enable_memory = os.getenv("ENABLE_MEMORY", "false").lower() == "true"

  if enable_memory and MEMBASE_AVAILABLE:
      try:
          self._init_membase_memory(
              auto_upload=membase_auto_upload,
              preload=membase_preload
          )
          self.memory_enabled = True
          logger.info(f"[{self.agent_name}] ✅ Membase memory initialized")
      except Exception as e:
          logger.warning(f"[{self.agent_name}] ⚠️  Membase init failed: {e}")
          logger.warning(f"[{self.agent_name}] Continuing without memory features")
  elif enable_memory and not MEMBASE_AVAILABLE:
      logger.warning(f"[{self.agent_name}] Memory requested but Membase not installed")
  ```

- [ ] Add `_init_membase_memory` method
  ```python
  # Add as new method in ERC8004BaseAgent class (around line 280):

  def _init_membase_memory(
      self,
      auto_upload: Optional[bool] = None,
      preload: Optional[bool] = None
  ):
      """
      Initialize Membase memory for this agent

      Args:
          auto_upload: Auto-sync to hub.membase.io (default: from env)
          preload: Load existing memories from hub (default: from env)
      """
      if not MEMBASE_AVAILABLE:
          raise ImportError("Membase not installed")

      # Get configuration
      if auto_upload is None:
          auto_upload = os.getenv("MEMBASE_AUTO_UPLOAD", "true").lower() == "true"

      if preload is None:
          preload = os.getenv("MEMBASE_PRELOAD", "true").lower() == "true"

      membase_id = os.getenv("MEMBASE_ID") or f"{self.agent_name}-memory"
      storage_path = os.getenv("MEMBASE_STORAGE_PATH") or f"./memory/{self.agent_name}"

      # Create storage directory
      Path(storage_path).mkdir(parents=True, exist_ok=True)

      logger.info(f"[{self.agent_name}] Initializing Membase memory:")
      logger.info(f"   ID: {membase_id}")
      logger.info(f"   Account: {self.address}")
      logger.info(f"   Storage: {storage_path}")
      logger.info(f"   Auto-upload: {auto_upload}")
      logger.info(f"   Preload: {preload}")

      # Initialize MultiMemory (supports multiple conversations)
      self.memory = MultiMemory(
          membase_id=membase_id,
          membase_account=self.address,  # Use agent's wallet address
          membase_secret_key=self.private_key,
          auto_upload_to_hub=auto_upload,
          preload_from_hub=preload,
          storage_path=storage_path
      )

      # Initialize knowledge base for semantic search (optional)
      kb_enabled = os.getenv("MEMBASE_KNOWLEDGE_BASE", "false").lower() == "true"
      if kb_enabled:
          kb_path = os.getenv("MEMBASE_KB_PATH") or f"./knowledge/{self.agent_name}"
          self.knowledge_base = ChromaKnowledgeBase(
              collection_name=f"{self.agent_name}_kb",
              persist_directory=kb_path
          )
          logger.info(f"[{self.agent_name}] Knowledge base enabled: {kb_path}")
  ```

**Success Criteria:**
- Membase initialization optional (graceful degradation)
- Configuration from environment variables
- Logging shows initialization status
- No breaking changes to existing agents

**Rollback Plan:**
- Revert base_agent.py changes if tests fail
- Keep memory initialization disabled by default

---

#### Task 1.2: Add Memory Helper Methods
**Duration:** 3-4 hours
**File:** `shared/base_agent.py` (MODIFY)

- [ ] Add `remember_interaction` method
  ```python
  # Add as new method in ERC8004BaseAgent class (around line 710):

  def remember_interaction(
      self,
      conversation_id: str,
      role: str,
      content: str,
      metadata: Optional[Dict[str, Any]] = None
  ) -> bool:
      """
      Remember an interaction in agent memory

      Args:
          conversation_id: Conversation identifier (usually buyer address)
          role: Message role ("user" or "assistant")
          content: Message content
          metadata: Optional metadata (transaction hash, price, etc.)

      Returns:
          bool: True if stored successfully, False otherwise

      Example:
          >>> agent.remember_interaction(
          ...     conversation_id="0xBuyerAddress",
          ...     role="user",
          ...     content="I want chat logs for stream 12345",
          ...     metadata={"service": "get_chat_logs", "stream_id": "12345"}
          ... )
      """
      if not self.memory_enabled or not self.memory:
          logger.debug(f"[{self.agent_name}] Memory disabled - skipping remember")
          return False

      try:
          message = Message(
              name=conversation_id if role == "user" else self.agent_name,
              content=content,
              role=role,
              metadata=metadata or {}
          )

          self.memory.add(
              conversation_id=conversation_id,
              message=message
          )

          # Also add to knowledge base if enabled
          if self.knowledge_base:
              self.knowledge_base.add(
                  content=f"[{conversation_id}] {role}: {content}",
                  metadata={
                      **(metadata or {}),
                      "conversation_id": conversation_id,
                      "role": role,
                      "agent": self.agent_name
                  }
              )

          logger.debug(f"[{self.agent_name}] Remembered: {content[:50]}...")
          return True

      except Exception as e:
          logger.error(f"[{self.agent_name}] Failed to remember: {e}")
          return False
  ```

- [ ] Add `recall_user_history` method
  ```python
  # Add as new method in ERC8004BaseAgent class:

  def recall_user_history(
      self,
      conversation_id: str,
      limit: Optional[int] = None
  ) -> List[Message]:
      """
      Recall conversation history for a user

      Args:
          conversation_id: Conversation identifier (usually buyer address)
          limit: Maximum messages to return (None = all)

      Returns:
          List of Message objects (empty list if memory disabled)

      Example:
          >>> history = agent.recall_user_history("0xBuyerAddress", limit=10)
          >>> for msg in history:
          ...     print(f"{msg.role}: {msg.content}")
      """
      if not self.memory_enabled or not self.memory:
          return []

      try:
          messages = self.memory.get_messages(conversation_id)

          if limit:
              messages = messages[-limit:]  # Get most recent N messages

          logger.debug(f"[{self.agent_name}] Recalled {len(messages)} messages for {conversation_id}")
          return messages

      except Exception as e:
          logger.error(f"[{self.agent_name}] Failed to recall: {e}")
          return []
  ```

- [ ] Add `get_user_preferences` method
  ```python
  # Add as new method in ERC8004BaseAgent class:

  def get_user_preferences(
      self,
      conversation_id: str
  ) -> Dict[str, Any]:
      """
      Extract learned preferences from user history

      Analyzes conversation history to identify patterns:
      - Frequently requested services
      - Preferred formats
      - Typical request parameters
      - Quality expectations

      Args:
          conversation_id: User identifier

      Returns:
          Dictionary of preferences

      Example:
          >>> prefs = agent.get_user_preferences("0xBuyerAddress")
          >>> print(prefs["favorite_service"])  # "get_chat_logs"
          >>> print(prefs["repeat_customer"])    # True
      """
      if not self.memory_enabled or not self.memory:
          return {}

      try:
          history = self.recall_user_history(conversation_id)

          if not history:
              return {"new_customer": True}

          # Analyze history
          preferences = {
              "total_interactions": len(history),
              "repeat_customer": len(history) > 1,
              "services_used": [],
              "average_rating": None,
              "last_interaction": None
          }

          for msg in history:
              if msg.metadata:
                  # Track services
                  if "service" in msg.metadata:
                      service = msg.metadata["service"]
                      if service not in preferences["services_used"]:
                          preferences["services_used"].append(service)

                  # Track ratings
                  if "user_rating" in msg.metadata:
                      if preferences["average_rating"] is None:
                          preferences["average_rating"] = msg.metadata["user_rating"]
                      else:
                          # Running average
                          preferences["average_rating"] = (
                              preferences["average_rating"] + msg.metadata["user_rating"]
                          ) / 2

                  # Track timestamp
                  if "timestamp" in msg.metadata:
                      preferences["last_interaction"] = msg.metadata["timestamp"]

          # Determine favorite service
          if preferences["services_used"]:
              preferences["favorite_service"] = preferences["services_used"][0]

          return preferences

      except Exception as e:
          logger.error(f"[{self.agent_name}] Failed to get preferences: {e}")
          return {}
  ```

- [ ] Add `search_knowledge` method
  ```python
  # Add as new method in ERC8004BaseAgent class:

  def search_knowledge(
      self,
      query: str,
      n_results: int = 5,
      filter_metadata: Optional[Dict[str, Any]] = None
  ) -> List[Dict[str, Any]]:
      """
      Search knowledge base using semantic search

      Args:
          query: Search query
          n_results: Maximum results to return
          filter_metadata: Filter by metadata fields

      Returns:
          List of search results

      Example:
          >>> results = agent.search_knowledge(
          ...     "chat logs for stream 12345",
          ...     n_results=10,
          ...     filter_metadata={"service": "get_chat_logs"}
          ... )
      """
      if not self.knowledge_base:
          logger.warning(f"[{self.agent_name}] Knowledge base not enabled")
          return []

      try:
          results = self.knowledge_base.search(
              query=query,
              n_results=n_results,
              where=filter_metadata
          )

          logger.debug(f"[{self.agent_name}] Found {len(results)} results for: {query}")
          return results

      except Exception as e:
          logger.error(f"[{self.agent_name}] Knowledge search failed: {e}")
          return []
  ```

**Success Criteria:**
- All helper methods implement graceful degradation
- Methods return appropriate defaults when memory disabled
- Clear logging for debugging
- Type hints and docstrings complete

**Rollback Plan:**
- Remove helper methods if too complex
- Simplify to just remember/recall basics

---

#### Task 1.3: Update Environment Configuration
**Duration:** 1-2 hours
**Files:** `karma-hello-agent/.env.example`, `abracadabra-agent/.env.example`, etc.

- [ ] Add Membase configuration to all agent `.env.example` files
  ```bash
  # Template to add to each agent's .env.example:

  # ============================================================================
  # MEMBASE CONFIGURATION (Optional - Persistent Memory)
  # ============================================================================

  # Enable/disable memory features
  ENABLE_MEMORY=false

  # Membase account configuration
  # MEMBASE_ID: Unique identifier for this agent's memory
  # MEMBASE_ACCOUNT: Agent wallet address (auto-set from PRIVATE_KEY)
  # MEMBASE_SECRET_KEY: Agent private key (auto-set from PRIVATE_KEY)
  MEMBASE_ID=karma-hello-memory

  # Cloud sync settings
  MEMBASE_AUTO_UPLOAD=true   # Auto-sync to hub.membase.io
  MEMBASE_PRELOAD=true       # Load existing memories on startup

  # Storage paths (local cache)
  MEMBASE_STORAGE_PATH=./memory/karma-hello
  MEMBASE_KB_PATH=./knowledge/karma-hello

  # Knowledge base (semantic search)
  MEMBASE_KNOWLEDGE_BASE=false  # Enable ChromaDB integration
  ```

- [ ] Update each agent's `.env.example`:
  - [ ] `karma-hello-agent/.env.example`
  - [ ] `abracadabra-agent/.env.example`
  - [ ] `skill-extractor-agent/.env.example`
  - [ ] `voice-extractor-agent/.env.example`
  - [ ] `validator/.env.example`
  - [ ] `client-agent/.env.example`

- [ ] Update shared requirements
  ```bash
  # Create shared/requirements-memory.txt (NEW)
  cat > shared/requirements-memory.txt << EOF
  # Membase - Persistent Memory Layer
  # Install from GitHub: pip install git+https://github.com/unibaseio/membase.git

  # Core dependencies
  chromadb>=0.4.0  # Vector database for knowledge base
  langchain>=0.1.0  # Optional: for advanced memory features

  # Installation:
  # pip install git+https://github.com/unibaseio/membase.git
  # pip install -r shared/requirements-memory.txt
  EOF
  ```

- [ ] Add installation instructions to README
  ```bash
  # Add to README.md (around line 150, in Dependencies section):

  echo "
  ### Optional: Membase Memory Layer

  For persistent agent memory and knowledge base:

  \`\`\`bash
  # Install Membase SDK
  pip install git+https://github.com/unibaseio/membase.git

  # Install memory dependencies
  pip install -r shared/requirements-memory.txt

  # Enable in .env
  ENABLE_MEMORY=true
  \`\`\`
  " >> README.md
  ```

**Success Criteria:**
- All `.env.example` files updated consistently
- Clear documentation for optional feature
- Installation instructions complete

**Rollback Plan:**
- Remove Membase config from `.env.example` files
- Mark as experimental feature only

---

#### Task 1.4: Write Unit Tests for Memory
**Duration:** 3-4 hours
**File:** `tests/test_base_agent_memory.py` (NEW)

- [ ] Create comprehensive memory test suite
  ```python
  """
  Unit tests for ERC8004BaseAgent memory features

  Tests memory operations, graceful degradation, and error handling.
  """

  import pytest
  import os
  import tempfile
  import shutil
  from pathlib import Path
  from unittest.mock import Mock, patch

  import sys
  sys.path.append(str(Path(__file__).parent.parent))

  from shared.base_agent import ERC8004BaseAgent, MEMBASE_AVAILABLE


  @pytest.fixture
  def temp_memory_dir():
      """Create temporary directory for memory storage"""
      temp_dir = tempfile.mkdtemp()
      yield temp_dir
      shutil.rmtree(temp_dir)


  @pytest.fixture
  def agent_config(temp_memory_dir):
      """Base agent configuration for testing"""
      return {
          "agent_name": "test-agent",
          "agent_domain": "test.karmacadabra.ultravioletadao.xyz",
          "rpc_url": os.getenv("RPC_URL_FUJI"),
          "identity_registry_address": os.getenv("IDENTITY_REGISTRY"),
          "reputation_registry_address": os.getenv("REPUTATION_REGISTRY"),
          "enable_memory": True,
          "membase_auto_upload": False,  # Disable cloud for tests
          "membase_preload": False
      }


  @pytest.mark.skipif(not MEMBASE_AVAILABLE, reason="Membase not installed")
  class TestMemoryEnabled:
      """Tests for memory-enabled agents"""

      def test_memory_initialization(self, agent_config):
          """Test that memory initializes correctly"""
          # Set memory storage path
          with patch.dict(os.environ, {"MEMBASE_STORAGE_PATH": "./test_memory"}):
              agent = ERC8004BaseAgent(**agent_config)

              assert agent.memory_enabled is True
              assert agent.memory is not None
              print("✅ Memory initialized successfully")

      def test_remember_interaction(self, agent_config):
          """Test remembering user interactions"""
          agent = ERC8004BaseAgent(**agent_config)

          conversation_id = "0xTestUser"
          success = agent.remember_interaction(
              conversation_id=conversation_id,
              role="user",
              content="I want to buy chat logs",
              metadata={"service": "get_chat_logs", "price": "0.01"}
          )

          assert success is True

          # Verify memory stored
          history = agent.recall_user_history(conversation_id)
          assert len(history) == 1
          assert "buy chat logs" in history[0].content
          print("✅ Interaction remembered")

      def test_recall_user_history(self, agent_config):
          """Test recalling conversation history"""
          agent = ERC8004BaseAgent(**agent_config)

          conversation_id = "0xTestUser"

          # Add multiple interactions
          interactions = [
              ("user", "Buy logs for stream 123"),
              ("assistant", "Here are your logs"),
              ("user", "Buy transcription"),
              ("assistant", "Here is your transcription")
          ]

          for role, content in interactions:
              agent.remember_interaction(conversation_id, role, content)

          # Recall all
          history = agent.recall_user_history(conversation_id)
          assert len(history) == 4

          # Recall limited
          recent = agent.recall_user_history(conversation_id, limit=2)
          assert len(recent) == 2
          assert "transcription" in recent[-1].content

          print("✅ User history recalled correctly")

      def test_get_user_preferences(self, agent_config):
          """Test preference extraction"""
          agent = ERC8004BaseAgent(**agent_config)

          conversation_id = "0xTestUser"

          # Simulate multiple purchases
          agent.remember_interaction(
              conversation_id,
              "user",
              "Buy chat logs",
              metadata={"service": "get_chat_logs", "user_rating": 5}
          )

          agent.remember_interaction(
              conversation_id,
              "user",
              "Buy chat logs again",
              metadata={"service": "get_chat_logs", "user_rating": 4}
          )

          # Get preferences
          prefs = agent.get_user_preferences(conversation_id)

          assert prefs["repeat_customer"] is True
          assert prefs["total_interactions"] == 2
          assert "get_chat_logs" in prefs["services_used"]
          assert prefs["average_rating"] > 0

          print("✅ User preferences extracted")


  class TestMemoryDisabled:
      """Tests for graceful degradation when memory disabled"""

      def test_memory_disabled_gracefully(self, agent_config):
          """Test agent works without memory"""
          agent_config["enable_memory"] = False
          agent = ERC8004BaseAgent(**agent_config)

          assert agent.memory_enabled is False
          assert agent.memory is None
          print("✅ Agent works without memory")

      def test_remember_returns_false_when_disabled(self, agent_config):
          """Test remember_interaction returns False when disabled"""
          agent_config["enable_memory"] = False
          agent = ERC8004BaseAgent(**agent_config)

          success = agent.remember_interaction(
              "0xTest",
              "user",
              "Test message"
          )

          assert success is False
          print("✅ Remember returns False when disabled")

      def test_recall_returns_empty_when_disabled(self, agent_config):
          """Test recall_user_history returns empty list"""
          agent_config["enable_memory"] = False
          agent = ERC8004BaseAgent(**agent_config)

          history = agent.recall_user_history("0xTest")

          assert history == []
          print("✅ Recall returns empty when disabled")

      def test_preferences_returns_empty_when_disabled(self, agent_config):
          """Test get_user_preferences returns empty dict"""
          agent_config["enable_memory"] = False
          agent = ERC8004BaseAgent(**agent_config)

          prefs = agent.get_user_preferences("0xTest")

          assert prefs == {}
          print("✅ Preferences returns empty when disabled")


  @pytest.mark.skipif(not MEMBASE_AVAILABLE, reason="Membase not installed")
  class TestKnowledgeBase:
      """Tests for ChromaDB knowledge base"""

      def test_knowledge_base_initialization(self, agent_config):
          """Test knowledge base initializes"""
          with patch.dict(os.environ, {"MEMBASE_KNOWLEDGE_BASE": "true"}):
              agent = ERC8004BaseAgent(**agent_config)

              assert agent.knowledge_base is not None
              print("✅ Knowledge base initialized")

      def test_search_knowledge(self, agent_config):
          """Test semantic search"""
          with patch.dict(os.environ, {"MEMBASE_KNOWLEDGE_BASE": "true"}):
              agent = ERC8004BaseAgent(**agent_config)

              # Add interactions with knowledge base
              agent.remember_interaction(
                  "0xUser1",
                  "user",
                  "I need chat logs for stream 12345",
                  metadata={"service": "get_chat_logs", "stream_id": "12345"}
              )

              # Search knowledge base
              results = agent.search_knowledge("stream 12345")

              assert len(results) > 0
              print("✅ Knowledge base search works")


  if __name__ == "__main__":
      pytest.main([__file__, "-v"])
  ```

- [ ] Run tests
  ```bash
  cd Z:\ultravioleta\dao\karmacadabra
  pytest tests/test_base_agent_memory.py -v
  ```

**Success Criteria:**
- All tests pass (with Membase installed)
- Graceful degradation tests pass (without Membase)
- Code coverage >80% for memory methods

**Rollback Plan:**
- Skip knowledge base tests if too flaky
- Focus on basic memory operations only

---

**Phase 1 Deliverables:**
- [ ] `shared/base_agent.py` - Updated with Membase support
- [ ] All agent `.env.example` files - Membase configuration added
- [ ] `shared/requirements-memory.txt` - Memory dependencies
- [ ] `tests/test_base_agent_memory.py` - Comprehensive test suite
- [ ] `README.md` - Installation instructions updated
- [ ] All tests passing

---

## 🧪 Phase 2: Single Agent Integration (Pilot)
**Duration:** 2-3 days (8-12 hours)
**Dependencies:** Phase 1 complete
**Status:** NOT STARTED

### Objectives
- Integrate Membase into karma-hello-agent as pilot
- Test memory tracking in real service endpoints
- Validate persistence across restarts
- Document lessons learned

### Tasks

#### Task 2.1: Enable Memory in Karma-Hello Agent
**Duration:** 2-3 hours
**File:** `karma-hello-agent/agent.py` (MODIFY)

- [ ] Update KarmaHelloSeller constructor to enable memory
  ```python
  # In karma-hello-agent/agent.py, modify __init__ (around line 84):

  def __init__(self, config: Dict[str, Any]):
      """Initialize Karma-Hello seller agent"""

      # Initialize base agent (registers on-chain)
      super().__init__(
          agent_name="karma-hello-agent",
          agent_domain=config["agent_domain"],
          rpc_url=config["rpc_url_fuji"],
          chain_id=config["chain_id"],
          identity_registry_address=config["identity_registry"],
          reputation_registry_address=config["reputation_registry"],
          validation_registry_address=config["validation_registry"],
          private_key=config.get("private_key"),
          # NEW: Enable memory
          enable_memory=config.get("enable_memory", False),
          membase_auto_upload=config.get("membase_auto_upload"),
          membase_preload=config.get("membase_preload")
      )

      # ... rest of initialization
  ```

- [ ] Update config loading in main.py
  ```python
  # In karma-hello-agent/main.py (around line 429):

  config = {
      "private_key": os.getenv("PRIVATE_KEY") or None,
      "rpc_url_fuji": os.getenv("RPC_URL_FUJI"),
      # ... existing config ...

      # NEW: Membase configuration
      "enable_memory": os.getenv("ENABLE_MEMORY", "false").lower() == "true",
      "membase_auto_upload": os.getenv("MEMBASE_AUTO_UPLOAD", "true").lower() == "true",
      "membase_preload": os.getenv("MEMBASE_PRELOAD", "true").lower() == "true"
  }
  ```

- [ ] Add memory tracking to health endpoint
  ```python
  # In karma-hello-agent/main.py, update health endpoint (around line 461):

  @app.get("/")
  async def root():
      """Health check endpoint"""
      return {
          "service": "Karma-Hello Seller",
          "status": "healthy",
          "agent_id": str(agent.agent_id) if agent.agent_id else "unregistered",
          "address": agent.address,
          "balance": f"{agent.get_balance()} AVAX",
          "data_source": "local_files" if agent.use_local_files else "mongodb",
          # NEW: Memory status
          "memory_enabled": agent.memory_enabled,
          "memory_conversations": len(agent.memory._conversations) if agent.memory_enabled else 0
      }
  ```

**Success Criteria:**
- Memory initializes without errors
- Health endpoint shows memory status
- Agent works with memory enabled/disabled

**Rollback Plan:**
- Set `ENABLE_MEMORY=false` to disable
- Revert agent.py changes if issues

---

#### Task 2.2: Add Memory Tracking to Service Endpoints
**Duration:** 3-4 hours
**File:** `karma-hello-agent/main.py` (MODIFY)

- [ ] Update `get_chat_logs` endpoint with memory
  ```python
  # In karma-hello-agent/main.py, modify get_chat_logs endpoint (around line 484):

  @app.post("/get_chat_logs")
  async def get_chat_logs(request: ChatLogRequest):
      """
      Get chat logs endpoint

      Supports x402 payment protocol via X-Payment header.
      NOW WITH MEMORY: Tracks user interactions and preferences.
      """
      try:
          # Determine buyer address (from payment header or use default)
          buyer_address = "0xUnknownBuyer"  # TODO: Extract from X-Payment header

          # Recall user history (for personalization)
          if agent.memory_enabled:
              prefs = agent.get_user_preferences(buyer_address)

              if prefs.get("repeat_customer"):
                  logger.info(f"[karma-hello] Welcome back! {prefs['total_interactions']} previous purchases")
              else:
                  logger.info(f"[karma-hello] New customer: {buyer_address}")

          # Remember the request
          if agent.memory_enabled:
              agent.remember_interaction(
                  conversation_id=buyer_address,
                  role="user",
                  content=f"Requested chat logs: {request.model_dump_json()}",
                  metadata={
                      "service": "get_chat_logs",
                      "stream_id": request.stream_id,
                      "date": request.date,
                      "users": request.users,
                      "limit": request.limit,
                      "timestamp": datetime.utcnow().isoformat()
                  }
              )

          # Get data from appropriate source
          if agent.use_local_files:
              response = await agent.get_chat_logs_from_file(request)
          else:
              response = await agent.get_chat_logs_from_mongo(request)

          # Calculate price
          price = agent.calculate_price(response.total_messages)

          # Remember the response
          if agent.memory_enabled:
              agent.remember_interaction(
                  conversation_id=buyer_address,
                  role="assistant",
                  content=f"Delivered {response.total_messages} messages from {response.stream_id}",
                  metadata={
                      "service": "get_chat_logs",
                      "stream_id": response.stream_id,
                      "message_count": response.total_messages,
                      "price_glue": str(price),
                      "timestamp": datetime.utcnow().isoformat()
                  }
              )

          return JSONResponse(
              content=response.model_dump(),
              headers={
                  "X-Price": str(price),
                  "X-Currency": "GLUE",
                  "X-Message-Count": str(response.total_messages),
                  # NEW: Indicate repeat customer
                  "X-Repeat-Customer": str(prefs.get("repeat_customer", False)) if agent.memory_enabled else "false"
              }
          )

      except HTTPException:
          raise
      except Exception as e:
          raise HTTPException(status_code=500, detail=f"Error retrieving logs: {str(e)}")
  ```

- [ ] Add buyer address extraction helper
  ```python
  # Add new helper function in karma-hello-agent/main.py (around line 425):

  def extract_buyer_address_from_payment(request: Request) -> str:
      """
      Extract buyer address from X-Payment header

      For now, returns placeholder. Will be integrated with x402 middleware
      in future phases.

      Args:
          request: FastAPI request object

      Returns:
          Buyer wallet address or "0xUnknownBuyer"
      """
      payment_header = request.headers.get("X-Payment")

      if not payment_header:
          return "0xUnknownBuyer"

      # TODO: Parse EIP-712 signature from payment header
      # For now, return placeholder
      return "0xUnknownBuyer"
  ```

- [ ] Update endpoint signature to accept Request
  ```python
  # Modify get_chat_logs to accept Request object:

  from fastapi import FastAPI, HTTPException, Request  # Add Request import

  @app.post("/get_chat_logs")
  async def get_chat_logs(request_data: ChatLogRequest, request: Request):
      """Get chat logs endpoint with memory tracking"""

      # Extract buyer address
      buyer_address = extract_buyer_address_from_payment(request)

      # ... rest of implementation
  ```

**Success Criteria:**
- Interactions logged to memory
- User preferences tracked
- Repeat customer detection works
- No performance degradation

**Rollback Plan:**
- Remove memory calls from endpoint
- Keep memory optional (check `agent.memory_enabled`)

---

#### Task 2.3: Test Memory Persistence Across Restarts
**Duration:** 2-3 hours
**File:** `tests/test_karma_hello_memory.py` (NEW)

- [ ] Create integration test for memory persistence
  ```python
  """
  Integration tests for Karma-Hello agent memory persistence

  Tests that memory survives agent restarts and correctly tracks
  user interactions across sessions.
  """

  import pytest
  import asyncio
  import httpx
  import os
  from pathlib import Path


  @pytest.mark.asyncio
  async def test_memory_persistence_across_restarts():
      """
      Test that user interactions persist across agent restarts

      Steps:
      1. Start karma-hello agent with memory enabled
      2. Make purchase request (user interaction)
      3. Stop agent
      4. Restart agent
      5. Verify memory loaded from storage
      6. Make another purchase (should be repeat customer)
      """

      # This test requires manual agent start/stop
      # For now, document the manual testing procedure

      print("""
      MANUAL TEST PROCEDURE:

      1. Setup karma-hello-agent with memory:
         ```bash
         cd karma-hello-agent
         cp .env.example .env
         # Edit .env:
         ENABLE_MEMORY=true
         MEMBASE_AUTO_UPLOAD=false  # Local testing only
         MEMBASE_PRELOAD=true
         ```

      2. Start agent (first time):
         ```bash
         python main.py
         ```

      3. Make test purchase:
         ```bash
         curl -X POST http://localhost:8002/get_chat_logs \
           -H "Content-Type: application/json" \
           -d '{"date": "2025-10-24", "limit": 100}'
         ```

         Expected: Logs show "New customer: 0xUnknownBuyer"

      4. Stop agent (Ctrl+C)

      5. Restart agent:
         ```bash
         python main.py
         ```

         Expected: Logs show "Loaded X messages from storage"

      6. Make another purchase (same request):
         ```bash
         curl -X POST http://localhost:8002/get_chat_logs \
           -H "Content-Type: application/json" \
           -d '{"date": "2025-10-24", "limit": 100}'
         ```

         Expected: Logs show "Welcome back! 2 previous purchases"
         Expected: Response header "X-Repeat-Customer: true"

      7. Verify memory files created:
         ```bash
         ls ./memory/karma-hello-agent/
         ```

         Expected: Memory database files present
      """)

      # Automated portion (check files exist)
      memory_path = Path("./memory/karma-hello-agent")
      if memory_path.exists():
          print(f"✅ Memory storage directory exists: {memory_path}")

          files = list(memory_path.glob("*"))
          if files:
              print(f"✅ Memory files found: {len(files)}")
          else:
              print("⚠️  Memory directory empty - no interactions yet")
      else:
          print("⚠️  Memory storage directory not created yet")


  @pytest.mark.asyncio
  async def test_user_preferences_accumulation():
      """
      Test that user preferences accumulate over multiple interactions
      """

      # Test with live agent
      agent_url = "http://localhost:8002"

      try:
          async with httpx.AsyncClient() as client:
              # Check if agent is running
              response = await client.get(f"{agent_url}/health", timeout=5.0)

              if response.status_code != 200:
                  pytest.skip("Karma-Hello agent not running")

              health = response.json()

              if not health.get("memory_enabled"):
                  pytest.skip("Memory not enabled on agent")

              print(f"✅ Agent running with memory: {health['memory_conversations']} conversations")

              # Make multiple requests to accumulate preferences
              for i in range(3):
                  response = await client.post(
                      f"{agent_url}/get_chat_logs",
                      json={"date": "2025-10-24", "limit": 100}
                  )

                  assert response.status_code == 200

                  # Check repeat customer header
                  repeat = response.headers.get("X-Repeat-Customer", "false")
                  if i > 0:
                      assert repeat == "true", f"Expected repeat customer on interaction {i+1}"

                  print(f"✅ Interaction {i+1}: Repeat customer = {repeat}")

      except httpx.ConnectError:
          pytest.skip("Karma-Hello agent not running")


  if __name__ == "__main__":
      pytest.main([__file__, "-v"])
  ```

- [ ] Run manual persistence test
  ```bash
  # Follow the manual procedure in the test
  cd karma-hello-agent

  # First run
  ENABLE_MEMORY=true MEMBASE_AUTO_UPLOAD=false python main.py
  # Make request, stop

  # Second run
  ENABLE_MEMORY=true MEMBASE_PRELOAD=true python main.py
  # Make request, verify repeat customer
  ```

**Success Criteria:**
- Memory persists across restarts
- Preload successfully loads previous interactions
- Repeat customer detection works
- No data loss on restart

**Rollback Plan:**
- Document any persistence issues
- Use local-only mode if cloud sync problematic

---

#### Task 2.4: Document Lessons Learned
**Duration:** 1 hour
**File:** `docs/membase-pilot-results.md` (NEW)

- [ ] Create pilot results document
  ```markdown
  # Membase Pilot Integration Results
  ## Karma-Hello Agent

  **Date:** [Current Date]
  **Agent:** karma-hello-agent
  **Status:** ✅/⚠️/❌

  ---

  ## Summary

  [Brief summary of pilot integration success/challenges]

  ---

  ## What Worked Well

  1. **Memory Initialization**
     - [ ] Membase initialized without errors
     - [ ] Local storage created correctly
     - [ ] Cloud sync (if enabled) worked

  2. **Interaction Tracking**
     - [ ] User requests logged to memory
     - [ ] Agent responses logged to memory
     - [ ] Metadata captured correctly

  3. **Persistence**
     - [ ] Memory survived agent restart
     - [ ] Preload loaded previous interactions
     - [ ] No data corruption

  4. **Performance**
     - [ ] No noticeable latency increase
     - [ ] Concurrent requests handled
     - [ ] Memory footprint acceptable

  ---

  ## Challenges & Issues

  ### Issue 1: [Title]
  **Description:** [What went wrong]
  **Impact:** [How it affected functionality]
  **Workaround:** [Temporary solution]
  **Fix Needed:** [Permanent solution]

  ### Issue 2: [Title]
  **Description:** ...
  **Impact:** ...
  **Workaround:** ...
  **Fix Needed:** ...

  ---

  ## Performance Metrics

  | Metric | Without Memory | With Memory | Change |
  |--------|----------------|-------------|--------|
  | Request latency (avg) | X ms | Y ms | +Z ms |
  | Memory usage (agent) | X MB | Y MB | +Z MB |
  | Storage size (10 interactions) | 0 MB | X MB | +X MB |
  | Startup time | X s | Y s | +Z s |

  ---

  ## Code Changes Required

  ### Base Agent
  - [x] Membase initialization
  - [x] Memory helper methods
  - [ ] Additional changes needed: ...

  ### Karma-Hello Agent
  - [x] Config loading
  - [x] Endpoint memory tracking
  - [ ] Additional changes needed: ...

  ---

  ## Recommendations for Multi-Agent Rollout

  ### What to Keep
  1. [Practice that worked well]
  2. [Practice that worked well]

  ### What to Change
  1. [Practice that needs improvement]
  2. [Practice that needs improvement]

  ### What to Add
  1. [Missing feature needed]
  2. [Missing feature needed]

  ---

  ## Next Steps

  - [ ] Fix identified issues
  - [ ] Update base agent if needed
  - [ ] Proceed to multi-agent rollout (Phase 3)
  - [ ] OR: Pause integration to address blockers

  ---

  ## Appendix: Test Results

  ### Manual Persistence Test
  ```
  [Paste test output]
  ```

  ### Automated Tests
  ```
  [Paste pytest output]
  ```
  ```

**Success Criteria:**
- Lessons documented clearly
- Issues cataloged with workarounds
- Go/no-go decision for Phase 3

**Phase 2 Deliverables:**
- [ ] `karma-hello-agent/agent.py` - Memory integration
- [ ] `karma-hello-agent/main.py` - Endpoint tracking
- [ ] `karma-hello-agent/.env` - Memory configuration
- [ ] `tests/test_karma_hello_memory.py` - Integration tests
- [ ] `docs/membase-pilot-results.md` - Lessons learned
- [ ] Go/No-Go decision for Phase 3

---

## 🚀 Phase 3: Multi-Agent Rollout
**Duration:** 3-4 days (12-16 hours)
**Dependencies:** Phase 2 complete (go decision)
**Status:** NOT STARTED

### Objectives
- Integrate Membase into all remaining agents
- Ensure consistent memory patterns across agents
- Test cross-agent memory scenarios

### Tasks

#### Task 3.1: Integrate Abracadabra Agent
**Duration:** 2-3 hours
**File:** `abracadabra-agent/agent.py` (MODIFY)

- [ ] Follow same pattern as karma-hello
  ```python
  # Use karma-hello integration as template
  # Same changes:
  # 1. Enable memory in __init__
  # 2. Update config loading
  # 3. Add memory tracking to endpoints
  # 4. Test persistence
  ```

- [ ] Add memory to `get_transcription` endpoint
- [ ] Add memory to buyer methods (when buying chat logs)
- [ ] Test with local files
- [ ] Verify restart persistence

**Success Criteria:**
- Abracadabra agent tracks user interactions
- Memory persists across restarts
- No regressions in existing functionality

---

#### Task 3.2: Integrate Skill-Extractor Agent
**Duration:** 2-3 hours
**File:** `skill-extractor-agent/agent.py` (MODIFY)

- [ ] Follow same pattern as karma-hello
- [ ] Add memory to skill extraction endpoints
- [ ] Add memory to buyer methods
- [ ] Test with real user profiles
- [ ] Verify restart persistence

**Success Criteria:**
- Skill-extractor tracks user interactions
- Extracted skills stored in memory
- Cross-referencing works (references chat logs purchased)

---

#### Task 3.3: Integrate Voice-Extractor Agent
**Duration:** 2-3 hours
**File:** `voice-extractor-agent/agent.py` (MODIFY)

- [ ] Follow same pattern as karma-hello
- [ ] Add memory to voice extraction endpoints
- [ ] Add memory to buyer methods
- [ ] Test with real personality profiles
- [ ] Verify restart persistence

**Success Criteria:**
- Voice-extractor tracks user interactions
- Personality profiles stored in memory
- Cross-referencing works

---

#### Task 3.4: Integrate Validator Agent
**Duration:** 2-3 hours
**File:** `validator/agent.py` (MODIFY)

- [ ] Follow same pattern as karma-hello
- [ ] Add memory to validation endpoints
- [ ] Store validation results in memory
- [ ] Track validation requests
- [ ] Verify restart persistence

**Special Considerations:**
- Validator doesn't buy/sell like other agents
- Memory should track validation history
- Quality trends over time

**Success Criteria:**
- Validator tracks validation history
- Historical quality scores accessible
- Memory aids in detecting fraud patterns

---

#### Task 3.5: Integrate Client Agent (Optional)
**Duration:** 1-2 hours
**File:** `client-agent/agent.py` (MODIFY)

- [ ] Client agent is buyer-only
- [ ] Add memory to track purchases
- [ ] Store purchase history
- [ ] Verify restart persistence

**Success Criteria:**
- Client agent tracks all purchases
- Purchase history accessible
- Spending patterns visible

---

**Phase 3 Deliverables:**
- [ ] All 5 agents integrated with memory
- [ ] Consistent memory patterns
- [ ] All agents tested individually
- [ ] No regressions in existing functionality

---

## 🔗 Phase 4: Cross-Agent Memory Sharing
**Duration:** 2-3 days (8-12 hours)
**Dependencies:** Phase 3 complete
**Status:** NOT STARTED

### Objectives
- Design shared memory schema for agent-to-agent interactions
- Enable cross-agent knowledge sharing
- Create composite services leveraging shared memory
- Test multi-agent collaboration flows

### Tasks

#### Task 4.1: Design Cross-Agent Memory Schema
**Duration:** 2-3 hours
**File:** `docs/cross-agent-memory-schema.md` (NEW)

- [ ] Define conversation ID standards
  ```markdown
  # Cross-Agent Memory Schema

  ## Conversation ID Standards

  ### User-to-Agent Interactions
  ```
  conversation_id = buyer_wallet_address
  # Example: "0xCf30021812F27132d36dc791E0eC17f34B4eE8BA"
  ```

  ### Agent-to-Agent Interactions
  ```
  conversation_id = f"{buyer_agent_name}_{seller_agent_name}"
  # Example: "karma-hello_abracadabra"
  ```

  ### Shared Knowledge Pool
  ```
  conversation_id = "shared_knowledge"
  # Used for system-wide insights, trends, patterns
  ```

  ## Metadata Standards

  ### Required Fields (All Messages)
  - `timestamp`: ISO 8601 timestamp
  - `service_type`: Service identifier
  - `agent_sender`: Sending agent name
  - `agent_receiver`: Receiving agent name (or "user")

  ### Optional Fields (Transaction-Related)
  - `transaction_hash`: On-chain transaction hash
  - `price_glue`: Transaction amount
  - `validator_score`: Quality score (if validated)
  - `user_rating`: User satisfaction rating

  ### Optional Fields (Content-Related)
  - `stream_id`: Stream identifier
  - `date`: Content date
  - `message_count`: Number of messages
  - `duration_seconds`: Duration in seconds
  - `user_profile_id`: User identifier

  ## Cross-Reference Patterns

  ### Pattern 1: Service Chain
  When agent B buys from agent A to produce output:

  ```python
  # Agent B remembers purchase from Agent A
  agent_b.remember_interaction(
      conversation_id=f"agent-b_agent-a",
      role="user",
      content="Purchased chat logs for stream 12345",
      metadata={
          "service_type": "get_chat_logs",
          "stream_id": "12345",
          "price_glue": "0.01",
          "transaction_hash": "0xabc...",
          "used_for_service": "skill_extraction",  # What B is producing
          "downstream_customer": "0xUserAddress"  # Who will buy from B
      }
  )
  ```

  ### Pattern 2: Knowledge Sharing
  Agents contribute to shared knowledge pool:

  ```python
  # Skill-extractor shares insight about user
  agent.remember_interaction(
      conversation_id="shared_knowledge",
      role="assistant",
      content="User 0xUser1 has skill in hackathon discovery",
      metadata={
          "insight_type": "user_skill",
          "user_address": "0xUser1",
          "skill_category": "discovery",
          "confidence": 0.95,
          "source_agent": "skill-extractor"
      }
  )

  # Voice-extractor can query this later
  shared_insights = agent.search_knowledge(
      query="skills for user 0xUser1",
      filter_metadata={"user_address": "0xUser1"}
  )
  ```
  ```

- [ ] Define cross-reference patterns
- [ ] Define shared knowledge pool structure
- [ ] Document metadata standards

**Success Criteria:**
- Clear schema documented
- All agents can follow schema
- Cross-references unambiguous

---

#### Task 4.2: Implement Cross-Agent Memory Methods
**Duration:** 3-4 hours
**File:** `shared/base_agent.py` (MODIFY)

- [ ] Add `remember_agent_interaction` method
  ```python
  # Add to shared/base_agent.py:

  def remember_agent_interaction(
      self,
      other_agent_name: str,
      role: str,
      content: str,
      metadata: Optional[Dict[str, Any]] = None
  ) -> bool:
      """
      Remember interaction with another agent

      Uses composite conversation ID for agent-to-agent interactions.

      Args:
          other_agent_name: Name of the other agent
          role: "user" (this agent buying) or "assistant" (this agent selling)
          content: Interaction description
          metadata: Transaction details

      Returns:
          bool: True if stored successfully

      Example:
          >>> # Skill-extractor buying from karma-hello
          >>> skill_agent.remember_agent_interaction(
          ...     other_agent_name="karma-hello",
          ...     role="user",
          ...     content="Purchased chat logs for user cyberpaisa",
          ...     metadata={
          ...         "service_type": "get_chat_logs",
          ...         "price_glue": "0.01",
          ...         "used_for": "skill_extraction"
          ...     }
          ... )
      """
      if not self.memory_enabled or not self.memory:
          return False

      # Create composite conversation ID
      if role == "user":
          # This agent is buyer
          conversation_id = f"{self.agent_name}_{other_agent_name}"
      else:
          # This agent is seller
          conversation_id = f"{other_agent_name}_{self.agent_name}"

      # Add standard metadata
      meta = metadata or {}
      meta.update({
          "agent_sender": self.agent_name if role == "assistant" else other_agent_name,
          "agent_receiver": other_agent_name if role == "assistant" else self.agent_name,
          "interaction_type": "agent_to_agent"
      })

      return self.remember_interaction(
          conversation_id=conversation_id,
          role=role,
          content=content,
          metadata=meta
      )
  ```

- [ ] Add `share_knowledge` method
  ```python
  # Add to shared/base_agent.py:

  def share_knowledge(
      self,
      insight: str,
      metadata: Optional[Dict[str, Any]] = None
  ) -> bool:
      """
      Share knowledge to shared knowledge pool

      All agents can contribute insights that other agents can query.

      Args:
          insight: Knowledge to share
          metadata: Context for the insight

      Returns:
          bool: True if shared successfully

      Example:
          >>> agent.share_knowledge(
          ...     insight="User 0xUser1 frequently requests stream analytics",
          ...     metadata={
          ...         "insight_type": "user_pattern",
          ...         "user_address": "0xUser1",
          ...         "confidence": 0.9
          ...     }
          ... )
      """
      if not self.memory_enabled or not self.memory:
          return False

      meta = metadata or {}
      meta.update({
          "source_agent": self.agent_name,
          "knowledge_type": "shared"
      })

      return self.remember_interaction(
          conversation_id="shared_knowledge",
          role="assistant",
          content=insight,
          metadata=meta
      )
  ```

- [ ] Add `query_shared_knowledge` method
  ```python
  # Add to shared/base_agent.py:

  def query_shared_knowledge(
      self,
      query: str,
      filter_metadata: Optional[Dict[str, Any]] = None,
      n_results: int = 5
  ) -> List[Dict[str, Any]]:
      """
      Query shared knowledge pool

      Search insights contributed by all agents.

      Args:
          query: Search query
          filter_metadata: Filter by metadata
          n_results: Maximum results

      Returns:
          List of knowledge items

      Example:
          >>> insights = agent.query_shared_knowledge(
          ...     query="user behavior patterns",
          ...     filter_metadata={"insight_type": "user_pattern"}
          ... )
      """
      if not self.knowledge_base:
          # Fallback: search memory directly
          if self.memory_enabled:
              messages = self.recall_user_history("shared_knowledge")
              # Simple text search
              return [
                  {"content": m.content, "metadata": m.metadata}
                  for m in messages
                  if query.lower() in m.content.lower()
              ][:n_results]
          return []

      # Use knowledge base for semantic search
      return self.search_knowledge(
          query=query,
          n_results=n_results,
          filter_metadata=filter_metadata
      )
  ```

**Success Criteria:**
- Cross-agent memory methods work
- Shared knowledge pool functional
- Agents can query each other's contributions

---

#### Task 4.3: Create Cross-Agent Collaboration Examples
**Duration:** 2-3 hours
**File:** `tests/test_cross_agent_memory.py` (NEW)

- [ ] Test agent-to-agent memory tracking
  ```python
  """
  Tests for cross-agent memory sharing

  Simulates multi-agent workflows where agents buy from each other
  and share knowledge.
  """

  import pytest
  import asyncio
  from pathlib import Path
  import sys

  sys.path.append(str(Path(__file__).parent.parent))

  from shared.base_agent import ERC8004BaseAgent


  @pytest.fixture
  def karma_hello_agent():
      """Mock karma-hello agent"""
      # Simplified mock - in reality would be full agent
      agent = ERC8004BaseAgent(
          agent_name="karma-hello",
          agent_domain="karma-hello.karmacadabra.ultravioletadao.xyz",
          enable_memory=True,
          membase_auto_upload=False
      )
      return agent


  @pytest.fixture
  def skill_extractor_agent():
      """Mock skill-extractor agent"""
      agent = ERC8004BaseAgent(
          agent_name="skill-extractor",
          agent_domain="skill-extractor.karmacadabra.ultravioletadao.xyz",
          enable_memory=True,
          membase_auto_upload=False
      )
      return agent


  def test_agent_to_agent_purchase_tracking(karma_hello_agent, skill_extractor_agent):
      """
      Test that agent-to-agent purchases are tracked in memory

      Scenario:
      1. Skill-extractor buys chat logs from karma-hello
      2. Skill-extractor processes logs to extract skills
      3. Both agents remember the interaction
      4. Memory shows clear chain of custody
      """

      # Skill-extractor buys from karma-hello
      skill_extractor_agent.remember_agent_interaction(
          other_agent_name="karma-hello",
          role="user",
          content="Purchased chat logs for user cyberpaisa",
          metadata={
              "service_type": "get_chat_logs",
              "user": "cyberpaisa",
              "price_glue": "0.01",
              "used_for": "skill_extraction"
          }
      )

      # Karma-hello remembers selling
      karma_hello_agent.remember_agent_interaction(
          other_agent_name="skill-extractor",
          role="assistant",
          content="Sold chat logs for user cyberpaisa",
          metadata={
              "service_type": "get_chat_logs",
              "user": "cyberpaisa",
              "price_glue": "0.01",
              "message_count": 500
          }
      )

      # Verify both sides recorded
      skill_history = skill_extractor_agent.recall_user_history("skill-extractor_karma-hello")
      karma_history = karma_hello_agent.recall_user_history("skill-extractor_karma-hello")

      assert len(skill_history) == 1
      assert len(karma_history) == 1
      assert "cyberpaisa" in skill_history[0].content
      assert "cyberpaisa" in karma_history[0].content

      print("✅ Agent-to-agent purchase tracked on both sides")


  def test_shared_knowledge_pool(karma_hello_agent, skill_extractor_agent):
      """
      Test that agents can share and query knowledge

      Scenario:
      1. Skill-extractor discovers user has hackathon skill
      2. Shares this to knowledge pool
      3. Karma-hello queries pool for user info
      4. Finds skill-extractor's insight
      """

      # Skill-extractor shares insight
      skill_extractor_agent.share_knowledge(
          insight="User cyberpaisa has exceptional hackathon discovery skills",
          metadata={
              "insight_type": "user_skill",
              "user": "cyberpaisa",
              "skill_category": "discovery",
              "confidence": 0.95
          }
      )

      # Karma-hello queries for user info
      insights = karma_hello_agent.query_shared_knowledge(
          query="skills for user cyberpaisa",
          filter_metadata={"user": "cyberpaisa"}
      )

      assert len(insights) > 0
      assert any("hackathon" in str(i).lower() for i in insights)

      print("✅ Shared knowledge pool works")


  def test_service_chain_memory(karma_hello_agent, skill_extractor_agent):
      """
      Test memory tracking for service chains

      Scenario:
      1. User requests skill profile from skill-extractor
      2. Skill-extractor buys chat logs from karma-hello
      3. Skill-extractor generates profile
      4. Memory shows complete chain: User → Skill-Extractor → Karma-Hello
      """

      user_address = "0xUser1"

      # Step 1: User requests skill profile
      skill_extractor_agent.remember_interaction(
          conversation_id=user_address,
          role="user",
          content="I want a skill profile for cyberpaisa",
          metadata={
              "service_type": "skill_extraction",
              "target_user": "cyberpaisa"
          }
      )

      # Step 2: Skill-extractor buys chat logs
      skill_extractor_agent.remember_agent_interaction(
          other_agent_name="karma-hello",
          role="user",
          content="Purchased chat logs for cyberpaisa",
          metadata={
              "service_type": "get_chat_logs",
              "user": "cyberpaisa",
              "used_for_service": "skill_extraction",
              "downstream_customer": user_address
          }
      )

      # Step 3: Skill-extractor delivers profile
      skill_extractor_agent.remember_interaction(
          conversation_id=user_address,
          role="assistant",
          content="Generated skill profile for cyberpaisa",
          metadata={
              "service_type": "skill_extraction",
              "source_data": "karma-hello chat logs",
              "skills_found": ["hackathon discovery", "ecosystem intel"]
          }
      )

      # Verify service chain
      user_history = skill_extractor_agent.recall_user_history(user_address)
      agent_history = skill_extractor_agent.recall_user_history("skill-extractor_karma-hello")

      assert len(user_history) == 2  # Request + delivery
      assert len(agent_history) == 1  # Purchase from karma-hello
      assert "cyberpaisa" in agent_history[0].content

      print("✅ Service chain tracked in memory")


  if __name__ == "__main__":
      pytest.main([__file__, "-v"])
  ```

- [ ] Run cross-agent tests
  ```bash
  pytest tests/test_cross_agent_memory.py -v
  ```

**Success Criteria:**
- Agent-to-agent interactions tracked
- Shared knowledge pool works
- Service chains visible in memory

---

#### Task 4.4: Implement Real Cross-Agent Scenario
**Duration:** 2-3 hours
**File:** `scripts/demo_cross_agent_memory.py` (NEW)

- [ ] Create demonstration script
  ```python
  """
  Demonstration of cross-agent memory sharing

  Simulates real workflow:
  1. User requests skill profile from skill-extractor
  2. Skill-extractor buys chat logs from karma-hello
  3. Skill-extractor generates profile using CrewAI
  4. Voice-extractor queries shared knowledge for personality insights
  5. All interactions tracked in memory
  """

  import asyncio
  import httpx
  from datetime import datetime


  async def demo_cross_agent_collaboration():
      """
      Demonstrate cross-agent memory sharing

      Requires all agents running with memory enabled.
      """

      print("=" * 70)
      print("CROSS-AGENT MEMORY SHARING DEMONSTRATION")
      print("=" * 70)
      print()

      # Configuration
      user_address = "0xDemoUser"
      target_user = "cyberpaisa"

      karma_hello_url = "http://localhost:8002"
      skill_extractor_url = "http://localhost:8004"
      voice_extractor_url = "http://localhost:8005"

      async with httpx.AsyncClient() as client:

          # Step 1: User requests skill profile
          print("[1] User requests skill profile from skill-extractor...")

          response = await client.post(
              f"{skill_extractor_url}/extract_skills",
              json={"username": target_user}
          )

          if response.status_code == 200:
              skills = response.json()
              print(f"    ✅ Received skill profile:")
              print(f"       Skills: {skills['skills'][:3]}...")
              print()
          else:
              print(f"    ❌ Failed: {response.status_code}")
              return

          # Step 2: Check skill-extractor's memory
          print("[2] Checking skill-extractor's memory...")

          # (Would query agent's memory endpoint if exposed)
          # For now, memory is internal to agent
          print("    ✅ Skill-extractor remembered:")
          print("       - User request from", user_address)
          print("       - Purchase from karma-hello")
          print("       - Skill extraction completion")
          print()

          # Step 3: Voice-extractor queries shared knowledge
          print("[3] Voice-extractor queries shared knowledge...")

          # (Would query shared knowledge pool)
          # For now, simulated
          print("    ✅ Found shared insights:")
          print("       - cyberpaisa has hackathon discovery skill (from skill-extractor)")
          print("       - cyberpaisa active in ecosystem intel (from karma-hello)")
          print()

          # Step 4: Demonstrate knowledge composition
          print("[4] Composing multi-agent profile...")

          # Voice-extractor can now create richer profile
          # by combining:
          # - Chat logs (from karma-hello)
          # - Extracted skills (from skill-extractor)
          # - Shared knowledge pool insights

          print("    ✅ Composite profile created:")
          print("       - Personality: [from voice-extractor]")
          print("       - Skills: [from skill-extractor]")
          print("       - Activity: [from karma-hello]")
          print()

      print("=" * 70)
      print("DEMONSTRATION COMPLETE")
      print("=" * 70)
      print()
      print("Key Takeaways:")
      print("- All agent interactions tracked in memory")
      print("- Shared knowledge pool enables discovery")
      print("- Service chains create value composition")
      print("- Memory enables personalization over time")


  if __name__ == "__main__":
      asyncio.run(demo_cross_agent_collaboration())
  ```

- [ ] Run demonstration
  ```bash
  # Start all agents with memory enabled
  # In separate terminals:
  cd karma-hello-agent && ENABLE_MEMORY=true python main.py
  cd skill-extractor-agent && ENABLE_MEMORY=true python main.py
  cd voice-extractor-agent && ENABLE_MEMORY=true python main.py

  # Run demo
  python scripts/demo_cross_agent_memory.py
  ```

**Success Criteria:**
- Demo runs successfully
- Cross-agent collaboration visible
- Memory enables value composition

**Phase 4 Deliverables:**
- [ ] `docs/cross-agent-memory-schema.md` - Schema documented
- [ ] `shared/base_agent.py` - Cross-agent memory methods
- [ ] `tests/test_cross_agent_memory.py` - Cross-agent tests
- [ ] `scripts/demo_cross_agent_memory.py` - Demonstration
- [ ] All cross-agent scenarios tested

---

## 🚀 Phase 5: Advanced Features
**Duration:** 3-4 days (12-16 hours)
**Dependencies:** Phase 4 complete
**Status:** NOT STARTED

### Objectives
- Implement ChromaKnowledgeBase for semantic search
- Add memory-based pricing (loyalty discounts)
- Create memory analytics (user insights)
- Build admin dashboard for memory inspection
- Optimize performance

### Tasks

#### Task 5.1: Full ChromaDB Integration
**Duration:** 3-4 hours
**File:** `shared/base_agent.py` (MODIFY)

- [ ] Enable knowledge base by default (if memory enabled)
- [ ] Auto-sync memory to knowledge base
- [ ] Implement advanced search features
- [ ] Add document management

**Details:**
```python
# In shared/base_agent.py, modify _init_membase_memory:

# Always initialize knowledge base when memory enabled
self.knowledge_base = ChromaKnowledgeBase(
    collection_name=f"{self.agent_name}_kb",
    persist_directory=f"./knowledge/{self.agent_name}"
)

# Auto-sync messages to knowledge base
def remember_interaction(self, ...):
    # ... existing code ...

    # Auto-add to knowledge base
    if self.knowledge_base:
        self.knowledge_base.add(
            content=f"[{conversation_id}] {role}: {content}",
            metadata=metadata
        )
```

**Success Criteria:**
- Knowledge base initializes automatically
- All memories indexed for search
- Semantic search works reliably

---

#### Task 5.2: Memory-Based Pricing (Loyalty Discounts)
**Duration:** 3-4 hours
**File:** `shared/base_agent.py` (MODIFY)

- [ ] Add `calculate_loyalty_discount` method
  ```python
  # Add to shared/base_agent.py:

  def calculate_loyalty_discount(
      self,
      conversation_id: str,
      base_price: Decimal
  ) -> Tuple[Decimal, float]:
      """
      Calculate loyalty discount based on user history

      Discount tiers:
      - New customer: 0% discount
      - 2-5 purchases: 5% discount
      - 6-10 purchases: 10% discount
      - 11-20 purchases: 15% discount
      - 21+ purchases: 20% discount (max)

      Args:
          conversation_id: User identifier
          base_price: Original price in GLUE

      Returns:
          Tuple of (discounted_price, discount_percentage)

      Example:
          >>> price, discount = agent.calculate_loyalty_discount(
          ...     "0xUser1",
          ...     Decimal("0.10")
          ... )
          >>> print(f"Original: 0.10 GLUE, Discounted: {price} GLUE ({discount}% off)")
      """
      if not self.memory_enabled:
          return base_price, 0.0

      prefs = self.get_user_preferences(conversation_id)
      purchases = prefs.get("total_interactions", 0)

      # Determine discount tier
      if purchases >= 21:
          discount_pct = 20.0
      elif purchases >= 11:
          discount_pct = 15.0
      elif purchases >= 6:
          discount_pct = 10.0
      elif purchases >= 2:
          discount_pct = 5.0
      else:
          discount_pct = 0.0

      # Apply discount
      discount_multiplier = Decimal(str(1.0 - (discount_pct / 100.0)))
      discounted_price = base_price * discount_multiplier

      logger.info(
          f"[{self.agent_name}] Loyalty discount: "
          f"{purchases} purchases = {discount_pct}% off "
          f"(${base_price} → ${discounted_price})"
      )

      return discounted_price, discount_pct
  ```

- [ ] Update pricing in agents
  ```python
  # In karma-hello-agent/main.py, modify get_chat_logs:

  # Calculate price
  base_price = agent.calculate_price(response.total_messages)

  # Apply loyalty discount
  if agent.memory_enabled:
      final_price, discount_pct = agent.calculate_loyalty_discount(
          buyer_address,
          base_price
      )
  else:
      final_price, discount_pct = base_price, 0.0

  return JSONResponse(
      content=response.model_dump(),
      headers={
          "X-Price": str(final_price),
          "X-Base-Price": str(base_price),
          "X-Discount": str(discount_pct),
          "X-Currency": "GLUE"
      }
  )
  ```

**Success Criteria:**
- Discounts calculated correctly
- Repeat customers pay less
- Discount tiers work as expected

---

#### Task 5.3: Memory Analytics Dashboard
**Duration:** 4-5 hours
**File:** `scripts/memory_analytics.py` (NEW)

- [ ] Create analytics script
  ```python
  """
  Memory Analytics Dashboard

  Generates insights from agent memory:
  - Top customers by purchase count
  - Revenue by service type
  - Average user ratings
  - Service quality trends
  - User churn analysis
  """

  import argparse
  from pathlib import Path
  from collections import Counter, defaultdict
  from datetime import datetime, timedelta
  import json

  from shared.base_agent import ERC8004BaseAgent


  def analyze_agent_memory(agent_name: str):
      """Generate analytics for an agent's memory"""

      print(f"\n{'=' * 70}")
      print(f"MEMORY ANALYTICS: {agent_name}")
      print(f"{'=' * 70}\n")

      # Load agent (minimal config, just for memory access)
      agent = ERC8004BaseAgent(
          agent_name=agent_name,
          agent_domain=f"{agent_name}.karmacadabra.ultravioletadao.xyz",
          enable_memory=True,
          membase_auto_upload=False,
          membase_preload=True
      )

      if not agent.memory_enabled:
          print("❌ Memory not enabled or not available")
          return

      # Get all conversations
      conversation_ids = agent.memory._conversations.keys()

      print(f"Total Conversations: {len(conversation_ids)}\n")

      # Analytics
      total_interactions = 0
      service_counts = Counter()
      revenue_by_service = defaultdict(float)
      user_stats = {}

      for conv_id in conversation_ids:
          messages = agent.recall_user_history(conv_id)
          total_interactions += len(messages)

          for msg in messages:
              if msg.metadata:
                  # Service usage
                  service = msg.metadata.get("service_type")
                  if service:
                      service_counts[service] += 1

                  # Revenue
                  price = msg.metadata.get("price_glue")
                  if price and service:
                      try:
                          revenue_by_service[service] += float(price)
                      except ValueError:
                          pass

          # User stats
          if conv_id != "shared_knowledge":
              prefs = agent.get_user_preferences(conv_id)
              user_stats[conv_id] = prefs

      # Display analytics
      print("SERVICE USAGE:")
      for service, count in service_counts.most_common():
          print(f"  {service}: {count} requests")
      print()

      print("REVENUE BY SERVICE:")
      for service, revenue in sorted(revenue_by_service.items(), key=lambda x: x[1], reverse=True):
          print(f"  {service}: {revenue:.4f} GLUE")
      print()

      print("TOP CUSTOMERS:")
      top_users = sorted(
          user_stats.items(),
          key=lambda x: x[1].get("total_interactions", 0),
          reverse=True
      )[:10]

      for user_id, stats in top_users:
          print(f"  {user_id[:12]}...")
          print(f"    Purchases: {stats.get('total_interactions', 0)}")
          print(f"    Avg Rating: {stats.get('average_rating', 'N/A')}")
          print(f"    Services: {', '.join(stats.get('services_used', []))}")
          print()

      print(f"{'=' * 70}\n")


  if __name__ == "__main__":
      parser = argparse.ArgumentParser(description="Analyze agent memory")
      parser.add_argument("agent", help="Agent name (e.g., karma-hello-agent)")
      args = parser.parse_args()

      analyze_agent_memory(args.agent)
  ```

- [ ] Run analytics
  ```bash
  python scripts/memory_analytics.py karma-hello-agent
  python scripts/memory_analytics.py skill-extractor-agent
  ```

**Success Criteria:**
- Analytics generate successfully
- Insights actionable
- Performance acceptable (<10 seconds)

---

#### Task 5.4: Performance Optimization
**Duration:** 2-3 hours
**File:** `shared/base_agent.py` (MODIFY)

- [ ] Add memory caching
- [ ] Implement lazy loading
- [ ] Optimize knowledge base queries
- [ ] Add memory pruning (old data cleanup)

**Details:**
```python
# Add caching to reduce redundant queries
from functools import lru_cache

@lru_cache(maxsize=100)
def _cached_get_preferences(self, conversation_id: str):
    """Cached version of get_user_preferences"""
    return self.get_user_preferences(conversation_id)

# Add memory pruning
def prune_old_memories(self, days_to_keep: int = 90):
    """Delete memories older than N days"""
    # Implementation depends on Membase API
    pass
```

**Success Criteria:**
- Memory operations <100ms
- No memory leaks
- Pruning works correctly

**Phase 5 Deliverables:**
- [ ] Full ChromaDB integration
- [ ] Loyalty discount system
- [ ] Analytics dashboard
- [ ] Performance optimizations
- [ ] All features tested

---

## 🧪 Phase 6: Testing & Documentation
**Duration:** 2-3 days (8-12 hours)
**Dependencies:** Phase 5 complete
**Status:** NOT STARTED

### Objectives
- Comprehensive integration tests
- Load testing
- Documentation updates
- Example scripts
- Migration guide

### Tasks

#### Task 6.1: Comprehensive Integration Tests
**Duration:** 3-4 hours
**File:** `tests/test_membase_integration_full.py` (NEW)

- [ ] End-to-end test suite
- [ ] Multi-agent scenarios
- [ ] Error handling tests
- [ ] Performance benchmarks

**Test Coverage:**
- [ ] Memory initialization
- [ ] Interaction tracking
- [ ] Persistence across restarts
- [ ] Cross-agent memory sharing
- [ ] Knowledge base search
- [ ] Loyalty discounts
- [ ] Analytics generation
- [ ] Graceful degradation

---

#### Task 6.2: Load Testing
**Duration:** 2-3 hours
**File:** `tests/test_membase_load.py` (NEW)

- [ ] Concurrent user test
- [ ] Large memory volume test
- [ ] Cloud sync stress test
- [ ] Knowledge base query performance

---

#### Task 6.3: Update Documentation
**Duration:** 2-3 hours
**Files:** `README.md`, `README.es.md`

- [ ] Add Membase section to README
- [ ] Document memory features
- [ ] Add usage examples
- [ ] Update architecture diagram

**Template:**
```markdown
## Memory Layer (Membase)

Karmacadabra agents use Membase for persistent memory:

### Features
- **User History**: Track interactions over time
- **Learned Preferences**: Personalize services
- **Cross-Agent Sharing**: Agents collaborate via shared knowledge
- **Loyalty Discounts**: Reward repeat customers

### Setup
```bash
# Install Membase
pip install git+https://github.com/unibaseio/membase.git
pip install -r shared/requirements-memory.txt

# Enable in .env
ENABLE_MEMORY=true
MEMBASE_AUTO_UPLOAD=true
```

### Usage
```python
# Agents automatically track interactions
# Query user history:
history = agent.recall_user_history("0xUserAddress")

# Get preferences:
prefs = agent.get_user_preferences("0xUserAddress")

# Share knowledge:
agent.share_knowledge("User X has skill Y")
```
```

- [ ] Synchronize English and Spanish READMEs

---

#### Task 6.4: Create Example Scripts
**Duration:** 2 hours
**File:** `scripts/examples/membase_examples.py` (NEW)

- [ ] Basic memory usage
- [ ] Cross-agent collaboration
- [ ] Analytics generation
- [ ] Admin operations

---

#### Task 6.5: Write Migration Guide
**Duration:** 1-2 hours
**File:** `docs/membase-migration-guide.md` (NEW)

- [ ] Existing agents upgrade steps
- [ ] Data migration (if needed)
- [ ] Rollback procedure
- [ ] Troubleshooting guide

**Phase 6 Deliverables:**
- [ ] Full test suite passing
- [ ] Load tests successful
- [ ] README.md and README.es.md updated
- [ ] Example scripts complete
- [ ] Migration guide written

---

## 📊 Success Metrics

### Phase Completion Criteria

**Phase 0:** POC Complete
- [ ] Membase SDK functional
- [ ] Cloud sync working
- [ ] Go/No-Go decision made

**Phase 1:** Foundation Ready
- [ ] Base agent supports memory
- [ ] All `.env.example` updated
- [ ] Unit tests passing

**Phase 2:** Pilot Successful
- [ ] Karma-hello agent tracks interactions
- [ ] Memory persists across restarts
- [ ] No regressions

**Phase 3:** Multi-Agent Rollout
- [ ] All 5 agents have memory
- [ ] Consistent patterns
- [ ] All agents tested

**Phase 4:** Cross-Agent Sharing
- [ ] Agent-to-agent memory works
- [ ] Shared knowledge pool functional
- [ ] Service chains tracked

**Phase 5:** Advanced Features
- [ ] ChromaDB fully integrated
- [ ] Loyalty discounts working
- [ ] Analytics dashboard functional

**Phase 6:** Production Ready
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Load testing successful

### Performance Targets

| Metric | Target | Measured |
|--------|--------|----------|
| Memory write latency | <50ms | ___ ms |
| Memory read latency | <20ms | ___ ms |
| Cloud sync latency | <2s | ___ s |
| Knowledge base query | <100ms | ___ ms |
| Agent startup time increase | <5s | ___ s |
| Memory storage (1000 interactions) | <50MB | ___ MB |

### Quality Metrics

- [ ] Code coverage >80%
- [ ] Zero memory leaks
- [ ] Graceful degradation works 100%
- [ ] All documentation synchronized (EN/ES)
- [ ] Zero breaking changes to existing agents

---

## 🚨 Risk Management

### High-Risk Items

**Risk 1: Membase SDK Incompatibility**
- **Probability:** Medium
- **Impact:** High
- **Mitigation:** Phase 0 POC validates SDK early
- **Contingency:** Build custom memory layer using SQLite

**Risk 2: Cloud Sync Unreliable**
- **Probability:** Medium
- **Impact:** Medium
- **Mitigation:** Always use local storage as primary
- **Contingency:** Disable cloud sync, use local-only

**Risk 3: Performance Degradation**
- **Probability:** Low
- **Impact:** High
- **Mitigation:** Benchmark in Phase 2, optimize in Phase 5
- **Contingency:** Make memory completely optional

**Risk 4: BNB Testnet Compatibility Issues**
- **Probability:** Low
- **Impact:** Medium
- **Mitigation:** Test in Phase 0 with throwaway wallet
- **Contingency:** Use separate testnet wallet for Membase

### Rollback Strategy

**If Phase 0 fails:**
- Document findings
- Explore alternatives (LangChain memory, custom SQLite)
- Do NOT proceed to Phase 1

**If Phase 2 fails:**
- Disable memory in karma-hello agent
- Keep base agent changes (disabled by default)
- Fix issues before multi-agent rollout

**If Phase 3+ fails:**
- Roll back failing agents
- Keep working agents
- Fix issues incrementally

**Complete Rollback:**
```bash
# Disable memory in all agents
find . -name ".env" -exec sed -i 's/ENABLE_MEMORY=true/ENABLE_MEMORY=false/g' {} \;

# Revert base_agent.py
git checkout shared/base_agent.py

# Remove memory directories
rm -rf memory/ knowledge/
```

---

## 📝 Appendix: File Manifest

### New Files Created

```
plans/
└── membase-integration-plan.md (THIS FILE)

tests/
├── test_membase_poc.py
├── test_membase_knowledge.py
├── test_base_agent_memory.py
├── test_karma_hello_memory.py
├── test_cross_agent_memory.py
├── test_membase_integration_full.py
└── test_membase_load.py

docs/
├── membase-poc-results.md
├── membase-pilot-results.md
├── cross-agent-memory-schema.md
└── membase-migration-guide.md

scripts/
├── memory_analytics.py
├── demo_cross_agent_memory.py
└── examples/
    └── membase_examples.py

shared/
└── requirements-memory.txt

memory/ (gitignored)
└── {agent-name}/ (runtime directories)

knowledge/ (gitignored)
└── {agent-name}/ (runtime directories)
```

### Modified Files

```
shared/
└── base_agent.py (150+ lines added)

karma-hello-agent/
├── agent.py (modified __init__)
├── main.py (memory tracking in endpoints)
└── .env.example (Membase config added)

abracadabra-agent/
├── agent.py (modified __init__)
├── main.py (memory tracking in endpoints)
└── .env.example (Membase config added)

skill-extractor-agent/
├── agent.py (modified __init__)
├── main.py (memory tracking in endpoints)
└── .env.example (Membase config added)

voice-extractor-agent/
├── agent.py (modified __init__)
├── main.py (memory tracking in endpoints)
└── .env.example (Membase config added)

validator/
├── agent.py (modified __init__)
├── main.py (memory tracking in endpoints)
└── .env.example (Membase config added)

client-agent/
├── agent.py (modified __init__)
├── main.py (memory tracking in endpoints)
└── .env.example (Membase config added)

README.md (Membase section added)
README.es.md (Membase section added, synchronized)
.gitignore (memory/ and knowledge/ added)
```

---

## 🎯 Next Steps

### Immediate Actions (Before Starting)

1. **Review this plan** with team/stakeholders
2. **Allocate time** - 60-75 hours over 12-15 days
3. **Prepare environment** - Install dependencies
4. **Create branch** - `feature/membase-integration`

### Phase 0 Start Checklist

- [ ] Branch created: `git checkout -b feature/membase-integration`
- [ ] Test environment prepared
- [ ] Throwaway wallet generated
- [ ] Membase documentation reviewed
- [ ] This plan approved

### Development Flow

```bash
# For each phase:
git checkout feature/membase-integration

# Complete tasks
# Commit after each task (granular commits!)
git add [files]
git commit -m "Phase X, Task Y: [Description]

🤖 Generated with Claude Code
Co-Authored-By: Claude <noreply@anthropic.com>"

# Push after each phase
git push origin feature/membase-integration

# Create PR after Phase 2 (pilot complete)
# Merge to main after Phase 6 (production ready)
```

---

## ✅ Sign-Off

**Plan Created:** October 25, 2025
**Estimated Completion:** November 9, 2025 (15 days)
**Total Effort:** 60-75 hours

**Approved By:**
- [ ] Technical Lead: _______________
- [ ] Product Owner: _______________
- [ ] Agent Team: _______________

**Ready to Proceed:** ☐ Yes  ☐ No  ☐ Needs Revision

---

**END OF PLAN**

*This plan respects Karmacadabra's architecture, integrates Membase as Layer 3.5 (memory only), maintains backward compatibility, and follows the project's granular commit workflow and documentation synchronization requirements.*
