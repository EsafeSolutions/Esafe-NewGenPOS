"""Esafe print defaults stored on the existing POS Profile (Python 3.7)."""
FIELDS = {
    "silent": "esafepos_silent_printing",
    "automatic_receipt": "esafepos_auto_print_receipt",
    "receipt_output": "esafepos_receipt_output",
    "copies": "esafepos_print_copies",
    "document_paper": "esafepos_document_paper",
}


def defaults(profile):
    return {
        "silent": bool(profile.get(FIELDS["silent"])),
        "automatic_receipt": bool(profile.get(FIELDS["automatic_receipt"])),
        "receipt_output": profile.get(FIELDS["receipt_output"]) or "html",
        "copies": int(profile.get(FIELDS["copies"]) or 1),
        "document_paper": profile.get(FIELDS["document_paper"]) or "A4",
    }


def validate(values):
    if not isinstance(values, dict):
        raise ValueError("Invalid silent-printing defaults")
    output = values.get("receipt_output", "html")
    paper = values.get("document_paper", "A4")
    copies = values.get("copies", 1)
    if output not in ("html", "pdf", "raw") or paper not in ("A4", "Letter"):
        raise ValueError("Choose a supported receipt output and document paper")
    if isinstance(copies, bool) or str(copies) not in [str(n) for n in range(1, 100)]:
        raise ValueError("Print between 1 and 99 copies")
    return {"silent": 1 if values.get("silent") in (True, 1) else 0,
            "automatic_receipt": 1 if values.get("automatic_receipt") in (True, 1) else 0,
            "receipt_output": output, "copies": int(copies), "document_paper": paper}
