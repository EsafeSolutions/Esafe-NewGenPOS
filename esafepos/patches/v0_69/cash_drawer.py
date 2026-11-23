"""Repeatable cash-drawer configuration/offline-origin metadata setup."""
def execute():
    from esafepos.install import make_custom_fields
    make_custom_fields()
