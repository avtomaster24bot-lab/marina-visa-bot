# marina-visa-bot
«Автоматический маркетинговый агент Марина для ЛидерТур»

---

## Smart Auto Poster v2

The original `post_generator.py` remains in the repository as the legacy fallback.
The scheduled workflow now runs `smart_poster.py`.

### What v2 adds

- Agnes AI (`agnes-2.5-flash`) for one shared content plan and platform copy.
- Existing Pollinations image generation remains the primary AI image mechanism.
- Existing Pillow branding remains in use for the Telegram/post image.
- Agnes Video (`agnes-video-v2.0`) adds a vertical 9:16 MP4 with polling and fallback.
- Optional client photo/video mix from:
  - `assets/client/images/`
  - `assets/client/videos/`
- Telegram can publish photo + video together as one media group.
- Instagram-ready assets are generated on every run:
  - `generated/post.jpg`
  - `generated/reel.mp4` (when video succeeds)
  - `generated/instagram_caption.txt`
  - `generated/carousels/*.jpg`
  - `generated/stories/*.jpg`
  - `generated/content_plan.json`
- GitHub Actions uploads `generated/` as a 7-day artifact named `marina-social-package`.

### Required GitHub Actions secrets

Existing secrets stay unchanged:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID`

Add one new secret:

- `AGNES_API_KEY`

### Client media mix

The workflow currently uses:

- `CLIENT_IMAGE_PROBABILITY=0.35`
- `CLIENT_VIDEO_PROBABILITY=0.30`

If the client folders are empty, AI media is used automatically.

### Instagram publishing status

The repository now creates all Instagram-ready files, but does **not** automatically publish them to Meta yet.
This is intentional: the official Instagram publishing API needs a delivery mechanism for generated local media (publicly reachable media URL and account credentials). No S3/Cloudinary/new storage service was added without necessity.

The next integration step is to connect the generated package to the official Meta API while keeping GitHub Actions as the orchestrator.

---

## Germany-first posting and offline preview

The scheduled publisher still runs `smart_poster.py`. This update keeps that entry point and adds safer defaults.

### What changed

- Destination selection uses an independent 95% probability of Germany on each run (19 of 20 random slots), including the local fallback path. This is not a guaranteed quota of 19 Germany posts in every 20 publishes, and there is no persistent history or catch-up. The model cannot silently switch the already chosen country.
- Copy is filtered for visa guarantees, promised approval, and invented certainty (`100%`, «без отказа», «вам одобрят», and similar markers). Unsafe model output falls back to a conservative Germany-capable template.
- `python smart_poster.py --preview` (or `OFFLINE_PREVIEW=1`) writes a local poster, captions and a 15-25 second motion reel **before any network or API call**. It does not publish to Telegram and does not call Agnes, Pollinations or other paid APIs.
- Reels are assembled locally from motion frames plus an original procedural instrumental synthesized at runtime. Bundled files in `assets/music/` are not selected automatically: no license confirmation is documented for them, and a licensed opt-in is not implemented in this stage. Unused paid Agnes B-roll is no longer requested, because it was never composited into the finished file.
- If the main Telegram publication fails, the process now exits with a non-zero status so GitHub Actions cannot report a green run after a failed send. A reel send failure is reported separately as partial success and does not hide the main-post result.
- A typographic navy/gold fallback visual is used when no client or generated photo is available, so preview and degraded runs still produce a complete package.

### Preview without publishing

```bash
python smart_poster.py --preview --output preview_output
```

This writes `post.jpg`, `reel.mp4`, `post.txt`, `content_plan.json` and related files to the output directory. Preview does not read Telegram or Agnes secrets and does not make network calls.

Production publish remains:

```bash
python smart_poster.py
```

The GitHub Actions workflow still runs only on `schedule` and `workflow_dispatch`. Pushing a branch or opening a pull request does not publish.

### What this stage does not claim

- It does not add persistent lead analytics, start-parameter attribution, or a guaranteed country quota with history. The Telegram bot does not currently interpret `?start=` payloads.
- It does not invent visa requirements, processing times or approval odds.
- `video_generator.py` remains in the repository but is not called by the publisher.
