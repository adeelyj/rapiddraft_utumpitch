from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DfmRuleSet:
    id: str
    name: str
    description: str


RULE_SETS: list[DfmRuleSet] = [
    DfmRuleSet(
        id="general-dfm-v1",
        name="General DFM Baseline",
        description="Cross-process baseline checks for geometry, tolerances, and manufacturing readiness.",
    ),
    DfmRuleSet(
        id="precision-machining-v1",
        name="Precision Machining Rules",
        description="Rules focused on machinability, tool access, fixturing, and GD&T for machined parts.",
    ),
    DfmRuleSet(
        id="cost-optimization-v1",
        name="Cost Optimization Checklist",
        description="Emphasizes cycle-time, setup reduction, and process-cost drivers.",
    ),
]

BASE_ROLES = [
    "Manufacturing Engineer (DFM lead)",
    "GD&T + Metrology Engineer",
    "Assembly / DFA Reviewer",
    "Cost & Process Analyst",
]

TECH_ROLE_MAP: dict[str, list[str]] = {
    "cnc machining": ["CNC Programmer / Machining Specialist"],
    "sheet metal fabrication": ["Sheet Metal Fabrication Specialist"],
    "injection molding": ["Plastics Tooling / Molding Specialist"],
    "welding & fabrication": ["Welding / Fabrication Specialist"],
    "additive manufacturing": ["Manufacturing Engineer (DFM lead)"],
    "assembly": ["Assembly / DFA Reviewer"],
}


def list_rule_sets() -> list[dict[str, str]]:
    return [{"id": item.id, "name": item.name, "description": item.description} for item in RULE_SETS]


def resolve_roles(technology: str) -> list[str]:
    selected: list[str] = []
    normalized = technology.strip().lower()
    for key, roles in TECH_ROLE_MAP.items():
        if key in normalized:
            selected.extend(roles)
    for role in BASE_ROLES:
        if role not in selected:
            selected.append(role)
    return selected


def generate_dfm_report_markdown(
    technology: str,
    material: str,
    industry: str,
    rule_set_id: str,
    component_name: str,
) -> tuple[str, dict[str, list[str]]]:
    assumptions = [
        "Parting line, datums, and critical-to-function faces are inferred from supplied screenshot and inputs.",
        "No destructive testing assumptions; recommendations target first-pass manufacturability.",
        "Image content is accepted as reference input only (no automated vision analysis in this version).",
    ]
    high_risk_checks = [
        f"Validate geometry limits and tool access against {technology} constraints.",
        "Review minimum wall/rib/feature thickness and corner radii for process capability.",
        "Confirm datum strategy and tolerance stack-up for key functional dimensions.",
    ]
    medium_cost_drivers = [
        "Reduce setup count by standardizing orientation and fixturing assumptions.",
        f"Assess raw material availability and stock form for {material}.",
        "Flag secondary operations (deburr, heat treat, coating, inspection) impacting lead time.",
    ]
    suggested_next_steps = [
        "Run cross-functional review with process specialist and metrology owner.",
        "Prioritize high-risk items into ECO-ready action list with owners/dates.",
        "Re-submit updated geometry/screenshots after design revisions for delta review.",
    ]

    markdown = "\n".join(
        [
            "## Inputs",
            f"- Component: **{component_name}**",
            f"- Manufacturing process: **{technology}**",
            f"- Material: **{material}**",
            f"- Industry: **{industry}**",
            f"- Rule set: **{rule_set_id}**",
            "",
            "## Assumptions",
            *[f"- {item}" for item in assumptions],
            "",
            "## High-risk checks",
            *[f"- {item}" for item in high_risk_checks],
            "",
            "## Medium/cost drivers",
            *[f"- {item}" for item in medium_cost_drivers],
            "",
            "## Suggested next steps",
            *[f"- {item}" for item in suggested_next_steps],
        ]
    )

    structured = {
        "assumptions": assumptions,
        "highRiskChecks": high_risk_checks,
        "mediumCostDrivers": medium_cost_drivers,
        "suggestedNextSteps": suggested_next_steps,
    }
    return markdown, structured
