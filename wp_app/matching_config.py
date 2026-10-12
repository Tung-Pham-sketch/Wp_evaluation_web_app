# =============================================================================
# matching_config.py – EDITABLE MATCHING RULES (no code change needed)
# -----------------------------------------------------------------------------
# CUSTOMER_ALIASES   canonical customer code -> every spelling of it
#                    (Tally form, Customer AMP "Customer" column, external data).
#                    Used by matching.canonical_customer() and
#                    mpd_matching.customer_codes(). Case is ignored.
# CUSTOMER_FIRST     customers whose Customer AMP is searched BEFORE
#                    ALL AMP Task, per aircraft family ("32S", "350", "787",
#                    "ATR"). Default: DLH on A350. Read by
#                    mpd_matching.matching_plan() (layer 1) and
#                    services.lookup_amp() (layers 2–3).
# DEFAULT_TALLY_FORMAT  layout pre-selected in the upload form.
#
# The list of Tally formats is NOT here: it comes from adapters.ADAPTERS.
# =============================================================================

"""Matching configuration – edit these tables to change the rules.

No other code needs to change when a customer, an alias or a customer-first
rule is added. Values are compared in upper case, so "dlh" and "DLH" are equal.
"""
from __future__ import annotations


# Spellings of one customer code (Tally form, ALL Customer AMP, external data).
# The key is the canonical code used everywhere else.
CUSTOMER_ALIASES: dict[str, set[str]] = {
    "VA-VJ": {"VA-VJ", "VJC", "VIETJET", "VIETJET AIR"},
    "DLH": {"DLH", "LUFTHANSA", "LUFTHANSA GERMAN AIRLINES"},
}

# Customers whose Customer AMP is searched BEFORE ALL AMP Task (VNA), and the
# aircraft families the rule applies to ("32S" = A319/A320/A321, "350", "787", "ATR").
# To add a customer later, add one line, e.g.  "VA-VJ": {"32S"},
CUSTOMER_FIRST: dict[str, set[str]] = {
    "DLH": {"350"},
}

# Tally Sheet layout used when the upload form does not say otherwise.
# The list of layouts itself comes from the adapter registry (adapters.ADAPTERS).
DEFAULT_TALLY_FORMAT = "VietJet"
