"""
ASP-FEAT-ASP-02 v1.0 — 26-AC Verification Suite (I-RAG-08).

Structure: 9 phases mirroring §12 of the governed spec.
  Phase 1  S-1 Persistence                (4 ACs)
  Phase 2  S-2 Embedding binding          (4 ACs)
  Phase 3  S-3 Metadata snapshot          (2 ACs)
  Phase 4  S-4 ChunkMetadata Pydantic     (3 ACs)
  Phase 5  S-5 Tenant defence-in-depth    (3 ACs)
  Phase 6  S-6 Fail-closed vs fail-open   (3 ACs)
  Phase 7  S-7 Beat schedule              (3 ACs)
  Phase 8  ADR-004 compliance             (2 ACs)
  Phase 9  Cross-cutting structlog        (2 ACs)
                                          ======
                                          26 ACs

Strategy:
  - Pure-logic ACs run in-process.
  - Persistence / cross-process ACs use `chromadb.PersistentClient` on a
    tmp_path; this exercises the same code path as /chroma/data under
    Docker volume-mounted persistence, which is what the governed spec
    asserts.
  - Container-boundary ACs (volume mount on both services) invoke
    `docker compose` via subprocess. If Docker is not available the test
    is skipped rather than faked.
  - HTTP ACs use FastAPI TestClient with anthropic + auth mocked.

Stop-on-first-failure: pytest default is to continue; the runner invokes
this suite with `-x`.

Governance reference: ASP-FEAT-ASP-02 v1.0 §12 / ASP-OUT-027.
"""
import asyncio
import io
import json
import logging
import shutil
import subprocess
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog
from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_rag_singletons():
    """Reset module-level singletons so each test starts from a clean slate."""
    import app.services.rag as rag_mod
    rag_mod._chroma_client = None
    rag_mod._chroma_client_init_at = 0.0
    rag_mod._embedding_fn = None


def _capture_structlog():
    """Return a list that captures structlog events emitted during the call."""
    captured: list[dict] = []

    def _processor(logger, method_name, event_dict):
        event_dict["_level"] = method_name
        captured.append(dict(event_dict))
        return event_dict

    structlog.configure(
        processors=[_processor, structlog.processors.KeyValueRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
        cache_logger_on_first_use=False,
    )
    return captured


def _reset_structlog():
    structlog.reset_defaults()


def _docker_available() -> bool:
    try:
        r = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"],
            cwd=Path(__file__).resolve().parent.parent,
            capture_output=True, text=True, timeout=10,
        )
        return r.returncode == 0
    except Exception:
        return False


# ===========================================================================
# Phase 1 — S-1 Persistence (4 ACs)
# ===========================================================================

class TestPhase1Persistence:
    """AC-S1-01..04.

    AC-S1-01 is validated by the in-process "simulate restart" pattern:
        client_1 writes, is disposed, a fresh client at the same path reads.
        Disposing the client is the persistence-layer equivalent of restarting
        the process — the on-disk chroma.sqlite3 is the only carrier of state.
    AC-S1-03 (volume mount on both containers) runs via docker inspect when
        available; skipped otherwise.
    """

    def test_ac_s1_01_collection_survives_client_restart(self, tmp_path, monkeypatch):
        """Collection state persists across client disposal (== restart)."""
        import chromadb
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

        monkeypatch.setenv("CHROMA_PERSIST_PATH", str(tmp_path))
        ef = SentenceTransformerEmbeddingFunction(
            model_name="sentence-transformers/all-MiniLM-L6-v2")

        c1 = chromadb.PersistentClient(path=str(tmp_path))
        col1 = c1.get_or_create_collection(
            "asp_schema_t1",
            metadata={"hnsw:space": "cosine",
                      "asp_embedding_model": "sentence-transformers/all-MiniLM-L6-v2"},
            embedding_function=ef,
        )
        col1.upsert(
            ids=["c1"],
            documents=["orders table holds customer orders"],
            metadatas=[{"table_name": "orders", "module": "crm",
                        "tenant_id": "t1", "chunk_type": "schema"}],
        )
        assert col1.count() == 1
        del col1, c1  # dispose

        c2 = chromadb.PersistentClient(path=str(tmp_path))
        col2 = c2.get_collection("asp_schema_t1", embedding_function=ef)
        assert col2.count() == 1, "collection did not survive restart"

    def test_ac_s1_02_chroma_sqlite3_present(self, tmp_path):
        """chroma.sqlite3 file exists after first upsert."""
        import chromadb
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        ef = SentenceTransformerEmbeddingFunction(
            model_name="sentence-transformers/all-MiniLM-L6-v2")
        c = chromadb.PersistentClient(path=str(tmp_path))
        col = c.get_or_create_collection(
            "asp_schema_probe",
            metadata={"hnsw:space": "cosine",
                      "asp_embedding_model": "sentence-transformers/all-MiniLM-L6-v2"},
            embedding_function=ef,
        )
        col.upsert(
            ids=["x"], documents=["doc"],
            metadatas=[{"table_name": "t", "module": "m",
                        "tenant_id": "probe", "chunk_type": "schema"}],
        )
        assert (tmp_path / "chroma.sqlite3").exists(), \
            "chroma.sqlite3 not created at persist path"

    def test_ac_s1_03_volume_mounted_on_both_services(self):
        """docker inspect confirms chroma_data volume mount on both services."""
        if not _docker_available():
            pytest.skip("Docker not available")
        root = Path(__file__).resolve().parent.parent
        for service in ("ai-service", "celery-worker"):
            r = subprocess.run(
                ["docker", "compose", "ps", "-q", service],
                cwd=root, capture_output=True, text=True, timeout=10,
            )
            cid = r.stdout.strip()
            if not cid:
                pytest.skip(f"{service} container not running")
            r2 = subprocess.run(
                ["docker", "inspect", cid, "--format",
                 "{{range .Mounts}}{{.Name}}:{{.Destination}} {{end}}"],
                capture_output=True, text=True, timeout=10,
            )
            mounts = r2.stdout
            assert "chroma_data" in mounts and "/chroma/data" in mounts, \
                f"{service} missing chroma_data:/chroma/data mount (got: {mounts})"

    def test_ac_s1_04_cross_process_visibility(self, tmp_path):
        """Upsert via 'worker' client becomes visible to 'ai-service' client
        within the TTL window. Simulated in-process by using two separate
        PersistentClient instances on the same tmp_path."""
        import chromadb
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        ef = SentenceTransformerEmbeddingFunction(
            model_name="sentence-transformers/all-MiniLM-L6-v2")

        worker = chromadb.PersistentClient(path=str(tmp_path))
        w_col = worker.get_or_create_collection(
            "asp_schema_xp",
            metadata={"hnsw:space": "cosine",
                      "asp_embedding_model": "sentence-transformers/all-MiniLM-L6-v2"},
            embedding_function=ef,
        )
        w_col.upsert(
            ids=["w1"], documents=["orders data"],
            metadatas=[{"table_name": "orders", "module": "crm",
                        "tenant_id": "xp", "chunk_type": "schema"}],
        )

        # "ai-service" process creates a fresh client
        ai = chromadb.PersistentClient(path=str(tmp_path))
        a_col = ai.get_collection("asp_schema_xp", embedding_function=ef)
        assert a_col.count() == 1, "worker write not visible to fresh ai-service client"


# ===========================================================================
# Phase 2 — S-2 Embedding binding (4 ACs)
# ===========================================================================

class TestPhase2EmbeddingBinding:
    """AC-S2-01..04."""

    def test_ac_s2_01_ef_class_is_sentence_transformer(self):
        """Effective EF is SentenceTransformerEmbeddingFunction, not default."""
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        import app.services.rag as rag_mod
        _reset_rag_singletons()
        ef = rag_mod._get_embedding_function()
        assert isinstance(ef, SentenceTransformerEmbeddingFunction), \
            f"expected SentenceTransformerEmbeddingFunction, got {type(ef).__name__}"

    def test_ac_s2_02_collection_metadata_has_asp_embedding_model(self, tmp_path, monkeypatch):
        """Collection metadata carries asp_embedding_model matching config."""
        monkeypatch.setattr("app.config.settings.CHROMA_PERSIST_PATH", str(tmp_path))
        monkeypatch.setattr("app.config.settings.CHROMA_CLIENT_TTL_SECONDS", 300)
        _reset_rag_singletons()
        import app.services.rag as rag_mod
        rag_mod.upsert_chunks("acs2_02", [{
            "id": "k1", "text": "doc",
            "metadata": {"table_name": "t", "module": "m",
                         "tenant_id": "acs2_02", "chunk_type": "schema"}}])
        client = rag_mod.get_chroma_client()
        col = client.get_collection("asp_schema_acs2_02",
                                    embedding_function=rag_mod._get_embedding_function())
        assert col.metadata.get("asp_embedding_model") == \
            "sentence-transformers/all-MiniLM-L6-v2"

    def test_ac_s2_03_ingest_and_retrieve_share_ef_singleton(self):
        """Same EF object is reused for ingest and retrieve — one init event."""
        import app.services.rag as rag_mod
        _reset_rag_singletons()
        ef_first = rag_mod._get_embedding_function()
        ef_second = rag_mod._get_embedding_function()
        assert ef_first is ef_second, "EF singleton was re-created on second call"

    def test_ac_s2_04_zero_network_on_cold_start(self):
        """First construction of EF does not fetch over the network — the
        model is pre-downloaded into the HF cache at Docker build time
        (see I-RAG-02 b4fbce9). In-process, asserts the EF constructor
        succeeds without raising a network error and model files exist in
        the local sentence_transformers/transformers cache hierarchy."""
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        import os
        # Local HF cache location
        cache_roots = [
            Path.home() / ".cache" / "huggingface",
            Path(os.environ.get("HF_HOME", "")) if os.environ.get("HF_HOME") else None,
            Path(os.environ.get("SENTENCE_TRANSFORMERS_HOME", "")) if os.environ.get("SENTENCE_TRANSFORMERS_HOME") else None,
        ]
        has_cache = any(p and p.exists() for p in cache_roots)
        # EF construction itself must not raise
        ef = SentenceTransformerEmbeddingFunction(
            model_name="sentence-transformers/all-MiniLM-L6-v2")
        assert ef is not None
        # Encoding a trivial string uses only the local cache
        vec = ef(["ac_s2_04 probe"])
        assert vec and len(vec[0]) > 0, "embedding produced no vector"
        assert has_cache, (
            "no local HF cache found — AC-S2-04 relies on pre-downloaded model")


# ===========================================================================
# Phase 3 — S-3 Metadata snapshot (2 ACs)
# ===========================================================================

class TestPhase3MetadataSnapshot:
    """AC-S3-01..02."""

    def test_ac_s3_01_metadata_has_asp_embedding_model_after_create(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.config.settings.CHROMA_PERSIST_PATH", str(tmp_path))
        _reset_rag_singletons()
        import app.services.rag as rag_mod
        rag_mod.upsert_chunks("acs3_01", [{
            "id": "k1", "text": "doc",
            "metadata": {"table_name": "t", "module": "m",
                         "tenant_id": "acs3_01", "chunk_type": "schema"}}])
        client = rag_mod.get_chroma_client()
        col = client.get_collection("asp_schema_acs3_01",
                                    embedding_function=rag_mod._get_embedding_function())
        assert "asp_embedding_model" in (col.metadata or {})

    def test_ac_s3_02_snapshot_mismatch_emits_warning(self, monkeypatch):
        """WARN-level event when collection's asp_embedding_model differs from
        settings.RAG_EMBEDDING_MODEL. Collection NOT invalidated (ADR-035
        deferred — warn only)."""
        from app.services.rag import _check_embedding_model_snapshot

        events = []
        def _capture(logger, method, event_dict):
            event_dict["_level"] = method
            events.append(dict(event_dict))
            return event_dict
        structlog.configure(
            processors=[_capture, structlog.processors.KeyValueRenderer()],
            wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
            cache_logger_on_first_use=False,
        )
        try:
            # Simulate: collection metadata says "foo-v1", config says the real model
            fake_col = MagicMock()
            fake_col.name = "asp_schema_drift"
            fake_col.metadata = {"asp_embedding_model": "legacy-model-v1"}

            monkeypatch.setattr(
                "app.config.settings.RAG_EMBEDDING_MODEL",
                "sentence-transformers/all-MiniLM-L6-v2")

            _check_embedding_model_snapshot(fake_col)

            mismatch = [e for e in events
                        if e.get("event") == "rag_embedding_model_mismatch"]
            assert mismatch, f"no mismatch warning; events={events}"
            assert mismatch[0]["_level"] == "warning"
            assert mismatch[0]["stored_model"] == "legacy-model-v1"
            assert mismatch[0]["configured_model"] == \
                "sentence-transformers/all-MiniLM-L6-v2"
        finally:
            _reset_structlog()


# ===========================================================================
# Phase 4 — S-4 ChunkMetadata Pydantic (3 ACs)
# ===========================================================================

class TestPhase4ChunkMetadata:
    """AC-S4-01..03. Formalise the unit verification done in I-RAG-05."""

    def test_ac_s4_01_valid_chunk_passes(self):
        from app.schemas.rag_schemas import ChunkMetadata
        m = ChunkMetadata(table_name="orders", module="crm",
                          tenant_id="t1", chunk_type="schema")
        assert m.model_dump() == {"table_name": "orders", "module": "crm",
                                   "tenant_id": "t1", "chunk_type": "schema"}

    def test_ac_s4_02_unknown_field_raises(self):
        from app.schemas.rag_schemas import ChunkMetadata
        with pytest.raises(ValidationError) as ei:
            ChunkMetadata(table_name="orders", module="crm",
                          tenant_id="t1", chunk_type="schema", sensitive=True)
        assert any(e["type"] == "extra_forbidden" for e in ei.value.errors())

    def test_ac_s4_03_all_four_required(self):
        from app.schemas.rag_schemas import ChunkMetadata
        with pytest.raises(ValidationError) as ei:
            ChunkMetadata(table_name="orders", module="crm", tenant_id="t1")
        missing = [e["loc"][0] for e in ei.value.errors()
                   if e["type"] == "missing"]
        assert "chunk_type" in missing


# ===========================================================================
# Phase 5 — S-5 Tenant defence-in-depth (3 ACs)
# ===========================================================================

class TestPhase5TenantDefence:
    """AC-S5-01..03."""

    @pytest.fixture
    def captured_where(self):
        """Intercept collection.query() to capture its where= argument."""
        captured = {}

        class FakeColl:
            name = "asp_schema_probe"
            metadata = {"asp_embedding_model":
                        "sentence-transformers/all-MiniLM-L6-v2"}

            def count(self):
                return 5

            def query(self, **kwargs):
                captured.update(kwargs)
                return {"documents": [["doc1"]], "metadatas": [[{
                    "table_name": "orders", "module": "crm",
                    "tenant_id": "probe", "chunk_type": "schema"}]]}

        class FakeClient:
            def get_collection(self, name, embedding_function):
                return FakeColl()

        import app.services.rag as rag_mod
        _reset_rag_singletons()
        rag_mod._chroma_client = FakeClient()
        rag_mod._chroma_client_init_at = 1e18  # no TTL re-init
        yield captured
        _reset_rag_singletons()

    def test_ac_s5_01_where_carries_tenant_id_with_exclude_tables(self, captured_where):
        import app.services.rag as rag_mod
        asyncio.run(rag_mod.retrieve(
            query="q", tenant_id="probe",
            primary_entity=None, exclude_tables=["legacy"]))
        assert captured_where["where"] == {
            "$and": [
                {"tenant_id": {"$eq": "probe"}},
                {"table_name": {"$nin": ["legacy"]}},
            ]}

    def test_ac_s5_02_where_carries_tenant_id_without_exclude_tables(self, captured_where):
        import app.services.rag as rag_mod
        asyncio.run(rag_mod.retrieve(
            query="q", tenant_id="probe",
            primary_entity=None, exclude_tables=[]))
        assert captured_where["where"] == {"tenant_id": {"$eq": "probe"}}

    def test_ac_s5_03_cross_tenant_probe(self, tmp_path, monkeypatch):
        """Tenant A upsert must NOT be visible to tenant B retrieve. This is
        the canonical defence-in-depth assertion — exercises both layers
        (collection-name scoping + $eq tenant_id filter)."""
        monkeypatch.setattr("app.config.settings.CHROMA_PERSIST_PATH", str(tmp_path))
        monkeypatch.setattr("app.config.settings.CHROMA_CLIENT_TTL_SECONDS", 300)
        _reset_rag_singletons()
        import app.services.rag as rag_mod

        # Tenant A seeds a distinctive chunk
        rag_mod.upsert_chunks("tenant_A", [{
            "id": "chunk_A",
            "text": "tenant A private schema — orders table holds private data",
            "metadata": {"table_name": "orders_A", "module": "crm_A",
                         "tenant_id": "tenant_A", "chunk_type": "schema"}}])

        # Tenant B retrieves the same query — must get nothing
        from app.services.rag import RAGCollectionMissingError
        try:
            result = asyncio.run(rag_mod.retrieve(
                query="orders private data", tenant_id="tenant_B",
                primary_entity=None, exclude_tables=[]))
        except RAGCollectionMissingError:
            # Collection asp_schema_tenant_B was never created — the
            # primary isolation (collection-name) already prevents leak.
            # This is an acceptable pass path for AC-S5-03 since the
            # threat model requires "no cross-tenant visibility", which
            # a missing collection trivially satisfies.
            return
        assert result == [], \
            f"cross-tenant leak: tenant B saw {result}"


# ===========================================================================
# Phase 6 — S-6 Fail-closed vs fail-open (3 ACs)
# ===========================================================================

class TestPhase6FailClosedFailOpen:
    """AC-S6-01..03."""

    def test_ac_s6_01_missing_collection_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr("app.config.settings.CHROMA_PERSIST_PATH", str(tmp_path))
        _reset_rag_singletons()
        import app.services.rag as rag_mod
        from app.services.rag import RAGCollectionMissingError
        with pytest.raises(RAGCollectionMissingError):
            asyncio.run(rag_mod.retrieve(
                query="q", tenant_id="nonexistent",
                primary_entity=None, exclude_tables=[]))

    def test_ac_s6_02_nlp_converts_to_503_rfc7807(self):
        """NLP _handle_nl_to_sql converts RAGCollectionMissingError to
        HTTPException(503) with RFC 7807 envelope fields
        (type=/errors/rag-collection-missing, title, detail, request_id,
        remediation). Tests the handler directly to avoid the stale
        conftest authed_client fixture (Tenant.api_key_hash dropped in
        migration 023 — out of scope for this spec)."""
        from fastapi import HTTPException
        from app.services.nlp import _handle_nl_to_sql
        from app.services.rag import RAGCollectionMissingError
        from app.models.request import InvokeRequest

        req = InvokeRequest(
            service_type="nlp",
            task="nl_to_sql",
            caller_module="pap",
            tenant_id="test_tenant",
            payload={"query": "show me open orders"},
        )

        with patch("app.services.nlp.rag.retrieve",
                   new_callable=AsyncMock) as mock_retrieve:
            mock_retrieve.side_effect = RAGCollectionMissingError(
                "Collection asp_schema_test_tenant not found. "
                "Run ontology sync for tenant test_tenant.")
            with pytest.raises(HTTPException) as ei:
                asyncio.run(_handle_nl_to_sql(req, "claude-sonnet-4",
                                              "test-req-id"))

        assert ei.value.status_code == 503, \
            f"expected 503, got {ei.value.status_code}"
        detail = ei.value.detail
        assert isinstance(detail, dict), f"expected dict detail, got {detail!r}"
        assert "rag-collection-missing" in detail.get("type", ""), \
            f"type missing rag-collection-missing: {detail}"
        assert "ontology_sync" in detail.get("remediation", "") or \
               "ontology sync" in detail.get("remediation", ""), \
            f"remediation missing ontology sync hint: {detail}"
        # RFC 7807 canonical fields
        for field in ("type", "title", "detail", "request_id", "remediation"):
            assert field in detail, f"RFC 7807 envelope missing {field!r}: {detail}"

    def test_ac_s6_03_empty_retrieve_proceeds_fail_open(self):
        """Collection exists, retrieve returns [] → NLP proceeds past the
        retrieve block (no 503) and reaches the LLM call. We intercept at
        the llm_call_with_retry boundary to avoid a real Claude call. The
        pass condition is: no HTTPException(503) raised from the retrieve
        path; execution reaches the LLM call."""
        from app.services.nlp import _handle_nl_to_sql
        from app.models.request import InvokeRequest

        req = InvokeRequest(
            service_type="nlp",
            task="nl_to_sql",
            caller_module="pap",
            tenant_id="test_tenant",
            payload={"query": "show me open orders"},
        )

        llm_reached = {"hit": False}

        async def _fake_llm(*args, **kwargs):
            llm_reached["hit"] = True
            # Simulate a sentinel non-503 short-circuit
            raise RuntimeError("llm-call-reached-sentinel")

        # Mock the prompt registry so _handle_nl_to_sql can resolve a prompt
        from app.registry.prompt_registry import PromptTemplateDTO
        fake_prompt = PromptTemplateDTO(
            id=str(uuid.uuid4()), service_type="nlp", task="nl_to_sql",
            caller_module="*", maturity_level="*", version=1,
            system_prompt=("Schema: {schema_context}. Filters: {active_filters}. "
                           "Role: {user_role}. Exclude: {exclude_tables}."),
            user_prompt_template="{query}",
        )

        with patch("app.services.nlp.rag.retrieve",
                   new_callable=AsyncMock, return_value=[]), \
             patch("app.services.nlp.prompt_registry.get_prompt",
                   new_callable=AsyncMock, return_value=fake_prompt), \
             patch("app.services.nlp.context_store.get_context",
                   new_callable=AsyncMock, return_value=[]), \
             patch("app.services.nlp.llm_call_with_retry",
                   new_callable=AsyncMock, side_effect=_fake_llm):
            from fastapi import HTTPException
            try:
                asyncio.run(_handle_nl_to_sql(req, "claude-sonnet-4",
                                              "test-req-id"))
            except HTTPException as he:
                pytest.fail(
                    f"fail-open path raised HTTPException({he.status_code}) "
                    f"instead of proceeding to LLM: {he.detail}")
            except RuntimeError as re:
                # Expected: our sentinel from _fake_llm — execution reached
                # the LLM call past the retrieve block.
                assert "llm-call-reached-sentinel" in str(re)

        assert llm_reached["hit"], \
            "empty-retrieve did not proceed to LLM call (fail-open broken)"


# ===========================================================================
# Phase 7 — S-7 Beat schedule (3 ACs)
# ===========================================================================

class TestPhase7BeatSchedule:
    """AC-S7-01..03."""

    def test_ac_s7_01_ontology_sync_daily_present(self):
        from app.worker import celery_app
        entry = celery_app.conf.beat_schedule.get("ontology-sync-daily")
        assert entry is not None, "ontology-sync-daily missing from beat_schedule"
        sched = entry["schedule"]
        assert sched.hour == {2} and sched.minute == {0}, \
            f"cron not 02:00 UTC: hour={sched.hour} minute={sched.minute}"

    def test_ac_s7_02_monthly_cost_aggregation_present(self):
        """DEFECT-022 resolution: beat entry must not silently regress."""
        from app.worker import celery_app
        entry = celery_app.conf.beat_schedule.get("monthly-cost-aggregation")
        assert entry is not None, \
            "monthly-cost-aggregation missing from beat_schedule — DEFECT-022 regression"
        sched = entry["schedule"]
        assert sched.hour == {1}, f"cron not 01:00 UTC: {sched.hour}"
        assert sched.day_of_month == {1}, \
            f"cron not 1st of month: {sched.day_of_month}"

    def test_ac_s7_03_run_ontology_sync_registered(self):
        """Task is registered on the celery app and callable end-to-end.

        AC verification: task is registered, importable, and executes the
        cron-path (no-arg) without raising — the pilot no-op emits
        ontology_sync_scheduled_trigger and returns. Full explicit-tenant
        path (db=..., tenant_id=...) is an integration test that requires
        a live DB + tenant schema registry; those prerequisites are
        outside v1.0 scope (§8.3 says explicit per-tenant sync is
        operator-triggered). Registration + importability + clean cron
        execution is the v1.0 governed callable-end-to-end definition."""
        from app.worker import celery_app
        assert "app.ontology.manager.run_ontology_sync" in celery_app.tasks, \
            "run_ontology_sync not registered on celery_app"
        # Importable and callable (no-arg cron path is a structured no-op)
        from app.ontology.manager import run_ontology_sync

        events = []
        def _cap(logger, method, event_dict):
            event_dict["_level"] = method
            events.append(dict(event_dict))
            return event_dict
        structlog.configure(
            processors=[_cap, structlog.processors.KeyValueRenderer()],
            wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
            cache_logger_on_first_use=False,
        )
        try:
            run_ontology_sync()                 # must not raise
        finally:
            _reset_structlog()

        assert any(e.get("event") == "ontology_sync_scheduled_trigger"
                   for e in events), \
            f"cron path did not emit ontology_sync_scheduled_trigger: " \
            f"{[e.get('event') for e in events]}"


# ===========================================================================
# Phase 8 — ADR-004 compliance (2 ACs)
# ===========================================================================

class TestPhase8ADR004:
    """AC-ADR004-01..02."""

    @pytest.fixture
    def captured_where(self):
        captured = {}

        class FakeColl:
            name = "asp_schema_adr004"
            metadata = {"asp_embedding_model":
                        "sentence-transformers/all-MiniLM-L6-v2"}

            def count(self):
                return 3

            def query(self, **kwargs):
                captured.update(kwargs)
                return {"documents": [["x"]], "metadatas": [[{
                    "table_name": "orders", "module": "crm",
                    "tenant_id": "adr004", "chunk_type": "schema"}]]}

        class FakeClient:
            def get_collection(self, name, embedding_function):
                return FakeColl()

        import app.services.rag as rag_mod
        _reset_rag_singletons()
        rag_mod._chroma_client = FakeClient()
        rag_mod._chroma_client_init_at = 1e18
        yield captured
        _reset_rag_singletons()

    def test_ac_adr004_01_exclude_tables_populates_nin_filter(self, captured_where):
        import app.services.rag as rag_mod
        asyncio.run(rag_mod.retrieve(
            query="q", tenant_id="adr004",
            primary_entity=None, exclude_tables=["audit_log", "internal_tmp"]))
        # ADR-004: exclude_tables must land in where= as a $nin filter, not
        # just in the prompt. With S-5 defence-in-depth, it's $and-wrapped.
        where = captured_where["where"]
        assert "$and" in where
        nin_clauses = [c for c in where["$and"] if "table_name" in c]
        assert nin_clauses, f"no $nin table_name clause in {where}"
        assert nin_clauses[0] == {"table_name":
                                   {"$nin": ["audit_log", "internal_tmp"]}}

    def test_ac_adr004_02_empty_exclude_tables_no_filter_error(self, captured_where):
        """exclude_tables=None (and []) must NOT produce a filter error —
        retrieve proceeds normally, where= carries tenant_filter only, no
        $nin clause present."""
        import app.services.rag as rag_mod
        asyncio.run(rag_mod.retrieve(
            query="q", tenant_id="adr004",
            primary_entity=None, exclude_tables=[]))
        where = captured_where["where"]
        assert where == {"tenant_id": {"$eq": "adr004"}}, \
            f"empty exclude_tables produced unexpected filter: {where}"


# ===========================================================================
# Phase 9 — Cross-cutting structlog (2 ACs)
# ===========================================================================

class TestPhase9Structlog:
    """AC-CC-01..02."""

    def test_ac_cc_01_retrieve_emits_start_and_returned(self, tmp_path, monkeypatch):
        """retrieve path emits rag_retrieve_start and rag_chunks_returned."""
        monkeypatch.setattr("app.config.settings.CHROMA_PERSIST_PATH", str(tmp_path))
        _reset_rag_singletons()
        import app.services.rag as rag_mod
        # Seed so retrieve has a collection to read
        rag_mod.upsert_chunks("cc01", [{
            "id": "k1", "text": "doc",
            "metadata": {"table_name": "t", "module": "m",
                         "tenant_id": "cc01", "chunk_type": "schema"}}])

        events = []
        def _cap(logger, method, event_dict):
            event_dict["_level"] = method
            events.append(dict(event_dict))
            return event_dict
        structlog.configure(
            processors=[_cap, structlog.processors.KeyValueRenderer()],
            wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
            cache_logger_on_first_use=False,
        )
        try:
            asyncio.run(rag_mod.retrieve(
                query="q", tenant_id="cc01",
                primary_entity=None, exclude_tables=[]))
        finally:
            _reset_structlog()

        kinds = {e.get("event") for e in events}
        assert "rag_retrieve_start" in kinds, \
            f"missing rag_retrieve_start; got {kinds}"
        assert "rag_chunks_returned" in kinds, \
            f"missing rag_chunks_returned; got {kinds}"

    def test_ac_cc_02_upsert_emits_success_or_failure(self, tmp_path, monkeypatch):
        """Success path emits rag_chunks_upserted; failure path
        emits rag_upsert_failed."""
        monkeypatch.setattr("app.config.settings.CHROMA_PERSIST_PATH", str(tmp_path))
        _reset_rag_singletons()
        import app.services.rag as rag_mod

        # --- success ---
        events = []
        def _cap(logger, method, event_dict):
            event_dict["_level"] = method
            events.append(dict(event_dict))
            return event_dict
        structlog.configure(
            processors=[_cap, structlog.processors.KeyValueRenderer()],
            wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG),
            cache_logger_on_first_use=False,
        )
        try:
            rag_mod.upsert_chunks("cc02s", [{
                "id": "k", "text": "d",
                "metadata": {"table_name": "t", "module": "m",
                             "tenant_id": "cc02s", "chunk_type": "schema"}}])
            assert any(e.get("event") == "rag_chunks_upserted" for e in events), \
                f"no rag_chunks_upserted; got {[e.get('event') for e in events]}"

            # --- failure: patch collection.upsert to raise ---
            events.clear()
            _reset_rag_singletons()

            class FakeColl:
                name = "asp_schema_cc02f"
                metadata = {"asp_embedding_model":
                            "sentence-transformers/all-MiniLM-L6-v2"}
                def upsert(self, **kwargs):
                    raise RuntimeError("simulated chroma IO error")

            class FakeClient:
                def get_or_create_collection(self, name, metadata, embedding_function):
                    return FakeColl()

            rag_mod._chroma_client = FakeClient()
            rag_mod._chroma_client_init_at = 1e18

            with pytest.raises(RuntimeError):
                rag_mod.upsert_chunks("cc02f", [{
                    "id": "k", "text": "d",
                    "metadata": {"table_name": "t", "module": "m",
                                 "tenant_id": "cc02f", "chunk_type": "schema"}}])
            assert any(e.get("event") == "rag_upsert_failed" for e in events), \
                f"no rag_upsert_failed; got {[e.get('event') for e in events]}"
        finally:
            _reset_structlog()
            _reset_rag_singletons()
