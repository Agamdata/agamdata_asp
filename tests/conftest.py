"""
Test configuration and fixtures.
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
    return "test-api-key-12345"


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
def mock_db_session(test_api_key_hash):
    """
    Mock database session that returns a valid tenant for auth.
    """
    from app.models.db_models import Tenant

    tenant = Tenant(
        id=uuid.uuid4(),
        tenant_code="test_tenant",
        name="Test Tenant",
        api_key_hash=test_api_key_hash,
        monthly_quota_usd=50.0,
        is_active=True,
    )

    session_mock = MagicMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [tenant]
    result_mock.scalar_one_or_none.return_value = tenant
    session_mock.execute = AsyncMock(return_value=result_mock)
    session_mock.add = MagicMock()
    session_mock.commit = AsyncMock()
    session_mock.__aenter__ = AsyncMock(return_value=session_mock)
    session_mock.__aexit__ = AsyncMock(return_value=False)
    return session_mock, tenant


@pytest.fixture(scope="module")
def client(test_api_key, mock_db_session, mock_redis):
    """FastAPI test client with mocked infra."""
    session_mock, tenant = mock_db_session

    # Patch at all locations where init_db/init_redis are referenced
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
    """TestClient with the API key header pre-set."""
    client.headers.update({"X-ASP-API-Key": test_api_key})
    return client


@pytest.fixture(scope="function")
def mock_anthropic():
    """Patch anthropic client to return a controlled response."""
    with patch("app.services._shared.anthropic_client") as mock_shared, \
         patch("app.services.nlp.anthropic_client", mock_shared):
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

    with patch("app.registry.prompt_registry.get_prompt", side_effect=_get_prompt), \
         patch("app.registry.prompt_registry.get_prompt_variant", new_callable=AsyncMock, return_value=nl_to_sql_prompt) as mock:
        yield mock
