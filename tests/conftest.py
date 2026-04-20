"""
Test configuration and fixtures.

**Schema alignment (migration 023 / ASP-FEAT-ASP-00 v1.0 / ADR-032).**

The `tenants.api_key_hash` column was dropped in migration 023; the
authoritative API-key source is now the `tenant_api_keys` junction
table (`app.models.db_models.TenantApiKey`). New-format keys follow
the pattern `asp_<prefix12>_<secret32>` (see
`app.utils.key_generator.generate_api_key`). Fixtures below construct
a valid `Tenant` + `TenantApiKey` pair consistent with the Gateway
spec, and — because the prior session-level mocking cannot faithfully
reproduce the Gateway's dual-path `verify_api_key` flow — we use
FastAPI `app.dependency_overrides` to bypass auth in tests that only
need "a valid authenticated caller". This is the same pattern the
Gateway test suite itself uses for non-auth ACs.

Cleanup commit per ASP-OUT-030 directive.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import bcrypt
import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# In-memory mocks — no DB, no Redis, no external services needed
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def test_api_key():
    """Raw new-format test key: asp_<prefix12>_<secret32>.

    Not a real credential — prefix and secret are fixed so bcrypt only
    needs to be computed once per test session.
    """
    return "asp_testprefix00_" + ("T" * 32)


@pytest.fixture(scope="session")
def test_api_key_prefix():
    """12-char prefix matching test_api_key (base36)."""
    return "testprefix00"


@pytest.fixture(scope="session")
def test_api_key_hash(test_api_key):
    return bcrypt.hashpw(test_api_key.encode(), bcrypt.gensalt()).decode()


@pytest.fixture(scope="module")
def mock_redis():
    """Mock Redis client for tests that don't need real Redis."""
    redis_mock = MagicMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.setex = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=True)
    redis_mock.ping = AsyncMock(return_value=True)
    return redis_mock


@pytest.fixture(scope="module")
def mock_db_session(test_api_key_hash, test_api_key_prefix):
    """Mock database session returning a valid tenant + matching
    `tenant_api_keys` row for auth (migration 023 schema).

    The session.execute() result is shaped to serve BOTH call sites in
    `app.gateway.auth.verify_api_key`:
      - new-format fast path: `scalar_one_or_none()` returns the
        TenantApiKey row.
      - legacy fallback path: `scalars().all()` returns a list with
        the same row (harmless — legacy path only runs if new-format
        regex fails, and the default test_api_key fixture IS
        new-format, so this branch is rarely exercised by callers).
    And `session.get(Tenant, ...)` returns the Tenant object for the
    Gateway's post-bcrypt tenant lookup.
    """
    from app.models.db_models import Tenant, TenantApiKey

    tenant_id = uuid.uuid4()
    tenant = Tenant(
        id=tenant_id,
        tenant_code="test_tenant",
        name="Test Tenant",
        monthly_quota_usd=50.0,
        is_active=True,
    )
    api_key_row = TenantApiKey(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        key_prefix=test_api_key_prefix,
        api_key_hash=test_api_key_hash,
        is_active=True,
        label="conftest",
    )

    session_mock = MagicMock()
    result_mock = MagicMock()
    # new-format path
    result_mock.scalar_one_or_none.return_value = api_key_row
    # legacy-path fallback shape
    result_mock.scalars.return_value.all.return_value = [api_key_row]
    session_mock.execute = AsyncMock(return_value=result_mock)
    # Gateway auth post-bcrypt tenant lookup
    session_mock.get = AsyncMock(return_value=tenant)
    session_mock.add = MagicMock()
    session_mock.commit = AsyncMock()
    session_mock.__aenter__ = AsyncMock(return_value=session_mock)
    session_mock.__aexit__ = AsyncMock(return_value=False)
    return session_mock, tenant


@pytest.fixture(scope="module")
def client(mock_db_session, mock_redis):
    """FastAPI test client with mocked infra.

    Auth path remains REAL: the mocked session returns a valid
    `tenant_api_keys` row whose bcrypt hash matches the test key, so
    `verify_api_key` succeeds for the test key and correctly rejects
    any other header value. This preserves the behaviour of negative
    auth ACs (e.g. `test_ac20_invalid_api_key_401`) that exercise the
    wrong-key path with the same `client` fixture.
    """
    session_mock, _tenant = mock_db_session

    with patch("app.main.init_db", new_callable=AsyncMock), \
         patch("app.main.init_redis", new_callable=AsyncMock), \
         patch("app.infra.db.init_db", new_callable=AsyncMock), \
         patch("app.infra.redis.init_redis", new_callable=AsyncMock), \
         patch("app.infra.db.get_session") as mock_get_session, \
         patch("app.gateway.auth.get_session") as mock_auth_session, \
         patch("app.infra.redis.get_redis", return_value=mock_redis):

        mock_get_session.return_value.__aenter__ = AsyncMock(return_value=session_mock)
        mock_get_session.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_auth_session.return_value.__aenter__ = AsyncMock(return_value=session_mock)
        mock_auth_session.return_value.__aexit__ = AsyncMock(return_value=False)

        from app.main import app
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c


@pytest.fixture(scope="module")
def authed_client(client, test_api_key):
    """TestClient with the new-format API key header pre-set."""
    client.headers.update({"X-ASP-API-Key": test_api_key})
    return client


@pytest.fixture(scope="function")
def mock_anthropic():
    """Patch anthropic client to return a controlled response."""
    with patch("app.services._shared.anthropic_client") as mock_shared, \
         patch("app.services.nlp.anthropic_client", mock_shared), \
         patch("app.services.generation.anthropic_client", mock_shared):
        yield mock_shared


@pytest.fixture(scope="function")
def mock_rag():
    """Patch RAG retrieve to return empty list."""
    with patch("app.services.rag.retrieve", new_callable=AsyncMock, return_value=[]) as mock:
        yield mock


@pytest.fixture(scope="function")
def mock_prompt_registry():
    """Patch prompt registry to return a test prompt.

    Returns different prompts based on task name to support all NLP tasks.
    """
    from app.registry.prompt_registry import PromptTemplateDTO

    nl_to_sql_prompt = PromptTemplateDTO(
        id=str(uuid.uuid4()),
        service_type="nlp",
        task="nl_to_sql",
        caller_module="*",
        maturity_level="*",
        version=1,
        system_prompt=(
            "You are a SQL expert. Schema: {schema_context}. "
            "Filters: {active_filters}. Role: {user_role}. Exclude: {exclude_tables}."
        ),
        user_prompt_template="Convert this query to SQL: {query}",
    )

    classify_prompt = PromptTemplateDTO(
        id=str(uuid.uuid4()),
        service_type="nlp",
        task="classify_probe_result",
        caller_module="playwright_runner",
        maturity_level="*",
        version=1,
        system_prompt="You are a web form behavior classifier.",
        user_prompt_template=(
            "Form URL: {page_url}\nPage type: {page_type}\n"
            "Fields submitted: {submitted_fields}\n"
            "Post-submit URL: {post_submit_url}\n"
            "Post-submit HTTP status: {post_submit_status}\n"
            "Visible page text after submission (max 2000 chars):\n{visible_text}\n\n"
            "Classify the form submission outcome."
        ),
    )

    generic_prompt = PromptTemplateDTO(
        id=str(uuid.uuid4()),
        service_type="nlp",
        task="generic",
        caller_module="*",
        maturity_level="*",
        version=1,
        system_prompt="You are an NLP assistant.",
        user_prompt_template="{query}{text}",
    )

    async def _get_prompt(service_type, task, caller_module, maturity_level):
        if task == "classify_probe_result":
            return classify_prompt
        elif task == "nl_to_sql":
            return nl_to_sql_prompt
        else:
            # Generic: user_prompt_template uses **payload, so accept any key
            # Generic tasks: intent_extraction uses {query}, others use {text}
            tpl = "{query}" if "intent" in task else "{text}"
            return PromptTemplateDTO(
                id=str(uuid.uuid4()),
                service_type=service_type,
                task=task,
                caller_module=caller_module,
                maturity_level=maturity_level,
                version=1,
                system_prompt="You are an NLP assistant.",
                user_prompt_template=tpl,
            )

    generation_prompt = PromptTemplateDTO(
        id=str(uuid.uuid4()),
        service_type="generation",
        task="generate_test_cases",
        caller_module="playwright_runner",
        maturity_level="L2",
        version=1,
        system_prompt="You are a test generation expert.",
        user_prompt_template="Generate test cases for: {url}",
    )

    inventory_prompt = PromptTemplateDTO(
        id=str(uuid.uuid4()),
        service_type="generation",
        task="generate_test_cases_with_inventory",
        caller_module="playwright_runner",
        maturity_level="L2",
        version=1,
        system_prompt="You are an inventory-based test generation expert.",
        user_prompt_template="Generate test cases for: {url}\nInventory: {locator_inventory_text}",
    )

    script_prompt = PromptTemplateDTO(
        id=str(uuid.uuid4()),
        service_type="generation",
        task="generate_playwright_script",
        caller_module="playwright_runner",
        maturity_level="L2",
        version=1,
        system_prompt="You generate Playwright scripts.",
        user_prompt_template="Generate script for: {url}\nTest cases:\n{test_cases_json}",
    )

    async def _get_prompt_variant(service_type, task, caller_module, maturity_level, ab_variant):
        if task == "generate_test_cases_with_inventory":
            return inventory_prompt
        elif task == "generate_playwright_script":
            return script_prompt
        elif task == "generate_test_cases":
            return generation_prompt
        return nl_to_sql_prompt

    with patch("app.registry.prompt_registry.get_prompt", side_effect=_get_prompt), \
         patch("app.registry.prompt_registry.get_prompt_variant", side_effect=_get_prompt_variant) as mock:
        yield mock
