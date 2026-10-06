"""Test script for FastAPI POST /check-company endpoint.

Sends requests for 5 companies (3 real, 2 fake) and prints a formatted
table comparing Risk Score, Risk Level, and Triggered Reasons.
"""

import os
import sys
from typing import Any, Dict, List
import requests

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000/check-company")

# Test dataset: 3 real companies, 2 made-up/fake companies
TEST_CASES: List[Dict[str, Any]] = [
    {
        "category": "REAL",
        "payload": {
            "company_name": "Tata Consultancy Services",
            "claimed_domain": "tcs.com",
            "gstin": "24AAACT2727Q1ZW",
        },
    },
    {
        "category": "REAL",
        "payload": {
            "company_name": "State Bank of India",
            "claimed_domain": "sbi.co.in",
            "gstin": "24AAACS8577K1ZV",
        },
    },
    {
        "category": "REAL",
        "payload": {
            "company_name": "Infosys Limited",
            "claimed_domain": "infosys.com",
        },
    },
    {
        "category": "FAKE",
        "payload": {
            "company_name": "QuickHire Global Solutions Tech",
            "claimed_domain": "quickhire-instant-jobs-999.xyz",
            "gstin": "99ABCDE1234F1Z5",
        },
    },
    {
        "category": "FAKE",
        "payload": {
            "company_name": "Apex Dream Careers International",
            "claimed_domain": "apexdreamcareers-online.top",
        },
    },
]


def format_cell(text: str, width: int) -> str:
    """Pad or truncate text to fit column width."""
    text = str(text)
    if len(text) > width:
        return text[: width - 3] + "..."
    return text.ljust(width)


def print_table(results: List[Dict[str, Any]]) -> None:
    """Print results in a clean aligned table."""
    col_cat = 6
    col_name = 34
    col_score = 11
    col_level = 11
    col_reasons = 52

    header = (
        f"| {format_cell('Type', col_cat)} "
        f"| {format_cell('Company Name', col_name)} "
        f"| {format_cell('Risk Score', col_score)} "
        f"| {format_cell('Risk Level', col_level)} "
        f"| {format_cell('Reasons', col_reasons)} |"
    )
    separator = (
        f"|{'-' * (col_cat + 2)}"
        f"|{'-' * (col_name + 2)}"
        f"|{'-' * (col_score + 2)}"
        f"|{'-' * (col_level + 2)}"
        f"|{'-' * (col_reasons + 2)}|"
    )

    print("\n" + separator)
    print(header)
    print(separator)

    for r in results:
        category = r.get("category", "")
        name = r.get("company_name", "")
        score = str(r.get("risk_score", "N/A"))
        level = r.get("risk_level", "N/A").upper()
        reasons_list = r.get("reasons", [])

        if not reasons_list:
            reasons_str = "None (No risk factors identified)"
        else:
            reasons_str = "; ".join(reasons_list)

        row = (
            f"| {format_cell(category, col_cat)} "
            f"| {format_cell(name, col_name)} "
            f"| {format_cell(score, col_score)} "
            f"| {format_cell(level, col_level)} "
            f"| {format_cell(reasons_str, col_reasons)} |"
        )
        print(row)

    print(separator + "\n")


def run_tests() -> None:
    print(f"Connecting to FastAPI endpoint: {API_URL}")
    print(f"Total test cases to execute: {len(TEST_CASES)}\n")

    results: List[Dict[str, Any]] = []

    for i, test in enumerate(TEST_CASES, 1):
        category = test["category"]
        payload = test["payload"]
        company_name = payload["company_name"]

        print(f"[{i}/{len(TEST_CASES)}] Testing [{category}] '{company_name}'...")

        try:
            response = requests.post(API_URL, json=payload, timeout=30)

            if response.status_code == 200:
                data = response.json()
                results.append(
                    {
                        "category": category,
                        "company_name": company_name,
                        "risk_score": data.get("risk_score", 0),
                        "risk_level": data.get("risk_level", "unknown"),
                        "reasons": data.get("reasons", []),
                    }
                )
                print(f"     Status: {response.status_code} OK -> Score: {data.get('risk_score')}, Level: {data.get('risk_level')}")
            else:
                print(f"     [FAILED] HTTP {response.status_code}: {response.text[:120]}")
                results.append(
                    {
                        "category": category,
                        "company_name": company_name,
                        "risk_score": "ERR",
                        "risk_level": f"HTTP {response.status_code}",
                        "reasons": [f"API error: HTTP {response.status_code}"],
                    }
                )

        except requests.exceptions.ConnectionError:
            print(f"\n[ERROR] Unable to connect to server at {API_URL}.")
            print("Please ensure the FastAPI server is running before running this script.")
            print("To start the server, open another terminal and run:")
            print("    python main.py")
            print("    # or: uvicorn app.main:app --port 8000\n")
            sys.exit(1)
        except requests.exceptions.Timeout:
            print(f"     [TIMEOUT] Request timed out for '{company_name}'")
            results.append(
                {
                    "category": category,
                    "company_name": company_name,
                    "risk_score": "TIMEOUT",
                    "risk_level": "ERROR",
                    "reasons": ["Request timed out after 30s"],
                }
            )
        except Exception as e:
            print(f"     [ERROR] Unexpected error: {str(e)}")
            results.append(
                {
                    "category": category,
                    "company_name": company_name,
                    "risk_score": "ERR",
                    "risk_level": "ERROR",
                    "reasons": [str(e)],
                }
            )

    print_table(results)


if __name__ == "__main__":
    run_tests()
