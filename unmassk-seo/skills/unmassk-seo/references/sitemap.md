# Sitemap -- Analysis & Generation Reference

Reference data for auditing existing XML sitemaps and generating new ones.
Covers validation rules, quality gates for programmatic pages, sitemap index
architecture, and penalty risk assessment. Load this file when the user requests
sitemap analysis, sitemap generation, sitemap validation, or site architecture
planning.

---

## Operating Modes

This reference supports two distinct workflows. Determine the correct mode
before proceeding.

### Mode 1: Analyze Existing Sitemap

Use when the site already has a sitemap and the goal is to audit its quality,
find errors, and recommend fixes. Follow the Validation Checks and Quality
Signals sections.

### Mode 2: Generate New Sitemap

Use when the site needs a new sitemap created from scratch or the existing
sitemap requires a complete rebuild. Follow the Generation Process, Quality
Gates, and Safe vs. Risky Page Types sections.

---

## Validation Checks

Apply every check to the target sitemap. Report each check as pass, warning, or
fail with the specific evidence.

### XML Format Validation

1. **Well-formed XML** -- Parse the sitemap with an XML parser. Any parsing
   error is a Critical finding. Common issues: unclosed tags, invalid characters
   (ampersands not encoded as `&amp;`), missing XML declaration, BOM characters.

2. **Correct namespace** -- The root `<urlset>` element must declare the
   sitemaps.org namespace:
   ```xml
   <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
   ```
   Missing or incorrect namespace causes search engines to reject the file.

3. **Valid encoding** -- The XML declaration must specify UTF-8 encoding:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   ```

### URL Count Limit

Each sitemap file must contain fewer than **50,000 URLs** and be no larger than
**50 MB uncompressed**. Exceeding either limit causes search engines to
partially or fully ignore the file.

| Condition | Severity | Action |
|---|---|---|
| URL count < 50,000 | Pass | No action |
| URL count = 50,000 | Warning | Approaching limit, plan split |
| URL count > 50,000 | Critical | Split into multiple files with sitemap index |
| File size > 50 MB | Critical | Split into multiple files with sitemap index |

### lastmod Accuracy

The `<lastmod>` element must reflect the actual last modification date of the
page content. Check for these common problems:

| Problem | Severity | Evidence |
|---|---|---|
| All lastmod dates identical | Low | All dates are the same value (likely auto-generated) |
| lastmod in the future | High | Date is after today's date |
| lastmod older than actual page changes | Medium | Content was visibly updated but lastmod is stale |
| lastmod missing on all URLs | Low | No lastmod elements present (valid but unhelpful) |
| lastmod format invalid | High | Not in W3C datetime format (YYYY-MM-DD or YYYY-MM-DDThh:mm:ssTZD) |

When all lastmod dates are identical, search engines treat them as unreliable
and may ignore them entirely. Recommend using actual page modification dates
from the CMS or file system.

### Deprecated Tags

**`<priority>` and `<changefreq>` are ignored by Google.** Their presence is
not harmful but is misleading -- site owners may believe these values influence
crawl behavior when they do not.

| Tag | Status | Recommendation |
|---|---|---|
| `<priority>` | Deprecated | Remove. Provides no ranking or crawl benefit. |
| `<changefreq>` | Deprecated | Remove. Google uses its own crawl scheduling. |

Report their presence as **Info** severity. Do not flag as an error or require
removal, but recommend cleanup during the next sitemap update.

### URL Status Validation

Every URL in the sitemap must return HTTP 200. Check for:

| HTTP Status | Severity | Action |
|---|---|---|
| 200 | Pass | URL is valid |
| 301/302 (redirect) | Medium | Update sitemap to use the final destination URL |
| 404/410 (not found) | High | Remove from sitemap immediately |
| 403 (forbidden) | High | Fix access or remove from sitemap |
| 500 (server error) | High | Investigate server issue, remove if persistent |
| Timeout | Medium | Verify server performance, re-check later |

### robots.txt Reference

Verify the sitemap is referenced in robots.txt:

```
Sitemap: https://example.com/sitemap.xml
```

Missing robots.txt reference is a **Medium** severity finding. While search
engines can discover sitemaps through Search Console and other signals, the
robots.txt reference ensures all crawlers (not just Google) find the sitemap.

### Sitemap Coverage Analysis

Compare the sitemap against crawled/known pages:

1. **Pages in sitemap but not indexable** -- URLs that return non-200, have
   noindex, or redirect. These waste crawl budget.
2. **Indexable pages not in sitemap** -- Important pages the sitemap is missing.
   Crawl the site or check internal links to identify gaps.
3. **Non-canonical URLs in sitemap** -- URLs that have a `rel=canonical`
   pointing to a different URL. Remove these and include only canonical URLs.
4. **HTTP URLs in sitemap** -- All URLs must use HTTPS. Mixed HTTP/HTTPS in
   the sitemap is a **High** severity issue after HTTPS migration.

---

## Quality Signals

Beyond basic validation, assess the sitemap's architectural quality.

### Sitemap Organization

Well-organized sitemaps split content by type. Evaluate whether the site would
benefit from splitting:

| Content Type | Separate Sitemap | Naming Convention |
|---|---|---|
| Static pages | Yes, for sites with 100+ pages | `sitemap-pages.xml` |
| Blog posts / articles | Yes | `sitemap-posts.xml` |
| Product pages | Yes, for e-commerce | `sitemap-products.xml` |
| Category / collection pages | Yes, for large catalogs | `sitemap-categories.xml` |
| Image sitemaps | Optional | `sitemap-images.xml` |
| Video sitemaps | Optional | `sitemap-videos.xml` |
| Location pages | Yes, if programmatic | `sitemap-locations.xml` |

Recommend splitting when the total URL count exceeds 1,000 or when distinct
content types have different update frequencies.

### Sitemap Index

For sites requiring multiple sitemaps, use a sitemap index file:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap>
    <loc>https://example.com/sitemap-pages.xml</loc>
    <lastmod>2026-02-07</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://example.com/sitemap-posts.xml</loc>
    <lastmod>2026-02-07</lastmod>
  </sitemap>
  <sitemap>
    <loc>https://example.com/sitemap-products.xml</loc>
    <lastmod>2026-02-07</lastmod>
  </sitemap>
</sitemapindex>
```

The sitemap index has the same 50,000 entry and 50 MB limits. Each referenced
sitemap also has its own 50,000 URL limit. The theoretical maximum is
50,000 sitemaps x 50,000 URLs = 2.5 billion URLs per sitemap index.

Reference the sitemap index (not individual sitemaps) in robots.txt:

```
Sitemap: https://example.com/sitemap-index.xml
```

### Compression

Sitemaps can be gzip-compressed (`.xml.gz`). Recommend compression for sitemaps
over 10 MB or sites with bandwidth constraints. Search engines support gzip
sitemaps natively.

---

## Quality Gates for Programmatic Pages

Programmatic SEO generates pages at scale from templates and data. While
powerful, it carries significant penalty risk if the generated pages lack
genuine value.

### Location Page Thresholds

Location pages (city pages, service area pages, "plumber in [city]" pages) are
the highest-risk category for doorway page penalties.

| Threshold | Gate | Action |
|---|---|---|
| < 30 location pages | Pass | Proceed with standard quality checks |
| 30-49 location pages | **WARNING** | Require 60%+ unique content per page. Audit a sample of 5-10 pages for content uniqueness. Flag if pages differ only by city/location name. |
| 50+ location pages | **HARD STOP** | Require explicit justification from the user before proceeding. Document the justification. Audit content uniqueness rigorously. |

### What "60% Unique Content" Means

Compare any two location pages targeting different cities. At least 60% of the
page content (by word count) must be genuinely different -- not just the city
name swapped. Unique content includes:

- City-specific statistics and data
- Local regulations, requirements, or conditions
- References to local landmarks, neighborhoods, or institutions
- City-specific testimonials or case studies
- Locally relevant imagery (not stock photos reused across all pages)

### Doorway Page Algorithm

Google's doorway page algorithm specifically targets programmatic pages designed
to rank for location-specific queries while providing no location-specific
value. Penalties range from individual page suppression to site-wide manual
actions.

**Doorway page signals (triggers penalty risk):**

- Multiple pages targeting different cities with identical template content
- Only the city name, zip code, or state changes between pages
- No genuine local information, reviews, or data
- Pages exist solely to funnel users to a single conversion page
- Thin content (under 300 words of actual non-template text)
- No internal linking from the rest of the site (orphaned pages)

**Not doorway pages (acceptable at scale):**

- Pages with genuinely unique local content, data, and context
- Product pages with unique specifications, reviews, and pricing
- User-generated content pages (profiles, listings)
- Educational content with distinct information per page

### Content Uniqueness Audit

When auditing programmatic pages for sitemap inclusion:

1. Select 5-10 pages from different location/category groups.
2. Compare content pairwise -- calculate the percentage of text that differs.
3. Exclude template elements (header, footer, navigation, sidebar) from the
   comparison.
4. Flag any pair with less than 40% unique content as **thin content risk**.
5. Flag any pair with less than 20% unique content as **doorway page risk**
   (Critical severity).

---

## Safe vs. Risky Programmatic Page Types

### Safe at Scale

These page types can be generated programmatically with acceptable quality when
implemented correctly.

| Page Type | Why It Works | Minimum Requirements |
|---|---|---|
| Integration pages | Each integration has genuinely different setup docs, API details, and use cases | Real setup documentation, screenshots, unique configuration steps |
| Template/tool pages | Each template offers a downloadable or usable asset | Downloadable content, preview, usage instructions |
| Glossary pages | Each term has a unique definition and context | 200+ word definitions with examples, related terms, context |
| Product pages | Each product has unique specs, reviews, pricing | Unique specifications, real reviews, actual pricing, original images |
| User profile pages | Content is user-generated and inherently unique | Sufficient user-generated content to justify indexing |
| Comparison pages | Each comparison addresses a specific matchup | Real comparison data, feature matrices, genuine analysis |

### Risky at Scale (Penalty Prone)

These page types frequently trigger doorway page or thin content penalties.

| Page Type | Why It Fails | Red Flags |
|---|---|---|
| Location pages with city swapping | Only the city name changes; no local value | Identical content across 50+ pages with location token replacement |
| "Best [tool] for [industry]" | No industry-specific analysis or data | Generic content with industry name injected into template |
| "[Competitor] alternative" | No real comparison data or unique insight | Template content with competitor name swapped in |
| AI-generated mass content | No human review, no unique value, no expertise | Thousands of pages published simultaneously with formulaic content |
| Tag/taxonomy pages | Thin aggregation with no editorial value | Auto-generated pages for every possible tag combination |

### Decision Framework for Including Programmatic Pages in Sitemap

Ask these questions for each programmatic page type:

1. **Would a human visitor find this page useful?** If the page exists only for
   search engines, do not include it.
2. **Does this page contain information not available on other pages of the
   site?** If it duplicates another page with minor variations, do not include.
3. **Is there at least 300 words of non-template content?** Below this threshold,
   the page is likely too thin to index.
4. **Does the page have internal links from the rest of the site?** Orphaned
   programmatic pages signal low value.

If any answer is "no," recommend excluding the page type from the sitemap and
adding `noindex` to those pages.

---

## Generation Process

Follow these steps when creating a new sitemap.

### Step 1: Inventory

Catalog all indexable pages on the site. Sources:

- Crawl the site following internal links
- Check the CMS for published pages
- Review existing sitemaps (if any)
- Check Google Search Console for indexed pages
- Review the site's navigation and footer links

### Step 2: Classify

Group pages by content type (pages, posts, products, locations, etc.). This
determines sitemap organization.

### Step 3: Filter

Remove from the sitemap candidate list:

- Pages with `noindex` directives
- Non-canonical URLs (include only the canonical version)
- Redirect URLs (include only the final destination)
- Login-required pages
- Paginated pages (include page 1 only, or use `rel=next/prev`)
- Parameter variations of the same page
- Utility pages (privacy policy, terms of service -- include but deprioritize)

### Step 4: Apply Quality Gates

For programmatic page types, apply the location page thresholds and content
uniqueness checks described above. Block inclusion of pages that fail quality
gates.

### Step 5: Generate XML

Produce valid XML with proper namespace, UTF-8 encoding, and accurate lastmod
dates. Use the standard sitemap format:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/page</loc>
    <lastmod>2026-02-07</lastmod>
  </url>
</urlset>
```

Do not include `<priority>` or `<changefreq>` tags. They are deprecated and
ignored.

### Step 6: Split if Needed

If the total URL count exceeds 10,000, recommend splitting by content type with
a sitemap index. If it exceeds 50,000, splitting is mandatory.

### Step 7: Document

Generate a `STRUCTURE.md` file documenting:

- Total URL count per sitemap file
- Content type breakdown
- Quality gate results (especially for programmatic pages)
- Pages excluded and reasons
- Recommendations for ongoing maintenance

---

## Sitemap Maintenance

Sitemaps are not set-and-forget. Provide these ongoing maintenance
recommendations.

### Automated Updates

Recommend CMS plugins or build pipeline integration that automatically updates
the sitemap when pages are published, modified, or deleted. Manual sitemap
maintenance degrades over time.

### Regular Audits

| Check | Frequency | What to Look For |
|---|---|---|
| URL status codes | Monthly | New 404s, redirects, server errors |
| New pages missing from sitemap | Monthly | Published content not in sitemap |
| Removed pages still in sitemap | Monthly | Deleted or noindexed pages lingering |
| lastmod accuracy | Quarterly | Dates drifting from actual modification times |
| Total URL count | Quarterly | Approaching 50,000 limit |

### IndexNow Integration

For sites on Bing, Yandex, or other IndexNow-compatible search engines,
recommend implementing IndexNow to push new and updated URLs in real time
rather than waiting for crawlers to discover sitemap changes.

---

## Common Issues Table

Quick reference for all validation findings.

| Issue | Severity | Fix |
|---|---|---|
| Invalid XML (parse error) | Critical | Fix syntax errors, encode special characters |
| >50,000 URLs in single file | Critical | Split with sitemap index |
| URLs returning 404/410 | High | Remove from sitemap |
| noindexed URLs in sitemap | High | Remove from sitemap |
| Non-canonical URLs in sitemap | High | Replace with canonical URLs |
| HTTP URLs (not HTTPS) | High | Update all URLs to HTTPS |
| Redirected URLs (301/302) | Medium | Update to final destination URL |
| Not referenced in robots.txt | Medium | Add Sitemap: directive to robots.txt |
| All identical lastmod dates | Low | Use actual modification dates |
| priority/changefreq present | Info | Remove deprecated tags |
| No lastmod at all | Info | Add accurate lastmod dates |

---

## Output Templates

### For Analysis Mode

Generate a `SITEMAP-VALIDATION.md` report:

1. **Summary** -- total URLs, file count, index present, robots.txt reference
2. **Validation Results** -- pass/warning/fail for each check
3. **URL Status Breakdown** -- count by HTTP status code
4. **Coverage Analysis** -- missing pages, extra pages, non-canonical inclusions
5. **Quality Gate Results** -- programmatic page assessment if applicable
6. **Issues Table** -- all findings sorted by severity
7. **Recommendations** -- prioritized action items

### For Generation Mode

Produce:

1. `sitemap.xml` (or split files with `sitemap-index.xml`)
2. `STRUCTURE.md` documenting the site architecture and sitemap contents
3. Summary of URL counts, content type breakdown, and quality gate results

---

## Script Usage

Use the fetch script to retrieve existing sitemaps for analysis.

```
${CLAUDE_PLUGIN_ROOT}/skills/unmassk-seo/scripts/fetch_page.py <sitemap-url>
```

For sitemap generation, use the fetch and parse scripts to crawl key pages and
identify internal link structure.

```
${CLAUDE_PLUGIN_ROOT}/skills/unmassk-seo/scripts/fetch_page.py <url>
${CLAUDE_PLUGIN_ROOT}/skills/unmassk-seo/scripts/parse_html.py <file>
```

The parse script extracts internal links from each page, which can be used to
build a crawl-based page inventory for sitemap generation.
