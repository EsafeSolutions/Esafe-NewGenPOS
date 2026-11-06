# Translating EsafePOS

EsafePOS is a point of sale app for ERPNext, used by shop owners, managers and
cashiers. Two kinds of text are translated:

- **ui_partN.json**: the till's screens (Vue app). Each row is
  `{id, key, en, ar, screen}`. Translate `en`. `ar` is the Arabic already
  shipped, useful to see what a short label means. `screen` is the file it
  appears on. Keys that start with `status:` are invoice statuses, `day:` are
  weekday abbreviations (give the usual 2 or 3 letter abbreviation of the
  target language), `lang:xx` is the name of language xx written in the
  target language (for example Spanish `lang:de` = "Alemán").
- **server_partN.json**: messages from the server (errors and notices shown at
  the till or in ERPNext's desk) and the labels, descriptions and select
  options of the app's DocTypes. Each row is `{id, en, context, where}`.

## Output

For language `xx` and part `N`, write `xx_ui_partN.json` and `xx_server_partN.json`
in this folder: each ONE JSON object mapping every id of the input to its
translation (`{"u0001": "...", ...}` or `{"s0001": "...", ...}`). Every id must be
present. Valid UTF-8 JSON, nothing else in the file.

## Rules (all strict)

1. Use `glossary_xx.json` for every term it lists, the same word every time.
   A value written as `Long form (short: X)` means: use the long form, and X
   where a label has little room; never copy the brackets themselves.
   `erp_terms_xx.json` is ERPNext's own translation of its doctypes: use it only
   to recognise a doctype, the glossary wins.
2. Keep every placeholder exactly: `{0}`, `{1}`, `{name}`, `{n}`, `{currency}` and
   so on, same names, same count. Never translate the word inside the braces.
   Keep `%s` style ones too. Keep HTML tags and their attributes exactly.
3. Keep these marks where the source has them: a leading `+ `, a trailing ` *`
   (required field), a trailing `…` (the single ellipsis character), `▸`, `·`,
   `%`, `→`, quotes around a name.
4. No em dash (U+2014), no en dash (U+2013) and no semicolon (`;`, nor the Arabic or full-width one) anywhere. Use a comma, a
   colon or a full stop instead.
5. Keep in Latin letters and untranslated: EsafePOS, ERPNext, Frappe, EsafePOS Reports,
   Insights, ExchangeRate-API, ZATCA, currency codes (USD, EUR, SAR, ZWG), field
   and code names (snake_case like mobile_no, anything in backticks), file names,
   URLs, keyboard keys (Enter, Esc, F2).
6. Digits stay Western (0-9) and unchanged.
7. Buttons and labels stay short, the till has little room: prefer the shortest
   natural wording. A select option or a label is a label, not a sentence.
8. Translate the meaning for a shop, not word by word. Keep every fact of the
   source (numbers, conditions, what happens), add nothing, drop nothing.
9. The tone of the source: plain, direct, friendly, no marketing words.

## Check before you finish

Run a small Node script (node is installed) over your output files: every input
id present, placeholders (`{...}`, `%s`) equal to the English as a multiset, the
marks of rule 3 kept, no em dash, en dash or semicolon. Fix and check again until clean.
