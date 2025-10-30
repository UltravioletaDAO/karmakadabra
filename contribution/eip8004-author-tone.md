# EIP-8004 Author Tone & Style Guide

> Expressive style model extracted from ERC-8004: Trustless Agents for reuse in EIP-8004a (Bidirectional Trust Extension)

**Created:** October 30, 2025
**Source:** https://eips.ethereum.org/EIPS/eip-8004
**Purpose:** Maintain consistent authorial voice across extension documentation

---

## 1. Core Tone Characteristics

### 1.1 Formal Yet Accessible
- **Balance precision with clarity**: Use technical terms but define them contextually
- **Example from EIP-8004**: "The _tokenId_ in ERC-721 is referred to as _agentId_. The owner of the ERC-721 token is the owner of the agent and can transfer ownership."
- **Pattern**: *Term in context* → *One-line definition* → *Implication*

### 1.2 Prescriptive Authority
- Heavy use of RFC 2119 keywords: **MUST**, **SHOULD**, **MAY**, **OPTIONAL**
- Clear requirements without ambiguity
- **Example**: "The key words 'MUST', 'MUST NOT', 'REQUIRED', 'SHALL'... are to be interpreted as described in RFC 2119"
- **Pattern**: State requirement → Cite standard → Proceed

### 1.3 Problem-First Framing
- Start with **use case**, not technology
- **Example**: "To foster an open, cross-organizational agent economy, we need mechanisms for discovering and trusting agents in untrusted settings."
- **Pattern**: *Desired outcome* → *Current gap* → *Proposed solution*

### 1.4 Honest Limitation Acknowledgment
- Candidly address what the protocol **cannot** solve
- **Example**: "Pre-authorization for feedback only partially mitigates spam, as Sybil attacks are still possible"
- **Pattern**: *Security claim* → *Limitation* → *Ecosystem-level mitigation*

---

## 2. Structural Hierarchy

### 2.1 Section Order (Strict)
1. **Abstract** - Use-case focused (2-3 sentences)
2. **Motivation** - Problem statement (2-4 paragraphs)
3. **Specification** - Technical requirements (bulk of document)
4. **Rationale** - Design justification (design choices explained)
5. **Backwards Compatibility** - Breaking changes (or lack thereof)
6. **Security Considerations** - Threat model and limitations
7. **Test Cases** - Validation examples (optional but recommended)
8. **Copyright** - Waiver (always CC0)

### 2.2 Subsection Patterns
- Use **bold for emphasis** on key concepts
- Use *italics for quoted specifications*
- Use `code` for identifiers, function names, JSON keys
- Use blockquotes for JSON/Solidity examples

### 2.3 Header Capitalization
- Main sections: Title Case (e.g., "Security Considerations")
- Subsections: Sentence case with leading capital (e.g., "Feedback mechanism")

---

## 3. Sentence Structure & Rhythm

### 3.1 Opening Sentence Patterns
- **Abstract**: "This protocol proposes to use [technology] to [outcome] without [constraint], thus enabling [vision]."
- **Motivation**: "[Protocol X] allows [capability], while [Protocol Y] handles [capability]."
- **Specification**: "The key words MUST, SHOULD... are to be interpreted as described in RFC 2119."

### 3.2 Definition Pattern
```
[Term] [context]: [one-line definition]. [Implication or example].
```
**Example**: "The _tokenId_ in ERC-721 is referred to as _agentId_. The owner of the ERC-721 token is the owner of the agent and can transfer ownership."

### 3.3 Transition Phrases
- **Gap identification**: "However, these agent communication protocols don't inherently cover..."
- **Solution introduction**: "This ERC addresses this need through..."
- **Rationale**: "For this reason, this protocol links..."
- **Limitation**: "Pre-authorization only partially mitigates..."

### 3.4 Sentence Length
- **Short for requirements**: 8-15 words (e.g., "Agents MUST register before submitting feedback.")
- **Medium for explanation**: 15-25 words (contextual definitions)
- **Long for rationale**: 25-40 words (design justifications with clauses)

---

## 4. Lexicon & Vocabulary

### 4.1 Technical Terms (Use These)
- **Registry** (not "database" or "storage")
- **Agent** (not "AI" or "bot" unless contextually necessary)
- **Feedback** (not "rating" or "review" in base EIP-8004)
- **Authorization** (not "permission" or "approval")
- **Validator** (not "verifier" unless referring to cryptographic verification)
- **Metadata** (not "data" when referring to off-chain JSON)

### 4.2 Verbs of Requirement
- **MUST** - Absolute requirement (critical for interoperability)
- **SHOULD** - Strong recommendation (best practice)
- **MAY** - Optional (implementer choice)
- **CAN** - Capability statement (neutral)

### 4.3 Avoiding Ambiguity
- ❌ Avoid: "Users might want to..."
- ✅ Use: "Clients MAY choose to..."
- ❌ Avoid: "This could be useful for..."
- ✅ Use: "This enables [specific use case]."

### 4.4 Precision Over Jargon
- Use **specific terms** but define them inline
- Example: "feedbackAuth (a signed tuple authorizing feedback submission)"
- Pattern: `technical-term` (plain-English definition)

---

## 5. Code & Example Integration

### 5.1 JSON Structure Presentation
```json
{
  "field_name": "value",
  "description": "inline comment explaining purpose"
}
```
- Use **snake_case** for JSON keys (EIP-8004 convention)
- Add inline comments as values when demonstrating structure

### 5.2 Solidity Function Signatures
```solidity
function methodName(uint256 parameter) external returns (bool);
```
- One function per code block
- Include visibility (`external`, `public`) and mutability (`view`, `pure`)
- Add `/// @notice` comments for developer context

### 5.3 Example Placement
- **After specification**: Examples illustrate requirements
- **Not before**: Don't use examples to introduce concepts
- **Pattern**: *Specify requirement* → *Show example* → *Explain edge case*

---

## 6. Rationale Section Patterns

### 6.1 Design Decision Format
```
**Choice Made**: [What was chosen]
**Reason**: [Why it was chosen]
**Alternative Considered**: [What was rejected and why]
```

### 6.2 Example from EIP-8004
"For this reason, this protocol links from the blockchain to a flexible registration file including a list where endpoints can be added at will."
- **Pattern**: *Problem* (rigid on-chain data) → *Solution* (off-chain flexibility) → *Mechanism* (URI link)

### 6.3 Rationale Tone
- Justify **without defending** (no "we believe" or "in our opinion")
- State facts: "This approach enables X" (not "We think this is better")
- Reference precedent: "Similar to EIP-XXXX" (cite existing standards)

---

## 7. Security Considerations Patterns

### 7.1 Threat Identification
- **Name the attack**: "Sybil attacks", "Spam submissions", "Front-running"
- **Explain the risk**: One sentence on impact
- **Mitigation**: What the protocol does (and doesn't do)

### 7.2 Honest Limitation Phrasing
- "Pre-authorization **only partially mitigates** spam"
- "The protocol's contribution is to make signals public and use the same schema"
- **Pattern**: *Acknowledge limitation* → *Explain protocol's role* → *Defer to ecosystem*

### 7.3 Avoid Overclaiming
- ❌ "This protocol is secure against Sybil attacks"
- ✅ "Pre-authorization for feedback only partially mitigates spam, as Sybil attacks are still possible"

---

## 8. Formatting & Visual Hierarchy

### 8.1 Emphasis Rules
- **Bold**: Key concepts on first mention (e.g., **Identity Registry**)
- *Italics*: Quoted text or field names in prose (e.g., _tokenId_)
- `Code`: Identifiers, function names, JSON keys (e.g., `agentId`)
- CAPS: RFC 2119 keywords only (e.g., MUST, SHOULD)

### 8.2 List Formatting
- Use numbered lists for **sequential steps**
- Use bullet lists for **parallel concepts**
- Use definition lists (bold term: explanation) for **glossaries**

### 8.3 Whitespace
- One blank line between paragraphs
- Two blank lines between major sections
- No blank lines within code blocks

---

## 9. Backwards Compatibility Patterns

### 9.1 Zero Breaking Changes (Ideal)
"This EIP introduces new functionality without modifying existing interfaces. Implementations of the base EIP-8004 remain fully compatible."

### 9.2 Optional Extensions
"The new methods are **OPTIONAL**. Registries MAY implement them to enable [use case], but existing registries continue to function without modification."

### 9.3 Migration Path (If Breaking)
If breaking changes exist (avoid if possible):
1. State the change clearly
2. Explain the necessity
3. Provide migration guidance

---

## 10. Abstract Writing Formula

### 10.1 Three-Sentence Structure
1. **Problem**: What gap exists?
2. **Solution**: What does this protocol do?
3. **Outcome**: What does it enable?

### 10.2 EIP-8004 Example Deconstructed
- Sentence 1: "This protocol proposes to use blockchains to discover, choose, and interact with agents across organizational boundaries without pre-existing trust"
  - Technology: blockchains
  - Actions: discover, choose, interact
  - Context: across organizational boundaries
  - Constraint removed: without pre-existing trust
- Sentence 2: "...thus enabling open-ended agent economies."
  - Outcome: open-ended agent economies

### 10.3 Extension Abstract Formula (for EIP-8004a)
"This extension proposes to add [new capability] to EIP-8004, enabling [outcome] without [existing limitation], thus [vision]."

---

## 11. Motivation Writing Patterns

### 11.1 Opening Pattern
- Start with **ecosystem context** (what protocols already exist)
- **Example**: "MCP allows servers to list capabilities, while A2A handles agent authentication"
- Establish the landscape before identifying the gap

### 11.2 Gap Identification
- Use transition: "However, [existing solution] doesn't inherently cover [missing capability]"
- State the need: "To foster [vision], we need [capability]"

### 11.3 Evidence Integration
- Cite precedents: "Systems like Uber and Airbnb demonstrate bidirectional trust at scale"
- Cite costs: "eBay reports $1.8B annual losses from buyer fraud"
- Cite data: "Analysis of 99 transactions on Avalanche Fuji revealed..."
- **Pattern**: *Claim* → *Evidence* → *Implication*

---

## 12. Test Cases Format

### 12.1 Structure
```
**Test**: [Short name]
**Setup**: [Initial state]
**Action**: [What is tested]
**Expected Result**: [What should happen]
**Assertion**: [How to verify]
```

### 12.2 Example
```
**Test**: Client rates server
**Setup**: Client 0xABC and server 0xDEF registered
**Action**: Client submits rating of 85
**Expected Result**: Rating stored and event emitted
**Assertion**: `getClientRating(serverId, clientId)` returns (true, 85)
```

---

## 13. Common Mistakes to Avoid

### 13.1 Voice & Tone
- ❌ "We decided to use X" → ✅ "This protocol uses X"
- ❌ "I think this is better" → ✅ "This approach enables Y"
- ❌ "Users will love this" → ✅ "This enables [use case]"

### 13.2 Precision
- ❌ "Probably secure" → ✅ "Mitigates X attack via Y mechanism"
- ❌ "Might work with" → ✅ "Compatible with" or "Incompatible with"
- ❌ "Around 50,000 gas" → ✅ "~50,000 gas" or "50,000 ± 5,000 gas"

### 13.3 Scope
- ❌ Discussing implementation details in Abstract
- ❌ Introducing new concepts in Rationale (should be in Specification)
- ❌ Defending design choices in Security (state facts only)

---

## 14. Enhanced Tone for Public-Facing Articles

> For Week 6 blog post and case study, **adapt** this tone for non-technical readers:

### 14.1 Keep from EIP Style
- ✅ Problem-first framing
- ✅ Honest limitation acknowledgment
- ✅ Concrete examples
- ✅ Clear structure

### 14.2 Modify for Accessibility
- 🔄 Replace RFC 2119 keywords with plain English ("must" → "needs to")
- 🔄 Add analogies for complex concepts ("like Uber's driver ratings, but on a blockchain")
- 🔄 Use storytelling for case studies (narrative flow)
- 🔄 Add section TL;DRs for skimmers

### 14.3 Maintain Technical Credibility
- ✅ Still cite evidence (99 transactions, $1.8B losses)
- ✅ Still use precise terms (define on first use)
- ✅ Still acknowledge limitations (builds trust)
- ❌ Don't oversimplify to the point of inaccuracy

---

## 15. Quick Reference Checklist

Before publishing any EIP-8004 extension content, verify:

### Structural
- [ ] Abstract is 2-3 sentences (problem → solution → outcome)
- [ ] Motivation starts with ecosystem context
- [ ] Specification uses RFC 2119 keywords
- [ ] Rationale explains design choices (not defends them)
- [ ] Security acknowledges limitations honestly
- [ ] Backwards Compatibility states impact clearly

### Tone
- [ ] No first-person ("we", "I", "our")
- [ ] Prescriptive authority (MUST, SHOULD, MAY)
- [ ] Precise vocabulary (registry, feedback, agent)
- [ ] Problem-first framing (use case before tech)

### Technical
- [ ] All terms defined contextually
- [ ] Code examples after specification
- [ ] Gas costs cited with ± range
- [ ] No overclaiming security

### Formatting
- [ ] Bold for key concepts on first mention
- [ ] Italics for field names in prose
- [ ] Code for identifiers
- [ ] One blank line between paragraphs

---

## 16. Example Transformations

### 16.1 Technical to Accessible (Blog Post)
**EIP Style**: "Pre-authorization for feedback only partially mitigates spam, as Sybil attacks are still possible."

**Blog Style**: "Requiring permission before someone can rate you helps reduce spam, but it doesn't stop someone from creating fake accounts to inflate their reputation—that's a problem the whole ecosystem needs to tackle together."

### 16.2 Specification to Narrative (Case Study)
**EIP Style**: "The Reputation Registry stores feedback signals where clients submit scores (0-100) and optional metadata."

**Case Study Style**: "When karma-hello bought chat logs from abracadabra, it could rate the quality from 0 to 100. It gave abracadabra a 97—excellent transcription quality, fast delivery. That rating is now permanent on the blockchain."

---

## 17. Voice Consistency Matrix

| Document Type | Tone | Person | Keywords | Examples |
|---------------|------|--------|----------|----------|
| **EIP Extension** | Formal, prescriptive | Third person | MUST, SHOULD, MAY | Specification-first |
| **Blog Post** | Accessible, authoritative | Second person ("you") | needs to, should, can | Story-first |
| **Case Study** | Narrative, concrete | Third person (story) | demonstrate, show, enable | Data-first |
| **API Docs** | Instructional, precise | Second person ("you") | must, will, returns | Code-first |

---

## 18. Filing System

**Use this guide for:**
- `contribution/week6/6.2-FORMAL-EXTENSION.md` - Strict EIP tone
- `contribution/week6/6.3-BLOG-POST.md` - Enhanced accessible tone
- `contribution/week6/6.4-CASE-STUDY.md` - Narrative technical tone

**Reference sections:**
- Abstract writing: §10
- Motivation writing: §11
- Security phrasing: §7
- Public-facing adaptation: §14

---

## Copyright

This style guide is released under CC0 (public domain) to match EIP-8004 licensing.

**Author**: Claude (Anthropic)
**Derived From**: ERC-8004: Trustless Agents (Dan Finlay et al., 2025)
**Last Updated**: October 30, 2025
