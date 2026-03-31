import json
import random
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Reference data pools
# ---------------------------------------------------------------------------

FIRST_NAMES = [
    "Milan", "Ana", "Nikola", "Jelena", "Marko",
    "Ivana", "Stefan", "Tamara", "Luka", "Marija",
    "Petar", "Jovana", "Nemanja", "Milica", "Dragan",
    "Zorana", "Vladimir", "Teodora", "Aleksa", "Sofija",
]

LAST_NAMES = [
    "Jovanovic", "Petrovic", "Ilic", "Markovic", "Stojanovic",
    "Pavlovic", "Nikolic", "Djordjevic", "Simic", "Milosevic",
    "Todorovic", "Lazarevic", "Ristic", "Kovacevic", "Popovic",
]

STREETS = [
    "Bulevar Kralja Aleksandra 155, Belgrade, Serbia",
    "Jurija Gagarina 42, New Belgrade, Serbia",
    "Cara Dusana 18, Novi Sad, Serbia",
    "Knez Mihailova 7, Belgrade, Serbia",
    "Bulevar Oslobodjenja 99, Novi Sad, Serbia",
    "Vojvode Stepe 88, Belgrade, Serbia",
    "Maksima Gorkog 23, Novi Sad, Serbia",
    "Nemanjina 11, Belgrade, Serbia",
    "Branka Radicevica 5, Nis, Serbia",
    "Zmaj Jovina 14, Subotica, Serbia",
    "Obilicev Venac 3, Kragujevac, Serbia",
    "Svetozara Markovica 67, Cacak, Serbia",
]

CLAIM_TYPES = [
    "water_damage", "fire_damage", "theft",
    "storm_damage", "glass_breakage", "smoke_damage",
]

SYNT_IMAGES_DIR = Path(__file__).parent / "synt-images"

IMAGE_POOL: dict[str, list[str]] = {
    "fire_damage": [
        "fire-damage-after-the-fire-10.jpg",
        "fire-damage-kotlas-01.jpg",
        "fire-damage-national-photo-co.jpg",
    ],
    "smoke_damage": [
        "smoke-incense-india.jpg",
        "smoke-incense-sri-dalada.jpg",
        "smoke-photography-5.jpg",
    ],
    "glass_breakage": [
        "broken-glass-explosion.jpg",
        "broken-glass-light-fixture.jpg",
        "broken-glass-road.jpg",
    ],
    "storm_damage": [
        "broken-glass-explosion.jpg",
        "broken-glass-road.jpg",
        "fire-damage-after-the-fire-10.jpg",
    ],
    "water_damage": [
        "broken-glass-road.jpg",
        "fire-damage-after-the-fire-10.jpg",
        "smoke-photography-5.jpg",
    ],
    "theft": [
        "broken-glass-explosion.jpg",
        "fire-damage-national-photo-co.jpg",
        "broken-glass-light-fixture.jpg",
    ],
}

CAUSES = {
    "water_damage": [
        "sudden pipe burst", "washing machine hose failure",
        "overflow from upstairs apartment", "toilet supply line leak",
        "frozen pipe rupture after cold snap", "dishwasher drain blockage",
    ],
    "fire_damage": [
        "kitchen grease fire", "electrical short circuit",
        "space heater malfunction", "candle left unattended",
        "faulty wiring in attic", "overloaded power strip",
    ],
    "theft": [
        "forced entry through rear door", "balcony door break-in",
        "storage room burglary", "smashed ground-floor window",
        "lock picking while residents away", "garage break-in",
    ],
    "storm_damage": [
        "hail impact on roof", "wind-driven rain intrusion",
        "fallen tree branch", "lightning strike on chimney",
        "flash flood ground-level entry", "tornado debris impact",
    ],
    "glass_breakage": [
        "window broken during storm", "accidental impact",
        "vandalism", "thermal stress crack", "projectile from lawn mower",
    ],
    "smoke_damage": [
        "minor stove fire", "electrical appliance smoke event",
        "neighboring unit smoke migration", "fireplace backdraft",
        "HVAC system circulated smoke from garage",
    ],
}

STATUSES = [
    "new", "investigating", "pending_documents", "coverage_review",
    "paid", "partially_paid", "denied", "closed_no_payment", "reopened",
]

CHANNELS = ["phone", "email", "mobile_app", "broker_portal"]

ADJUSTERS = [
    "Ana Petrovic", "Nikola Ilic", "Jasmina Ristic", "Ivan Kovacevic",
    "Milos Stankovic", "Dragana Vucic", "Bojan Lazarevic", "Sanja Milutinovic",
    "Zoran Pantic", "Maja Obradovic", "Dejan Savic", "Ivana Filipovic",
]

DOC_TYPE_MAP = {
    "water_damage": ["claim_form", "photo_set", "plumber_invoice", "adjuster_report"],
    "fire_damage": ["claim_form", "photo_set", "fire_report", "adjuster_report"],
    "theft": ["claim_form", "photo_set", "police_report", "contents_inventory"],
    "storm_damage": ["claim_form", "photo_set", "weather_report", "roofer_estimate"],
    "glass_breakage": ["claim_form", "photo_set", "repair_quote"],
    "smoke_damage": ["claim_form", "photo_set", "cleaning_estimate", "adjuster_report"],
}

ALL_ENDORSEMENTS = [
    "Accidental discharge or overflow of water",
    "Temporary repairs and emergency mitigation",
    "Replacement cost on contents",
    "Extended replacement cost on dwelling",
    "Ordinance or law coverage",
    "Service line coverage",
    "Sewer and drain backup coverage",
    "Earthquake coverage rider",
    "Scheduled personal property",
    "Home business coverage",
    "Identity fraud expense coverage",
    "Equipment breakdown coverage",
    "Water damage from appliance leakage",
    "Inflation guard endorsement",
    "Green improvements coverage",
]

ALL_EXCLUSIONS = [
    "Long-term seepage over 14 days",
    "Wear and tear",
    "Intentional damage",
    "Negligence after known damage",
    "Earth movement / subsidence",
    "Government action or seizure",
    "Nuclear hazard",
    "Power failure originating off premises",
    "War or military action",
    "Mold exceeding 30-day discovery window",
    "Flood (requires separate flood policy)",
    "Vermin or pest infestation",
    "Faulty workmanship or materials",
    "Gradual deterioration",
]

# Realistic file naming patterns
DOC_FILENAME_TEMPLATES = {
    "claim_form": [
        "claim_form_signed.pdf", "CLM_intake_form.pdf",
        "scan_001.pdf", "form_20{yy}{mm}{dd}.pdf",
    ],
    "photo_set": [
        "IMG_20{yy}{mm}{dd}_{hh}{mi}{ss}.jpg",
        "photo_damage_{n}.jpg", "DSC_{n:05d}.JPG",
        "damage_overview.png", "IMG_{n}.jpeg",
    ],
    "plumber_invoice": [
        "plumber_receipt_{name}.pdf", "invoice_{n}.pdf",
        "hydraulic_estimate.pdf", "vodoinstalater_racun.pdf",
    ],
    "adjuster_report": [
        "adjuster_field_report.pdf", "inspection_report_final.pdf",
        "report_{date}.pdf", "AR_{claim_id}.pdf",
    ],
    "fire_report": [
        "fire_brigade_report.pdf", "vatrogasci_izvestaj.pdf",
        "MUP_fire_incident_{n}.pdf",
    ],
    "police_report": [
        "police_report_{n}.pdf", "MUP_krivicna_prijava.pdf",
        "theft_report_20{yy}.pdf",
    ],
    "contents_inventory": [
        "stolen_items_list.pdf", "contents_inventory.xlsx",
        "popis_stvari.pdf", "inventory_photo_set.zip",
    ],
    "weather_report": [
        "RHMZ_weather_bulletin.pdf", "storm_report_{date}.pdf",
        "meteo_data_extract.pdf",
    ],
    "roofer_estimate": [
        "roof_repair_estimate.pdf", "krovopokrivac_ponuda.pdf",
        "estimate_{name}_{n}.pdf",
    ],
    "repair_quote": [
        "glass_repair_quote.pdf", "staklar_ponuda.pdf",
        "repair_estimate_{n}.pdf",
    ],
    "cleaning_estimate": [
        "cleaning_quote.pdf", "smoke_remediation_estimate.pdf",
        "ciscenje_ponuda_{n}.pdf",
    ],
}

# Rich note templates per claim type
NOTE_TEMPLATES = {
    "water_damage": [
        "Initial review completed. Cause of loss reported as {cause}.",
        "Contacted plumber who confirmed {cause}. Leak has been stopped.",
        "Spoke with upstairs neighbor {neighbor} who confirmed overflow incident on {date}.",
        "Water stain measurements: ceiling 2.1m x 1.4m, wall damage extends 0.8m from corner.",
        "Drying equipment deployed by ServPro. Moisture readings taken — subfloor at {moisture}% RH.",
        "Reviewed plumber's invoice. Labor 4hrs at 45 EUR/hr plus materials 120 EUR.",
        "Second site visit. Mold test negative. Drywall replacement needed in hallway.",
        "Insured reports residual musty smell. Recommended air quality test.",
        "Obtained estimate from contractor Petrovic & Sons: 2,850 EUR for full repair.",
        "Cross-referenced policy endorsement re: accidental discharge. Applies here.",
    ],
    "fire_damage": [
        "Initial review completed. Cause of loss reported as {cause}.",
        "Fire brigade report obtained. Incident classified as accidental, origin in kitchen.",
        "Smoke damage visible in adjacent rooms. Soot deposits on ceiling, walls, and furniture.",
        "Structural engineer assessment requested for load-bearing wall near fire origin.",
        "Insured displaced to hotel. Temporary living expenses authorized up to 1,500 EUR.",
        "Electrical panel inspection reveals {cause} originated at junction box B3.",
        "Contents inventory received. 47 items listed, total claimed value 8,200 EUR.",
        "Appliance replacement quotes obtained: range 650 EUR, microwave 180 EUR.",
        "Remediation company estimates 3-week timeline for full restoration.",
        "Final walkthrough completed. All repairs verified satisfactory.",
    ],
    "theft": [
        "Initial review completed. Cause of loss reported as {cause}.",
        "Police report number: {police_ref}. Investigation ongoing.",
        "Insured provided list of stolen items with purchase receipts for 60% of items.",
        "Locksmith invoice: 280 EUR for emergency door replacement. Receipts verified.",
        "Neighbor {neighbor} confirmed seeing unfamiliar van parked outside on incident date.",
        "Security camera footage from building entrance reviewed — poor quality, inconclusive.",
        "Serial numbers for electronics cross-referenced with purchase records.",
        "Several claimed items exceed depreciation threshold. Applied actual cash value.",
        "No signs of forced entry on secondary inspection — checking if lock was picked.",
        "Insured cooperating fully. All requested documentation provided within 48hrs.",
    ],
    "storm_damage": [
        "Initial review completed. Cause of loss reported as {cause}.",
        "RHMZ weather data confirms wind speeds of {wind_speed} km/h on date of loss.",
        "Roof inspection by drone. {tile_count} tiles displaced, flashing damaged at chimney.",
        "Temporary tarp installed by emergency crew. Cost 320 EUR — covered under emergency mitigation.",
        "Interior water stains from roof breach measured: 3.2 sqm ceiling, 1.8 sqm wall.",
        "Obtained two independent roofing estimates: 4,200 EUR and 3,800 EUR.",
        "Tree service removed fallen branch. Invoice: 450 EUR. Branch originated from neighbor property.",
        "Subrogation potential against neighbor's homeowner policy for tree damage — flagged.",
        "Guttering destroyed along north face. 12 linear meters need replacement.",
        "All emergency repairs completed. Permanent repairs scheduled for next week.",
    ],
    "glass_breakage": [
        "Initial review completed. Cause of loss reported as {cause}.",
        "Window measurements taken: {width}cm x {height}cm, double-glazed unit.",
        "Temporary board-up completed by insured. Reimbursement: 85 EUR.",
        "Glass replacement quote from Staklo Plus: {amount} EUR installed.",
        "Vandalism reported to police. Reference: {police_ref}.",
        "Window type is custom thermal — lead time 2 weeks for replacement.",
    ],
    "smoke_damage": [
        "Initial review completed. Cause of loss reported as {cause}.",
        "Air quality test conducted. Particulate levels elevated in living room and bedroom.",
        "Soft contents (curtains, upholstery) require professional cleaning or replacement.",
        "HVAC ducts inspected — smoke residue detected. Full duct cleaning recommended.",
        "Ozone treatment quote from CleanAir doo: 680 EUR for 3-room treatment.",
        "Insured's clothing sent for smoke odor removal. 23 items, estimated cost 340 EUR.",
        "Repainted living room ceiling and walls. Primer + 2 coats to seal smoke residue.",
        "Electronics inspection: TV and laptop show no smoke infiltration damage.",
    ],
}

COVERAGE_REASONING_TEMPLATES = {
    "covered": [
        "Loss is consistent with covered {type} event and supported by available documentation.",
        "After review of policy terms, the reported {type} falls within standard covered perils. Documentation supports the claim.",
        "Investigation confirms sudden and accidental {cause}. No exclusions apply. Recommend approval.",
        "Field inspection and supporting documents substantiate the claimed damages. Coverage confirmed under Section II.",
    ],
    "not_covered": [
        "Claim falls within policy exclusions based on investigation findings.",
        "Investigation reveals pre-existing condition consistent with gradual deterioration, excluded under policy Section I.B.3.",
        "Evidence indicates {cause} resulted from long-term neglect. Exclusion for wear and tear applies.",
        "Damage timeline exceeds the 14-day discovery window per seepage exclusion. Denial recommended.",
    ],
    "pending": [
        "Coverage review is incomplete pending final documentation or investigation.",
        "Awaiting engineer's structural assessment before coverage determination can be finalized.",
        "Additional documentation requested from insured. Decision deferred until receipt.",
        "Subrogation potential being evaluated. Coverage decision on hold pending legal review.",
    ],
}

CUSTOMER_LETTER_TEMPLATES = {
    "paid": [
        "Claim approved and payment issued after deductible.",
        "Your claim has been approved. The net settlement of {net} EUR has been transferred to your bank account.",
        "We are pleased to inform you that your {type} claim has been resolved. Payment details are enclosed.",
    ],
    "partially_paid": [
        "Claim partially approved. Some claimed items were not covered or lacked support.",
        "After careful review, we have approved a portion of your claim. Items without supporting documentation have been excluded.",
        "Your claim has been partially settled. The approved amount reflects covered damages less your deductible.",
    ],
    "denied": [
        "Claim denied due to policy exclusions or insufficient evidence.",
        "After thorough investigation, your claim has been denied. The reported damages fall under policy exclusion Section I.B.",
        "We regret to inform you that your claim cannot be approved. Please see the enclosed explanation of our decision.",
    ],
    "closed_no_payment": [
        "Claim closed without payment because the insured withdrew or did not provide required documents.",
        "This claim has been closed as the required supporting documentation was not received within the specified timeframe.",
    ],
    "pending": [
        "Claim remains open.",
        "Your claim is currently under review. We will contact you if additional information is needed.",
    ],
}

INTAKE_NARRATIVE_TEMPLATES = [
    "The insured called on {reported_date} to report {cause} at their property located at {address}. "
    "They described hearing a loud noise around {time} and discovering {damage_desc}. "
    "The insured stated they contacted {responder} immediately.",

    "Claim reported via {channel} on {reported_date}. The insured, {name}, stated that on {loss_date} "
    "they noticed {damage_desc} in their {room}. Cause appears to be {cause}. "
    "No injuries reported. The insured has already obtained a preliminary repair estimate.",

    "Broker {broker_name} filed this claim on behalf of the insured. The incident occurred on {loss_date} "
    "at {address}. The insured discovered {damage_desc} upon returning home from work. "
    "Emergency services were {called_or_not}. Initial damage estimate provided by the insured: {estimate} EUR.",

    "The insured reported {cause} via the mobile app at {time} on {reported_date}. "
    "Damage description: {damage_desc}. The insured has taken photos and temporary measures to prevent further damage. "
    "They are requesting an adjuster visit as soon as possible.",

    "Phone intake recorded by operator. The insured was visibly upset and described {cause} at {address}. "
    "The incident happened {days_ago} days ago but the insured only noticed the full extent today. "
    "Multiple rooms affected. The insured mentioned {damage_desc}.",
]

DAMAGE_DESCRIPTIONS = {
    "water_damage": [
        "extensive water pooling on the kitchen floor and hallway",
        "ceiling bubbling with water dripping through light fixtures",
        "warped laminate flooring in two rooms and damp drywall",
        "a steady stream of water coming from the bathroom ceiling",
        "discolored walls and a strong musty smell in the bedroom",
    ],
    "fire_damage": [
        "charred kitchen cabinets and melted countertop surface",
        "blackened walls in the living room with heavy soot throughout",
        "complete destruction of the laundry area and smoke in all rooms",
        "fire damage limited to one room but smoke odor permeating the flat",
        "melted electrical outlets and scorched paint on adjacent walls",
    ],
    "theft": [
        "a ransacked apartment with drawers emptied and closets opened",
        "missing electronics and jewelry from the bedroom safe",
        "the rear door was pried open and the lock mechanism destroyed",
        "missing laptop, tablet, and approximately 500 EUR in cash",
        "storage unit lock cut and bicycle plus power tools stolen",
    ],
    "storm_damage": [
        "roof tiles scattered in the yard and water entering the attic",
        "a large tree branch through the living room window",
        "displaced gutter along the entire north side of the house",
        "shattered skylights and water damage to the top floor",
        "fence panels blown down and garden shed partially collapsed",
    ],
    "glass_breakage": [
        "a shattered double-pane window in the living room",
        "cracked glass door panel on the balcony entrance",
        "broken storefront window approximately 2m x 1.5m",
        "thermal crack running diagonally across the bathroom window",
        "multiple window panes broken on the ground floor",
    ],
    "smoke_damage": [
        "heavy smoke residue on ceilings and walls in three rooms",
        "smoke-saturated soft furnishings and curtains throughout",
        "soot deposits on kitchen surfaces and inside cabinets",
        "a persistent smoke odor despite ventilation for several days",
        "discolored ceiling paint and smoke-damaged electronics",
    ],
}

WITNESS_TEMPLATES = [
    "{name}, a neighbor from flat {flat}, stated they heard a loud noise at approximately {time} "
    "and noticed {observation}.",
    "Building superintendent {name} confirmed that {observation}. They were first on scene and "
    "contacted emergency services.",
    "{name} (spouse of insured) was home at the time and described the sequence of events: {observation}.",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def random_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def random_email(full_name: str) -> str:
    normalized = full_name.lower().replace(" ", ".")
    domain = random.choice(["example.com", "gmail.com", "yahoo.rs", "mail.rs"])
    return f"{normalized}@{domain}"


def random_phone() -> str:
    prefix = random.choice(["60", "61", "62", "63", "64", "65", "66", "69"])
    return f"+381{prefix}{random.randint(1000000, 9999999)}"


def random_date_range(start_days_ago=180, end_days_ago=5):
    today = datetime.now(tz=None).date()
    loss_date = today - timedelta(days=random.randint(end_days_ago, start_days_ago))
    reported_date = loss_date + timedelta(days=random.randint(0, 5))
    return loss_date.isoformat(), reported_date.isoformat()


def random_time_str():
    return f"{random.randint(6, 22):02d}:{random.randint(0, 59):02d}"


def pick_completeness():
    """Return completeness level: how much data stays in the top-level JSON."""
    roll = random.random()
    if roll < 0.20:
        return "easy"   # 80-100% fields present
    elif roll < 0.70:
        return "medium"  # 40-70% fields present
    else:
        return "hard"    # 20-40% fields present


def resolve_filename_template(tmpl: str, claim_id: str, reported_date: str) -> str:
    """Fill placeholders in a filename template with realistic values."""
    dt = datetime.fromisoformat(reported_date)
    result = tmpl
    result = result.replace("{yy}", f"{dt.year % 100:02d}")
    result = result.replace("{mm}", f"{dt.month:02d}")
    result = result.replace("{dd}", f"{dt.day:02d}")
    result = result.replace("{hh}", f"{random.randint(6, 22):02d}")
    result = result.replace("{mi}", f"{random.randint(0, 59):02d}")
    result = result.replace("{ss}", f"{random.randint(0, 59):02d}")
    result = result.replace("{n:05d}", f"{random.randint(1000, 99999):05d}")
    result = result.replace("{n}", str(random.randint(1, 999)))
    result = result.replace("{name}", random.choice(LAST_NAMES).lower())
    result = result.replace("{date}", dt.strftime("%Y%m%d"))
    result = result.replace("{claim_id}", claim_id)
    result = result.replace("{amount}", str(random.randint(200, 5000)))
    return result


# ---------------------------------------------------------------------------
# Policy generation — with variety
# ---------------------------------------------------------------------------

def policy_for_claim():
    eff_year = random.choice([2024, 2025, 2026])
    eff_month = random.randint(1, 12)
    effective = f"{eff_year}-{eff_month:02d}-01"
    exp_year = eff_year + 1
    expiration = f"{exp_year}-{eff_month:02d}-01"

    n_endorsements = random.randint(1, 5)
    n_exclusions = random.randint(2, 6)

    return {
        "product": random.choice(["Homeowners Basic", "Homeowners Plus", "Condo Protect"]),
        "effective_date": effective,
        "expiration_date": expiration,
        "deductible_eur": random.choice([100, 150, 200, 250, 300, 500, 750, 1000]),
        "coverage_limits": {
            "dwelling_eur": random.choice([60000, 80000, 100000, 120000, 150000, 200000]),
            "contents_eur": random.choice([15000, 20000, 30000, 35000, 50000]),
            "water_damage_eur": random.choice([3000, 5000, 7500, 10000, 15000]),
        },
        "endorsements": random.sample(ALL_ENDORSEMENTS, n_endorsements),
        "exclusions": random.sample(ALL_EXCLUSIONS, n_exclusions),
    }


# ---------------------------------------------------------------------------
# Document generation — realistic filenames & file_path
# ---------------------------------------------------------------------------

def make_documents(claim_id: str, claim_type: str, reported_date: str, completeness: str):
    base_dt = datetime.fromisoformat(reported_date)
    all_doc_types = DOC_TYPE_MAP[claim_type]

    if completeness == "hard":
        doc_types = random.sample(all_doc_types, k=max(1, len(all_doc_types) // 2))
    elif completeness == "medium":
        doc_types = random.sample(all_doc_types, k=max(2, len(all_doc_types) - 1))
    else:
        doc_types = list(all_doc_types)

    docs = []
    data_path = f"{claim_id}-data/data"
    for i, doc_type in enumerate(doc_types, start=1):
        templates = DOC_FILENAME_TEMPLATES.get(doc_type, [f"{doc_type}.pdf"])
        filename = resolve_filename_template(
            random.choice(templates), claim_id, reported_date
        )
        offset_hours = random.randint(i * 2, i * 8)
        doc = {
            "doc_id": f"DOC-{i:03d}",
            "doc_type": doc_type,
            "title": filename,
            "created_at": (base_dt + timedelta(hours=offset_hours)).isoformat() + "Z",
            "file_path": f"{data_path}/{filename}",
        }
        docs.append(doc)
    return docs


# ---------------------------------------------------------------------------
# Adjuster notes — richer templates
# ---------------------------------------------------------------------------

def make_adjuster_notes(claim_type: str, cause: str, status: str, reported_date: str,
                        completeness: str):
    base_dt = datetime.fromisoformat(reported_date)
    templates = NOTE_TEMPLATES.get(claim_type, NOTE_TEMPLATES["water_damage"])

    if completeness == "hard":
        n_notes = random.randint(0, 1)
    elif completeness == "medium":
        n_notes = random.randint(1, 3)
    else:
        n_notes = random.randint(2, 5)

    if n_notes == 0:
        return None

    selected = random.sample(templates, k=min(n_notes, len(templates)))
    notes = []
    for i, tmpl in enumerate(selected):
        ts = base_dt + timedelta(days=i, hours=random.randint(8, 18),
                                 minutes=random.randint(0, 59))
        text = tmpl.format(
            cause=cause,
            type=claim_type.replace("_", " "),
            neighbor=random_name(),
            date=(base_dt - timedelta(days=random.randint(0, 2))).isoformat(),
            moisture=random.randint(55, 95),
            police_ref=f"PU-{random.randint(1000, 9999)}-{random.randint(2025, 2026)}",
            wind_speed=random.randint(60, 140),
            tile_count=random.randint(5, 30),
            width=random.choice([60, 80, 100, 120, 140]),
            height=random.choice([80, 100, 120, 140, 160]),
            amount=random.randint(200, 3000),
        )
        notes.append({
            "timestamp": ts.isoformat() + "Z",
            "author": random.choice(ADJUSTERS),
            "note": text,
        })

    return notes


# ---------------------------------------------------------------------------
# Coverage review
# ---------------------------------------------------------------------------

def make_coverage_review(status: str, claim_type: str, cause: str, deductible: int,
                         completeness: str):
    approved_repairs = random.randint(500, 8000)
    approved_contents = random.choice([0, 0, 150, 300, 600, 1200, 2500])

    if status in {"paid", "partially_paid"}:
        decision = "covered"
        templates = COVERAGE_REASONING_TEMPLATES["covered"]
    elif status == "denied":
        decision = "not_covered"
        templates = COVERAGE_REASONING_TEMPLATES["not_covered"]
        approved_repairs = 0
        approved_contents = 0
    else:
        decision = "pending"
        templates = COVERAGE_REASONING_TEMPLATES["pending"]

    reasoning_text = random.choice(templates).format(
        type=claim_type.replace("_", " "),
        cause=cause,
    )

    review = {
        "reviewed_by": random.choice(ADJUSTERS),
        "decision": decision,
        "applied_deductible_eur": deductible if decision == "covered" else 0,
        "approved_repairs_eur": approved_repairs,
        "approved_contents_eur": approved_contents,
    }

    if completeness != "hard":
        review["reasoning"] = reasoning_text

    return review


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def make_resolution(status: str, coverage_review: dict, reported_date: str,
                    claim_type: str, completeness: str):
    gross = coverage_review["approved_repairs_eur"] + coverage_review["approved_contents_eur"]
    deductible = coverage_review["applied_deductible_eur"]
    net = max(gross - deductible, 0)
    base_dt = datetime.fromisoformat(reported_date)
    resolution_days = random.randint(3, 14)
    resolution_date = (base_dt + timedelta(days=resolution_days)).strftime("%Y-%m-%d")

    outcome_map = {
        "paid": "paid",
        "partially_paid": "partially_paid",
        "denied": "denied",
        "closed_no_payment": "closed_no_payment",
    }
    outcome = outcome_map.get(status, "pending")

    if outcome == "partially_paid":
        partial_gross = max(gross // 2, deductible + 100)
        net = partial_gross - deductible
        gross = partial_gross

    if outcome in {"denied", "closed_no_payment", "pending"}:
        gross = 0
        deductible = 0
        net = 0

    letter_templates = CUSTOMER_LETTER_TEMPLATES.get(outcome, CUSTOMER_LETTER_TEMPLATES["pending"])

    result = {
        "resolution_date": resolution_date if outcome != "pending" else None,
        "outcome": outcome,
        "gross_settlement_eur": gross,
        "deductible_eur": deductible,
        "net_payment_eur": net,
        "payment_method": random.choice(["bank_transfer", "check"]) if outcome in {"paid", "partially_paid"} else None,
    }

    if completeness != "hard":
        result["customer_letter_summary"] = random.choice(letter_templates).format(
            net=net, type=claim_type.replace("_", " "),
        )

    return result


# ---------------------------------------------------------------------------
# Conversation seed questions
# ---------------------------------------------------------------------------

def make_questions(status: str):
    base_questions = [
        "What is the current claim status?",
        "What caused the loss?",
        "Which documents are attached?",
        "What is the deductible?",
        "Summarize the claim timeline.",
    ]

    status_specific = {
        "paid": [
            "Why was the claim approved?",
            "How much was paid to the insured?",
            "How was the final payment calculated?",
        ],
        "partially_paid": [
            "Why was only part of the claim paid?",
            "Which damages were approved versus excluded?",
        ],
        "denied": [
            "Why was the claim denied?",
            "Which exclusion applied?",
            "What facts in the file support the denial?",
        ],
        "pending_documents": [
            "What documents are still missing?",
            "What is blocking resolution?",
        ],
        "investigating": [
            "What facts are still under investigation?",
            "Has the adjuster inspected the property yet?",
        ],
        "coverage_review": [
            "What policy provisions are relevant to the decision?",
            "Is there enough evidence to approve this claim?",
        ],
    }

    extras = status_specific.get(status, ["What are the next steps on this claim?"])
    n = random.randint(2, len(base_questions))
    return random.sample(base_questions, n) + extras


# ---------------------------------------------------------------------------
# Claim intake
# ---------------------------------------------------------------------------

def make_claim_intake(claim_type: str, cause: str, completeness: str):
    intake = {
        "reported_by": random.choice(["insured", "broker", "spouse"]),
        "channel": random.choice(CHANNELS),
        "summary": f"Reported {claim_type.replace('_', ' ')} caused by {cause}.",
        "cause_of_loss": cause,
        "injuries_reported": random.choices([False, True], weights=[0.92, 0.08])[0],
    }

    if completeness != "hard":
        intake["initial_damage_estimate_eur"] = random.randint(300, 12000)
        intake["emergency_mitigation_completed"] = random.choice([True, False])
    else:
        if random.random() > 0.5:
            intake["initial_damage_estimate_eur"] = random.randint(300, 12000)

    return intake


# ============================================================================
# Companion data folder generation
# ============================================================================

def _gen_companion_adjuster_notes(claim_type: str, cause: str, status: str,
                                  reported_date: str, insured_name: str):
    """Generate a verbose adjuster_notes.json for the companion data folder."""
    base_dt = datetime.fromisoformat(reported_date)
    templates = NOTE_TEMPLATES.get(claim_type, NOTE_TEMPLATES["water_damage"])
    n_notes = random.randint(4, 12)
    selected = (templates * 3)[:n_notes]
    random.shuffle(selected)
    selected = selected[:n_notes]

    notes = []
    for i, tmpl in enumerate(selected):
        days_offset = i * random.choice([0, 1, 1, 2])
        ts = base_dt + timedelta(days=days_offset, hours=random.randint(7, 20),
                                 minutes=random.randint(0, 59))
        text = tmpl.format(
            cause=cause,
            type=claim_type.replace("_", " "),
            neighbor=random_name(),
            date=(base_dt - timedelta(days=random.randint(0, 3))).isoformat(),
            moisture=random.randint(55, 95),
            police_ref=f"PU-{random.randint(1000, 9999)}-{random.randint(2025, 2026)}",
            wind_speed=random.randint(60, 140),
            tile_count=random.randint(5, 30),
            width=random.choice([60, 80, 100, 120, 140]),
            height=random.choice([80, 100, 120, 140, 160]),
            amount=random.randint(200, 3000),
        )
        entry = {
            "author": random.choice(ADJUSTERS),
            "note": text,
        }
        if random.random() > 0.15:
            entry["timestamp"] = ts.isoformat() + "Z"
        if random.random() > 0.7:
            entry["internal_flag"] = random.choice(["urgent", "follow-up", "escalate", "routine"])
        notes.append(entry)

    return {"claim_adjuster_notes": notes, "total_entries": len(notes)}


def _gen_companion_documents(claim_id: str, claim_type: str, reported_date: str):
    """Generate a verbose documents.json for the companion data folder."""
    all_doc_types = DOC_TYPE_MAP[claim_type]
    extra_types = random.sample(
        ["photo_set", "photo_set", "adjuster_report"],
        k=random.randint(0, 2),
    )
    doc_types = all_doc_types + extra_types
    data_path = f"{claim_id}-data/data"

    docs = []
    for i, doc_type in enumerate(doc_types, start=1):
        templates = DOC_FILENAME_TEMPLATES.get(doc_type, [f"{doc_type}.pdf"])
        filename = resolve_filename_template(
            random.choice(templates), claim_id, reported_date
        )
        ext = filename.rsplit(".", 1)[-1].lower()
        file_type_map = {"pdf": "pdf", "jpg": "jpg", "jpeg": "jpeg", "png": "png",
                         "xlsx": "xlsx", "zip": "zip"}
        entry = {
            "file_path": f"{data_path}/{filename}",
            "file_type": file_type_map.get(ext, "pdf"),
            "doc_type": doc_type,
            "description": random.choice([
                filename,
                f"{doc_type.replace('_', ' ').title()} — uploaded by adjuster",
                f"Scanned document received via email on {reported_date}",
                "Photo taken on site during inspection",
                "",
            ]),
            "uploaded_by": random.choice(ADJUSTERS + ["insured", "broker", "system"]),
        }
        if random.random() > 0.3:
            entry["file_size_kb"] = random.randint(50, 8000)
        docs.append(entry)

    return {"documents": docs, "count": len(docs)}


def _gen_companion_coverage(claim_type: str, cause: str, status: str, policy: dict):
    """Generate a verbose coverage_details.json for the companion data folder."""
    decision = "covered" if status in {"paid", "partially_paid"} else (
        "not_covered" if status == "denied" else "pending"
    )

    paragraphs = [
        f"Coverage analysis for {claim_type.replace('_', ' ')} claim. "
        f"The reported cause of loss is: {cause}.",

        f"Policy product: {policy['product']}. Effective {policy['effective_date']} to "
        f"{policy['expiration_date']}. Deductible: {policy['deductible_eur']} EUR.",

        f"Applicable endorsements: {', '.join(policy['endorsements'][:3])}.",

        f"Relevant exclusions reviewed: {', '.join(policy['exclusions'][:3])}.",
    ]

    if decision == "covered":
        paragraphs.append(
            "After thorough review of the claim file, supporting documentation, and field "
            "inspection findings, the loss is determined to be a covered peril under the policy. "
            "No applicable exclusions identified."
        )
    elif decision == "not_covered":
        paragraphs.append(
            "The investigation findings indicate that the reported damage falls within one or "
            "more policy exclusions. Specifically, the evidence suggests pre-existing conditions "
            "or gradual deterioration that is expressly excluded."
        )
    else:
        paragraphs.append(
            "Coverage determination is pending. Additional documentation has been requested from "
            "the insured. The claim file will be reviewed again upon receipt."
        )

    n_items = random.randint(3, 8)
    damage_items = []
    for j in range(n_items):
        damage_items.append({
            "item": f"Damage item {j + 1}: {random.choice(['ceiling repair', 'wall patching', 'floor replacement', 'appliance', 'furniture', 'electronics', 'plumbing fix', 'electrical work', 'window replacement', 'roof tiles'])}",
            "estimated_cost_eur": random.randint(50, 3000),
            "approved": random.choice([True, True, True, False]) if decision == "covered" else False,
        })

    return {
        "analysis_narrative": "\n\n".join(paragraphs),
        "decision": decision,
        "reviewed_by": random.choice(ADJUSTERS),
        "damage_assessment": damage_items,
    }


def _gen_companion_financials(status: str, coverage_review: dict, policy: dict):
    """Generate a verbose financials.json for the companion data folder."""
    n_items = random.randint(4, 15)
    line_items = []
    total = 0
    categories = ["structural", "contents", "labor", "materials", "emergency",
                   "temporary_housing", "cleaning", "inspection_fees"]

    for j in range(n_items):
        amount = random.randint(30, 4000)
        total += amount
        source = random.choice(["adjuster_estimate", "contractor_quote",
                                "insured_receipt", "vendor_invoice"])
        line_items.append({
            "description": f"Line item {j + 1}",
            "category": random.choice(categories),
            "amount_eur": amount,
            "source": source,
        })

    adjuster_total = sum(li["amount_eur"] for li in line_items if li["source"] == "adjuster_estimate")
    contractor_total = sum(li["amount_eur"] for li in line_items if li["source"] == "contractor_quote")

    return {
        "line_items": line_items,
        "total_claimed_eur": total,
        "adjuster_estimate_total_eur": adjuster_total,
        "contractor_estimate_total_eur": contractor_total,
        "approved_gross_eur": coverage_review.get("approved_repairs_eur", 0) +
                              coverage_review.get("approved_contents_eur", 0),
        "deductible_applied_eur": coverage_review.get("applied_deductible_eur", 0),
        "policy_deductible_eur": policy["deductible_eur"],
    }


def _gen_companion_intake(claim_type: str, cause: str, reported_date: str,
                          loss_date: str, insured: dict, channel: str):
    """Generate a verbose intake_report.json for the companion data folder."""
    address = insured["property_address"]
    name = insured["full_name"]
    time_str = random_time_str()

    damage_desc = random.choice(DAMAGE_DESCRIPTIONS.get(claim_type, ["visible damage to the property"]))

    narrative = random.choice(INTAKE_NARRATIVE_TEMPLATES).format(
        reported_date=reported_date,
        loss_date=loss_date,
        cause=cause,
        address=address,
        name=name,
        time=time_str,
        damage_desc=damage_desc,
        channel=channel,
        room=random.choice(["kitchen", "living room", "bedroom", "bathroom", "hallway", "attic"]),
        broker_name=random_name(),
        called_or_not=random.choice(["called immediately", "not contacted"]),
        estimate=random.randint(500, 10000),
        days_ago=random.randint(1, 5),
        responder=random.choice(["a plumber", "the fire department", "the police",
                                  "their insurance broker", "the building superintendent"]),
    )

    result = {
        "incident_narrative": narrative,
        "damage_description": damage_desc,
        "reported_by": name,
        "report_channel": channel,
        "report_time": time_str,
    }

    if random.random() > 0.5:
        n_witnesses = random.randint(1, 2)
        witnesses = []
        for _ in range(n_witnesses):
            w_name = random_name()
            observation = random.choice([
                "water dripping from the ceiling into the stairwell",
                "smoke coming from the window of the apartment",
                "an unfamiliar person leaving the building quickly",
                "roof tiles falling during the storm",
                "a loud cracking sound followed by glass breaking",
            ])
            stmt = random.choice(WITNESS_TEMPLATES).format(
                name=w_name, flat=random.randint(1, 20),
                time=random_time_str(), observation=observation,
            )
            witnesses.append({"witness_name": w_name, "statement": stmt})
        result["witness_statements"] = witnesses

    return result


def generate_companion_data(claim: dict, coverage_review: dict, policy: dict):
    """Generate all companion JSON files for a claim. Returns dict of filename -> content."""
    claim_id = claim["claim_id"]
    claim_type = claim["claim_type"]
    cause = claim.get("claim_intake", {}).get("cause_of_loss", "") if claim.get("claim_intake") else ""
    if not cause:
        cause = random.choice(CAUSES.get(claim_type, ["unknown cause"]))
    status = claim["status"]
    reported_date = claim["reported_date"]
    loss_date = claim["loss_date"]
    insured = claim["insured"]
    channel = claim.get("claim_intake", {}).get("channel", "phone") if claim.get("claim_intake") else "phone"

    companions = {}

    companions["adjuster_notes.json"] = _gen_companion_adjuster_notes(
        claim_type, cause, status, reported_date, insured["full_name"],
    )

    companions["documents.json"] = _gen_companion_documents(
        claim_id, claim_type, reported_date,
    )

    companions["coverage_details.json"] = _gen_companion_coverage(
        claim_type, cause, status, policy,
    )

    companions["financials.json"] = _gen_companion_financials(
        status, coverage_review, policy,
    )

    companions["intake_report.json"] = _gen_companion_intake(
        claim_type, cause, reported_date, loss_date, insured, channel,
    )

    return companions


def pick_claim_images(claim_type: str, count: int = 3) -> list[str]:
    """Pick 2-3 images for a claim based on its type."""
    pool = IMAGE_POOL.get(claim_type, [])
    if not pool:
        pool = list({img for imgs in IMAGE_POOL.values() for img in imgs})
    k = min(count, len(pool))
    return random.sample(pool, k=random.randint(min(2, k), k))


# ============================================================================
# Main claim generation
# ============================================================================

def generate_claim(idx: int) -> tuple[dict, dict, str]:
    """Generate a single claim. Returns (claim_dict, companion_data, completeness)."""
    full_name = random_name()
    claim_type = random.choice(CLAIM_TYPES)
    cause = random.choice(CAUSES[claim_type])
    status = random.choice(STATUSES)
    loss_date, reported_date = random_date_range()
    policy = policy_for_claim()
    deductible = policy["deductible_eur"]
    completeness = pick_completeness()
    claim_id = f"CLM-2026-{idx:04d}"

    insured = {
        "full_name": full_name,
        "email": random_email(full_name),
        "phone": random_phone(),
        "property_address": random.choice(STREETS),
    }

    claim = {
        "claim_id": claim_id,
        "policy_id": f"POL-{random.randint(100000, 999999)}",
        "status": status,
        "claim_type": claim_type,
        "loss_date": loss_date,
        "reported_date": reported_date,
        "insured": insured,
        "policy": policy,
        "data_path": f"{claim_id}-data/data",
    }

    intake = make_claim_intake(claim_type, cause, completeness)
    if completeness == "hard" and random.random() < 0.3:
        pass  # omit claim_intake entirely
    else:
        claim["claim_intake"] = intake

    docs = make_documents(claim_id, claim_type, reported_date, completeness)
    if completeness == "hard" and random.random() < 0.4:
        pass  # omit documents
    else:
        claim["documents"] = docs

    notes = make_adjuster_notes(claim_type, cause, status, reported_date, completeness)
    if notes is not None:
        claim["adjuster_notes"] = notes

    coverage_review = make_coverage_review(status, claim_type, cause, deductible, completeness)
    resolution = make_resolution(status, coverage_review, reported_date, claim_type, completeness)

    if completeness == "hard" and random.random() < 0.5:
        pass  # omit coverage_review
    else:
        claim["coverage_review"] = coverage_review

    if completeness == "hard" and random.random() < 0.4:
        pass  # omit resolution
    else:
        claim["resolution"] = resolution

    claim["conversation_seed_questions"] = make_questions(status)

    companion_data = generate_companion_data(claim, coverage_review, policy)

    return claim, companion_data, completeness


# ============================================================================
# Export
# ============================================================================

def export_claims_json(output_dir: str = "synthetic_claims", count: int = 10, seed: int = 42):
    random.seed(seed)
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    for old_file in out_path.glob("CLM-*.json"):
        old_file.unlink()
    for old_dir in out_path.glob("CLM-*-data"):
        shutil.rmtree(old_dir)

    claims = []
    stats = {"easy": 0, "medium": 0, "hard": 0}

    for i in range(1, count + 1):
        claim, companion_data, completeness = generate_claim(i)
        claims.append(claim)
        stats[completeness] += 1

        file_path = out_path / f"{claim['claim_id']}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(claim, f, indent=2, ensure_ascii=False)

        data_dir = out_path / f"{claim['claim_id']}-data" / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        for filename, content in companion_data.items():
            companion_path = data_dir / filename
            with open(companion_path, "w", encoding="utf-8") as f:
                json.dump(content, f, indent=2, ensure_ascii=False)

        # Copy synthetic images into companion data folder
        images = pick_claim_images(claim["claim_type"])
        for img_name in images:
            src = SYNT_IMAGES_DIR / img_name
            if src.exists():
                shutil.copy2(src, data_dir / img_name)
        # Append image entries to documents.json
        if "documents.json" in companion_data:
            docs = companion_data["documents.json"]
            data_path = f"{claim['claim_id']}-data/data"
            for img_name in images:
                docs["documents"].append({
                    "file_path": f"{data_path}/{img_name}",
                    "file_type": "jpg",
                    "doc_type": "photo_set",
                    "description": f"Site inspection photo — {img_name.replace('-', ' ').rsplit('.', 1)[0]}",
                    "uploaded_by": random.choice(ADJUSTERS + ["insured"]),
                    "file_size_kb": (SYNT_IMAGES_DIR / img_name).stat().st_size // 1024
                    if (SYNT_IMAGES_DIR / img_name).exists() else 0,
                })
            docs["count"] = len(docs["documents"])
            with open(data_dir / "documents.json", "w", encoding="utf-8") as f:
                json.dump(docs, f, indent=2, ensure_ascii=False)

    print(f"Generated {count} claims: {stats}")
    print(f"Output: {out_path.resolve()}")
    return claims


if __name__ == "__main__":
    export_claims_json()
