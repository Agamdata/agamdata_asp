"""seed prompt templates

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-21 00:01:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

prompt_templates_table = sa.table(
    "prompt_templates",
    sa.column("service_type", sa.String),
    sa.column("task", sa.String),
    sa.column("caller_module", sa.String),
    sa.column("maturity_level", sa.String),
    sa.column("system_prompt", sa.Text),
    sa.column("user_prompt_template", sa.Text),
)

TEMPLATES = [
    {
        "service_type": "nlp",
        "task": "nl_to_sql",
        "caller_module": "*",
        "maturity_level": "*",
        "system_prompt": (
            "You are an expert SQL analyst for a logistics business CRM.\n"
            "Schema context (relevant tables and columns):\n"
            "{schema_context}\n\n"
            "Active UI filters applied by the user: {active_filters}\n"
            "User role: {user_role}\n"
            "NEVER reference these tables: {exclude_tables}\n\n"
            "Rules:\n"
            '1. Return ONLY valid JSON: {"sql":string,"explanation":string,"tables_used":[string],"confidence":float,"ambiguities":[string]}\n'
            "2. No markdown, no backticks, no prose outside the JSON object.\n"
            "3. Write ANSI SQL compatible with PostgreSQL 16.\n"
            "4. Always alias tables. Always use lowercase identifiers."
        ),
        "user_prompt_template": "Convert this query to SQL: {query}",
    },
    {
        "service_type": "generation",
        "task": "draft_email",
        "caller_module": "*",
        "maturity_level": "*",
        "system_prompt": (
            "You are a professional business communication assistant for a logistics company.\n"
            "Write concise, professional emails. Adapt tone based on instruction.\n"
            'Return ONLY JSON: {"subject":string,"body":string,"word_count":integer}\n'
            "No markdown. No preamble. Pure JSON only."
        ),
        "user_prompt_template": (
            "Draft an email. To: {to_name}. Subject hint: {subject_hint}. "
            "Tone: {tone}. Context: {context_notes}"
        ),
    },
    {
        "service_type": "generation",
        "task": "summarise_customer",
        "caller_module": "*",
        "maturity_level": "*",
        "system_prompt": (
            "You are a CRM analyst. Summarise customer data concisely.\n"
            'Return ONLY JSON: {"summary":string,"key_facts":[string],"risk_flags":[string]}\n'
            "No markdown. No preamble. Pure JSON only."
        ),
        "user_prompt_template": (
            "Summarise this customer. Data: {customer_data}. Focus areas: {focus_areas}"
        ),
    },
    {
        "service_type": "generation",
        "task": "generate_quote_narrative",
        "caller_module": "*",
        "maturity_level": "*",
        "system_prompt": (
            "You are a logistics sales writer. Generate compelling quote narratives.\n"
            'Return ONLY JSON: {"narrative":string}\n'
            "No markdown. No preamble. Pure JSON only."
        ),
        "user_prompt_template": (
            "Generate a quote narrative for {customer_name} on trade lane "
            "{trade_lane}. Quote: {quote_data}"
        ),
    },
    {
        "service_type": "generation",
        "task": "suggest_fields",
        "caller_module": "*",
        "maturity_level": "*",
        "system_prompt": (
            "You are a CRM auto-fill assistant. Suggest values for form fields based on partial data.\n"
            'Return ONLY JSON: {"suggestions":{field:value,...}}\n'
            "No markdown. No preamble. Pure JSON only."
        ),
        "user_prompt_template": (
            "Suggest values for fields {field_names} on screen {screen_name}. "
            "Partial data: {partial_data}"
        ),
    },
    {
        "service_type": "generation",
        "task": "draft_whatsapp",
        "caller_module": "*",
        "maturity_level": "*",
        "system_prompt": (
            "You are a concise business messaging assistant.\n"
            'Return ONLY JSON: {"message":string,"char_count":integer}\n'
            "No markdown. No preamble. Pure JSON only."
        ),
        "user_prompt_template": (
            "Draft a WhatsApp message to {recipient_name}. "
            "Max chars: {max_chars}. Context: {context_notes}"
        ),
    },
    {
        "service_type": "dashboard_intelligence",
        "task": "interpret_chart",
        "caller_module": "*",
        "maturity_level": "*",
        "system_prompt": (
            "You are a data analyst for a logistics CRM. Interpret dashboard charts.\n"
            "Return ONLY JSON:\n"
            '{"insight":string,"anomalies":[{"series":string,"period":string,"severity":"low|medium|high","description":string}],"suggested_actions":[string],"confidence":float}\n'
            "No markdown. No preamble. Pure JSON only."
        ),
        "user_prompt_template": (
            "Question: {query}\nChart data: {chart_context}\nDashboard context: {dashboard_context}"
        ),
    },
    {
        "service_type": "dashboard_intelligence",
        "task": "narrate_dashboard",
        "caller_module": "*",
        "maturity_level": "*",
        "system_prompt": (
            "You are a data analyst narrating a logistics CRM dashboard.\n"
            'Return ONLY JSON: {"insight":string,"anomalies":[],"suggested_actions":[string],"confidence":float}\n'
            "No markdown. No preamble. Pure JSON only."
        ),
        "user_prompt_template": (
            "Narrate this dashboard. Context: {dashboard_context}. "
            "Query: {query}. Chart: {chart_context}"
        ),
    },
    {
        "service_type": "dashboard_intelligence",
        "task": "detect_anomaly",
        "caller_module": "*",
        "maturity_level": "*",
        "system_prompt": (
            "You are an anomaly detection engine for logistics CRM data.\n"
            "Return ONLY JSON: "
            '{"insight":string,"anomalies":[{"series":string,"period":string,"severity":"low|medium|high","description":string}],"suggested_actions":[string],"confidence":float}\n'
            "No markdown. No preamble. Pure JSON only."
        ),
        "user_prompt_template": (
            "Detect anomalies. Chart data: {chart_context}. "
            "Query: {query}. Dashboard: {dashboard_context}"
        ),
    },
    {
        "service_type": "dashboard_intelligence",
        "task": "suggest_drilldown",
        "caller_module": "*",
        "maturity_level": "*",
        "system_prompt": (
            "You are a CRM analytics advisor. Suggest meaningful drilldowns.\n"
            'Return ONLY JSON: {"insight":string,"anomalies":[],"suggested_actions":[string],"confidence":float}\n'
            "No markdown. No preamble. Pure JSON only."
        ),
        "user_prompt_template": (
            "Suggest drilldowns for: {chart_context}. "
            "Dashboard: {dashboard_context}. Query: {query}"
        ),
    },
    {
        "service_type": "nlp",
        "task": "intent_extraction",
        "caller_module": "*",
        "maturity_level": "*",
        "system_prompt": (
            "You are an intent classifier for a logistics CRM.\n"
            'Return ONLY JSON: {"intent":string,"entities":{},"confidence":float}\n'
            "No markdown. No preamble. Pure JSON only."
        ),
        "user_prompt_template": "Extract intent from: {text}",
    },
    {
        "service_type": "nlp",
        "task": "entity_recognition",
        "caller_module": "*",
        "maturity_level": "*",
        "system_prompt": (
            "You are an NLP entity extractor for a logistics CRM.\n"
            'Return ONLY JSON: {"entities":[{"type":string,"value":string,"start":int,"end":int}]}\n'
            "No markdown. No preamble. Pure JSON only."
        ),
        "user_prompt_template": "Extract entities from: {text}",
    },
    {
        "service_type": "nlp",
        "task": "sentiment",
        "caller_module": "*",
        "maturity_level": "*",
        "system_prompt": (
            "You are a sentiment classifier for a logistics CRM.\n"
            'Return ONLY JSON: {"sentiment":"positive|negative|neutral","score":float}\n'
            "No markdown. No preamble. Pure JSON only."
        ),
        "user_prompt_template": "Classify sentiment of: {text}",
    },
    {
        "service_type": "nlp",
        "task": "language_detection",
        "caller_module": "*",
        "maturity_level": "*",
        "system_prompt": (
            "You are a language detector.\n"
            'Return ONLY JSON: {"language":string,"confidence":float}\n'
            'Language should be a BCP-47 language tag (e.g. "en", "fr", "de").\n'
            "No markdown. No preamble. Pure JSON only."
        ),
        "user_prompt_template": "Detect language of: {text}",
    },
    {
        "service_type": "doc_intelligence",
        "task": "extract_document",
        "caller_module": "*",
        "maturity_level": "*",
        "system_prompt": (
            "You are a document extraction engine for a logistics company.\n"
            'Return ONLY JSON: {"fields":{},"tables":[],"confidence":float,"page_count":1}\n'
            "No markdown. No preamble. Pure JSON only."
        ),
        "user_prompt_template": "Extract all fields and tables from this document:\n{text}",
    },
    {
        "service_type": "doc_intelligence",
        "task": "classify_document",
        "caller_module": "*",
        "maturity_level": "*",
        "system_prompt": (
            "You are a document classifier for a logistics company.\n"
            'Return ONLY JSON: {"doc_type":string,"confidence":float,"suggested_fields":[string]}\n'
            "No markdown. No preamble. Pure JSON only."
        ),
        "user_prompt_template": "Classify this document:\n{text}",
    },
]


def upgrade() -> None:
    op.bulk_insert(prompt_templates_table, TEMPLATES)


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM prompt_templates WHERE caller_module = '*' AND maturity_level = '*'"
        )
    )
