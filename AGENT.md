# Razhur Content Bridge — Local Agent Guide

> **Read this file before generating content.** It tells you (the AI agent) exactly
> how to take an article you produced locally and publish it to the live WordPress
> site as a **draft**, including the featured image and SEO meta — in a single
> authenticated request. No database sync, no FTP.

---

## 1. What this system does

```
  YOU (local agent)                       LIVE SITE (destination)
  ┌────────────────────┐   1 HTTPS POST   ┌──────────────────────────────┐
  │ • write the article │  ──────────────► │ Razhur Content Bridge plugin │
  │ • do internal SEO   │   title+body+    │  → creates a DRAFT post      │
  │ • make the image    │   image(base64)+ │  → sets the featured image   │
  │ • build payload.json│   seo + auth     │  → writes Rank Math/Yoast meta│
  │ • run publish script│                  │  → returns post_id + edit URL │
  └────────────────────┘                  └──────────────────────────────┘
```

- **Direction is push-only.** You send everything; the destination never connects back to your machine.
- **The image travels inside the request** as base64. The destination does not download from localhost.
- **Default result is a DRAFT** — a human reviews it in wp-admin before it goes public.
- **The plugin auto-detects Rank Math or Yoast** and writes the right SEO fields. You always use the same generic field names below.

---

## 2. One-time setup (already done by the site owner)

On the **destination** site:
1. The `razhur-content-bridge` plugin is installed and **enabled** (Settings → Content Bridge).
2. An **Application Password** was created (Users → Profile → Application Passwords).
3. Credentials are stored locally in `.razhur-bridge.env` (see below). **Never** print or commit this file.

`.razhur-bridge.env` format:
```bash
RAZHUR_BRIDGE_URL="https://example.com"          # destination site root, no trailing slash
RAZHUR_BRIDGE_USER="the-wp-login"                # WordPress username (Author or higher)
RAZHUR_BRIDGE_APP_PASSWORD="xxxx xxxx xxxx xxxx"  # the Application Password
RAZHUR_BRIDGE_TOKEN=""                            # only if the admin set an extra secret token
```

---

## 3. Your workflow, step by step

1. **Write the article** as clean HTML for the `content` field (`<h2>`, `<p>`, `<ul>`, `<a>`, `<img>`, etc. — no `<html>`/`<body>` wrapper, no inline styles).
2. **Do internal SEO**: choose a focus keyword, write an SEO title (≤60 chars) and meta description (≤155 chars), set internal links inside the body, write a slug.
   - Before writing, run the internal-link helper with the topic/keyword:
     ```bash
     PYTHONDONTWRITEBYTECODE=1 python3 scripts/content_index.py suggest --topic "article topic" --keyword "focus keyword"
     ```
   - Use `internal-link-targets.json` for important landing pages and `content-index.json` for previously generated posts.
   - Add links naturally inside the body; do not force unrelated anchors.
3. **Create the featured image** (e.g. via Codex) and save it locally, e.g. `./image.webp`.
4. **Base64-encode the image and embed it** in the payload (the publish script does this for you — just pass the image path).
5. **Build `payload.json`** following the contract in section 4.
6. **Publish** with the script in section 5.
7. **Report** the returned `edit_link` to the user so they can review the draft.
8. **Keep the local archive**: the publish script automatically records successful posts in `content-index.json` and saves sanitized copies under `content/posts/`.
9. **For existing posts, update instead of republishing**: if the user gives an existing post ID or asks to fix SEO/content on an existing draft, use `./razhur-publish.sh --update POST_ID payload.json [image.webp]` so no duplicate draft is created.

---

## 4. Request contract (`payload.json`)

Only `title` and `content` are required. Everything else is optional.

| Field | Type | Notes |
|---|---|---|
| `title` | string | **Required.** Post title (plain text). |
| `content` | string | **Required.** Full article body as HTML. |
| `slug` | string | URL slug. Use ASCII/transliterated for clean URLs. |
| `excerpt` | string | Short summary for listings. |
| `status` | string | `draft` (default), `pending`, or `publish`. Leave as `draft` unless told otherwise. |
| `categories` | string[] or int[] | Category names (created if missing) or term IDs. Omit to use the site default. |
| `tags` | string[] | Tag names (created if missing). |
| `featured_image` | object | `{ "filename", "mime", "alt", "data" }`. `data` = base64 image bytes. The script fills `data` from the image path you pass. |
| `featured_image_url` | string | Alternative to `featured_image`: a public image URL the site will fetch. Use only one. |
| `seo.title` | string | SEO meta title. Target around 55-60 characters. |
| `seo.description` | string | Meta description. Target around 140-155 characters. |
| `seo.focus_keyword` | string | Primary keyword. |
| `seo.canonical` | string | Canonical URL (usually leave empty). |
| `seo.social.facebook.title` | string | Facebook/Open Graph title. Falls back to SEO title if omitted by the SEO plugin. |
| `seo.social.facebook.description` | string | Facebook/Open Graph description. |
| `seo.social.facebook.image` | string | Public social image URL. If omitted, the plugin uses the uploaded featured image URL when available. |
| `seo.social.twitter.title` | string | Twitter/X title. |
| `seo.social.twitter.description` | string | Twitter/X description. |
| `seo.social.twitter.image` | string | Public Twitter/X image URL. If omitted, the plugin uses the uploaded featured image URL when available. |

**Template** (leave `featured_image.data` empty — the script injects it):
```json
{
  "title": "Your article title",
  "content": "<h2>Heading</h2><p>Body…</p>",
  "slug": "your-article-title",
  "excerpt": "One-sentence summary.",
  "status": "draft",
  "categories": ["Guides"],
  "tags": ["keyword-a", "keyword-b"],
  "featured_image": { "filename": "image.webp", "mime": "image/webp", "alt": "Describe the image", "data": "" },
  "seo": {
    "title": "SEO Title (≤60 chars)",
    "description": "Meta description ≤155 chars.",
    "focus_keyword": "main keyword",
    "canonical": "",
    "social": {
      "facebook": {
        "title": "Open Graph title",
        "description": "Open Graph description.",
        "image": ""
      },
      "twitter": {
        "title": "Twitter title",
        "description": "Twitter description.",
        "image": ""
      }
    }
  }
}
```

---

## 5. Publish

```bash
# payload.json built per section 4, image at ./image.webp
./razhur-publish.sh payload.json ./image.webp
```

- Pass the image path as the 2nd argument and the script base64-encodes it into `featured_image.data` for you. Omit it if you used `featured_image_url` or no image.
- On success the script prints JSON containing `post_id` and `edit_link`. Show `edit_link` to the user.
- On success the script also prints SEO metadata write details when the destination plugin returns them.
- On success the script archives the payload locally:
  - `content-index.json` for future internal-link suggestions.
  - `content/posts/YYYY-MM-DD-slug.json` for machine-readable history.
  - `content/posts/YYYY-MM-DD-slug.md` for human review.

**Update an existing post** (partial update, safe for SEO-only fixes):
```bash
./razhur-publish.sh --update 123 payload.json
```

- Use this when a draft already exists and the user asks to fix SEO title, meta description, content, categories, tags, slug, status, or featured image.
- The update endpoint only changes fields included in the payload. If the payload contains only `seo`, the post body/title are left untouched.
- Passing an image path with `--update` replaces/sets the featured image and lets the SEO plugin use that image for social meta.

**Verify connectivity first** (optional, recommended before the first publish of a session):
```bash
./razhur-publish.sh --status
```
Returns the detected SEO plugin, the default status, and the authenticated user. A `401` means the credentials are wrong; a `403` means the endpoint is disabled in plugin settings.

---

## 6. Rules & gotchas

- **Keep `status` as `draft`** unless the user explicitly says publish.
- **Do not invent credentials.** They live in `.razhur-bridge.env`. If it is missing, ask the user to create it from the plugin's Help tab.
- **Never print the Application Password or token** in your output or in committed files.
- **HTML only in `content`** — no Markdown. Convert before sending.
- **One image source**: either `featured_image` (base64) or `featured_image_url`, not both.
- **Allowed image types**: jpeg, png, webp, gif.
- If `image_error` is non-null in the response, the post was still created but the image failed — report it.
- Before each new article, consult `internal-link-targets.json` and `content-index.json` so new content can link to key landing pages and prior posts.

---

## 7. Internal linking workflow

Important landing pages live in:
```bash
internal-link-targets.json
```

Previously generated articles live in:
```bash
content-index.json
content/posts/
```

Suggest targets for a new topic:
```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/content_index.py suggest \
  --topic "بیمه بیکاری و اخراج کارگر" \
  --keyword "بیمه بیکاری"
```

Use the suggestions as editorial input. Prefer:
- 1-3 links to high-priority landing pages.
- 1-3 links to genuinely relevant previous posts.
- Natural anchors that already fit the paragraph.
- CTA links near the end only when the user intent is consultation or service-oriented.

---

## 8. Get the latest script

The reference publisher script lives at:
**https://github.com/moradi-arash/razhur-content-bridge-cli**

Download `razhur-publish.sh` from there into this folder if it is not already present.
