# Razhur Content Bridge — CLI

A tiny, dependency-light command-line publisher for the **[Razhur Content Bridge](https://wordpress.org/plugins/)** WordPress plugin.

It takes an article you produced **locally** — title, HTML body, a featured image and SEO meta — and pushes it to a **live WordPress site as a draft** in a single authenticated HTTPS request. No database sync, no FTP, no remote DB connection.

It is designed to be driven either by a human or by an **AI coding agent** (Claude Code, Codex, etc.): point the agent at [`AGENT.md`](AGENT.md) and it knows exactly how to generate content and publish it through this script.

```
  LOCAL (you / your agent)                 LIVE SITE (destination)
  ┌───────────────────────┐  1 HTTPS POST  ┌──────────────────────────────┐
  │ write article + SEO    │ ─────────────► │ Razhur Content Bridge plugin │
  │ generate image         │  title+body+   │  → creates a DRAFT post      │
  │ build payload.json     │  image(base64)+│  → sets the featured image   │
  │ run razhur-publish.sh  │  seo + auth    │  → writes Rank Math/Yoast meta│
  └───────────────────────┘                └──────────────────────────────┘
```

- **Push-only** — the destination never connects back to your machine.
- **Image travels inside the request** as base64; nothing is fetched from localhost.
- **Draft by default** — a human reviews before anything goes public.
- **SEO-aware** — the plugin auto-detects **Rank Math** or **Yoast** and writes the right meta, including social/Open Graph fields when supported.
- **Internal-link aware** — optional local helpers keep a content index and suggest landing-page/post targets for future articles.

---

## Requirements

- The **Razhur Content Bridge** plugin installed and enabled on the destination WordPress site.
- An **Application Password** for a user with the `edit_posts` capability (Author or higher).
- Locally: `bash`, `curl`, and `base64`. `python3` is used for safe JSON image injection (optional but recommended).

---

## Install

```bash
git clone https://github.com/moradi-arash/razhur-content-bridge-cli.git
cd razhur-content-bridge-cli
chmod +x razhur-publish.sh
```

---

## Configure

Copy the example env file and fill in your destination site's credentials:

```bash
cp .razhur-bridge.env.example .razhur-bridge.env
```

```bash
RAZHUR_BRIDGE_URL="https://your-site.com"          # site root, no trailing slash
RAZHUR_BRIDGE_USER="your-wp-login"                 # WordPress username (Author+)
RAZHUR_BRIDGE_APP_PASSWORD="xxxx xxxx xxxx xxxx"    # Application Password
RAZHUR_BRIDGE_TOKEN=""                             # only if the admin set an extra token
```

> **`.razhur-bridge.env` is git-ignored.** Never commit it or print its contents.

Optional, for internal linking:

```bash
cp internal-link-targets.example.json internal-link-targets.json
```

Edit `internal-link-targets.json` with your important landing pages, menu pages and preferred anchor keywords. This file is site-specific and git-ignored.

### Where do I get the Application Password?

On the destination site: **Users → Profile → Application Passwords** → enter a name (e.g. `content-bridge`) → **Add New Application Password** → copy it immediately (shown once). Requires HTTPS.

---

## Usage

**Test connectivity & auth** (recommended before the first publish):

```bash
./razhur-publish.sh --status
# → {"ok":true,"seo_plugin":"rank_math","default_status":"draft","user":"..."}
```

**Publish an article** (with a featured image):

```bash
./razhur-publish.sh payload.json ./image.webp
```

- The 2nd argument is the image path; the script base64-encodes it and injects it into `featured_image.data` for you.
- Omit it if you used `featured_image_url` or no image.
- On success it prints the response JSON and the `edit_link` to review the draft.
- On success it records a sanitized local archive in `content-index.json` and `content/posts/` so future articles can link back to previous content.

**Update an existing post** (partial update, useful for SEO-only fixes):

```bash
./razhur-publish.sh --update 123 payload.json
```

Use this when the destination post already exists. The bridge only changes fields included in the payload, so a payload with only `seo` updates Rank Math/Yoast metadata without touching the title or body. Passing an image path also sets/replaces the featured image:

```bash
./razhur-publish.sh --update 123 payload.json ./image.webp
```

---

## `payload.json` reference

Only `title` and `content` are required.

| Field | Type | Notes |
|---|---|---|
| `title` | string | **Required.** Plain-text title. |
| `content` | string | **Required.** Full article body as **HTML** (no Markdown). |
| `slug` | string | URL slug. |
| `excerpt` | string | Short summary. |
| `status` | string | `draft` (default), `pending`, `publish`. |
| `categories` | string[] / int[] | Names (created if missing) or term IDs. |
| `tags` | string[] | Tag names. |
| `featured_image` | object | `{ "filename", "mime", "alt", "data" }` — `data` filled by the script. |
| `featured_image_url` | string | Alternative to `featured_image` (a public URL). Use only one. |
| `seo.title` | string | SEO meta title (≤60 chars). |
| `seo.description` | string | Meta description (≤155 chars). |
| `seo.focus_keyword` | string | Primary keyword. |
| `seo.canonical` | string | Canonical URL (usually empty). |
| `seo.social.facebook.title` | string | Facebook/Open Graph title. |
| `seo.social.facebook.description` | string | Facebook/Open Graph description. |
| `seo.social.facebook.image` | string | Public Open Graph image URL. If omitted, the plugin can use the uploaded featured image. |
| `seo.social.twitter.title` | string | Twitter/X title. |
| `seo.social.twitter.description` | string | Twitter/X description. |
| `seo.social.twitter.image` | string | Public Twitter/X image URL. If omitted, the plugin can use the uploaded featured image. |

**Template:**

```json
{
  "title": "How to choose running shoes",
  "content": "<h2>Intro</h2><p>Full HTML body…</p>",
  "slug": "choose-running-shoes",
  "excerpt": "A short summary.",
  "status": "draft",
  "categories": ["Guides"],
  "tags": ["shoes", "running"],
  "featured_image": { "filename": "shoes.webp", "mime": "image/webp", "alt": "Running shoes", "data": "" },
  "seo": {
    "title": "How to Choose Running Shoes (2026)",
    "description": "A practical guide.",
    "focus_keyword": "running shoes",
    "canonical": "",
    "social": {
      "facebook": {
        "title": "How to Choose Running Shoes",
        "description": "A practical guide to choosing comfortable running shoes.",
        "image": ""
      },
      "twitter": {
        "title": "How to Choose Running Shoes",
        "description": "A practical guide to choosing comfortable running shoes.",
        "image": ""
      }
    }
  }
}
```

Supported image types: `jpeg`, `png`, `webp`, `gif`.

For SEO-only updates, see [`seo-update.example.json`](seo-update.example.json).

---

## Using it with an AI agent

[`AGENT.md`](AGENT.md) is written for AI coding agents. Drop this repo into your working folder and tell the agent:

> "Read `AGENT.md`, write the article, then publish it as a draft with `razhur-publish.sh`."

The agent will produce the HTML, do internal SEO, build `payload.json`, embed the image and call the script — reporting back the draft's edit link.

### Internal-link suggestions

Before writing a new article, ask the agent to use the helper:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/content_index.py suggest \
  --topic "article topic" \
  --keyword "focus keyword"
```

The helper reads:

- `internal-link-targets.json` for important landing pages and menu pages.
- `content-index.json` for previously generated posts.

Both are local/site-specific and git-ignored. `content-index.json` is updated automatically after successful publishes.

---

## Response

```json
{
  "success": true,
  "action": "update",
  "post_id": 123,
  "status": "draft",
  "edit_link": "https://your-site.com/wp-admin/post.php?post=123&action=edit",
  "preview_link": "https://your-site.com/?p=123&preview=true",
  "seo_plugin": "rank_math",
  "seo_meta": {
    "plugin": "rank_math",
    "written": ["title", "description", "focus_keyword"],
    "skipped": [],
    "warnings": []
  },
  "featured_image_id": 124,
  "image_error": null
}
```

`401` → wrong credentials. `403` → endpoint disabled in plugin settings. A non-null `image_error` means the post was created but the image failed.

---

## Security notes

- Credentials live only in `.razhur-bridge.env` (git-ignored). Rotate the Application Password anytime from the user profile without touching your main password.
- The script sends over HTTPS only and never logs secrets.
- The optional `RAZHUR_BRIDGE_TOKEN` adds a second factor on top of the Application Password.

---

## License

GPL-2.0-or-later. See [LICENSE](LICENSE).
