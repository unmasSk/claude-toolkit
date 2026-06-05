# Attack Patterns — What Worked

## Mixed alphanumeric tokens silently dropped by tokenizer
- Pattern: query containing `[A-Z]{1,2}\d+` or `\d+[A-Za-z]+` tokens (BM25, v2, auth3)
- The regex `[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ]{3,}` only captures pure-letter sequences of 3+
- 'BM25' produces empty token set → no matches even when corpus has BM25 entries
- Works on any codebase using this tokenizer for technical terms

## Fixed SCAN_DEPTH with no warning when corpus exceeds it
- SCAN_DEPTH=500 is hardcoded. If repo has >500 commits, old entries silently disappear.
- No error, no warning — `(no matches)` for entries that exist but are beyond horizon
- Effective attack: large/old repos with important early decisions silently invisible

## Tombstone normalization asymmetry via HTML comment chars
- Tombstone collected via `normalize(trailers[key])` — does NOT call `_sanitize()`
- Entry text stored via `_sanitize(trailers[kind])` then `normalize(text)`
- If entry text contains `<!--` or `-->`, sanitize removes them, normalize sees different string
- Tombstone norm: `'antipattern - <!-- note --> use bm25'`
- Entry norm: `'antipattern - note use bm25'` → no match → tombstone fails to suppress
