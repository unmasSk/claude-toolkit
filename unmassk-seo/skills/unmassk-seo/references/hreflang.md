# Hreflang -- International SEO Reference

Reference data for validating existing hreflang implementations, generating
correct hreflang tags, and auditing international SEO configurations. Load this
file when the user requests hreflang validation, international SEO audit,
multi-language site analysis, or hreflang tag generation.

---

## What Hreflang Does

Hreflang tells search engines which language and regional version of a page to
serve to users in different locales. Without hreflang, search engines may show
the wrong language version in results, or treat language variants as duplicate
content and suppress all but one.

Hreflang is supported by Google and Yandex. Bing uses the `content-language`
HTTP header and `<meta http-equiv="content-language">` tag instead. Provide
both hreflang (for Google/Yandex) and content-language (for Bing) when
targeting international audiences.

---

## 8 Validation Checks

Apply all 8 checks to every hreflang implementation. Each check is independent
-- a page can pass some and fail others. Report each check individually with
specific evidence.

### Check 1: Self-Referencing Tags

Every page with hreflang must include an hreflang tag pointing to itself. The
self-referencing URL must exactly match the page's canonical URL, including
protocol, domain, path, and trailing slash.

**Why it matters:** Missing self-referencing tags cause Google to ignore the
entire hreflang set for that page. This is the most common and most damaging
hreflang error.

**What to check:**

- Every page in the hreflang set has a tag pointing to its own URL.
- The self-referencing URL matches the canonical URL exactly.
- There are no differences in protocol (HTTP vs HTTPS), trailing slashes, or
  www/non-www.

**Example -- correct:**

```html
<!-- On page https://example.com/page -->
<link rel="alternate" hreflang="en-US" href="https://example.com/page" />
<link rel="alternate" hreflang="fr" href="https://example.com/fr/page" />
<link rel="alternate" hreflang="x-default" href="https://example.com/page" />
```

**Example -- incorrect (missing self-reference):**

```html
<!-- On page https://example.com/page -- WRONG: no en-US tag pointing to self -->
<link rel="alternate" hreflang="fr" href="https://example.com/fr/page" />
<link rel="alternate" hreflang="x-default" href="https://example.com/page" />
```

**Severity:** Critical. Google ignores the entire hreflang set when self-
referencing tags are missing.

### Check 2: Return Tags (Bidirectional)

Hreflang relationships must be bidirectional. If page A declares page B as an
alternate, page B must declare page A as an alternate. This applies to every
pair in the set -- the relationship graph must be a full mesh.

**Why it matters:** Missing return tags invalidate the hreflang signal for both
pages in the pair. One-directional hreflang is treated as an error, not a
partial signal.

**What to check:**

- For every hreflang tag on page A pointing to page B, verify that page B has
  a corresponding hreflang tag pointing back to page A.
- Check all pairs, not just adjacent pages. In a set of 5 language versions,
  each page must reference all 5 (including itself), producing 25 total tags
  (5 pages x 5 references each).
- Verify the URLs match exactly in both directions.

**How to audit at scale:**

1. Collect all hreflang tags from all pages in the set.
2. Build a directed graph of hreflang relationships.
3. Verify the graph is complete (every node connects to every other node).
4. Flag any missing edges as broken return tags.

**Severity:** Critical. Missing return tags invalidate hreflang for both pages
in the pair.

### Check 3: x-default Tag

The x-default hreflang value designates the fallback page for users whose
language or region does not match any specific hreflang variant.

**Requirements:**

- Every hreflang set must include exactly one x-default.
- x-default typically points to the language selector page, the English version,
  or the most widely applicable version.
- x-default must have return tags from all other language versions (it
  participates in the bidirectional requirement).
- Only one x-default per set of alternates.

**What to check:**

- x-default is present in the hreflang set.
- Only one x-default exists per page set.
- x-default URL is valid and returns HTTP 200.
- All other language versions include x-default in their hreflang tags.

**Example:**

```html
<link rel="alternate" hreflang="en-US" href="https://example.com/page" />
<link rel="alternate" hreflang="fr" href="https://example.com/fr/page" />
<link rel="alternate" hreflang="de" href="https://example.de/page" />
<link rel="alternate" hreflang="x-default" href="https://example.com/page" />
```

**Severity:** High. Missing x-default means users with unmatched locales may
see the wrong version or no version.

### Check 4: Language Code Validation (ISO 639-1)

Language codes in hreflang must use **ISO 639-1 two-letter codes**. Three-letter
codes (ISO 639-2), full language names, and non-standard codes are invalid.

**Valid codes (examples):**

| Language | Correct Code | Common Mistake |
|---|---|---|
| English | `en` | `eng` (ISO 639-2, invalid) |
| French | `fr` | `fre` or `fra` (invalid) |
| German | `de` | `ger` or `deu` (invalid) |
| Japanese | `ja` | `jp` (country code, not language) |
| Chinese (Simplified) | `zh-Hans` | `zh` alone (ambiguous) |
| Chinese (Traditional) | `zh-Hant` | `zh` alone (ambiguous) |
| Spanish | `es` | `esp` (invalid) |
| Portuguese | `pt` | `por` (invalid) |
| Korean | `ko` | `kr` (country code, not language) |
| Arabic | `ar` | `ara` (invalid) |

**Special cases:**

- Chinese requires a script subtag: `zh-Hans` (Simplified) or `zh-Hant`
  (Traditional). Using bare `zh` is ambiguous and should be flagged.
- Serbian uses `sr-Latn` (Latin script) or `sr-Cyrl` (Cyrillic script).
- Norwegian: use `nb` (Bokmal) or `nn` (Nynorsk), not bare `no` (ambiguous).

**What to check:**

- All language codes are exactly 2 characters (except script subtags).
- No three-letter codes are used.
- Ambiguous codes have proper qualifiers.
- Codes are lowercase.

**Severity:** High. Invalid language codes cause Google to ignore the hreflang
tag entirely.

### Check 5: Region Code Validation (ISO 3166-1 Alpha-2)

Optional region qualifiers use **ISO 3166-1 Alpha-2** country codes. The format
is `language-REGION` with lowercase language and uppercase region.

**Valid examples:**

| Target | Code | Format |
|---|---|---|
| English (United States) | `en-US` | Correct |
| English (United Kingdom) | `en-GB` | Correct |
| Portuguese (Brazil) | `pt-BR` | Correct |
| Spanish (Mexico) | `es-MX` | Correct |
| French (Canada) | `fr-CA` | Correct |

**Common mistakes:**

| Mistake | Correct | Reason |
|---|---|---|
| `en-uk` | `en-GB` | UK is not a valid ISO 3166-1 code. Great Britain is `GB`. |
| `en-US` (correct) vs `en-us` | `en-US` | Region must be uppercase. Most parsers accept lowercase, but spec requires uppercase. |
| `es-LA` | `es-MX`, `es-AR`, etc. | Latin America is not a country. Use specific country codes. |
| `fr-EU` | `fr` (no region) | Europe is not a country. Use language-only code for pan-European targeting. |
| `en-UK` | `en-GB` | Most common single error in hreflang implementations. |
| `pt-PT` vs `pt` | Both valid | `pt-PT` targets Portugal specifically; `pt` targets all Portuguese speakers. Use intentionally. |

**When to use region codes:**

- Use region codes when content is specifically localized for a country (pricing,
  regulations, spelling differences).
- Use language-only codes when content targets all speakers of that language
  regardless of location.
- Do not add region codes just for completeness -- they narrow the targeting
  scope.

**What to check:**

- Region codes are valid ISO 3166-1 Alpha-2 codes.
- Region codes are uppercase.
- No fictional or aggregate codes (LA, EU, UK).
- Region usage is intentional (not arbitrary).

**Severity:** High. Invalid region codes cause Google to ignore the hreflang tag.

### Check 6: Canonical URL Alignment

Hreflang tags must appear only on canonical pages, and the URLs in hreflang
tags must be canonical URLs.

**Rules:**

- If a page has `rel=canonical` pointing to a different URL, hreflang tags on
  that page are ignored by Google. Only the canonical URL's hreflang tags are
  processed.
- The URL in each hreflang tag must match the canonical URL of the target page
  exactly (including trailing slashes, www/non-www, protocol).
- Non-canonical pages (parameter variations, paginated pages, mobile-specific
  URLs) must not appear in any hreflang set.

**What to check:**

1. For each page with hreflang tags, verify its canonical URL points to itself.
2. For each URL in the hreflang set, verify that page's canonical also points
   to itself.
3. Compare hreflang URLs against canonical URLs -- they must match exactly.
4. Flag any hreflang URL whose target has a canonical pointing elsewhere.

**Common conflict patterns:**

| Conflict | Result | Fix |
|---|---|---|
| Page has hreflang but canonical points elsewhere | Hreflang ignored entirely | Move hreflang to canonical URL only |
| Hreflang URL includes trailing slash, canonical does not | May be treated as different URLs | Normalize trailing slashes |
| Hreflang uses www, canonical uses non-www | URLs treated as different pages | Standardize all URLs |
| Hreflang on AMP page | AMP has different canonical handling | Use hreflang on canonical, not AMP version |

**Severity:** High. Canonical/hreflang misalignment silently breaks
international targeting.

### Check 7: Protocol Consistency

All URLs within a single hreflang set must use the same protocol. Mixing HTTP
and HTTPS in one set causes validation failures.

**What to check:**

- All URLs in the hreflang set use HTTPS.
- No HTTP URLs remain after HTTPS migration.
- Cross-domain sets (e.g., example.com and example.de) both use HTTPS.

**Post-migration checklist:**

After migrating to HTTPS, verify that ALL hreflang tags across ALL language
versions have been updated to HTTPS. This is commonly missed because hreflang
tags exist on multiple pages across multiple language versions -- updating one
language version but forgetting others breaks the entire set.

**Severity:** Medium. Mixed protocols cause validation failures but may not
completely break hreflang if search engines resolve redirects.

### Check 8: Cross-Domain Support

Hreflang works across different domains (e.g., `example.com` and `example.de`).
Cross-domain setups have additional requirements.

**What to check:**

- Return tags exist on both domains (bidirectional across domains).
- Both domains are verified in Google Search Console under the same property
  or linked properties.
- For cross-domain setups, sitemap-based implementation is recommended over
  HTML link tags (easier to maintain, centralized management).
- DNS and hosting are independently functional for all domains.

**Cross-domain patterns:**

| Pattern | Example | Notes |
|---|---|---|
| Country-code TLDs | `example.com`, `example.de`, `example.fr` | Strongest geo-signal, but expensive to maintain |
| Subdomains | `en.example.com`, `de.example.com` | Good balance of signal and maintenance |
| Subdirectories | `example.com/en/`, `example.com/de/` | Easiest to maintain, all under one domain |
| Mixed | `example.com` (English), `example.de` (German) | Common in practice, requires cross-domain hreflang |

**Severity:** Medium for missing cross-domain verification. Critical if return
tags are missing across domains.

---

## Implementation Methods

Three methods exist for implementing hreflang. Choose one method per site --
using multiple methods simultaneously (e.g., HTML tags AND sitemap) is allowed
but not recommended, as it creates maintenance burden and risk of inconsistency.

### Method 1: HTML Link Tags

Place hreflang tags in the `<head>` section of every page. Every page must
include all alternates including itself.

```html
<head>
  <link rel="alternate" hreflang="en-US" href="https://example.com/page" />
  <link rel="alternate" hreflang="en-GB" href="https://example.co.uk/page" />
  <link rel="alternate" hreflang="fr" href="https://example.com/fr/page" />
  <link rel="alternate" hreflang="de" href="https://example.de/page" />
  <link rel="alternate" hreflang="x-default" href="https://example.com/page" />
</head>
```

**Best for:** Sites with fewer than 50 language/region variants per page.

**Advantages:**

- Easy to implement in templates
- Visible in page source for debugging
- Works with any web server

**Disadvantages:**

- Bloats `<head>` section with many variants (10 languages = 10 link tags per
  page)
- Hard to maintain at scale
- Template changes required for every new language
- Server-side rendering required (hreflang in JavaScript-rendered head is
  unreliable)

### Method 2: HTTP Headers

Set hreflang via HTTP response headers. Use for non-HTML resources (PDFs,
downloadable files) or when HTML head modification is impractical.

```
Link: <https://example.com/page>; rel="alternate"; hreflang="en-US",
      <https://example.com/fr/page>; rel="alternate"; hreflang="fr",
      <https://example.de/page>; rel="alternate"; hreflang="de",
      <https://example.com/page>; rel="alternate"; hreflang="x-default"
```

**Best for:** PDFs, documents, and other non-HTML files. Also useful when the
HTML template system cannot be modified.

**Advantages:**

- Works for non-HTML resources
- No HTML modification needed
- Applied at server/CDN level

**Disadvantages:**

- Requires server configuration access (Apache, Nginx, CDN rules)
- Not visible in HTML source (harder to debug)
- Complex to maintain for many URLs
- Header size limits may restrict large hreflang sets

**Server configuration examples:**

Apache (.htaccess):
```apache
<Files "document.pdf">
  Header add Link '<https://example.com/document.pdf>; rel="alternate"; hreflang="en"'
  Header add Link '<https://example.com/fr/document.pdf>; rel="alternate"; hreflang="fr"'
</Files>
```

Nginx:
```nginx
location /document.pdf {
    add_header Link '<https://example.com/document.pdf>; rel="alternate"; hreflang="en"';
    add_header Link '<https://example.com/fr/document.pdf>; rel="alternate"; hreflang="fr"';
}
```

### Method 3: XML Sitemap (Recommended for Large Sites)

Include hreflang annotations directly in the XML sitemap. This is the
recommended method for sites with many language variants, cross-domain setups,
or more than 50 pages.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:xhtml="http://www.w3.org/1999/xhtml">
  <url>
    <loc>https://example.com/page</loc>
    <xhtml:link rel="alternate" hreflang="en-US"
                href="https://example.com/page" />
    <xhtml:link rel="alternate" hreflang="fr"
                href="https://example.com/fr/page" />
    <xhtml:link rel="alternate" hreflang="de"
                href="https://example.de/page" />
    <xhtml:link rel="alternate" hreflang="x-default"
                href="https://example.com/page" />
  </url>
  <url>
    <loc>https://example.com/fr/page</loc>
    <xhtml:link rel="alternate" hreflang="en-US"
                href="https://example.com/page" />
    <xhtml:link rel="alternate" hreflang="fr"
                href="https://example.com/fr/page" />
    <xhtml:link rel="alternate" hreflang="de"
                href="https://example.de/page" />
    <xhtml:link rel="alternate" hreflang="x-default"
                href="https://example.com/page" />
  </url>
</urlset>
```

**Critical rules for sitemap hreflang:**

- Include the `xmlns:xhtml` namespace declaration on the `<urlset>` element.
- Every `<url>` entry must include ALL language alternates (including itself).
- Each language variant must appear as its own `<url>` entry with its own full
  set of `<xhtml:link>` alternates.
- Split at 50,000 URLs per sitemap file (standard sitemap limit).
- Self-referencing and return tag rules still apply within the sitemap.

**Best for:** Sites with 50+ pages, many language variants, or cross-domain
setups.

**Advantages:**

- Scalable -- handles thousands of pages and dozens of languages
- Centralized management -- all hreflang data in one place
- Easier cross-domain implementation (no need to modify templates on each domain)
- No impact on page load (hreflang data is not in the HTML)

**Disadvantages:**

- Not visible on the page (harder to verify without crawling the sitemap)
- Requires sitemap maintenance discipline
- Must keep sitemap hreflang in sync with actual page availability

### Method Comparison

| Factor | HTML Link Tags | HTTP Headers | XML Sitemap |
|---|---|---|---|
| Best for | Small sites (<50 variants) | Non-HTML files | Large sites, cross-domain |
| Scalability | Low | Low | High |
| Maintenance | Template changes | Server config | Sitemap updates |
| Visibility | In HTML source | In response headers | In sitemap file |
| Cross-domain | Supported | Supported | Recommended |
| Debugging | Easy (view source) | Medium (check headers) | Medium (parse sitemap) |

**Recommendation:** Use XML sitemap method for any site with more than 10
language/region variants or more than 100 international pages. Use HTML link
tags for small sites. Use HTTP headers only for non-HTML resources.

---

## Hreflang Generation Process

Follow these steps when generating hreflang tags from scratch.

### Step 1: Detect Languages

Scan the site for language indicators:

- **URL path patterns:** `/en/`, `/fr/`, `/de/` subdirectories
- **Subdomain patterns:** `en.example.com`, `fr.example.com`
- **TLD patterns:** `example.com`, `example.de`, `example.fr`
- **HTML lang attribute:** `<html lang="en-US">`
- **Content-Language header:** `Content-Language: en`
- **Hreflang tags already present** (if partial implementation exists)

Document every detected language with its URL pattern.

### Step 2: Map Page Equivalents

For each page in the primary language, identify its equivalent in every other
language. Build a mapping table:

| Page | en-US | fr | de | es |
|---|---|---|---|---|
| Homepage | `/` | `/fr/` | `/de/` | `/es/` |
| About | `/about` | `/fr/a-propos` | `/de/ueber-uns` | `/es/acerca` |
| Pricing | `/pricing` | `/fr/tarifs` | `/de/preise` | `/es/precios` |
| Blog | `/blog` | `/fr/blog` | `/de/blog` | `/es/blog` |

**Handle missing equivalents:**

- If a page exists in some languages but not others, do not include the missing
  language in that page's hreflang set.
- Do not point hreflang at a generic fallback (e.g., the homepage) when the
  specific page equivalent does not exist.
- Document which pages lack full language coverage for the site owner.

### Step 3: Validate Language and Region Codes

Before generating tags, verify every language/region code against the ISO
standards:

1. Language codes against ISO 639-1 (two-letter).
2. Region codes (if used) against ISO 3166-1 Alpha-2.
3. Script subtags (if needed) against ISO 15924.
4. Flag and correct any invalid codes before proceeding.

### Step 4: Generate Tags

For each page, generate the complete set of hreflang tags including:

- One tag for each language variant (pointing to the exact canonical URL)
- Self-referencing tag (pointing to the current page's canonical URL)
- x-default tag (pointing to the designated fallback)

Generate in the chosen implementation method (HTML, HTTP headers, or sitemap
XML).

### Step 5: Verify Bidirectionality

After generating all tags, verify that every relationship is bidirectional:

1. Build the complete relationship graph.
2. For every directed edge A -> B, verify edge B -> A exists.
3. Flag any missing return tags.
4. The graph must be a complete directed graph (full mesh) for each page set.

### Step 6: Add x-default

For each page set:

1. Designate one URL as x-default (typically the language selector or English
   version).
2. Add x-default to every page's hreflang set.
3. Verify x-default has return tags from all other variants.

### Step 7: Output

Generate the implementation artifacts:

- **HTML method:** Code snippets for each page's `<head>` section.
- **HTTP header method:** Server configuration rules (Apache/Nginx).
- **Sitemap method:** Complete `hreflang-sitemap.xml` file.

Include a validation summary confirming all 8 checks pass on the generated
implementation.

---

## Common Mistakes and Fixes

Quick reference for the most frequent hreflang errors encountered in audits.

| Issue | Severity | How to Identify | Fix |
|---|---|---|---|
| Missing self-referencing tag | Critical | Page has hreflang to others but not itself | Add hreflang tag pointing to the page's own canonical URL |
| Missing return tags (A->B but no B->A) | Critical | Build relationship graph, check for missing edges | Add matching return tags on all alternates |
| Missing x-default | High | No x-default in hreflang set | Add x-default pointing to fallback/selector page |
| `eng` instead of `en` | High | Three-letter language code detected | Replace with ISO 639-1 two-letter code |
| `jp` instead of `ja` | High | Country code used as language code | Use correct ISO 639-1 language code for Japanese |
| `en-uk` instead of `en-GB` | High | Invalid region code | Use ISO 3166-1 Alpha-2: GB for Great Britain |
| `es-LA` (Latin America) | High | Aggregate region used | Use specific country codes (es-MX, es-AR, es-CO) |
| Hreflang on non-canonical URL | High | Page has rel=canonical pointing elsewhere | Move hreflang to the canonical URL only |
| HTTP/HTTPS mismatch in URLs | Medium | Mixed protocols in one hreflang set | Standardize all URLs to HTTPS |
| Trailing slash inconsistency | Medium | Some URLs have trailing slash, others do not | Match the canonical URL format exactly |
| Hreflang in both HTML and sitemap | Low | Duplicate implementation | Choose one method; prefer sitemap for large sites |
| Language without region when needed | Low | Content is region-specific but code is language-only | Add region qualifier when pricing, regulations, or dialect differ |
| `zh` without script subtag | Medium | Chinese content without Hans/Hant qualifier | Use `zh-Hans` or `zh-Hant` to disambiguate |

---

## Output Templates

### Validation Report

Generate an `HREFLANG-VALIDATION.md` report:

**Summary:**

- Total pages scanned: XX
- Language variants detected: XX
- Total hreflang tags found: XX
- Issues found: XX (Critical: X, High: X, Medium: X, Low: X)
- Implementation method: HTML / HTTP headers / Sitemap / Mixed

**Validation Results by Check:**

| Check | Status | Issues Found |
|---|---|---|
| 1. Self-Referencing Tags | Pass/Fail | XX pages missing self-reference |
| 2. Return Tags | Pass/Fail | XX broken return tag pairs |
| 3. x-default | Pass/Fail | XX sets missing x-default |
| 4. Language Codes (ISO 639-1) | Pass/Fail | XX invalid language codes |
| 5. Region Codes (ISO 3166-1) | Pass/Fail | XX invalid region codes |
| 6. Canonical Alignment | Pass/Fail | XX canonical mismatches |
| 7. Protocol Consistency | Pass/Fail | XX protocol mismatches |
| 8. Cross-Domain | Pass/Fail/N/A | XX cross-domain issues |

**Per-Page Results:**

| Language | URL | Self-Ref | Return Tags | x-default | Canonical | Protocol | Status |
|---|---|---|---|---|---|---|---|
| en-US | https://... | Pass | Pass | Pass | Pass | Pass | Pass |
| fr | https://... | Fail | Fail | Pass | Pass | Pass | Fail |

**Issues Detail:**

For each issue, report: page URL, check number, severity, description, and
specific fix.

**Recommendations:**

Prioritized list of fixes, starting with Critical severity.

### Generation Output

When generating hreflang, produce:

1. Implementation code (HTML snippets, server config, or sitemap XML)
2. Language/page mapping table
3. Validation summary confirming all 8 checks pass
4. Migration guide if switching implementation methods

---

## Script Usage

Use the fetch and parse scripts to retrieve pages for hreflang validation.

```
${CLAUDE_PLUGIN_ROOT}/skills/unmassk-seo/scripts/fetch_page.py <url>
${CLAUDE_PLUGIN_ROOT}/skills/unmassk-seo/scripts/parse_html.py <file>
```

The parse script extracts all `<link rel="alternate" hreflang="...">` tags from
the HTML head. For HTTP header-based implementations, inspect the raw response
headers from the fetch script output. For sitemap-based implementations, fetch
and parse the sitemap XML directly.

To validate a complete international site, fetch the homepage of each language
variant, parse hreflang tags from each, and cross-reference the sets for
bidirectional completeness.
