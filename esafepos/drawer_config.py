"""Validated workstation drawer configuration; no financial side effects (Python 3.7)."""
import json

FIELD = "esafepos_cash_drawers"


def validate(values):
    if not isinstance(values, dict):
        raise ValueError("Invalid cash drawer settings")
    result = {"enabled": values.get("enabled", False), "automatic": values.get("automatic", False),
              "pin": values.get("pin", 0), "onMs": values.get("onMs", 100), "offMs": values.get("offMs", 500)}
    if any(type(result[key]) is not bool for key in ("enabled", "automatic")):
        raise ValueError("Choose enabled or disabled for drawer policies")
    if type(result["pin"]) is not int or result["pin"] not in (0, 1):
        raise ValueError("Choose connector pin 2 or pin 5")
    for key in ("onMs", "offMs"):
        if type(result[key]) is not int or not 2 <= result[key] <= 510 or result[key] % 2:
            raise ValueError("Pulse times must be even integers from 2 to 510 milliseconds")
    return result


def registry(profile):
    value = profile.get(FIELD) or "{}"
    result = json.loads(value) if isinstance(value, str) else value
    if not isinstance(result, dict):
        raise ValueError("Invalid workstation drawer registry; ask an administrator to review it")
    return result
