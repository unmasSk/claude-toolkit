# Strategic SEO Planning -- Reference

Comprehensive SEO strategy planning for new or existing websites. Covers
industry-specific templates, competitive analysis, content strategy,
site architecture design, and phased implementation roadmaps. Use this
reference when the user says "SEO plan", "SEO strategy", "content strategy",
"site architecture", "SEO roadmap", or requests a strategic plan for a
website.

---

## Planning Process

Execute these phases in order. Each phase builds on the output of the
previous phase.

### Phase 1 -- Discovery

Gather foundational information before designing the strategy.

1. **Business type**: Identify the business model to select the correct
   industry template (SaaS, e-commerce, local service, publisher, agency,
   or generic). Use signals from the homepage:
   - SaaS: pricing page, /features, /integrations, /docs, "free trial"
   - E-commerce: /products, /collections, /cart, "add to cart", Product schema
   - Local service: phone number, address, service area, "serving [city]"
   - Publisher: /blog, /articles, /topics, Article schema, author pages
   - Agency: /case-studies, /portfolio, /industries, "our work", client logos
2. **Target audience**: Define primary and secondary audience segments.
3. **Competitors**: Identify top 5 organic competitors (not just business
   competitors -- sites ranking for the same keywords).
4. **Goals**: Define measurable objectives (traffic targets, conversion
   goals, ranking targets, revenue from organic).
5. **Current state**: If the site exists, assess current organic performance,
   indexed pages, keyword rankings, and technical health.
6. **Budget and timeline**: Understand resource constraints that affect
   strategy scope and phase durations.
7. **Key performance indicators (KPIs)**: Define the metrics that will
   measure success at each phase.

### Phase 2 -- Competitive Analysis

Analyze the top 5 competitors to identify gaps and opportunities.

1. **Content strategy analysis**: Map competitor content types, publishing
   frequency, content depth, and topic coverage.
2. **Schema usage**: Identify which schema types competitors implement and
   whether they have rich results.
3. **Technical setup**: Evaluate competitor page speed, mobile experience,
   URL structure, and site architecture.
4. **Keyword gaps**: Identify keywords competitors rank for that the target
   site does not.
5. **Content opportunities**: Identify topics competitors have not covered
   or have covered poorly.
6. **E-E-A-T signals**: Assess competitor author pages, credentials,
   editorial policies, and trust signals.
7. **Domain authority estimation**: Gauge competitor link profiles and
   domain strength.

### Phase 3 -- Architecture Design

Design the site structure based on the industry template and competitive
analysis.

1. Load the appropriate industry template (see Industry Templates below).
2. Design URL hierarchy and content pillars based on the template.
3. Plan internal linking strategy (hub/spoke model for content clusters).
4. Design sitemap structure with quality gates applied.
5. Map information architecture to user journeys (awareness, consideration,
   decision).
6. Identify programmatic page opportunities (see `references/programmatic.md`
   for scale guidelines).

### Phase 4 -- Content Strategy

Define the content plan that fills gaps identified in competitive analysis.

1. **Content gap analysis**: Map content the target site needs vs what
   competitors have.
2. **Page types and counts**: Estimate the number of pages needed per type
   (service pages, blog posts, landing pages, comparison pages).
3. **Publishing cadence**: Define realistic publishing frequency based on
   available resources.
4. **E-E-A-T building plan**: Define how to demonstrate experience,
   expertise, authoritativeness, and trustworthiness (author bios,
   credentials, case studies, original research).
5. **Content calendar**: Prioritize content creation by expected impact
   and resource requirements.

### Phase 5 -- Technical Foundation

Define the technical requirements for the SEO strategy.

1. **Hosting and performance**: CDN, caching, server response time targets.
2. **Schema markup plan**: Define which schema types apply to each page type
   (see the industry template for recommendations).
3. **Core Web Vitals targets**: LCP <=2.5s, INP <=200ms, CLS <=0.1.
4. **AI search readiness**: GEO optimization requirements (see
   `references/geo.md`), llms.txt, structured data for AI citability.
5. **Mobile-first**: All content and functionality must work on mobile. Google
   uses mobile-first indexing exclusively (100% complete July 5, 2024).

---

## Implementation Roadmap -- 4 Phases

### Phase 1 -- Foundation (Weeks 1-4)

**Objective**: Establish technical infrastructure and core pages.

**Actions:**
- Set up or verify hosting, CDN, and caching configuration.
- Implement HTTPS, robots.txt, and XML sitemap.
- Verify Google Search Console and analytics tracking.
- Create or optimize core pages: homepage, about, contact, main service/product
  pages.
- Implement essential schema markup (Organization, WebSite, and page-type-specific
  schema).
- Set up Core Web Vitals monitoring.
- Configure mobile-first responsive design.
- Establish URL convention and redirect strategy.

**Deliverables**: Technical foundation verified, core pages live, schema
implemented, analytics tracking confirmed.

### Phase 2 -- Expansion (Weeks 5-12)

**Objective**: Build out content and establish topical authority.

**Actions:**
- Create content for primary product/service pages.
- Launch blog or resource section with initial posts (target 2-4 posts/month).
- Build internal linking structure connecting core pages, blog, and resources.
- Set up local SEO elements (if applicable): Google Business Profile, NAP
  consistency, local schema.
- Create comparison and alternatives pages for key competitors (see
  `references/competitor.md`).
- Implement breadcrumb navigation and BreadcrumbList schema.
- Begin building E-E-A-T signals: author pages, credentials, editorial policy.

**Deliverables**: Primary content published, blog launched, internal linking
live, local SEO configured.

### Phase 3 -- Scale (Weeks 13-24)

**Objective**: Accelerate content production and build authority.

**Actions:**
- Develop advanced content: in-depth guides, original research, case studies.
- Launch programmatic page sets if applicable (follow
  `references/programmatic.md` guidelines).
- Begin link building and outreach campaign.
- Implement GEO optimization (see `references/geo.md`).
- Optimize Core Web Vitals based on real user data.
- Expand comparison content and roundup pages.
- Build content clusters around primary topic pillars.
- Monitor and optimize based on ranking data and traffic analytics.

**Deliverables**: Advanced content published, link building active, GEO
optimized, programmatic pages launched.

### Phase 4 -- Authority (Months 7-12)

**Objective**: Establish domain authority and thought leadership.

**Actions:**
- Publish thought leadership content: original research, industry analysis,
  expert interviews.
- Pursue PR and media mentions for brand authority signals.
- Implement advanced schema types (Product, SoftwareApplication, etc.) based
  on page type evolution.
- Continuous optimization: update existing content, improve underperforming
  pages, expand successful topics.
- Monitor AI citation across Google AI Overviews, ChatGPT, and Perplexity.
- Conduct quarterly content audits to prune or consolidate thin content.
- Review and update competitive analysis quarterly.

**Deliverables**: Thought leadership published, media mentions acquired,
continuous optimization in place, quarterly review cadence established.

---

## KPI Tracking Template

| Metric | Baseline | 3 Month | 6 Month | 12 Month |
|--------|----------|---------|---------|----------|
| Organic Traffic | ... | ... | ... | ... |
| Keyword Rankings (top 10) | ... | ... | ... | ... |
| Keyword Rankings (top 3) | ... | ... | ... | ... |
| Domain Authority | ... | ... | ... | ... |
| Indexed Pages | ... | ... | ... | ... |
| Core Web Vitals (passing) | ... | ... | ... | ... |
| Conversion Rate (organic) | ... | ... | ... | ... |
| Backlinks (referring domains) | ... | ... | ... | ... |
| AI Citation Frequency | ... | ... | ... | ... |

Set realistic targets based on competitive analysis and current baseline.
Targets must be measurable and time-bound.

### Success Criteria

- Clear, measurable goals defined for each phase.
- Resource requirements documented (writers, developers, designers).
- Dependencies identified (e.g., CMS migration blocks URL changes).
- Risk mitigation strategies for each major initiative.
- Rollback plans for technical changes.

---

## Industry Templates

Select the template matching the detected business type. If the business
does not fit a specific template, use the Generic template.

---

### SaaS Template

#### Industry Characteristics

- Long sales cycles with multiple touchpoints.
- Feature-focused decision making.
- Comparison shopping behavior.
- Heavy research phase before purchase.
- Integration and ecosystem considerations.

#### Recommended Site Architecture

```
/
+-- Home
+-- /product (or /platform)
|   +-- /features
|   |   +-- /feature-1
|   |   +-- /feature-2
|   +-- /integrations
|   |   +-- /integration-1
|   +-- /security
+-- /solutions
|   +-- /by-industry
|   |   +-- /industry-1
|   +-- /by-use-case
|       +-- /use-case-1
+-- /pricing
+-- /customers
|   +-- /case-studies
|   |   +-- /case-study-1
|   +-- /testimonials
+-- /resources
|   +-- /blog
|   +-- /guides
|   +-- /webinars
|   +-- /templates
|   +-- /glossary
+-- /docs (or /help)
|   +-- /api
+-- /company
|   +-- /about
|   +-- /careers
|   +-- /press
|   +-- /contact
+-- /compare
    +-- /vs-competitor-1
    +-- /vs-competitor-2
```

#### Content Priorities

**High priority pages:**
1. Homepage (value proposition, social proof).
2. Features overview.
3. Pricing page.
4. Key integrations.
5. Top 3-5 use case pages.

**Medium priority pages:**
1. Individual feature pages.
2. Industry solution pages.
3. Case studies (2-3 detailed ones).
4. Comparison pages (vs competitors).

**Content marketing focus:**
1. Bottom-of-funnel: Comparison guides, ROI calculators.
2. Middle-of-funnel: How-to guides, best practices.
3. Top-of-funnel: Industry trends, educational content.

#### Schema Recommendations

| Page Type | Schema Types |
|-----------|-------------|
| Homepage | Organization, WebSite, SoftwareApplication |
| Product/Features | SoftwareApplication, Offer |
| Pricing | SoftwareApplication, Offer (with pricing) |
| Blog | Article, BlogPosting |
| Case Studies | Article, Organization (customer) |
| Documentation | TechArticle |

#### Key Metrics

- Organic traffic to pricing page.
- Demo/trial signups from organic.
- Blog to pricing page conversion.
- Comparison page rankings.
- Integration page performance.

#### Comparison Pages (SaaS-Specific)

Comparison pages are among the highest-converting content types for SaaS,
with conversion rates of 4-7% vs 0.5-1.8% for standard blog content.

**Recommended page types:**
- `/{product}-vs-{competitor}` -- Direct 1:1 comparison.
- `/{competitor}-alternative` -- Targeting competitor brand searches.
- `/compare/{category}` -- Category comparison hub.
- `/best-{category}-tools` -- Roundup-style pages.

**Best practices:**
- Include structured comparison tables with pricing, features, pros/cons.
- Be factually accurate about competitors -- verify claims regularly.
- Include customer testimonials from users who switched.
- Update regularly -- stale comparison data damages credibility.
- Cross-reference `references/competitor.md` for detailed frameworks.

**Legal considerations:**
- Nominative fair use generally permits competitor brand mentions for
  comparison purposes.
- Do NOT imply endorsement or affiliation.
- Do NOT make false or unverifiable claims about competitor products.

#### GEO Checklist (SaaS)

- [ ] Include clear, structured feature comparisons AI systems can parse and cite.
- [ ] Use SoftwareApplication schema with complete feature lists and pricing.
- [ ] Publish original benchmark data, case studies, and ROI metrics.
- [ ] Build content clusters around key product categories and use cases.
- [ ] Ensure integration pages have clear, quotable descriptions.
- [ ] Structure pricing information in tables AI can extract.
- [ ] Monitor AI citation across Google AI Overviews, ChatGPT, and Perplexity.

---

### E-commerce Template

#### Industry Characteristics

- High transaction intent.
- Product comparison behavior.
- Price sensitivity.
- Visual-first decision making.
- Seasonal demand patterns.
- Competitive marketplace listings.

#### Recommended Site Architecture

```
/
+-- Home
+-- /collections (or /categories)
|   +-- /category-1
|   |   +-- /subcategory-1
|   +-- /category-2
+-- /products
|   +-- /product-1
|   +-- /product-2
+-- /brands
|   +-- /brand-1
+-- /sale (or /deals)
+-- /new-arrivals
+-- /best-sellers
+-- /gift-guide
+-- /blog
|   +-- /buying-guides
|   +-- /how-to
|   +-- /trends
+-- /about
+-- /contact
+-- /shipping
+-- /returns
+-- /faq
```

#### Schema Recommendations

| Page Type | Schema Types |
|-----------|-------------|
| Product Page | Product, Offer, AggregateRating, Review, BreadcrumbList |
| Category Page | CollectionPage, ItemList, BreadcrumbList |
| Brand Page | Brand, Organization |
| Blog | Article, BlogPosting |

**Additional e-commerce schema (2025):**
- **ProductGroup**: Use for products with variants (size, color). Wraps
  individual Product entries with `variesBy` and `hasVariant` properties.
- **Certification**: For product certifications (Energy Star, safety,
  organic). Replaced EnergyConsumptionDetails (April 2025). Use
  `hasCertification` on Product.
- **OfferShippingDetails**: Include shipping rate, handling time, and transit
  time. Critical for Merchant Center eligibility.

**Product schema example:**

```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Product Name",
  "image": ["https://example.com/product.jpg"],
  "description": "Product description",
  "sku": "SKU123",
  "brand": {
    "@type": "Brand",
    "name": "Brand Name"
  },
  "offers": {
    "@type": "Offer",
    "price": "99.99",
    "priceCurrency": "USD",
    "availability": "https://schema.org/InStock",
    "url": "https://example.com/product"
  },
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "4.5",
    "reviewCount": "42"
  }
}
```

**Google Merchant Center**: Products can appear in Google Shopping for free.
Ensure Product structured data is in initial server-rendered HTML (not
JavaScript-injected) with required properties: `name`, `image`, `price`,
`priceCurrency`, `availability`.

#### Content Requirements

**Product pages (min 400 words):**
- Unique product descriptions (not manufacturer copy).
- Feature highlights and specifications table.
- Use cases / who it is for.
- Size/fit guide (for apparel).
- Customer reviews.

**Category pages (min 400 words):**
- Category introduction.
- Buying guide excerpt.
- Featured products.
- Subcategory links.
- Filter/sort options.

#### Content Priorities

**High priority:**
1. Category pages (top level).
2. Best-selling product pages.
3. Homepage.
4. Buying guides for main categories.

**Medium priority:**
1. Subcategory pages.
2. Brand pages.
3. Comparison content.
4. Seasonal landing pages.

**Blog topics:**
- Buying guides ("How to Choose...").
- Product comparisons.
- Trend reports.
- Use cases and inspiration.
- Care and maintenance guides.

#### Technical Considerations (E-commerce)

**Pagination:** Use `rel="next"`/`rel="prev"` or load-more. Ensure all
products are crawlable. Canonical to main category page.

**Faceted navigation:** Noindex filter combinations that create duplicate
content. Use canonical tags. Ensure popular filters remain indexable.

**Product variations:** Single URL for parent product with variants, or
separate URLs with canonical to parent. Structured data for all variants.

#### Key Metrics

- Revenue from organic search.
- Product page rankings.
- Category page rankings.
- Click-through rate (rich results).
- Average order value from organic.

#### GEO Checklist (E-commerce)

- [ ] Include clear product specs, dimensions, materials in structured format.
- [ ] Use ProductGroup schema for variant products.
- [ ] Provide original product photography with descriptive alt text.
- [ ] Include genuine customer review content (AggregateRating schema).
- [ ] Maintain consistent product entity data across all platforms.
- [ ] Structure comparison content with clear feature tables AI can parse.
- [ ] Add detailed FAQ content for common product questions.

---

### Local Service Template

#### Industry Characteristics

- Geographic-focused searches.
- High intent, quick decision making.
- Reviews heavily influence decisions.
- Phone calls are primary conversion.
- Mobile-first user behavior.
- Emergency/urgent service needs.

#### Recommended Site Architecture

```
/
+-- Home
+-- /services
|   +-- /service-1
|   +-- /service-2
+-- /locations
|   +-- /city-1
|   |   +-- /service-1-city-1
|   +-- /city-2
+-- /about
+-- /reviews
+-- /gallery (or /portfolio)
+-- /blog
+-- /contact
+-- /emergency (if applicable)
+-- /faq
```

#### Quality Gates (Location Pages)

- WARNING at 30+ location pages.
- HARD STOP at 50+ location pages.

| Page Type | Min Words | Unique % |
|-----------|-----------|----------|
| Primary Location | 600 | 60%+ |
| Service Area | 500 | 40%+ |
| Service Page | 800 | 100% |

**What makes location pages unique:**
- Local landmarks and neighborhoods.
- Specific services offered at that location.
- Local team members.
- Location-specific testimonials.
- Community involvement.
- Local regulations or considerations.

#### Schema Recommendations

| Page Type | Schema Types |
|-----------|-------------|
| Homepage | LocalBusiness, Organization |
| Service Pages | Service, LocalBusiness |
| Location Pages | LocalBusiness (with geo) |
| Contact | ContactPage, LocalBusiness |
| Reviews | LocalBusiness (with AggregateRating) |

**LocalBusiness schema example:**

```json
{
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "name": "Business Name",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "123 Main St",
    "addressLocality": "City",
    "addressRegion": "State",
    "postalCode": "12345"
  },
  "telephone": "+1-555-555-5555",
  "openingHours": "Mo-Fr 08:00-18:00",
  "geo": {
    "@type": "GeoCoordinates",
    "latitude": "40.7128",
    "longitude": "-74.0060"
  },
  "areaServed": ["City 1", "City 2"],
  "priceRange": "$$"
}
```

#### NAP Consistency

Ensure Name, Address, Phone (NAP) is identical across:
- Website (header, footer, contact page).
- Google Business Profile.
- Local directories (Yelp, Apple Maps, Bing Places).
- Social media profiles.

Any inconsistency in NAP data confuses search engines and reduces local
ranking potential. Audit NAP across all platforms before launching local
SEO campaigns.

#### Google Business Profile (2025-2026 Updates)

- **Video verification** is now standard -- postcard verification has been
  largely phased out. Prepare for a short video verification process.
- **WhatsApp integration** replaced Google Business Chat (deprecated).
  Businesses can connect WhatsApp as their primary messaging channel.
- **Q&A removed from Maps** -- replaced by AI-generated answers. Ensure
  GBP description, services, and website FAQ are comprehensive.
- **Business hours are a top-5 ranking factor** -- keep hours accurate.
  Consider extended hours if feasible.
- **Review "Stories" format** -- Google Maps shows review snippets in a
  swipeable Stories format on mobile. Encourage detailed, descriptive
  reviews with photos.

#### Service Area Business (SAB) Update (June 2025)

Google updated SAB guidelines to disallow entire states or countries as
service areas. SABs must specify: cities, postal/ZIP codes, or neighborhoods.
If serving an entire metro area, list the major cities within it.

#### Content Priorities

**High priority:**
1. Homepage with clear service area.
2. Core service pages.
3. Primary city page.
4. Contact page with all locations.

**Medium priority:**
1. Service + location combination pages.
2. FAQ page.
3. About/team page.
4. Reviews/testimonials page.

**Blog topics:**
- Seasonal maintenance tips.
- How to choose a [service provider].
- Warning signs of [problem].
- DIY vs professional comparisons.
- Local regulations and permits.

#### Key Metrics

- Local pack rankings.
- Phone call volume from organic.
- Direction requests.
- Google Business Profile insights.
- Reviews count and rating.

#### AI Visibility for Local

AI Overviews appear for only ~0.14% of local keywords (March 2025 data).
Local SEO faces less AI disruption than other verticals. However, ChatGPT
and Perplexity are increasingly used for local recommendations.

**Optimize for AI local visibility:**
- Ensure presence on expert-curated "best of" lists (ranked #1 AI visibility
  factor in Whitespark 2026 report).
- Maintain consistent NAP across all platforms.
- Build genuine review volume and quality.
- Use LocalBusiness schema with complete properties.

#### GEO Checklist (Local)

- [ ] Include clear, quotable service descriptions and pricing ranges.
- [ ] Use LocalBusiness schema with complete geo, openingHours, and areaServed.
- [ ] Build presence on curated "best of" and local directory lists.
- [ ] Maintain consistent NAP across all platforms.
- [ ] Include original photos of work, team, and location.
- [ ] Structure FAQ content for common local service questions.
- [ ] Monitor AI citation in ChatGPT and Perplexity local recommendations.

---

### Publisher Template

#### Industry Characteristics

- High content volume.
- Time-sensitive content (news).
- Ad revenue dependent on traffic.
- Authority and trust critical.
- Competing with social platforms.
- AI Overviews impact on traffic.

#### Recommended Site Architecture

```
/
+-- Home
+-- /news (or /latest)
+-- /topics
|   +-- /topic-1
|   +-- /topic-2
+-- /authors
|   +-- /author-1
+-- /opinion
+-- /reviews
+-- /guides
+-- /videos
+-- /podcasts
+-- /newsletter
+-- /about
|   +-- /editorial-policy
|   +-- /corrections
|   +-- /contact
+-- /[year]/[month]/[slug] (article URLs)
```

#### Schema Recommendations

| Page Type | Schema Types |
|-----------|-------------|
| Article | NewsArticle or Article, Person (author), Organization (publisher) |
| Author Page | Person, ProfilePage |
| Topic Page | CollectionPage, ItemList |
| Homepage | WebSite, Organization |
| Video | VideoObject |
| Podcast | PodcastEpisode, PodcastSeries |

**NewsArticle schema example:**

```json
{
  "@context": "https://schema.org",
  "@type": "NewsArticle",
  "headline": "Article Headline",
  "datePublished": "2026-02-07T10:00:00Z",
  "dateModified": "2026-02-07T14:30:00Z",
  "author": {
    "@type": "Person",
    "name": "Author Name",
    "url": "https://example.com/authors/author-name"
  },
  "publisher": {
    "@type": "Organization",
    "name": "Publication Name",
    "logo": {
      "@type": "ImageObject",
      "url": "https://example.com/logo.png"
    }
  },
  "image": ["https://example.com/article-image.jpg"],
  "mainEntityOfPage": {
    "@type": "WebPage",
    "@id": "https://example.com/article-url"
  }
}
```

#### E-E-A-T Requirements (Publishers)

Publishers face the highest E-E-A-T scrutiny of any industry.

**Author pages must include:**
- Full name and photo.
- Bio and credentials.
- Areas of expertise.
- Contact information.
- Social profiles (sameAs).
- Previous articles by this author.

**Editorial standards:**
- Clear correction policy.
- Transparent editorial process.
- Fact-checking procedures.
- Conflict of interest disclosures.

#### Content Freshness Strategy

- Set up a content freshness calendar: review and update evergreen content
  quarterly.
- For news content, ensure `dateModified` is updated on every revision.
- Remove or redirect stale content that no longer provides value.
- Monitor Google Discover and Google News traffic separately from organic
  search.

#### Syndication Guidelines

- Use canonical tags pointing to the original article when syndicating
  content to other platforms.
- Implement `rel="canonical"` on syndicated copies, not on the original.
- If syndicating to platforms that do not support canonical tags, delay
  syndication by 24-48 hours to allow Google to index the original first.
- Monitor for unauthorized syndication (content scraping) and file DMCA
  takedowns when necessary.

#### Publisher SEO Updates (2025-2026)

- **Google News automatic inclusion**: Google News no longer accepts manual
  applications (since March 2025). Inclusion is fully automatic based on
  content quality criteria. Focus on Google News sitemap markup and consistent,
  high-quality publishing cadence.
- **KPI shift**: Traffic-based KPIs (sessions, pageviews) are declining in
  relevance as AI Overviews reduce click-through rates. Shift to: subscriber
  conversions, time on page, scroll depth, newsletter signups, AI citation
  frequency, revenue per visitor.
- **Site reputation abuse risk**: Publishers hosting third-party content
  (coupons, product reviews, affiliate content) under their domain are at
  high risk. Google penalized Forbes, WSJ, Time, and CNN for this in late
  2024. Ensure strong editorial oversight and clear first-party involvement.

#### Content Priorities

**High priority:**
1. Breaking news (speed matters).
2. Evergreen guides on core topics.
3. Author pages with credentials.
4. Topic hubs/pillar pages.

**Medium priority:**
1. Opinion/analysis pieces.
2. Video content.
3. Interactive content.
4. Newsletter landing pages.

#### Technical Considerations (Publisher)

- Ad placement affects CLS -- lazy load ads and images below fold.
- Optimize hero images for LCP.
- Minimize render-blocking resources.
- Consider dropping AMP (no longer required for Top Stories). Ensure canonical
  setup is correct if still using AMP.
- Proper pagination for multi-page articles.

#### Key Metrics

- Page views from organic.
- Time on page.
- Pages per session.
- Newsletter signups from organic.
- Google News/Discover traffic.
- AI Overview appearances.
- AI citation frequency.

#### GEO Checklist (Publisher)

- [ ] Include clear, quotable facts in articles.
- [ ] Use tables for data-heavy content.
- [ ] Include expert quotes with attribution.
- [ ] Display update dates prominently.
- [ ] Use structured headings (H2/H3).
- [ ] Publish first-party data and original research.
- [ ] Ensure author entities are defined with Person schema + sameAs links.
- [ ] Monitor AI citation frequency across Google AI Overviews, AI Mode,
      ChatGPT, Perplexity.
- [ ] Treat AI citation as a standalone KPI alongside organic traffic.

---

### Agency Template

#### Industry Characteristics

- Service-based, high-value transactions.
- Expertise and trust are paramount.
- Long consideration cycles.
- Portfolio/case study driven decisions.
- Relationship-based sales.
- Niche specialization benefits.

#### Recommended Site Architecture

```
/
+-- Home
+-- /services
|   +-- /service-1
|   |   +-- /sub-service-1
|   +-- /service-2
+-- /industries
|   +-- /industry-1
|   +-- /industry-2
+-- /work (or /case-studies)
|   +-- /case-study-1
|   +-- /case-study-2
+-- /about
|   +-- /team
|   |   +-- /team-member-1
|   +-- /culture
|   +-- /careers
+-- /insights (or /blog)
|   +-- /articles
|   +-- /guides
|   +-- /webinars
|   +-- /podcasts
+-- /contact
+-- /process
+-- /faq
```

#### Schema Recommendations

| Page Type | Schema Types |
|-----------|-------------|
| Homepage | Organization, ProfessionalService |
| Service Page | Service, ProfessionalService |
| Case Study | Article, Organization (client) |
| Team Member | Person, ProfilePage |
| Blog | Article, BlogPosting |

**ProfessionalService schema example:**

```json
{
  "@context": "https://schema.org",
  "@type": "ProfessionalService",
  "name": "Agency Name",
  "description": "What the agency does",
  "url": "https://example.com",
  "logo": "https://example.com/logo.png",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "123 Agency St",
    "addressLocality": "City",
    "addressRegion": "State",
    "postalCode": "12345"
  },
  "telephone": "+1-555-555-5555",
  "areaServed": "National",
  "hasOfferCatalog": {
    "@type": "OfferCatalog",
    "name": "Services",
    "itemListElement": [
      {
        "@type": "Offer",
        "itemOffered": {
          "@type": "Service",
          "name": "Service 1"
        }
      }
    ]
  }
}
```

#### Portfolio SEO

Optimize the agency's portfolio/case studies section for search visibility.

- Use descriptive, keyword-rich titles (e.g., "E-commerce Redesign for
  [Client] -- 150% Revenue Growth" not "Project #47").
- Include the industry and service type in the URL slug.
- Add Article schema to case study pages with the client Organization as
  a linked entity.
- Include measurable results with specific metrics in the opening paragraph
  for AI citability.
- Cross-link case studies to related service pages and industry pages.

#### Case Study SEO

Case studies are the highest-value content type for agencies. Optimize each
one for search and conversion.

**Case study structure (min 1,000 words):**
1. Executive summary with headline metric.
2. Client background and industry context.
3. Challenge details (what problem needed solving).
4. Solution approach (methodology and strategy).
5. Implementation process (timeline and steps).
6. Measurable results (specific numbers, percentages, revenue impact).
7. Client testimonial (direct quote with name and title).
8. Related services with CTA.

#### Service Page SEO

**Service pages (min 800 words):**
- Clear value proposition in the first paragraph.
- Methodology overview.
- Deliverables list.
- Relevant case studies embedded or linked.
- Team members who deliver this service.
- CTA to schedule consultation.

**Industry pages (min 800 words):**
- Industry-specific challenges.
- How the agency solves them differently.
- Relevant case studies.
- Industry credentials and experience.
- Client logos (with permission).

#### E-E-A-T Requirements (Agency)

**Team pages must include:**
- Professional headshots.
- Detailed bios with credentials.
- Industry experience.
- Speaking engagements.
- Publications.
- Social profiles (sameAs links).

#### Content Priorities

**High priority:**
1. Service pages (detailed, specific).
2. Industry pages (vertical expertise).
3. 3-5 detailed case studies.
4. Team/leadership pages.

**Medium priority:**
1. Methodology/process page.
2. Blog with thought leadership.
3. Comparison content (vs alternatives).
4. FAQ page.

**Thought leadership topics:**
- Industry trend analysis.
- How-to guides (non-competitive).
- Original research/surveys.
- Event recaps and insights.
- Expert interviews.
- Tool/technology reviews.

#### Key Metrics

- Organic traffic to service pages.
- Case study page views.
- Contact form submissions from organic.
- Time on page for key content.
- Blog to service page conversion.

#### GEO Checklist (Agency)

- [ ] Publish original case studies with specific, citable metrics and results.
- [ ] Use Person schema with sameAs links for all team members.
- [ ] Use ProfilePage schema for team member pages.
- [ ] Include clear, quotable expertise statements in service descriptions.
- [ ] Produce original industry research and surveys AI systems can cite.
- [ ] Structure thought leadership with clear headings and extractable insights.
- [ ] Maintain consistent agency entity information across directories and
      social profiles.
- [ ] Monitor AI citation in ChatGPT, Perplexity, and Google AI Overviews.

---

### Generic Template

#### Overview

Apply this template to businesses that do not fit neatly into SaaS, local
service, e-commerce, publisher, or agency categories. Customize based on
the specific business model.

#### Recommended Site Architecture

```
/
+-- Home
+-- /products (or /services)
|   +-- /product-1
|   +-- /product-2
+-- /solutions (if applicable)
|   +-- /solution-1
+-- /about
|   +-- /team
|   +-- /history
|   +-- /values
+-- /resources
|   +-- /blog
|   +-- /guides
|   +-- /faq
|   +-- /glossary
+-- /contact
+-- /support
+-- /legal
    +-- /privacy
    +-- /terms
```

#### Universal SEO Principles

**Every page must have:**
- Unique title tag (30-60 characters).
- Unique meta description (120-160 characters).
- Single H1 matching page intent.
- Logical heading hierarchy (H1 then H2 then H3).
- Internal links to related content.
- Clear call-to-action.

#### Schema for All Sites

| Page Type | Schema Types |
|-----------|-------------|
| Homepage | Organization, WebSite |
| About | Organization, AboutPage |
| Contact | ContactPage |
| Blog | Article, BlogPosting |
| FAQ | (FAQPage only for gov/health) |
| Product/Service | Product or Service |

#### Content Quality Standards

**Minimum word counts:**

| Page Type | Min Words |
|-----------|-----------|
| Homepage | 500 |
| Product/Service | 800 |
| Blog Post | 1,500 |
| About Page | 400 |
| Landing Page | 600 |

**E-E-A-T essentials:**
1. Experience: Share real examples and case studies.
2. Expertise: Display credentials and qualifications.
3. Authoritativeness: Earn mentions and citations.
4. Trustworthiness: Full contact info, policies visible.

#### Technical Foundations

**Must-haves:**
- [ ] HTTPS enabled.
- [ ] Mobile-responsive design.
- [ ] robots.txt configured.
- [ ] XML sitemap submitted.
- [ ] Google Search Console verified.
- [ ] Core Web Vitals passing (LCP <=2.5s, INP <=200ms, CLS <=0.1).

**Should-haves:**
- [ ] Structured data on key pages.
- [ ] Internal linking strategy.
- [ ] 404 error page optimized.
- [ ] Redirect chains eliminated.
- [ ] Image optimization (WebP, lazy loading).

#### Content Priorities

**Phase 1 (weeks 1-4):** Homepage optimization, core product/service pages,
about and contact pages, basic schema.

**Phase 2 (weeks 5-12):** Blog launch (2-4 posts/month), FAQ page,
additional product/service pages, internal linking audit.

**Phase 3 (weeks 13-24):** Consistent content publishing, link building
outreach, GEO optimization, performance optimization.

**Phase 4 (months 7-12):** Thought leadership content, original research,
PR and media mentions, advanced schema.

#### Key Metrics

- Organic traffic (overall and by section).
- Keyword rankings (branded and non-branded).
- Conversion rate from organic.
- Pages indexed.
- Core Web Vitals scores.
- Backlinks acquired.

#### Customization Points

Adjust this template based on:
1. Business model: B2B vs B2C vs D2C.
2. Geographic scope: Local, national, or international.
3. Content type: Product-focused vs content-heavy.
4. Competition level: Niche vs competitive market.
5. Resources: Budget and team capacity.

#### GEO Checklist (Generic)

- [ ] Include clear, quotable facts and statistics AI systems can extract.
- [ ] Use structured data (Schema.org) to help AI systems understand content.
- [ ] Build topical authority through comprehensive content clusters.
- [ ] Provide original data, research, or unique perspectives.
- [ ] Maintain consistent entity information across the web.
- [ ] Structure content with clear headings, definitions, and step-by-step formats.
- [ ] Consider adding an `llms.txt` file at site root (emerging convention for
      AI crawlers).
- [ ] Monitor AI citation across Google AI Overviews, ChatGPT, Perplexity,
      and Bing Copilot.

---

## Output Deliverables

Every SEO plan produces these deliverables.

### 1. SEO-STRATEGY.md

Complete strategic plan including:
- Business and audience summary.
- Industry template selection and rationale.
- Key findings from competitive analysis.
- Strategic priorities and phased approach.
- Resource requirements and timeline.
- Risk assessment and mitigation strategies.

### 2. COMPETITOR-ANALYSIS.md

Competitive intelligence report including:
- Top 5 competitor profiles (domain authority, traffic estimates, content
  strategy, schema usage).
- Keyword gap analysis.
- Content opportunity map.
- E-E-A-T comparison.
- Competitive advantages and vulnerabilities.

### 3. CONTENT-CALENDAR.md

Content roadmap including:
- Prioritized content list by phase.
- Content types and estimated word counts.
- Publishing cadence.
- Keyword targets per content piece.
- Internal linking plan for new content.
- E-E-A-T building activities (author bios, case studies, original research).

### 4. IMPLEMENTATION-ROADMAP.md

Phased action plan including:
- Phase 1-4 task lists with owners and deadlines.
- Dependencies between tasks.
- Technical implementation checklist.
- Schema implementation plan by page type.
- Milestone definitions and success criteria per phase.

### 5. SITE-STRUCTURE.md

URL hierarchy and architecture including:
- Complete URL tree based on industry template.
- Content pillar definitions.
- Internal linking strategy diagram.
- Sitemap structure.
- Navigation hierarchy recommendations.
- Programmatic page opportunities (if applicable).

---

## MCP Integration

If DataForSEO MCP available, use `dataforseo_labs_google_competitors_domain`
for competitive intelligence -- identify organic competitors by domain overlap.
Use `dataforseo_labs_google_domain_intersection` to find keyword overlap
between the target site and competitors. Use
`dataforseo_labs_bulk_traffic_estimation` for traffic estimates across
competitor domains. Use `kw_data_google_ads_search_volume` for keyword
research -- validate search volume for target keywords. Use
`dataforseo_labs_bulk_keyword_difficulty` to assess ranking difficulty for
priority keywords. Use `business_data_business_listings_search` for local
business data when working with the Local Service template.
