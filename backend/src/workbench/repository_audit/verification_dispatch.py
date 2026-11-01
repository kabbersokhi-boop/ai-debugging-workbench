"""Choose a verifier by its versioned plan, retaining the existing implementation unchanged."""

from workbench.repository_audit import generated, independent


def handler(verification):
    if verification is not None and (
        not isinstance(verification, dict) or not isinstance(verification.get("plan"), dict)
    ):
        raise ValueError("Invalid versioned verification record")
    if verification and verification.get("plan", {}).get("version") == "generated-plan-v1":
        return generated
    return independent


def engine_id(verification=None):
    return handler(verification).engine_id()


def check(evidence, *, historical=False):
    return handler(evidence.get("verification")).check(evidence, historical=historical)


def evaluate(audit_id, evidence, cancel):
    return handler(evidence.get("verification")).evaluate(audit_id, evidence, cancel)


def validate(result, audit_id, evidence):
    return handler(evidence.get("verification")).validate(result, audit_id, evidence)
