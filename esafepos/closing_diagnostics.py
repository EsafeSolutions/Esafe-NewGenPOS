"""Keep the cause of a closing error ahead of ERPNext's follow-up advice.

Callers pass plain text, after stripping ERPNext's HTML with accounting_periods.plain.
No stock values, document statuses or accounting rules are changed here.
"""
import re


def error_summary(text, length=180):
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if not lines:
        return ""
    # ERPNext appends a second paragraph about zero valuation. Taking only the
    # last line hid the item and invoice that actually caused this refusal.
    for line in lines:
        if re.search(r"valuation\s+rate\s+for\s+(?:the\s+)?item\b", line, re.I):
            cause = re.split(r"Here are the options to proceed", line, maxsplit=1, flags=re.I)[0]
            return " ".join(cause.split())[:length]
    # For other tracebacks the final exception line remains the useful summary.
    return " ".join(lines[-1].split())[:length]
