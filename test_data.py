import json
import random
from datetime import datetime, timedelta
from pathlib import Path


FIRST_NAMES = [
    "Milan", "Ana", "Nikola", "Jelena", "Marko",
    "Ivana", "Stefan", "Tamara", "Luka", "Marija"
]

LAST_NAMES = [
    "Jovanovic", "Petrovic", "Ilic", "Markovic", "Stojanovic",
    "Pavlovic", "Nikolic", "Djordjevic", "Simic", "Milosevic"
]

STREETS = [
    "Bulevar Kralja Aleksandra 155, Belgrade, Serbia",
    "Jurija Gagarina 42, New Belgrade, Serbia",
    "Cara Dusana 18, Novi Sad, Serbia",
    "Knez Mihailova 7, Belgrade, Serbia",
    "Bulevar Oslobodjenja 99, Novi Sad, Serbia"
]

CLAIM_TYPES = [
    "water_damage",
    "fire_damage",
    "theft",
    "storm_damage",
    "glass_breakage",
    "smoke_damage"
]

CAUSES = {
    "water_damage": [
        "sudden pipe burst",
        "washing machine hose failure",
        "overflow from upstairs apartment"
    ],
    "fire_damage": [
        "kitchen grease fire",
        "electrical short circuit",
        "space heater malfunction"
    ],
    "theft": [
        "forced entry through rear door",
        "balcony door break-in",
        "storage room burglary"
    ],
    "storm_damage": [
        "hail impact on roof",
        "wind-driven rain intrusion",
        "fallen tree branch"
    ],
    "glass_breakage": [
        "window broken during storm",
        "accidental impact",
        "vandalism"
    ],
    "smoke_damage": [
        "minor stove fire",
        "electrical appliance smoke event",
        "neighboring unit smoke migration"
    ]
}

STATUSES = [
    "new",
    "investigating",
    "pending_documents",
    "coverage_review",
    "paid",
    "partially_paid",
    "denied",
    "closed_no_payment",
    "reopened"
]

CHANNELS = ["phone", "email", "mobile_app", "broker_portal"]

ADJUSTERS = ["Ana Petrovic", "Nikola Ilic", "Jasmina Ristic", "Ivan Kovacevic"]

DOC_TYPE_MAP = {
    "water_damage": ["claim_form", "photo_set", "plumber_invoice", "adjuster_report"],
    "fire_damage": ["claim_form", "photo_set", "fire_report", "adjuster_report"],
    "theft": ["claim_form", "photo_set", "police_report", "contents_inventory"],
    "storm_damage": ["claim_form", "photo_set", "weather_report", "roofer_estimate"],
    "glass_breakage": ["claim_form", "photo_set", "repair_quote"],
    "smoke_damage": ["claim_form", "photo_set", "cleaning_estimate", "adjuster_report"]
}


def random_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def random_email(full_name: str) -> str:
    normalized = full_name.lower().replace(" ", ".")
    return f"{normalized}@example.com"


def random_phone() -> str:
    return f"+38164{random.randint(1000000, 9999999)}"


def random_date_range(start_days_ago=120, end_days_ago=5):
    today = datetime.utcnow().date()
    loss_date = today - timedelta(days=random.randint(end_days_ago, start_days_ago))
    reported_date = loss_date + timedelta(days=random.randint(0, 3))
    return loss_date.isoformat(), reported_date.isoformat()


def policy_for_claim():
    return {
        "product": random.choice(["Homeowners Basic", "Homeowners Plus", "Condo Protect"]),
        "effective_date": "2025-05-01",
        "expiration_date": "2026-05-01",
        "deductible_eur": random.choice([100, 150, 250, 500]),
        "coverage_limits": {
            "dwelling_eur": random.choice([80000, 120000, 150000]),
            "contents_eur": random.choice([20000, 35000, 50000]),
            "water_damage_eur": random.choice([5000, 10000, 15000]),
        },
        "endorsements": [
            "Accidental discharge or overflow of water",
            "Temporary repairs and emergency mitigation"
        ],
        "exclusions": [
            "Long-term seepage over 14 days",
            "Wear and tear",
            "Intentional damage",
            "Negligence after known damage"
        ]
    }


def make_documents(claim_type: str, reported_date: str):
    base_dt = datetime.fromisoformat(reported_date)
    docs = []
    for i, doc_type in enumerate(DOC_TYPE_MAP[claim_type], start=1):
        docs.append({
            "doc_id": f"DOC-{i:03d}",
            "doc_type": doc_type,
            "title": doc_type.replace("_", " ").title(),
            "created_at": (base_dt + timedelta(hours=i * 4)).isoformat() + "Z"
        })
    return docs


def make_adjuster_notes(claim_type: str, cause: str, status: str, reported_date: str):
    base_dt = datetime.fromisoformat(reported_date)
    notes = [
        {
            "timestamp": base_dt.isoformat() + "Z",
            "author": random.choice(ADJUSTERS),
            "note": f"Initial review completed. Cause of loss reported as {cause}."
        }
    ]

    if status in {"investigating", "coverage_review", "paid", "partially_paid", "denied", "closed_no_payment", "reopened"}:
        notes.append({
            "timestamp": (base_dt + timedelta(days=1, hours=4, minutes=15)).isoformat() + "Z",
            "author": random.choice(ADJUSTERS),
            "note": f"Inspection performed for {claim_type}. Photos and supporting documents reviewed."
        })

    if status == "denied":
        notes.append({
            "timestamp": (base_dt + timedelta(days=2, hours=7, minutes=30)).isoformat() + "Z",
            "author": random.choice(ADJUSTERS),
            "note": "Evidence suggests exclusion may apply due to wear and tear or long-term unresolved condition."
        })

    return notes


def make_coverage_review(status: str, claim_type: str, deductible: int):
    approved_repairs = random.randint(800, 6500)
    approved_contents = random.choice([0, 150, 300, 600, 1200])

    if status in {"paid", "partially_paid"}:
        decision = "covered"
        reasoning = f"Loss is consistent with covered {claim_type.replace('_', ' ')} event and supported by available documentation."
    elif status == "denied":
        decision = "not_covered"
        reasoning = "Claim falls within policy exclusions based on investigation findings."
        approved_repairs = 0
        approved_contents = 0
    else:
        decision = "pending"
        reasoning = "Coverage review is incomplete pending final documentation or investigation."

    return {
        "reviewed_by": random.choice(ADJUSTERS),
        "decision": decision,
        "reasoning": reasoning,
        "applied_deductible_eur": deductible if decision == "covered" else 0,
        "approved_repairs_eur": approved_repairs,
        "approved_contents_eur": approved_contents
    }


def make_resolution(status: str, coverage_review: dict, reported_date: str):
    gross = coverage_review["approved_repairs_eur"] + coverage_review["approved_contents_eur"]
    deductible = coverage_review["applied_deductible_eur"]
    net = max(gross - deductible, 0)
    base_dt = datetime.fromisoformat(reported_date)
    resolution_date = (base_dt + timedelta(days=4)).strftime("%Y-%m-%d")

    if status == "paid":
        return {
            "resolution_date": resolution_date,
            "outcome": "paid",
            "gross_settlement_eur": gross,
            "deductible_eur": deductible,
            "net_payment_eur": net,
            "payment_method": random.choice(["bank_transfer", "check"]),
            "customer_letter_summary": "Claim approved and payment issued after deductible."
        }

    if status == "partially_paid":
        partial_gross = max(gross // 2, deductible + 100)
        partial_net = partial_gross - deductible
        return {
            "resolution_date": resolution_date,
            "outcome": "partially_paid",
            "gross_settlement_eur": partial_gross,
            "deductible_eur": deductible,
            "net_payment_eur": partial_net,
            "payment_method": "bank_transfer",
            "customer_letter_summary": "Claim partially approved. Some claimed items were not covered or lacked support."
        }

    if status == "denied":
        return {
            "resolution_date": resolution_date,
            "outcome": "denied",
            "gross_settlement_eur": 0,
            "deductible_eur": 0,
            "net_payment_eur": 0,
            "payment_method": None,
            "customer_letter_summary": "Claim denied due to policy exclusions or insufficient evidence."
        }

    if status == "closed_no_payment":
        return {
            "resolution_date": resolution_date,
            "outcome": "closed_no_payment",
            "gross_settlement_eur": 0,
            "deductible_eur": 0,
            "net_payment_eur": 0,
            "payment_method": None,
            "customer_letter_summary": "Claim closed without payment because the insured withdrew or did not provide required documents."
        }

    return {
        "resolution_date": None,
        "outcome": "pending",
        "gross_settlement_eur": 0,
        "deductible_eur": 0,
        "net_payment_eur": 0,
        "payment_method": None,
        "customer_letter_summary": "Claim remains open."
    }


def make_questions(status: str):
    base_questions = [
        "What is the current claim status?",
        "What caused the loss?",
        "Which documents are attached?",
        "What is the deductible?",
        "Summarize the claim timeline."
    ]

    status_specific = {
        "paid": [
            "Why was the claim approved?",
            "How much was paid to the insured?",
            "How was the final payment calculated?"
        ],
        "partially_paid": [
            "Why was only part of the claim paid?",
            "Which damages were approved versus excluded?"
        ],
        "denied": [
            "Why was the claim denied?",
            "Which exclusion applied?",
            "What facts in the file support the denial?"
        ],
        "pending_documents": [
            "What documents are still missing?",
            "What is blocking resolution?"
        ],
        "investigating": [
            "What facts are still under investigation?",
            "Has the adjuster inspected the property yet?"
        ],
        "coverage_review": [
            "What policy provisions are relevant to the decision?",
            "Is there enough evidence to approve this claim?"
        ]
    }

    return base_questions + status_specific.get(status, ["What are the next steps on this claim?"])


def generate_claim(idx: int) -> dict:
    full_name = random_name()
    claim_type = random.choice(CLAIM_TYPES)
    cause = random.choice(CAUSES[claim_type])
    status = random.choice(STATUSES)
    loss_date, reported_date = random_date_range()
    policy = policy_for_claim()
    deductible = policy["deductible_eur"]

    claim = {
        "claim_id": f"CLM-2026-{idx:04d}",
        "policy_id": f"POL-{random.randint(100000, 999999)}",
        "status": status,
        "claim_type": claim_type,
        "loss_date": loss_date,
        "reported_date": reported_date,
        "insured": {
            "full_name": full_name,
            "email": random_email(full_name),
            "phone": random_phone(),
            "property_address": random.choice(STREETS)
        },
        "policy": policy,
        "claim_intake": {
            "reported_by": random.choice(["insured", "broker", "spouse"]),
            "channel": random.choice(CHANNELS),
            "summary": f"Reported {claim_type.replace('_', ' ')} caused by {cause}.",
            "cause_of_loss": cause,
            "initial_damage_estimate_eur": random.randint(500, 9000),
            "emergency_mitigation_completed": random.choice([True, False]),
            "injuries_reported": False
        },
        "documents": make_documents(claim_type, reported_date),
        "adjuster_notes": make_adjuster_notes(claim_type, cause, status, reported_date),
    }

    coverage_review = make_coverage_review(status, claim_type, deductible)
    resolution = make_resolution(status, coverage_review, reported_date)

    claim["coverage_review"] = coverage_review
    claim["resolution"] = resolution
    claim["conversation_seed_questions"] = make_questions(status)

    return claim


def export_claims_json(output_dir: str = "synthetic_claims", count: int = 10, seed: int = 42):
    random.seed(seed)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    for old_file in out_path.glob("CLM-*.json"):
        old_file.unlink()

    claims = []
    for i in range(1, count + 1):
        claim = generate_claim(i)
        claims.append(claim)

        file_path = out_path / f"{claim['claim_id']}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(claim, f, indent=2, ensure_ascii=False)

    return claims


if __name__ == "__main__":
    export_claims_json()
