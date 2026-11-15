import unittest

from esafepos.receipt_barcode import invoice_modules, invoice_raster, invoice_svg_data


class ReceiptBarcodeTests(unittest.TestCase):
    def test_code128_has_checksum_stop_and_quiet_zones(self):
        expected = "1101001110010110011100100010110001110001011011000010100100011101101100011101011"
        self.assertEqual(invoice_modules("12345678"), "0000000000" + expected + "0000000000")

    def test_typical_invoice_fits_58_and_80_mm_with_complete_bars(self):
        invoice = "ACC-PSINV-2026-00004"
        bits = invoice_modules(invoice)
        for width in (384, 512):
            with self.subTest(width=width):
                packet = invoice_raster(invoice, width)
                self.assertEqual(packet[:4], b"\x1dv0\x00")
                bytes_wide = int.from_bytes(packet[4:6], "little")
                rows = int.from_bytes(packet[6:8], "little")
                self.assertLessEqual(bytes_wide * 8, width)
                self.assertEqual(len(packet), 8 + bytes_wide * rows)
                expected = "".join(bit * 2 for bit in bits) if len(bits) * 2 <= width else bits
                self.assertEqual("".join(f"{byte:08b}" for byte in packet[8:8 + bytes_wide]),
                                 expected.ljust(bytes_wide * 8, "0"))

    def test_unsupported_or_oversized_id_can_fall_back_to_plain_text(self):
        self.assertIsNone(invoice_svg_data("unsupported\n"))
        self.assertEqual(invoice_raster("Z" * 48, 384), b"")
