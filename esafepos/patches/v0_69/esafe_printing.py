"""Repeatable metadata migration; existing IP/format/business records are preserved."""


def execute():
    from esafepos.install import make_custom_fields

    make_custom_fields()
