"""
Tests for Task 4.2: Knowledge Base Builder

Tests chunk extraction, topic classification, and KB assembly.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "extractors"))

from knowledge_base_builder import (
    build_knowledge_base,
    chunk_id,
    classify_topic,
    extract_tags,
    process_profiles,
    _extract_chunks_from_product,
    _group_into_threads,
    _thread_to_content,
)


# --- Tests: classify_topic ---


class TestClassifyTopic:
    def test_defi_keywords(self):
        topics = classify_topic("I'm providing liquidity on Uniswap defi pool")
        assert "defi" in topics

    def test_trading_keywords(self):
        topics = classify_topic("Buy ETH now, bullish chart pattern")
        assert "trading" in topics

    def test_ai_keywords(self):
        topics = classify_topic("This LLM agent uses Claude for AI tasks")
        assert "ai" in topics

    def test_blockchain_keywords(self):
        topics = classify_topic("Ethereum L2 bridge rollup")
        assert "blockchain" in topics

    def test_unknown_defaults_to_general(self):
        topics = classify_topic("Hello world nice weather")
        assert topics == ["general"]

    def test_multiple_topics(self):
        topics = classify_topic("Trading DeFi tokens on Uniswap with AI signals")
        assert len(topics) >= 2

    def test_max_three_topics(self):
        topics = classify_topic(
            "Trading DeFi NFT blockchain AI design python community governance"
        )
        assert len(topics) <= 3


# --- Tests: extract_tags ---


class TestExtractTags:
    def test_extracts_matching_keywords(self):
        tags = extract_tags("Building a DeFi pool with Uniswap swap")
        assert "defi" in tags or "swap" in tags or "pool" in tags

    def test_max_ten_tags(self):
        tags = extract_tags(
            "ai ml llm gpt claude agent chatbot neural defi yield liquidity "
            "swap pool farm stake lending trade trading buy sell long"
        )
        assert len(tags) <= 10

    def test_empty_input(self):
        tags = extract_tags("")
        assert tags == []


# --- Tests: chunk_id ---


class TestChunkId:
    def test_deterministic(self):
        id1 = chunk_id("hello world", "source1")
        id2 = chunk_id("hello world", "source1")
        assert id1 == id2

    def test_different_content(self):
        id1 = chunk_id("hello", "source1")
        id2 = chunk_id("world", "source1")
        assert id1 != id2

    def test_format(self):
        cid = chunk_id("test", "src")
        assert cid.startswith("chunk-")
        assert len(cid) == 18  # "chunk-" + 12 hex chars


# --- Tests: _extract_chunks_from_product ---


class TestExtractChunksFromProduct:
    def test_stream_analysis_topics(self):
        data = {
            "topic_breakdown": [
                {"topic": "DeFi yields", "summary": "Discussion about yield farming strategies", "confidence": 0.8},
                {"topic": "NFT drops", "summary": "New collection launches", "confidence": 0.6},
            ],
            "key_moments": [
                {"description": "Peak engagement when 0xultravioleta explains Uniswap v4 hooks", "timestamp": "15:30"},
            ],
            "timestamp": "2026-02-25T10:00:00Z",
        }
        chunks = _extract_chunks_from_product(data, "analyze_stream", "test.json")
        assert len(chunks) >= 2  # 2 topics + 1 moment
        assert any("DeFi" in c["content"] for c in chunks)

    def test_trending_predictions(self):
        data = {
            "predictions": [
                {"topic": "AI Agents", "confidence": 0.85, "reason": "Growing interest in autonomous systems"},
                {"topic": "L2 Bridges", "confidence": 0.6},
            ]
        }
        chunks = _extract_chunks_from_product(data, "predict_trending", "test.json")
        assert len(chunks) == 2
        assert chunks[0]["confidence"] == 0.85

    def test_blog_post(self):
        data = {
            "title": "DeFi Yield Strategies 2026",
            "content": "A comprehensive guide to yield farming in the current market...",
        }
        chunks = _extract_chunks_from_product(data, "generate_blog", "test.json")
        assert len(chunks) == 1
        assert chunks[0]["source_type"] == "blog_post"
        assert "title" in chunks[0]

    def test_knowledge_graph(self):
        data = {
            "nodes": [
                {"name": "Uniswap", "description": "Leading DEX protocol", "centrality": 0.9},
                {"name": "Aave", "description": "Lending protocol", "centrality": 0.7},
            ]
        }
        chunks = _extract_chunks_from_product(data, "knowledge_graph", "test.json")
        assert len(chunks) == 2
        assert chunks[0]["confidence"] == 0.9

    def test_empty_data(self):
        chunks = _extract_chunks_from_product({}, "analyze_stream", "empty.json")
        assert chunks == []

    def test_short_content_filtered(self):
        data = {"topic_breakdown": [{"topic": "X", "summary": "", "confidence": 0.5}]}
        chunks = _extract_chunks_from_product(data, "analyze_stream", "test.json")
        # "Topic: X - " is 11 chars, below MIN_CHUNK_LENGTH
        assert len(chunks) == 0


# --- Tests: _group_into_threads ---


class TestGroupIntoThreads:
    def test_groups_messages(self):
        messages = [{"username": f"user{i}", "message": f"msg {i}"} for i in range(25)]
        threads = _group_into_threads(messages)
        assert len(threads) >= 1
        assert sum(len(t) for t in threads) == 25

    def test_empty_messages(self):
        assert _group_into_threads([]) == []

    def test_single_message(self):
        threads = _group_into_threads([{"username": "u", "message": "hi"}])
        assert len(threads) == 1


# --- Tests: _thread_to_content ---


class TestThreadToContent:
    def test_formats_messages(self):
        thread = [
            {"username": "alice", "message": "Hello"},
            {"username": "bob", "message": "Hi there"},
        ]
        content = _thread_to_content(thread)
        assert "alice: Hello" in content
        assert "bob: Hi there" in content

    def test_max_20_messages(self):
        thread = [{"username": f"u{i}", "message": f"msg{i}"} for i in range(30)]
        content = _thread_to_content(thread)
        lines = content.strip().split("\n")
        assert len(lines) <= 20


# --- Tests: build_knowledge_base ---


class TestBuildKnowledgeBase:
    def test_writes_jsonl_files(self, tmp_path):
        chunks = [
            {"id": "chunk-001", "topic": "defi", "content": "DeFi yield farming strategies", "source": "test", "source_type": "test", "timestamp": "", "tags": ["defi"], "confidence": 0.8},
            {"id": "chunk-002", "topic": "ai", "content": "AI agent development patterns", "source": "test", "source_type": "test", "timestamp": "", "tags": ["ai"], "confidence": 0.7},
            {"id": "chunk-003", "topic": "defi", "content": "Uniswap liquidity pools", "source": "test", "source_type": "test", "timestamp": "", "tags": ["defi"], "confidence": 0.6},
        ]
        index = build_knowledge_base(chunks, tmp_path)

        assert index["total_chunks"] == 3
        assert index["total_topics"] == 2

        # Check JSONL files
        defi_chunks = (tmp_path / "defi" / "chunks.jsonl").read_text(encoding="utf-8")
        assert len(defi_chunks.strip().split("\n")) == 2

        ai_chunks = (tmp_path / "ai" / "chunks.jsonl").read_text(encoding="utf-8")
        assert len(ai_chunks.strip().split("\n")) == 1

        # Check index
        index_data = json.loads((tmp_path / "_index.json").read_text(encoding="utf-8"))
        assert index_data["total_chunks"] == 3

    def test_deduplicates_by_id(self, tmp_path):
        chunks = [
            {"id": "chunk-dup", "topic": "ai", "content": "Same content", "source": "a", "source_type": "test", "timestamp": "", "tags": [], "confidence": 0.5},
            {"id": "chunk-dup", "topic": "ai", "content": "Same content", "source": "b", "source_type": "test", "timestamp": "", "tags": [], "confidence": 0.5},
        ]
        index = build_knowledge_base(chunks, tmp_path)
        assert index["total_chunks"] == 1

    def test_topic_filter(self, tmp_path):
        chunks = [
            {"id": "c1", "topic": "defi", "content": "DeFi stuff", "source": "t", "source_type": "t", "timestamp": "", "tags": [], "confidence": 0.5},
            {"id": "c2", "topic": "ai", "content": "AI stuff", "source": "t", "source_type": "t", "timestamp": "", "tags": [], "confidence": 0.5},
        ]
        index = build_knowledge_base(chunks, tmp_path, topic_filter="defi")
        assert index["total_chunks"] == 1
        assert not (tmp_path / "ai").exists()

    def test_empty_chunks(self, tmp_path):
        index = build_knowledge_base([], tmp_path)
        assert index["total_chunks"] == 0
        assert index["total_topics"] == 0
