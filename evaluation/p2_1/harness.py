"""Small external-style harness for the Kaapi P2.1 golden cases.

The harness owns evaluation grading. Kaapi supplies the deterministic static
assessment, policy requirement result, findings, and evidence; this module
does not inspect configuration or implement security controls itself.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from kaapi import analyze_text
from kaapi.model import ConfigError
from kaapi.policy import PolicyError


OUTCOMES = {"PASS", "FAIL", "INCONCLUSIVE", "NOT_TESTED"}
MINIMUM_REQUIRED_EVIDENCE = {
    "organisation_policy",
    "policy_requirement",
    "requirement_observation",
}
BASELINE_LIMITATION = (
    "Configuration analysis establishes configured authority and resolved "
    "capability; it does not verify runtime enforcement or agent behaviour."
)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _policy_requirement(document: dict[str, Any], control_id: str) -> dict[str, Any] | None:
    policy = document.get("organisation_policy")
    if not isinstance(policy, dict):
        return None
    for requirement in policy.get("requirements", []):
        if isinstance(requirement, dict) and requirement.get("control_id") == control_id:
            return requirement
    return None


def _evidence_present(
    document: dict[str, Any],
    requirement: dict[str, Any] | None,
    kind: str,
    control_id: str,
) -> bool:
    if kind == "organisation_policy":
        return isinstance(document.get("organisation_policy"), dict)
    if kind == "policy_requirement":
        return requirement is not None
    if kind == "requirement_observation":
        return bool(
            requirement
            and isinstance(requirement.get("observed"), dict)
            and requirement.get("observed")
        )
    if kind == "finding":
        return any(
            isinstance(finding, dict)
            and finding.get("id") == control_id
            and bool(finding.get("evidence"))
            for finding in document.get("findings", [])
        )
    return False


def assess_configuration(
    config_content: str | bytes,
    *,
    runtime: str,
    security_requirement: dict[str, Any],
    source: str | None = None,
) -> dict[str, Any]:
    """Return a deterministic harness assessment for one configuration.

    The requirement must contain a Kaapi policy document, a control ID, and
    ``required_evidence`` names. Only ``PASS`` from the policy requirement
    grades as a passing security requirement. A missing result or required
    evidence is inconclusive; an unsupported policy control is not tested.
    """
    control_id = security_requirement.get("control_id")
    policy = security_requirement.get("policy")
    required_evidence = security_requirement.get("required_evidence", [])
    if (
        not isinstance(control_id, str)
        or not isinstance(policy, dict)
        or not isinstance(required_evidence, list)
        or not required_evidence
        or any(not isinstance(item, str) for item in required_evidence)
        or not MINIMUM_REQUIRED_EVIDENCE.issubset(required_evidence)
    ):
        return {
            "grade": "NOT_TESTED",
            "limitations": [
                "The security requirement must declare all minimum evidence "
                "categories."
            ],
            "evidence": {},
        }

    try:
        document = analyze_text(
            config_content,
            runtime=runtime,
            source=source,
            policy=policy,
        )
    except (ConfigError, PolicyError) as exc:
        return {
            "grade": "NOT_TESTED",
            "limitations": [f"Input could not be assessed: {exc}"],
            "evidence": {},
        }

    requirement = _policy_requirement(document, control_id)
    if requirement is None:
        return {
            "grade": "INCONCLUSIVE",
            "security_posture": document.get("posture"),
            "policy_verdict": document.get("organisation_policy", {}).get("verdict"),
            "limitations": ["Kaapi returned no matching policy requirement."],
            "evidence": {"organisation_policy": document.get("organisation_policy")},
        }

    observed = requirement.get("observed", {})
    if (
        isinstance(observed, dict)
        and (
            observed.get("policy_runtime_supported") is False
            or observed.get("control_available") is False
        )
    ):
        grade = "NOT_TESTED"
        limitations = ["The selected policy requirement is unsupported for this runtime."]
    else:
        missing = [
            item
            for item in required_evidence
            if not _evidence_present(document, requirement, item, control_id)
        ]
        if missing:
            grade = "INCONCLUSIVE"
            limitations = [f"Required evidence is missing: {', '.join(missing)}."]
        elif requirement.get("status") == "PASS":
            grade = "PASS"
            limitations = []
        else:
            grade = "FAIL"
            limitations = []

    evidence = {
        "policy_requirement": requirement,
        "findings": [
            finding
            for finding in document.get("findings", [])
            if isinstance(finding, dict) and finding.get("id") == control_id
        ],
    }
    return {
        "grade": grade,
        "security_posture": document["posture"],
        "policy_verdict": document["organisation_policy"]["verdict"],
        "policy_status": requirement["status"],
        "evidence": evidence,
        "limitations": [BASELINE_LIMITATION, *limitations],
    }


def evaluate_case(case_dir: str | Path) -> dict[str, Any]:
    """Run and grade one checked-in golden case."""
    root = Path(case_dir)
    manifest = _load_json(root / "evaluation.json")
    runtime = manifest.get("runtime")
    config_name = manifest.get("config")
    requirement = manifest.get("security_requirement")
    if not isinstance(runtime, str) or not isinstance(config_name, str) or not isinstance(requirement, dict):
        return {
            "case_id": manifest.get("case_id"),
            "grade": "NOT_TESTED",
            "limitations": ["The golden-case manifest is malformed."],
            "evidence": {},
        }
    try:
        content = (root / config_name).read_bytes()
    except OSError as exc:
        return {
            "case_id": manifest.get("case_id"),
            "grade": "NOT_TESTED",
            "limitations": [f"Configuration input is unavailable: {exc.strerror or 'I/O error'}"],
            "evidence": {},
        }
    result = assess_configuration(
        content,
        runtime=runtime,
        security_requirement=requirement,
        source=f"golden:{manifest.get('case_id', root.name)}",
    )
    return {"case_id": manifest.get("case_id", root.name), **result}


def _main() -> int:
    parser = argparse.ArgumentParser(description="Run one Kaapi P2.1 golden evaluation case")
    parser.add_argument("case", type=Path, help="golden-case directory")
    args = parser.parse_args()
    result = evaluate_case(args.case)
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    return 0 if result.get("grade") in OUTCOMES else 1


if __name__ == "__main__":
    raise SystemExit(_main())
