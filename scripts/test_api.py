"""
ASP API Test Script
Tests all major service types against a running ASP instance.

Usage:
    python scripts/test_api.py --key asp-your-api-key-here
    python scripts/test_api.py --key asp-your-api-key-here --url http://localhost:8000
"""
import argparse
import json
import sys
import httpx

BASE_URL = "http://localhost:8000"
TENANT_ID = "default"


def print_header(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_result(resp: httpx.Response):
    if resp.status_code == 200:
        print(f"  ✅ Status : {resp.status_code}")
        data = resp.json()
        print(f"  Response : {json.dumps(data, indent=4)}")
    else:
        print(f"  ❌ Status : {resp.status_code}")
        print(f"  Error    : {resp.text}")


def run_tests(api_key: str, base_url: str):
    headers = {
        "X-ASP-Api-Key": api_key,
        "Content-Type": "application/json",
    }

    with httpx.Client(base_url=base_url, headers=headers, timeout=30) as client:

        # ── Health Check ──────────────────────────────────────────
        print_header("1. Health Check")
        resp = client.get("/api/v1/health")
        print_result(resp)

        # ── NLP: Intent Extraction ────────────────────────────────
        print_header("2. NLP — Intent Extraction")
        resp = client.post("/api/v1/ai/invoke", json={
            "service_type": "nlp",
            "task": "intent_extraction",
            "caller_module": "crm",
            "tenant_id": TENANT_ID,
            "quality_tier": "standard",
            "payload": {
                "text": "Show me all overdue invoices from last month"
            }
        })
        print_result(resp)

        # ── NLP: Sentiment ────────────────────────────────────────
        print_header("3. NLP — Sentiment Analysis")
        resp = client.post("/api/v1/ai/invoke", json={
            "service_type": "nlp",
            "task": "sentiment",
            "caller_module": "crm",
            "tenant_id": TENANT_ID,
            "quality_tier": "standard",
            "payload": {
                "text": "The delivery was extremely late and damaged. Very disappointed."
            }
        })
        print_result(resp)

        # ── NLP: Language Detection ───────────────────────────────
        print_header("4. NLP — Language Detection")
        resp = client.post("/api/v1/ai/invoke", json={
            "service_type": "nlp",
            "task": "language_detection",
            "caller_module": "crm",
            "tenant_id": TENANT_ID,
            "quality_tier": "standard",
            "payload": {
                "text": "Bonjour, je voudrais suivre ma commande"
            }
        })
        print_result(resp)

        # ── Generation: Draft Email ───────────────────────────────
        print_header("5. Generation — Draft Email")
        resp = client.post("/api/v1/ai/invoke", json={
            "service_type": "generation",
            "task": "draft_email",
            "caller_module": "crm",
            "tenant_id": TENANT_ID,
            "quality_tier": "enhanced",
            "payload": {
                "to_name": "John Smith",
                "subject_hint": "Invoice #1234 overdue",
                "tone": "professional but firm",
                "context_notes": "Invoice is 30 days overdue, amount $5,200"
            }
        })
        print_result(resp)

        # ── Generation: Summarise Customer ────────────────────────
        print_header("6. Generation — Summarise Customer")
        resp = client.post("/api/v1/ai/invoke", json={
            "service_type": "generation",
            "task": "summarise_customer",
            "caller_module": "crm",
            "tenant_id": TENANT_ID,
            "quality_tier": "standard",
            "payload": {
                "customer_data": "Acme Corp. 5 years client. Annual spend $120k. 3 overdue invoices. Primary contact: Jane Doe.",
                "focus_areas": "payment behaviour, risk"
            }
        })
        print_result(resp)

        # ── Dashboard Intelligence: Interpret Chart ───────────────
        print_header("7. Dashboard — Interpret Chart")
        resp = client.post("/api/v1/ai/invoke", json={
            "service_type": "dashboard_intelligence",
            "task": "interpret_chart",
            "caller_module": "dashboard",
            "tenant_id": TENANT_ID,
            "quality_tier": "standard",
            "payload": {
                "query": "Why did revenue drop in March?",
                "chart_context": "Monthly revenue: Jan=$120k, Feb=$135k, Mar=$89k, Apr=$142k",
                "dashboard_context": "Logistics CRM revenue dashboard"
            }
        })
        print_result(resp)

        # ── Cost Summary ──────────────────────────────────────────
        print_header("8. Cost — Usage Summary")
        resp = client.get("/api/v1/cost/summary")
        print_result(resp)

    print(f"\n{'=' * 60}")
    print("  Tests complete!")
    print(f"{'=' * 60}\n")
    print("  📖 Interactive docs: http://localhost:8000/docs")
    print("  📊 Celery monitor : http://localhost:5555\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test the ASP API")
    parser.add_argument("--key", required=True, help="API key (from create_tenant.py)")
    parser.add_argument("--url", default=BASE_URL, help="Base URL of the API")
    args = parser.parse_args()

    run_tests(api_key=args.key, base_url=args.url)
