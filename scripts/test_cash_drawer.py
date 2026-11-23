"""Cash drawer authorization and migration tests; no real ERP or hardware."""
import datetime
import json
import types
import sys
import unittest
from unittest.mock import Mock
import test_esafe_printing as base

fake = base.fake
utils = sys.modules["frappe.utils"]
utils.flt = lambda value: float(value or 0)
utils.get_datetime = lambda value: value if isinstance(value, datetime.datetime) else datetime.datetime.fromisoformat(value)
utils.now_datetime = datetime.datetime.now
from esafepos.api import cash_drawer as drawer
from esafepos.drawer_config import validate, FIELD


class Doc(base.Doc):
    meta = types.SimpleNamespace(has_field=lambda field: True)
    def set(self, key, value): self[key] = value
    def save(self): pass
    def reload(self): pass


class DrawerTests(unittest.TestCase):
    register = base.EsafePrintingTests.register
    value = base.EsafePrintingTests.value

    def setUp(self):
        base.EsafePrintingTests.setUp(self)
        self.invoice = Doc(self.invoice)
        self.settings = dict(enabled=True, automatic=True, pin=0, onMs=100, offMs=500)
        self.profile = Doc(doctype="POS Profile", name="Till", company="Company", print_format="Preserved")
        self.profile[FIELD] = json.dumps({base.DEVICE: dict(self.settings, printerId="receipt-id")})
        self.invoice.update(owner="cashier", docstatus=1, grand_total=100, outstanding_amount=0, is_pos=1,
                            esafepos_session="SHIFT", creation=datetime.datetime.now(), payments=[{"mode_of_payment":"Cash","amount":100}])
        self.shift = Doc(doctype="POS Register Session", name="SHIFT", status="Open", pos_profile="Till", company="Company", opened_by="cashier")
        fake.get_doc = lambda dt, name=None: Doc(dt) if isinstance(dt, dict) else self.invoice if dt=="POS Invoice" else self.shift if dt=="POS Register Session" else self.profile if dt=="POS Profile" else base.STORE[name]
        fake.get_cached_doc = lambda *args: self.profile
        fake.has_permission = Mock(return_value=True)
        self.returned = False
        fake.db.exists = lambda dt, filters=None: True if dt=="DocType" else self.returned
        fake.db.sql = Mock()
        fake.get_cached_value = lambda dt, name, field: "Company" if dt=="POS Profile" else "Cash" if name=="Cash" else "Bank"
        base.permissions.can_cash_out = Mock(return_value=True)
        base.audit.SETTINGS_CHANGE = "Settings change"
        self.setup_allowed = True
        settings = types.ModuleType("esafepos.api.printing_settings")
        def profile(name, write=False):
            if not self.setup_allowed or name!="Till": raise PermissionError("Setup denied")
            return self.profile
        settings._profile = profile
        sys.modules[settings.__name__] = settings
        session = types.ModuleType("esafepos.api.session")
        session.get_open_session = lambda profile: {"name":"SHIFT"} if profile=="Till" else None
        sys.modules[session.__name__] = session
        register = types.ModuleType("esafepos.api.register")
        def owner(doc):
            if doc.opened_by!=fake.session.user: raise PermissionError("Another cashier")
        register._assert_owner_or_manager = owner
        sys.modules[register.__name__] = register

    def pulse(self, **extra):
        values=dict(self.settings, mode="payment")
        values.update(extra.pop("drawer", {}))
        payload=dict(role="drawer", output="raw", automatic=1, printer_id="receipt-id", drawer=values)
        payload.update(extra)
        return self.register(**payload)

    def test_disabled_defaults_and_strict_vectors(self):
        self.assertEqual(validate({}), dict(enabled=False, automatic=False, pin=0, onMs=100, offMs=500))
        for values in ({"pin":True},{"pin":2},{"onMs":3},{"onMs":0},{"offMs":512},{"offMs":2.0},{"onMs":"100"}):
            with self.subTest(values=values), self.assertRaises(ValueError): validate(values)
        self.assertEqual(validate({"onMs":2,"offMs":510,"pin":1})["pin"],1)

    def test_paid_cash_and_cash_card_split_are_eligible(self):
        self.assertTrue(drawer.payment_eligibility("Till","POS Invoice","INV-1")["eligible"])
        self.invoice["payments"]=[{"mode_of_payment":"Cash","amount":40},{"mode_of_payment":"Card","amount":60}]
        self.pulse()
        self.assertEqual(base.STORE[base.ID].drawer_mode,"payment")
        self.assertEqual(base.STORE[base.ID].printer_id,"receipt-id")

    def test_card_credit_unpaid_returns_offline_drafts_and_history_do_not_pulse(self):
        cases=[{"payments":[{"mode_of_payment":"Card","amount":100}]}, {"payments":[{"mode_of_payment":"Cash","amount":0}]},
               {"payments":[{"mode_of_payment":"Cash","amount":40},{"mode_of_payment":"Credit Sale","amount":60}]},
               {"outstanding_amount":10},{"is_return":1},{"docstatus":0},{"docstatus":2},{"esafepos_queued_offline":1},
               {"creation":datetime.datetime.now()-datetime.timedelta(minutes=6)}]
        for changes in cases:
            original=dict(self.invoice);self.invoice.update(changes)
            with self.subTest(changes=changes), self.assertRaises(PermissionError): self.pulse()
            self.invoice.clear();self.invoice.update(original)
        self.returned=True
        with self.assertRaises(PermissionError):self.pulse()

    def test_same_intent_retry_and_cross_workstation_original_guard(self):
        self.pulse();self.assertEqual(self.pulse()["name"],base.ID)
        other="44444444-4444-4444-8444-444444444444"
        entries=json.loads(self.profile[FIELD]);entries[other]=entries[base.DEVICE];self.profile[FIELD]=json.dumps(entries)
        with self.assertRaises(PermissionError):self.pulse(request_id="33333333-3333-4333-8333-333333333333",workstation=other)
        self.assertEqual(len(base.STORE),1)

    def test_wrong_outlet_user_printer_settings_and_guest_are_denied(self):
        for kwargs in ({"pos_profile":"Other"},{"printer_id":"other-id"},{"drawer":{"onMs":102}}):
            with self.subTest(kwargs=kwargs),self.assertRaises(PermissionError): self.pulse(**kwargs)
        fake.session.user="Guest"
        with self.assertRaises(PermissionError):self.pulse()

    def test_sale_and_session_permissions_and_owner_are_enforced(self):
        fake.has_permission.return_value=False
        with self.assertRaises(PermissionError):self.pulse()
        fake.has_permission.return_value=True
        self.invoice["owner"]="other cashier"
        with self.assertRaises(PermissionError):self.pulse()
        self.invoice["owner"]="cashier";self.shift["deny"]=True
        with self.assertRaises(PermissionError):self.pulse()

    def test_auto_receipt_policy_cannot_skip_linked_receipt(self):
        self.profile.update(esafepos_silent_printing=1,esafepos_auto_print_receipt=1)
        with self.assertRaises(PermissionError):self.pulse()

    def test_setup_test_and_manual_permissions_are_separate(self):
        values=dict(self.settings, mode="test")
        self.setup_allowed=False
        with self.assertRaises(PermissionError):self.register(role="drawer",output="raw",printer_id="receipt-id",reference={"doctype":"POS Profile","name":"Till"},drawer=values)
        self.setup_allowed=True
        values.update(mode="manual",reason="Change float")
        base.permissions.can_cash_out.return_value=False
        with self.assertRaises(PermissionError):self.register(role="drawer",output="raw",printer_id="receipt-id",reference={"doctype":"POS Register Session","name":"SHIFT"},drawer=values)
        base.permissions.can_cash_out.return_value=True
        self.register(role="drawer",output="raw",printer_id="receipt-id",reference={"doctype":"POS Register Session","name":"SHIFT"},drawer=values)
        self.assertEqual(base.STORE[base.ID].drawer_reason,"Change float")

    def test_receipt_requires_submitted_same_queue_and_original(self):
        self.register(printer_id="receipt-id")
        for state in ("queued","preparing","failed","unknown","cancelled"):
            base.STORE[base.ID]["state"]=state
            with self.subTest(state=state),self.assertRaises(PermissionError): self.pulse(request_id="33333333-3333-4333-8333-333333333333",drawer={"receiptIntent":base.ID})
        base.STORE[base.ID]["state"]="submitted"
        self.pulse(request_id="33333333-3333-4333-8333-333333333333",drawer={"receiptIntent":base.ID})

    def test_setup_preserves_other_workstations_and_business_preferences(self):
        other="44444444-4444-4444-8444-444444444444"
        drawer.save_setup("Till",other,"second-id",dict(self.settings,pin=1))
        entries=json.loads(self.profile[FIELD])
        self.assertEqual(entries[base.DEVICE]["printerId"],"receipt-id")
        self.assertEqual(entries[other]["pin"],1)
        self.assertEqual(self.profile.print_format,"Preserved")
        fake.db.sql.assert_called_once()

    def test_outcomes_do_not_mutate_sale_or_claim_physical_opening(self):
        before=dict(self.invoice);self.pulse()
        base.api.record_event(base.ID,"unknown",job_id="native-pulse")
        self.assertEqual(dict(self.invoice),before)
        self.assertEqual(base.STORE[base.ID].state,"unknown")

    def test_pulse_cannot_be_reprinted_under_receipt_role(self):
        self.pulse()
        with self.assertRaises(PermissionError):
            self.register(request_id="33333333-3333-4333-8333-333333333333",reprint_of=base.ID,
                          reference={"doctype":"POS Invoice","name":"INV-1","reprint":1})

    def test_manual_retry_cannot_change_original_reason(self):
        args=dict(role="drawer",output="raw",printer_id="receipt-id",reference={"doctype":"POS Register Session","name":"SHIFT"})
        self.register(drawer=dict(self.settings,mode="manual",reason="Original reason"),**args)
        with self.assertRaises(PermissionError):
            self.register(drawer=dict(self.settings,mode="manual",reason="Changed reason"),**args)


if __name__=="__main__":unittest.main()
