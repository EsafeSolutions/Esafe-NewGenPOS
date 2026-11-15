"""Code 128 invoice IDs for public HTML and ESC/POS receipts."""

import re


# Alternating bar and space widths, in codeword order. The browser encoder
# has the same patterns in frontend/src/barcode.js.
_WIDTHS = """
212222 222122 222221 121223 121322 131222 122213 122312 132212 221213 221312 231212
112232 122132 122231 113222 123122 123221 223211 221132 221231 213212 223112 312131
311222 321122 321221 312212 322112 322211 212123 212321 232121 111323 131123 131321
112313 132113 132311 211313 231113 231311 112133 112331 132131 113123 113321 133121
313121 211331 231131 213113 213311 213131 311123 311321 331121 312113 312311 332111
314111 221411 431111 111224 111422 121124 121421 141122 141221 112214 112412 122114
122411 142112 142211 241211 221114 413111 241112 134111 111242 121142 121241 114212
124112 124211 411212 421112 421211 212141 214121 412121 111143 111341 131141 114113
114311 411113 411311 113141 114131 311141 411131 211412 211214 211232 2331112
""".split()


def invoice_modules(invoice_id):
    if not re.fullmatch(r"[ -~]{1,48}", invoice_id or ""):
        return ""
    values = []
    active_set = None
    for part in re.findall(r"[0-9]+|[^0-9]+", invoice_id):
        pair_digits = part.isdigit() and (len(part) >= 4 or part == invoice_id and len(part) == 2)
        if pair_digits:
            if active_set != "C":
                values.append(105 if active_set is None else 99)
                active_set = "C"
            end = len(part) - len(part) % 2
            values.extend(int(part[i:i + 2]) for i in range(0, end, 2))
            part = part[end:]
        if part:
            if active_set != "B":
                values.append(104 if active_set is None else 100)
                active_set = "B"
            values.extend(ord(char) - 32 for char in part)
    checksum = values[0] + sum(index * value for index, value in enumerate(values[1:], 1))
    values.extend((checksum % 103, 106))
    return "0" * 10 + "".join(
        ("1" if index % 2 == 0 else "0") * int(width)
        for value in values
        for index, width in enumerate(_WIDTHS[value])
    ) + "0" * 10


def invoice_svg_data(invoice_id):
    modules = invoice_modules(invoice_id)
    if not modules:
        return None
    path = "".join("M{} 0h{}v40h-{}z".format(run.start(), len(run[0]), len(run[0]))
                   for run in re.finditer(r"1+", modules))
    return {"width": len(modules), "path": path}


def invoice_raster(invoice_id, max_dots):
    modules = invoice_modules(invoice_id)
    if not modules:
        return b""
    if len(modules) * 2 <= max_dots:
        modules = "".join(bit * 2 for bit in modules)
    bytes_wide = (len(modules) + 7) // 8
    if bytes_wide * 8 > max_dots:
        return b""
    height = 56
    line = int(modules.ljust(bytes_wide * 8, "0"), 2).to_bytes(bytes_wide, "big")
    return b"\x1dv0\x00" + bytes_wide.to_bytes(2, "little") + height.to_bytes(2, "little") + line * height
