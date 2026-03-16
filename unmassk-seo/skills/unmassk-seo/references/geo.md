# GEO -- Generative Engine Optimization Reference

Reference data for analyzing and optimizing content for AI-powered search
experiences: Google AI Overviews, ChatGPT web search, Perplexity, and Bing
Copilot. Load this file when the user requests GEO analysis, AI search
optimization, AI visibility checks, or AI Overviews readiness.

---

## Market Context

AI search is no longer experimental. These platforms now serve billions of
queries and reshape how users discover content.

| Platform | Scale | Key Behavior |
|---|---|---|
| Google AI Overviews | 1.5 billion users/month across 200+ countries, 50%+ query coverage | Cites from top-10 ranking pages (92%), but 47% of citations come from pages ranking below position 5 |
| ChatGPT web search | 900 million weekly active users | Cites Wikipedia (47.9%), Reddit (11.3%), authoritative domains |
| Perplexity | 500+ million monthly queries | Cites Reddit (46.7%), Wikipedia, community-validated sources |
| Bing Copilot | Integrated into Edge and Windows | Draws from Bing index, prefers IndexNow-enabled sites |

AI-referred sessions grew 527% between January and May 2025 (SparkToro data).
Only 11% of domains are cited by both ChatGPT and Google AI Overviews for the
same query. Platform-specific optimization is not optional -- each AI engine
selects sources differently.

---

## GEO Health Score (0-100)

Compute each dimension as 0-100, multiply by weight, and sum.

| Dimension | Weight | What It Measures |
|---|---|---|
| Citability | 25% | Passage structure, directness, data density, extractability |
| Structural Readability | 20% | Heading hierarchy, formatting, scannable layout |
| Multi-Modal Content | 15% | Images, video, infographics, interactive elements |
| Authority & Brand Signals | 20% | Authorship, dates, citations, entity presence across platforms |
| Technical Accessibility | 20% | SSR, AI crawler access, llms.txt, RSL licensing |

Report the aggregate score and each dimension score separately. Flag any
dimension scoring below 40 as a critical gap.

---

## Dimension 1: Citability (25%)

### Optimal Passage Length

The ideal passage length for AI citation is **134-167 words**. Passages in this
range are long enough to convey a complete answer and short enough for AI engines
to extract without truncation. Measure the word count of each major content block
and flag passages that fall outside this range.

### Strong Citability Signals

Evaluate content for these characteristics. Each present signal strengthens the
likelihood of AI citation:

- **Direct answer in the first 40-60 words** of each section. AI engines favor
  content that leads with the answer rather than building up to it.
- **Self-contained answer blocks** that can be extracted without surrounding
  context. If a passage requires reading the previous paragraph to make sense,
  it is weakly citable.
- **Specific statistics with source attribution.** "Revenue grew 34% in Q3 2025
  (SEC filing)" is strongly citable. "Revenue grew significantly" is not.
- **Definition patterns** following "X is..." or "X refers to..." structures.
  AI engines extract definitions at high rates.
- **Claims with named sources.** "According to [Study/Organization], [claim]"
  is extractable. Unsourced claims are not.
- **Unique data points** not available on competing pages. Original research,
  proprietary survey results, and first-party data create exclusive citability.
- **Clear, quotable sentences** with concrete facts. Brevity and precision
  increase extraction probability.

### Weak Citability Signals

Flag these as deficiencies:

- Vague or general statements without specifics
- Opinions stated without supporting evidence
- Conclusions buried deep in long paragraphs
- Absence of data points, statistics, or named sources
- Passages that depend on prior context to be understood
- Marketing language without factual substance

### Passage-Level Analysis

When auditing a page, identify every content block and evaluate:

1. Word count (target: 134-167 words)
2. Does it open with a direct answer?
3. Is it self-contained (extractable)?
4. Does it contain at least one specific fact, statistic, or attributed claim?
5. Could an AI engine quote it verbatim as a useful answer?

Report each passage with a pass/fail assessment. Highlight the top 3 passages
with highest citability and the bottom 3 that need rewriting.

---

## Dimension 2: Structural Readability (20%)

AI engines parse document structure to identify relevant sections. Well-
structured content is selected at significantly higher rates.

### Heading Hierarchy

Verify a clean H1 > H2 > H3 hierarchy with no skipped levels. Flag:

- Multiple H1 tags (only one H1 per page)
- Skipped levels (H1 directly to H3)
- Non-descriptive headings ("More Info", "Details")
- Excessively long headings (over 70 characters)

### Question-Based Headings

Question-format H2 and H3 headings (e.g., "What is GEO?", "How does AI
citation work?") match query patterns that AI engines use for source selection.
Recommend converting at least 40% of H2/H3 headings to question format where
the content supports it naturally.

### Content Formatting

Evaluate the presence and quality of:

- **Short paragraphs** (2-4 sentences). Walls of text reduce selection rates.
- **Tables** for comparative data. AI engines extract tabular data at high rates.
- **Ordered lists** for step-by-step processes.
- **Unordered lists** for multi-item collections.
- **FAQ sections** with clear question-answer pairing. Note: FAQPage schema no
  longer generates Google rich results for commercial sites (restricted August
  2023), but FAQ content structure still benefits AI citation and LLM
  comprehension.
- **Bold/emphasis** on key terms within paragraphs to aid scanning.

### What 92% Means

92% of AI Overview citations come from pages ranking in the top 10, but the
selection logic differs from traditional ranking. A page at position 8 with
excellent structure can be cited over a position 1 page with poor formatting.
Structure is the differentiator among already-ranking pages.

---

## Dimension 3: Multi-Modal Content (15%)

Content with multi-modal elements sees **156% higher selection rates** for AI
citation compared to text-only pages.

### Elements to Check

- **Relevant images** with descriptive alt text (not decorative stock photos)
- **Embedded video** content (YouTube, Vimeo, or self-hosted)
- **Infographics and charts** that visualize data points
- **Interactive elements** such as calculators, tools, or configurators
- **Structured data** supporting media (ImageObject, VideoObject schema)

### Scoring Guidance

| Multi-Modal Elements Present | Score Range |
|---|---|
| Text only, no media | 0-20 |
| Images present but generic/decorative | 20-40 |
| Relevant images with good alt text | 40-60 |
| Images + video or infographics | 60-80 |
| Images + video + interactive elements + supporting schema | 80-100 |

Recommend adding at least one relevant, non-decorative image per major section
and at least one video or interactive element per page for GEO purposes.

---

## Dimension 4: Authority & Brand Signals (20%)

### Brand Mentions vs. Backlinks

Brand mentions correlate 3x more strongly with AI visibility than traditional
backlinks (Ahrefs December 2025 study of 75,000 brands).

| Signal | Correlation with AI Citations | Priority |
|---|---|---|
| YouTube mentions | ~0.737 (strongest single signal) | Critical |
| Reddit mentions | High | High |
| Wikipedia presence | High | High |
| LinkedIn presence | Moderate | Medium |
| Domain Rating (backlinks) | ~0.266 (comparatively weak) | Low for GEO |

### On-Page Authority Signals

Check every audited page for:

- **Author byline with credentials.** Named author with professional title,
  relevant expertise, and links to professional profiles (LinkedIn, institutional
  page). Anonymous content scores near zero.
- **Publication date and last-updated date.** Both must be present and accurate.
  Stale content (last updated >12 months ago) receives reduced citation
  probability.
- **Citations to primary sources.** Links to academic studies, official
  documentation, regulatory filings, and original data. Self-referential linking
  does not count.
- **Organization credentials.** About page, institutional affiliations, awards,
  certifications, industry memberships.
- **Expert quotes with attribution.** Named experts with titles and affiliations.

### Entity Presence Audit

Check brand/author presence across these platforms:

1. **Wikipedia** -- Does the brand or primary author have a Wikipedia article?
   Is the article well-maintained and accurate?
2. **Wikidata** -- Is there a Wikidata entity with proper claims and sameAs
   links?
3. **Reddit** -- Is the brand mentioned in relevant subreddits? Are mentions
   positive, neutral, or negative?
4. **YouTube** -- Does the brand have a YouTube channel? Are there third-party
   videos mentioning the brand?
5. **LinkedIn** -- Do key authors have complete LinkedIn profiles with published
   content?

Report presence/absence for each platform with actionable recommendations for
gaps.

### Schema Support for Authority

Recommend implementing these schema types to reinforce authority signals:

- `Person` schema for authors (with `sameAs` links to Wikipedia, LinkedIn,
  Twitter)
- `Organization` schema (with `sameAs` links to all verified social profiles)
- `Article` or `BlogPosting` schema with `author`, `datePublished`,
  `dateModified`
- `WebPage` schema with `speakable` property for voice search optimization

---

## Dimension 5: Technical Accessibility (20%)

### Server-Side Rendering

**AI crawlers do NOT execute JavaScript.** Content loaded via client-side
JavaScript is invisible to GPTBot, ClaudeBot, PerplexityBot, and all other AI
crawlers. This is the single most common technical failure in GEO audits.

Check for:

- Server-side rendering (SSR) or static site generation (SSG) for all critical
  content
- Content visible in the raw HTML response (curl the page and verify)
- No critical content behind JavaScript hydration, lazy-loading triggers, or
  "read more" accordions
- Meta tags (title, description, canonical, hreflang) rendered server-side

If the site uses a JavaScript framework (React, Vue, Angular, Next.js, Nuxt),
verify that SSR or SSG is configured and that the HTML response contains the
full content without client-side rendering.

### AI Crawler Access

Check `robots.txt` for explicit rules targeting AI crawlers.

| Crawler | Owner | Purpose | Recommendation |
|---|---|---|---|
| GPTBot | OpenAI | ChatGPT web search | Allow (critical for ChatGPT visibility) |
| OAI-SearchBot | OpenAI | OpenAI search features | Allow |
| ChatGPT-User | OpenAI | ChatGPT browsing mode | Allow |
| ClaudeBot | Anthropic | Claude web features | Allow |
| PerplexityBot | Perplexity | Perplexity AI search | Allow |
| CCBot | Common Crawl | Training data collection | Optional block (does not affect search) |
| anthropic-ai | Anthropic | Claude training | Optional block (does not affect search) |
| Bytespider | ByteDance | TikTok/Douyin AI | Block unless targeting Chinese market |
| cohere-ai | Cohere | Cohere model training | Optional block |

**Recommendation:** Allow GPTBot, OAI-SearchBot, ClaudeBot, and PerplexityBot
for AI search visibility. Blocking these crawlers directly prevents citation by
their respective platforms. Blocking CCBot, anthropic-ai, and cohere-ai is
acceptable if the goal is to prevent training data usage without losing search
visibility.

Report each crawler with its current status (allowed, blocked, not mentioned)
and flag any visibility-critical crawler that is blocked.

Note: blocking Google-Extended in robots.txt prevents Gemini training but does
NOT affect Google Search indexing or AI Overviews.

### llms.txt Standard

The **llms.txt** standard provides AI crawlers with a structured content guide
at the root of a domain. Check for `/llms.txt` at the site root.

**Expected location:** `https://example.com/llms.txt`

**Expected format:**

```
# Site Title
> Brief site description

## Main Sections
- [Page Title](url): Description of page content
- [Another Page](url): Description of content

## Key Facts
- Important fact 1
- Important fact 2
```

**Validation checklist:**

1. File exists at domain root
2. Contains a descriptive site title and summary
3. Lists key pages with URLs and descriptions
4. Includes important facts and contact/authority information
5. Uses valid Markdown formatting
6. Is accessible to AI crawlers (not blocked by robots.txt)

If `/llms.txt` is missing, recommend creating one. Provide a draft based on the
site's primary pages and content themes identified during the audit.

### RSL 1.0 (Really Simple Licensing)

RSL 1.0 (December 2025) is a machine-readable standard for declaring AI
licensing terms. Backed by Reddit, Yahoo, Medium, Quora, Cloudflare, Akamai,
and Creative Commons.

Check for RSL implementation. If present, verify the licensing terms are
appropriate for the site's AI visibility goals. If absent, note as a low-
priority recommendation -- RSL adoption is still early but growing.

---

## Platform-Specific Optimization

Each AI platform selects sources differently. After computing the aggregate GEO
score, provide platform-specific assessments.

### Google AI Overviews

- **Reach:** 1.5 billion users/month, 200+ countries
- **Source selection:** 92% from top-10 ranking pages. Strong traditional SEO is
  the prerequisite.
- **Optimization focus:** Passage-level structure, direct answers, question-based
  headings, server-side rendering, featured snippet-style formatting.
- **Key insight:** Pages ranking below position 5 account for 47% of citations.
  Structure and citability can overcome ranking position.

### ChatGPT Web Search

- **Reach:** 900 million weekly active users
- **Source selection:** Wikipedia (47.9%), Reddit (11.3%), authoritative domains
  with strong entity presence.
- **Optimization focus:** Entity presence on Wikipedia and Reddit, author
  credentials, primary source citations, factual density.
- **Key insight:** ChatGPT strongly favors entity-rich, encyclopedic content.
  Brand mentions matter more than backlinks.

### Perplexity

- **Source selection:** Reddit (46.7%), Wikipedia, community-validated sources.
- **Optimization focus:** Community presence, discussion-validated claims,
  original research, data-backed content.
- **Key insight:** Perplexity weighs community validation signals. Positive
  Reddit threads and forum discussions about a brand or topic significantly
  increase citation probability.

### Bing Copilot

- **Source selection:** Bing index, authoritative sites, IndexNow-enabled domains.
- **Optimization focus:** Bing SEO fundamentals, IndexNow implementation for
  fast content discovery, structured data, Bing Webmaster Tools verification.
- **Key insight:** Sites using IndexNow get content indexed faster in Bing,
  which flows through to Copilot citations.

---

## MCP Tool Integration

If DataForSEO MCP tools are available, use them to enrich GEO analysis with
live data. Do not assume MCP availability -- check first.

### Available MCP Tools for GEO

| Tool | Purpose | When to Use |
|---|---|---|
| `ai_optimization_chat_gpt_scraper` | Scrape what ChatGPT web search returns for target queries | Verify actual ChatGPT visibility for the site's primary keywords |
| `ai_opt_llm_ment_search` | Track LLM mentions of the brand across AI platforms | Measure brand mention frequency and sentiment across AI engines |
| `ai_opt_llm_ment_top_domains` | Identify top cited domains for target queries | Benchmark against competitors in AI citation rankings |

### MCP Usage Workflow

1. **Check availability** -- verify MCP tools are configured before calling.
2. **ChatGPT visibility check** -- use `ai_optimization_chat_gpt_scraper` with
   the site's top 5-10 target keywords. Record which queries return citations
   to the site and which do not.
3. **LLM mention tracking** -- use `ai_opt_llm_ment_search` with the brand name
   and primary product/service terms. Record mention frequency and context.
4. **Competitive benchmarking** -- use `ai_opt_llm_ment_top_domains` for the
   site's primary keywords. Identify which domains are being cited instead.
5. **Cross-reference** -- compare MCP data with on-page analysis. If the page
   has strong citability signals but low actual citations, the gap is likely
   in authority/brand signals or technical accessibility.

---

## Quick Wins (Low Effort, High Impact)

Recommend these first. Each can be implemented in under 2 hours.

1. Add a "What is [topic]?" definition in the first 60 words of key pages.
2. Restructure existing content into 134-167 word self-contained answer blocks.
3. Convert flat headings to question-based H2/H3 format.
4. Add specific statistics with source attribution to existing claims.
5. Add publication date and last-updated date to all content pages.
6. Implement Person schema for content authors with sameAs links.
7. Allow GPTBot, OAI-SearchBot, ClaudeBot, and PerplexityBot in robots.txt.

## Medium Effort Improvements

Recommend after quick wins are implemented.

1. Create `/llms.txt` with structured content guidance for AI crawlers.
2. Add author bios with professional credentials, Wikipedia links, and LinkedIn
   profiles.
3. Verify and fix server-side rendering for all critical content.
4. Build entity presence on Reddit and YouTube through genuine participation.
5. Add comparison tables with specific data points to key pages.
6. Implement FAQ content sections (structured Q&A format, not relying on
   FAQPage schema for rich results).

## High Impact Investments

Recommend for long-term GEO strategy.

1. Create original research, surveys, or proprietary data sets that produce
   unique, exclusively citable content.
2. Build Wikipedia presence for the brand and key personnel (following Wikipedia
   notability guidelines).
3. Establish a YouTube channel with content that naturally mentions the brand
   and key topics.
4. Implement comprehensive entity linking with sameAs properties across all
   verified platforms.
5. Develop unique interactive tools or calculators that attract citations and
   backlinks.

---

## Output Template

Generate a `GEO-ANALYSIS.md` report with this structure:

1. **GEO Readiness Score: XX/100** with dimension breakdown table
2. **Platform Breakdown** -- individual scores for Google AIO, ChatGPT,
   Perplexity, and Bing Copilot
3. **AI Crawler Access Status** -- per-crawler allowed/blocked table
4. **llms.txt Status** -- present, missing, or malformed with recommendations
5. **Brand Mention Analysis** -- presence on Wikipedia, Reddit, YouTube,
   LinkedIn with evidence
6. **Passage-Level Citability** -- audit of content blocks against the 134-167
   word optimal range, with top/bottom passages identified
7. **Server-Side Rendering Check** -- JavaScript dependency analysis with
   specific findings
8. **Top 5 Highest-Impact Changes** -- prioritized by effort vs. impact
9. **Schema Recommendations** -- for AI discoverability (Person, Organization,
   Article, speakable)
10. **Content Reformatting Suggestions** -- specific passages to rewrite with
    before/after guidance

---

## Script Usage

Use the fetch and parse scripts to retrieve page content for GEO analysis.

```
${CLAUDE_PLUGIN_ROOT}/skills/unmassk-seo/scripts/fetch_page.py <url>
${CLAUDE_PLUGIN_ROOT}/skills/unmassk-seo/scripts/parse_html.py <file>
```

After fetching and parsing, check robots.txt manually:

```
${CLAUDE_PLUGIN_ROOT}/skills/unmassk-seo/scripts/fetch_page.py <domain>/robots.txt
```

Inspect the raw HTML output for SSR verification -- content must be present in
the initial response without JavaScript execution.
