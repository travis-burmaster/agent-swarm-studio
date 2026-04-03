# Skill: SEO Audit

## Purpose
Score a company's on-page SEO across all key technical and content dimensions.

## Technical SEO Checklist

Run for homepage and top 5 pages (pricing, about, blog index, main product page):

### Meta & Head Elements
- [ ] `<title>` tag: present, unique, 50-60 chars, contains primary keyword
- [ ] `<meta name="description">`: present, 140-155 chars, contains CTA
- [ ] `<meta name="robots">`: not accidentally set to noindex
- [ ] Canonical tag: self-referencing or cross-domain handled correctly
- [ ] OG tags: `og:title`, `og:description`, `og:image`, `og:url`
- [ ] Twitter Card tags: `twitter:card`, `twitter:title`, `twitter:description`
- [ ] `<html lang="">`: language attribute set

### Content Structure
- [ ] Single `<h1>` on page (not zero, not multiple)
- [ ] `<h2>` tags used for section structure
- [ ] Image `alt` attributes present (check 3-5 images)
- [ ] Internal links: are key pages linked from homepage?
- [ ] External links: do outbound links have `rel="noopener"`?

### Schema Markup (check page source)
- [ ] `Organization` schema
- [ ] `WebSite` schema with SearchAction
- [ ] `Product` or `SoftwareApplication` schema
- [ ] `FAQPage` schema on FAQ/pricing pages
- [ ] `Article` schema on blog posts
- [ ] `BreadcrumbList` schema

### Performance Signals (inferred)
- [ ] CDN detected (Cloudflare, Fastly, etc. — check response headers)
- [ ] Image optimization (WebP/AVIF formats?)
- [ ] Lazy loading signals

## Scoring
Score each section: 0 (missing), 1 (partial), 2 (complete)
Max score: depends on applicable items
Report as: X / Y possible points

## Output
```
**SEO Technical Audit — [Company Name] — [URL]**

Meta & Head:      X / 14 pts
Content Structure: X / 10 pts
Schema Markup:    X / 12 pts
Performance:      X / 6 pts

Overall SEO Health: [score]% — [Poor/Fair/Good/Excellent]

Critical gaps:
1. [gap 1]
2. [gap 2]
```
