# =============================================================================
# wp_app – APPLICATION PACKAGE
# -----------------------------------------------------------------------------
# Makes wp_app a Python package. No code on purpose.
# Map of the package:
#   config.py           paths, env variables, MATCH_LOGIC_VERSION
#   database.py         SQLite connection, schema, column migrations
#   matching_config.py  editable matching rules (customer aliases, customer-first)
#   adapters.py         registry: Tally format -> parser / structure inspector
#   parsers.py          read VietJet and Lufthansa Excel files
#   matching.py         shared matching helpers + layers 2–3 (prefix / Title)
#   mpd_matching.py     layer 1 = MPD-key matching (main flow)
#   services.py         5-step workflow, evaluation, startup migrations, delete
#   minidb.py           AMOS popup, add/edit MiniDB records, change export
#   reference_data.py   import ALL AMP Task / Customer AMP / Jobcard master
#   utils.py            small text / column / MHR helpers
#   api/                HTTP routers (thin: validate -> call service -> respond)
# =============================================================================

"""VAECO Workpack Evaluation application package."""
