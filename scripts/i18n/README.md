# Translating EsafePOS

EsafePOS speaks a language in two places:

- **The till's screens**: `frontend/src/messages.js` holds English and Arabic
  (both in the main bundle), every other language is `frontend/src/locales/<code>.js`,
  fetched only when a cashier picks it. Keys are the English text.
- **The server's messages** (errors, notices, DocType labels):
  `esafepos/translations/<code>.csv`, the file Frappe reads on v13 to v16.
  The till sends its language as Frappe's `_lang` with every request, so these
  and ERPNext's own messages come back in the language on the screen.

`<code>` is always the ERPNext Language code (`es`, `de`, `zh`, `pt-BR` ...).
A language is shipped when both files exist and it is listed in `LANGUAGES` in
`frontend/src/i18n.js` (suite `78-languages.sh` checks the two lists match).

## Adding a language

All the scripts take a work folder for the big intermediate files (nothing in
it is committed).

1. **The server's texts.** Run `extract_server.py` with a site connected, on a
   bench that has the current code (the test benches: `run-py16.sh
   scripts/i18n/extract_server.py`). It lists what Frappe's own extractor sees
   into `/tmp/esafepos_msgs.json`: copy that to `<work>/esafepos_msgs.json`.
2. **The till's texts:** `node scripts/i18n/prep.mjs <work>` writes
   `ui_strings.json`, `server_strings.json` and the parts to translate.
3. **What ERPNext already translates:** `python3 scripts/i18n/erp_keys.py <work> <code>`
   on a bench. Frappe merges every app's translations and the app installed
   last wins, so EsafePOS must never ship a row for a text Frappe or ERPNext
   already translate: that would rename it across the whole desk.
   `write_csv.mjs` leaves those rows out.
4. **Translate** each part following `RULES.md` with `glossary_<code>.json`
   (write the glossary first: one word per POS term, used everywhere).
   Output: `<work>/<code>_ui_partN.json` and `<work>/<code>_server_partN.json`.
5. **Write the files:** `node scripts/i18n/write_locale.mjs <work> <code> "<English name>"`
   and `node scripts/i18n/write_csv.mjs <work> <code>`. Both refuse to write while
   a placeholder, a mark or a forbidden character (em or en dash, semicolon, an
   Arabic diacritic) is wrong, and list what to fix.
6. Add the language to `LANGUAGES` in `frontend/src/i18n.js` (its name written
   in itself, `dir: 'rtl'` for a right-to-left script), add `lang:<code>` to
   `prefixedEn` and to every dictionary, build, and look at the screens in it
   (light and dark) before shipping. A script Plus Jakarta Sans lacks (Thai,
   CJK, Cyrillic) needs a font in `styles.css`.
