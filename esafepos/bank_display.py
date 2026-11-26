"""Public receiving instructions for the customer monitor; never bank credentials."""
import json
import re


def clean_config(value):
    if isinstance(value, str):
        value = json.loads(value or "{}")
    if not isinstance(value, dict):
        raise ValueError("Bank display settings must be an object.")
    accounts = value.get("accounts") or []
    if not isinstance(accounts, list) or len(accounts) > 12:
        raise ValueError("Add at most 12 receiving bank accounts.")
    result = {"enabled": value.get("enabled") in (True, 1),
              "trigger": "bank" if value.get("trigger") == "bank" else "checkout", "accounts": []}
    for row in accounts:
        if not isinstance(row, dict):
            raise ValueError("Invalid bank account details.")
        account = {}
        for key in ("bank_name", "holder", "account_number", "branch", "swift", "payment_mode", "pos_profile", "currency"):
            account[key] = str(row.get(key) or "").strip()[:140]
        if not account["bank_name"] or not account["holder"] or not account["account_number"]:
            raise ValueError("Enter the bank, account holder and account number for each account.")
        if result["trigger"] == "bank" and not account["payment_mode"]:
            raise ValueError("Choose a payment method for every bank account when using the bank-only trigger.")
        account["currency"] = account["currency"].upper()
        if account["currency"] and not re.fullmatch(r"[A-Z]{3}", account["currency"]):
            raise ValueError("Use a three-letter bank account currency, for example LKR.")
        for key in ("logo", "qr_image"):
            path = str(row.get(key) or "").strip()
            if path and (not re.fullmatch(r"/files/[^?<>\"\\]+\.(?:png|jpg|jpeg|webp)", path, re.I) or ".." in path):
                raise ValueError("Upload a PNG, JPEG or WebP bank image.")
            account[key] = path
        account["qr_payload"] = str(row.get("qr_payload") or "").strip()
        if len(account["qr_payload"].encode("utf-8")) > 1500:
            raise ValueError("Keep the QR payload within 1500 bytes or upload the bank's QR image.")
        account["instructions"] = str(row.get("instructions") or "").strip()[:500]
        for key, default, low, high in (("logo_size", 72, 32, 160), ("qr_size", 240, 140, 360)):
            size = float(row.get(key) or default)
            if not low <= size <= high:
                raise ValueError("Bank image size is outside the allowed range.")
            account[key] = int(size)
        result["accounts"].append(account)
    if result["enabled"] and not result["accounts"]:
        raise ValueError("Add a receiving bank account before enabling the bank display.")
    return result


def settings_value(doc):
    try:
        return clean_config(doc.get("bank_transfer_display") or {})
    except (ValueError, TypeError, OverflowError):
        return {"enabled": False, "trigger": "checkout", "accounts": []}


def client_config(doc, profile):
    config = settings_value(doc)
    config["accounts"] = [row for row in config["accounts"] if not row["pos_profile"] or row["pos_profile"] == profile]
    return config
