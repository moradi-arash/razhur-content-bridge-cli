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
3. **Create the featured image** (e.g. via Codex) and save it locally, e.g. `./image.webp`.
4. **Base64-encode the image and embed it** in the payload (the publish script does this for you — just pass the image path).
5. **Build `payload.json`** following the contract in section 4.
6. **Publish** with the script in section 5.
7. **Report** the returned `edit_link` to the user so they can review the draft.

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
| `seo.title` | string | SEO meta title. |
| `seo.description` | string | Meta description. |
| `seo.focus_keyword` | string | Primary keyword. |
| `seo.canonical` | string | Canonical URL (usually leave empty). |

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
  "seo": { "title": "SEO Title (≤60 chars)", "description": "Meta description ≤155 chars.", "focus_keyword": "main keyword", "canonical": "" }
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

---

## 7. Get the latest script

The reference publisher script lives at:
**https://github.com/moradi-arash/razhur-content-bridge-cli**

Download `razhur-publish.sh` from there into this folder if it is not already present.
