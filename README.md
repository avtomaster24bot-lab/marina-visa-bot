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
