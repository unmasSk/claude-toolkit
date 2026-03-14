# Schema Markup Reference

On-demand reference for Schema.org structured data detection, validation, and generation. Covers active types, deprecated types, restricted types, JSON-LD validation rules, and ready-to-use templates.

**Schema.org Version:** 29.4 (December 8, 2025)

---

## Format Preference

Always use **JSON-LD** (`<script type="application/ld+json">`). Google's documentation explicitly recommends JSON-LD over Microdata and RDFa.

**AI Search Note:** Content with proper schema has approximately 2.5x higher chance of appearing in AI-generated answers (confirmed by Google and Microsoft, March 2025).

---

## Active Types — Recommend Freely

### Core Business Types

| Type | Use Case | Required Properties | Recommended Properties |
|------|----------|--------------------|-----------------------|
| Organization | Company/brand info | name, url | logo, contactPoint, sameAs, description, foundingDate |
| LocalBusiness | Physical business locations | name, address | telephone, openingHours, geo, priceRange, image, review |
| Service | Service offerings | name, provider | areaServed, description, offers, serviceType |

### Product and Commerce Types

| Type | Use Case | Required Properties | Recommended Properties |
|------|----------|--------------------|-----------------------|
| Product | Physical/digital products | name, image | description, sku, brand, offers, review, aggregateRating, gtin |
| ProductGroup | Product variants | name, productGroupID | variesBy, hasVariant |
| Offer | Pricing information | price, priceCurrency | availability, url, validFrom, priceValidUntil, itemCondition |
| AggregateRating | Rating summaries | ratingValue, reviewCount | bestRating, worstRating |
| Review | Individual reviews | reviewRating, author | itemReviewed, reviewBody, datePublished |

**Product Certification markup** (April 2025): Energy ratings, safety certifications. Replaced EnergyConsumptionDetails. Add `certification` property to Product schema for certified products.

**E-commerce requirements (updated):**
- `returnPolicyCountry` in MerchantReturnPolicy is now **required** (since March 2025)
- Product variant structured data expanded to include apparel, cosmetics, electronics
- Content API for Shopping sunsets August 18, 2026 — migrate to Merchant API

### Content Types

| Type | Use Case | Required Properties | Recommended Properties |
|------|----------|--------------------|-----------------------|
| Article | Blog posts, news articles | headline, author, datePublished | dateModified, image, publisher, description, wordCount |
| BlogPosting | Blog content specifically | headline, author, datePublished | Same as Article + blog-specific context |
| NewsArticle | News content | headline, author, datePublished | Same as Article + news-specific context |
| DiscussionForumPosting | Forum/community threads | headline, author, datePublished | text, url, interactionStatistic |

### Navigation and Site Types

| Type | Use Case | Required Properties | Recommended Properties |
|------|----------|--------------------|-----------------------|
| BreadcrumbList | Page navigation breadcrumbs | itemListElement | Each element: position, name, item (URL) |
| WebSite | Site-level information | name, url | potentialAction (SearchAction for sitelinks search box) |
| WebPage | Page-level metadata | name | description, datePublished, dateModified, breadcrumb |

### Person and Profile Types

| Type | Use Case | Required Properties | Recommended Properties |
|------|----------|--------------------|-----------------------|
| Person | Author, team member | name | jobTitle, url, sameAs, image, worksFor, alumniOf |
| ProfilePage | Author/creator profiles | mainEntity (Person) | name, url, description, sameAs |
| ContactPage | Contact pages | name, url | description |

### Media Types

| Type | Use Case | Required Properties | Recommended Properties |
|------|----------|--------------------|-----------------------|
| VideoObject | Video content | name, description, thumbnailUrl, uploadDate | duration, contentUrl, embedUrl, interactionStatistic |
| ImageObject | Image content | contentUrl | caption, creator, copyrightHolder, description |
| BroadcastEvent | Live broadcasts | isLiveBroadcast, startDate | videoObject, endDate |
| Clip | Video segments | name, startOffset, endOffset | url |
| SeekToAction | Video seek | target (with seek-to) | startOffset-input |

### Event and Job Types

| Type | Use Case | Required Properties | Recommended Properties |
|------|----------|--------------------|-----------------------|
| Event | Events and conferences | name, startDate | endDate, location, organizer, offers, image, description |
| JobPosting | Job listings | title, description, datePosted, hiringOrganization | jobLocation, baseSalary, employmentType, validThrough |
| Course | Educational content | name, description, provider | hasCourseInstance, offers |

### Application Types

| Type | Use Case | Required Properties | Recommended Properties |
|------|----------|--------------------|-----------------------|
| SoftwareApplication | Desktop/mobile apps | name, operatingSystem | applicationCategory, offers, aggregateRating, screenshot |
| WebApplication | Browser-based SaaS | name | applicationCategory, offers, browserRequirements, featureList |
| SoftwareSourceCode | Source code | name | codeRepository, programmingLanguage, runtimePlatform |

### Recent Additions (2024-2026)

| Type/Feature | Added | Notes |
|-------------|-------|-------|
| Product Certification markup | April 2025 | Energy ratings, safety certifications |
| ProductGroup | 2025 | E-commerce product variants with variesBy, hasVariant |
| ProfilePage | 2025 | Author/creator profile pages with mainEntity Person for E-E-A-T |
| DiscussionForumPosting | 2024 | Forum/community content |
| Speakable | Updated 2024 | Voice search optimization |
| LoyaltyProgram | June 2025 | Member pricing, loyalty card structured data |
| Organization-level shipping/return policies | November 2025 | Configure via Search Console without Merchant Center |
| ConferenceEvent | December 2025 | Schema.org v29.4 addition |
| PerformingArtsEvent | December 2025 | Schema.org v29.4 addition |

---

## Restricted Types — Only for Specific Sites

### FAQPage

**Restriction:** Government and healthcare authority sites ONLY (since August 2023).

Google severely limited FAQ rich results in August 2023. Only authoritative sources (government, health organizations) receive FAQ rich results.

**GEO nuance:** FAQPage schema still benefits AI/LLM citation visibility (ChatGPT, Perplexity, Google AI Overviews), even without Google rich results.

**Decision guidance:**
- **Existing FAQPage on commercial site:** Flag at Info priority, not Critical. Removal eliminates GEO citation upside.
- **Adding new FAQPage on commercial site:** Do not recommend for Google benefit. Acceptable only if AI search visibility is an explicit priority.

---

## Deprecated Types — Never Recommend

Never generate, recommend, or validate these types. If detected on a page, flag for removal.

| Type | Status | Deprecated Since | Notes |
|------|--------|-----------------|-------|
| HowTo | Rich results fully removed | September 2023 | Google stopped showing how-to rich results entirely |
| SpecialAnnouncement | Deprecated | July 31, 2025 | COVID-era schema, no longer processed |
| CourseInfo | Retired from rich results | June 2025 | Merged into Course — use Course instead |
| EstimatedSalary | Retired from rich results | June 2025 | No longer displayed in search results |
| LearningVideo | Retired from rich results | June 2025 | Use VideoObject instead |
| ClaimReview | Retired from rich results | June 2025 | Fact-check markup no longer generates rich results |
| VehicleListing | Retired from rich results | June 2025 | Vehicle listing structured data discontinued |
| Practice Problem | Retired from rich results | Late 2025 | Educational practice problems no longer displayed |
| Dataset | Retired from rich results | Late 2025 | Dataset Search feature discontinued |
| Book Actions | Deprecated then REVERSED | June 2025 | Still functional as of February 2026 — historical note only |

---

## JSON-LD Validation Rules

Apply these rules to every schema block, whether detected on a page or generated for implementation.

### Mandatory Validation Checklist

1. **@context** — Must be `"https://schema.org"` (not `http://schema.org`)
2. **@type** — Must be a valid, non-deprecated Schema.org type
3. **Required properties** — All required properties for the type must be present
4. **Data types** — Property values must match expected data types (string, number, URL, Date, etc.)
5. **No placeholder text** — No `[Business Name]`, `[TODO]`, `Lorem ipsum`, or similar placeholder content
6. **Absolute URLs** — All URL values must be absolute (starting with `https://`), never relative paths
7. **ISO 8601 dates** — All date values must use ISO 8601 format (`YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS+TZ`)
8. **Valid image URLs** — Image URLs must be accessible and return HTTP 200
9. **Valid JSON** — The JSON-LD block must parse as valid JSON without syntax errors

### Common Validation Errors

| Error | Impact | Fix |
|-------|--------|-----|
| Missing `@context` | Schema not recognized | Add `"@context": "https://schema.org"` |
| `http` instead of `https` in @context | May not be processed | Change to `https://schema.org` |
| Invalid `@type` | Schema ignored entirely | Use a valid Schema.org type name |
| Relative URLs | Properties ignored | Convert to absolute URLs |
| Invalid date format | Date properties ignored | Convert to ISO 8601 |
| Placeholder text left in | May trigger spam signals | Replace with real data or remove property |
| Nested type without `@type` | Nested object not interpreted | Add `@type` to all nested entities |
| Missing required properties | No rich result generated | Add all required properties per type |
| Array where single value expected | Unpredictable behavior | Match expected cardinality per property |

### Multiple Schema Blocks

Multiple JSON-LD blocks on a single page are valid and recommended when the page contains multiple entity types. Use separate `<script type="application/ld+json">` blocks or a single block with `@graph` array.

**@graph pattern example:**
```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "name": "Company Name",
      "url": "https://example.com"
    },
    {
      "@type": "WebPage",
      "name": "Page Title",
      "url": "https://example.com/page"
    },
    {
      "@type": "BreadcrumbList",
      "itemListElement": [
        {
          "@type": "ListItem",
          "position": 1,
          "name": "Home",
          "item": "https://example.com"
        }
      ]
    }
  ]
}
```

### Nesting vs Referencing

- **Nest** entities when one is a property of another (e.g., `author` inside `Article`)
- **Reference** with `@id` when the same entity appears in multiple places
- Use `@id` with a URI pattern (e.g., `"@id": "https://example.com/#organization"`) for cross-referencing

---

## JavaScript and Structured Data

Per Google's December 2025 JavaScript SEO guidance:

- Structured data injected via JavaScript may face **delayed processing**
- For time-sensitive markup (especially Product, Offer), include JSON-LD in the initial server-rendered HTML
- If canonical tags in raw HTML differ from those injected by JavaScript, Google may use EITHER one
- Google does NOT render JavaScript on pages returning non-200 HTTP status codes — any structured data injected via JS on error pages is invisible to Googlebot

**Best practice:** Always include JSON-LD in the initial server-rendered HTML response. Do not rely on client-side JavaScript to inject structured data.

---

## Common Schema Templates

Reference `schema-templates.json` in the references directory for complete, ready-to-use JSON-LD templates. The following are the most commonly needed templates with all required and recommended properties.

### Organization

```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "[Company Name]",
  "url": "[Website URL]",
  "logo": "[Logo URL — absolute, minimum 112x112px]",
  "description": "[Brief company description]",
  "contactPoint": {
    "@type": "ContactPoint",
    "telephone": "[Phone — E.164 format: +1-XXX-XXX-XXXX]",
    "contactType": "customer service",
    "availableLanguage": ["English"]
  },
  "sameAs": [
    "[Facebook URL]",
    "[LinkedIn URL]",
    "[Twitter/X URL]"
  ]
}
```

### LocalBusiness

```json
{
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "name": "[Business Name]",
  "image": "[Business Image URL]",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "[Street Address]",
    "addressLocality": "[City]",
    "addressRegion": "[State/Province]",
    "postalCode": "[ZIP/Postal Code]",
    "addressCountry": "[ISO 3166-1 alpha-2 code]"
  },
  "telephone": "[Phone — E.164 format]",
  "openingHoursSpecification": [
    {
      "@type": "OpeningHoursSpecification",
      "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
      "opens": "09:00",
      "closes": "17:00"
    }
  ],
  "geo": {
    "@type": "GeoCoordinates",
    "latitude": "[Latitude]",
    "longitude": "[Longitude]"
  },
  "priceRange": "[Price Range — e.g., $$]",
  "url": "[Website URL]"
}
```

### Article / BlogPosting

```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "[Title — max 110 characters]",
  "author": {
    "@type": "Person",
    "name": "[Author Name]",
    "url": "[Author Profile URL]"
  },
  "datePublished": "[YYYY-MM-DD]",
  "dateModified": "[YYYY-MM-DD]",
  "image": {
    "@type": "ImageObject",
    "url": "[Image URL — minimum 1200px wide]",
    "width": 1200,
    "height": 630
  },
  "publisher": {
    "@type": "Organization",
    "name": "[Publisher Name]",
    "logo": {
      "@type": "ImageObject",
      "url": "[Logo URL]"
    }
  },
  "description": "[Article summary — 150-160 characters]",
  "mainEntityOfPage": {
    "@type": "WebPage",
    "@id": "[Canonical URL]"
  }
}
```

### Product with Offer

```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "[Product Name]",
  "image": ["[Image URL 1]", "[Image URL 2]"],
  "description": "[Product description]",
  "sku": "[SKU]",
  "brand": {
    "@type": "Brand",
    "name": "[Brand Name]"
  },
  "offers": {
    "@type": "Offer",
    "price": "[Price — numeric only, no currency symbol]",
    "priceCurrency": "[ISO 4217 code — e.g., USD]",
    "availability": "https://schema.org/InStock",
    "url": "[Product Page URL]",
    "priceValidUntil": "[YYYY-MM-DD]",
    "itemCondition": "https://schema.org/NewCondition"
  },
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "[Average Rating]",
    "reviewCount": "[Number of Reviews]",
    "bestRating": "5",
    "worstRating": "1"
  }
}
```

### BreadcrumbList

```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {
      "@type": "ListItem",
      "position": 1,
      "name": "Home",
      "item": "[Homepage URL]"
    },
    {
      "@type": "ListItem",
      "position": 2,
      "name": "[Category Name]",
      "item": "[Category URL]"
    },
    {
      "@type": "ListItem",
      "position": 3,
      "name": "[Current Page Name]"
    }
  ]
}
```

Note: The last item in the breadcrumb should NOT include an `item` URL — it represents the current page.

### WebSite with SearchAction

```json
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "[Site Name]",
  "url": "[Homepage URL]",
  "potentialAction": {
    "@type": "SearchAction",
    "target": {
      "@type": "EntryPoint",
      "urlTemplate": "[Search URL with {search_term_string} placeholder]"
    },
    "query-input": "required name=search_term_string"
  }
}
```

### VideoObject

```json
{
  "@context": "https://schema.org",
  "@type": "VideoObject",
  "name": "[Video Title]",
  "description": "[Video description]",
  "thumbnailUrl": "[Thumbnail URL]",
  "uploadDate": "[YYYY-MM-DD]",
  "duration": "[ISO 8601 duration — e.g., PT5M30S for 5 min 30 sec]",
  "contentUrl": "[Direct video file URL]",
  "embedUrl": "[Embed URL]",
  "interactionStatistic": {
    "@type": "InteractionCounter",
    "interactionType": { "@type": "WatchAction" },
    "userInteractionCount": "[View Count]"
  }
}
```

### Event

```json
{
  "@context": "https://schema.org",
  "@type": "Event",
  "name": "[Event Name]",
  "startDate": "[YYYY-MM-DDTHH:MM:SS+TZ]",
  "endDate": "[YYYY-MM-DDTHH:MM:SS+TZ]",
  "location": {
    "@type": "Place",
    "name": "[Venue Name]",
    "address": {
      "@type": "PostalAddress",
      "streetAddress": "[Street]",
      "addressLocality": "[City]",
      "addressRegion": "[State]",
      "postalCode": "[ZIP]",
      "addressCountry": "[Country Code]"
    }
  },
  "organizer": {
    "@type": "Organization",
    "name": "[Organizer Name]",
    "url": "[Organizer URL]"
  },
  "offers": {
    "@type": "Offer",
    "price": "[Price]",
    "priceCurrency": "[Currency Code]",
    "availability": "https://schema.org/InStock",
    "url": "[Ticket URL]",
    "validFrom": "[YYYY-MM-DD]"
  },
  "image": "[Event Image URL]",
  "description": "[Event description]"
}
```

### JobPosting

```json
{
  "@context": "https://schema.org",
  "@type": "JobPosting",
  "title": "[Job Title]",
  "description": "[Full job description — HTML allowed]",
  "datePosted": "[YYYY-MM-DD]",
  "validThrough": "[YYYY-MM-DD]",
  "hiringOrganization": {
    "@type": "Organization",
    "name": "[Company Name]",
    "sameAs": "[Company URL]",
    "logo": "[Company Logo URL]"
  },
  "jobLocation": {
    "@type": "Place",
    "address": {
      "@type": "PostalAddress",
      "addressLocality": "[City]",
      "addressRegion": "[State]",
      "addressCountry": "[Country Code]"
    }
  },
  "baseSalary": {
    "@type": "MonetaryAmount",
    "currency": "[Currency Code]",
    "value": {
      "@type": "QuantitativeValue",
      "value": "[Salary]",
      "unitText": "YEAR"
    }
  },
  "employmentType": "[FULL_TIME, PART_TIME, CONTRACT, TEMPORARY, INTERN]"
}
```

---

## Testing and Validation Tools

| Tool | URL | Purpose |
|------|-----|---------|
| Google Rich Results Test | https://search.google.com/test/rich-results | Test whether a page is eligible for rich results |
| Schema.org Validator | https://validator.schema.org/ | Validate schema syntax against the Schema.org vocabulary |
| Google Search Console | Enhancement reports | Monitor rich result status across the site |

### Validation Workflow

1. Generate or detect schema on the page
2. Parse as JSON — verify valid JSON syntax
3. Run through the 9-point validation checklist (see JSON-LD Validation Rules above)
4. Check type against active/restricted/deprecated lists
5. Verify all required properties are present for the type
6. Test with Google Rich Results Test for rich result eligibility
7. Validate with Schema.org Validator for vocabulary compliance
8. Present findings with validation status per schema block

---

## Schema Strategy by Page Type

| Page Type | Recommended Schema Types |
|-----------|-------------------------|
| Homepage | Organization (or LocalBusiness), WebSite with SearchAction, BreadcrumbList |
| About page | Organization, Person (for team members), BreadcrumbList |
| Service page | Service, BreadcrumbList, FAQPage (only if govt/healthcare) |
| Product page | Product, Offer, AggregateRating, Review, BreadcrumbList |
| Blog post | Article or BlogPosting, Person (author), BreadcrumbList |
| News article | NewsArticle, Person (author), BreadcrumbList |
| Contact page | ContactPage, Organization (with contactPoint), BreadcrumbList |
| Event page | Event, BreadcrumbList |
| Job listing | JobPosting, BreadcrumbList |
| Video page | VideoObject, BreadcrumbList |
| Location page | LocalBusiness, BreadcrumbList |
| Category page | WebPage, BreadcrumbList, CollectionPage |
| Author profile | ProfilePage with Person as mainEntity |
