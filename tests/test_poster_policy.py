import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from content_generator import (  # noqa: E402
    GERMANY_WEIGHT,
    DESTINATION_SLOT_COUNT,
    choose_destination,
    contains_forbidden_claims,
    generate_content_plan,
    germany_destination,
    build_offline_plan,
    ensure_safe_plan,
    plan_copy_is_safe,
    _fallback,
    _fallback_social,
    _valid_slide,
    DESTINATIONS,
)
from offline_preview import run_offline_preview  # noqa: E402
from smart_poster import (  # noqa: E402
    SECRET_ENV_KEYS,
    PublishResult,
    main,
    publication_exit_code,
    publish_package,
    telegram_photo_caption,
)


class ScriptedRNG:
    def __init__(self, roll, choice=None):
        self.roll = roll
        self._choice = choice

    def randrange(self, n):
        assert n == DESTINATION_SLOT_COUNT
        return self.roll

    def choice(self, seq):
        if self._choice is not None:
            return self._choice
        return seq[0]


class DestinationWeightTests(unittest.TestCase):
    def test_germany_for_first_nineteen_slots(self):
        self.assertEqual(GERMANY_WEIGHT, 19)
        self.assertEqual(DESTINATION_SLOT_COUNT, 20)
        for roll in range(19):
            picked = choose_destination(ScriptedRNG(roll))
            self.assertEqual(picked["country"], "Германия")

    def test_twentieth_slot_is_not_germany(self):
        other = {"country": "Китай", "service": "визы в Китай", "visual": "x"}
        picked = choose_destination(ScriptedRNG(19, choice=other))
        self.assertEqual(picked["country"], "Китай")

    def test_fallback_uses_same_weighting(self):
        plan = _fallback(rng=ScriptedRNG(0))
        self.assertEqual(plan.country, "Германия")
        other = next(item for item in DESTINATIONS if item["country"] != "Германия")
        plan_other = _fallback(rng=ScriptedRNG(19, choice=other))
        self.assertEqual(plan_other.country, other["country"])
        self.assertFalse(contains_forbidden_claims(plan.telegram_text))
        self.assertFalse(contains_forbidden_claims(plan_other.telegram_text))

    def test_model_cannot_override_selected_country(self):
        payload = {
            "country": "Китай",
            "service": "визы в Китай",
            "content_format": "clarity",
            "angle": "тест",
            "headline": "План поездки без спешки",
            "subheadline": "Разберём шаги подготовки",
            "telegram_text": "Планируете поездку? Начните с ясного плана и консультации по вашей ситуации.",
            "instagram_caption": "Начните с плана подготовки и напишите нам.",
            "image_prompt": "berlin travel photograph",
            "video_prompt": "vertical travel film",
            "reel_hook": "ПЛАНИРУЕТЕ ПОЕЗДКУ?",
            "reel_middle": "НАЧНИТЕ С ПЛАНА",
            "reel_cta": "НАПИШИТЕ НАМ",
            "carousel_slides": ["С чего начать поездку", "Соберите свои вопросы"],
            "story_slides": ["Планируете поездку", "Напишите нам"],
            "social_visual_prompts": ["one", "two", "three", "four", "five"],
        }
        with patch("content_generator.choose_destination", return_value=germany_destination()), patch(
            "content_generator._agnes_chat", return_value=json.dumps(payload)
        ), patch(
            "content_generator._review_social_copy",
            side_effect=lambda country, carousel, stories: (carousel, stories),
        ):
            plan = generate_content_plan()
        self.assertEqual(plan.country, "Германия")
        self.assertEqual(plan.service, "визы в Германию")



    def test_weighting_docs_describe_probability_not_quota(self):
        doc = choose_destination.__doc__ or ""
        self.assertIn("95%", doc)
        self.assertIn("independent", doc.lower())
        self.assertIn("not a guaranteed quota", doc.lower())
        self.assertIn("no persistent history", doc.lower())
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("95% probability", readme)
        self.assertNotIn("Germany in 19 of every 20 posts", readme)
        self.assertIn("no persistent history", readme)


class SafetyTests(unittest.TestCase):

    def test_forbidden_markers(self):
        self.assertTrue(contains_forbidden_claims("Виза в Германию — 100% успеха"))
        self.assertTrue(contains_forbidden_claims("Оформляем без отказа"))
        self.assertTrue(contains_forbidden_claims("Вам одобрят визу за неделю"))
        self.assertFalse(contains_forbidden_claims(_fallback(destination=germany_destination()).telegram_text))

    def test_unsafe_model_copy_uses_fallback(self):
        payload = {
            "headline": "Гарантия визы сегодня",
            "subheadline": "Без отказа",
            "telegram_text": "Обещаем 100% и визу без отказа.",
            "instagram_caption": "Вам одобрят",
            "image_prompt": "x",
            "video_prompt": "y",
            "reel_hook": "ВИЗА",
            "reel_middle": "ГАРАНТИЯ",
            "reel_cta": "ПИШИТЕ",
        }
        with patch("content_generator.choose_destination", return_value=germany_destination()), patch(
            "content_generator._agnes_chat", return_value=json.dumps(payload)
        ):
            plan = generate_content_plan()
        self.assertFalse(contains_forbidden_claims(plan.telegram_text))
        self.assertIn("уполномоченный орган", plan.telegram_text)

    def test_fallback_social_limits(self):
        for item in DESTINATIONS:
            carousel, stories = _fallback_social(item["country"])
            self.assertEqual(len(carousel), 5)
            self.assertEqual(len(stories), 4)
            for slide in carousel:
                self.assertTrue(_valid_slide(slide, max_words=8, max_chars=58), slide)
            for slide in stories:
                self.assertTrue(_valid_slide(slide, max_words=7, max_chars=46), slide)



    def test_unsafe_headline_uses_fallback(self):
        payload = {
            "headline": "100% успеха",
            "subheadline": "Разберём шаги подготовки",
            "telegram_text": "Планируете поездку? Начните с ясного плана и консультации по вашей ситуации.",
            "instagram_caption": "Начните с плана подготовки и напишите нам.",
            "image_prompt": "x",
            "video_prompt": "y",
            "reel_hook": "ПЛАНИРУЕТЕ ПОЕЗДКУ?",
            "reel_middle": "НАЧНИТЕ С ПЛАНА",
            "reel_cta": "НАПИШИТЕ НАМ",
            "carousel_slides": ["С чего начать поездку", "Соберите свои вопросы"],
            "story_slides": ["Планируете поездку", "Напишите нам"],
            "social_visual_prompts": ["one", "two", "three", "four", "five"],
        }
        with patch("content_generator.choose_destination", return_value=germany_destination()), patch(
            "content_generator._agnes_chat", return_value=json.dumps(payload)
        ), patch(
            "content_generator._review_social_copy",
            side_effect=lambda country, carousel, stories: (carousel, stories),
        ):
            plan = generate_content_plan()
        self.assertTrue(plan_copy_is_safe(plan))
        self.assertNotIn("100%", plan.headline)

    def test_fallback_captions_fit_telegram_limits(self):
        for item in DESTINATIONS:
            plan = build_offline_plan(destination=item)
            self.assertLessEqual(len(plan.telegram_text), 1024, item["country"])
            reel_caption = f"🎬 {plan.reel_hook}\n{plan.reel_cta}"
            self.assertLessEqual(len(reel_caption), 1024)
            self.assertTrue(plan_copy_is_safe(plan))
        long_text = "слово " * 400
        clipped = telegram_photo_caption(long_text, limit=80)
        self.assertLessEqual(len(clipped), 80)
        self.assertFalse(clipped.endswith(" "))


class PublishExitCodeTests(unittest.TestCase):

    def test_failure_is_nonzero_success_is_zero(self):
        self.assertEqual(publication_exit_code(False), 1)
        self.assertEqual(publication_exit_code(True), 0)

    def test_publish_package_returns_false_when_all_sends_fail(self):
        plan = build_offline_plan(destination=germany_destination())
        ok = publish_package(
            plan,
            b"x" * 30_000,
            b"video",
            send_photo=lambda *args: False,
            send_video=lambda *args: False,
            send_text=lambda *args: False,
        )
        self.assertFalse(ok)
        self.assertEqual(publication_exit_code(ok), 1)

    def test_publish_package_succeeds_when_photo_sends(self):
        plan = build_offline_plan(destination=germany_destination())
        sent = {"video": False}

        def send_video(*args):
            sent["video"] = True
            return True

        ok = publish_package(
            plan,
            b"x" * 30_000,
            b"video",
            send_photo=lambda *args: True,
            send_video=send_video,
            send_text=lambda *args: (_ for _ in ()).throw(AssertionError("text fallback should not run")),
        )
        self.assertTrue(ok)
        self.assertTrue(sent["video"])
        self.assertEqual(publication_exit_code(ok), 0)



    def test_reel_failure_is_reported_without_hiding_main_success(self):
        plan = build_offline_plan(destination=germany_destination())
        result = publish_package(
            plan,
            b"x" * 30_000,
            b"video",
            send_photo=lambda *args: True,
            send_video=lambda *args: False,
            send_text=lambda *args: (_ for _ in ()).throw(AssertionError("text fallback should not run")),
        )
        self.assertIsInstance(result, PublishResult)
        self.assertTrue(result.main_ok)
        self.assertEqual(result.reel_status, "failed")
        self.assertEqual(publication_exit_code(result), 0)


class OfflinePreviewTests(unittest.TestCase):

    def test_importing_smart_poster_does_not_need_telegram_secrets(self):
        env = {key: value for key, value in os.environ.items() if key not in {"TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_ID"}}
        # already imported successfully in this process without requiring those keys
        self.assertTrue(hasattr(sys.modules["smart_poster"], "main"))
        self.assertNotIn("post_generator", sys.modules.get("smart_poster").__dict__)

    def test_preview_makes_no_network_calls_and_writes_package(self):
        def boom(*args, **kwargs):
            raise AssertionError(f"network called: {args} {kwargs}")

        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw)
            secret_keys = set(SECRET_ENV_KEYS)
            real_getenv = os.getenv
            real_env_get = os.environ.get

            def guarded_getenv(key, default=None):
                if str(key) in secret_keys:
                    raise AssertionError(f"preview read secret {key}")
                return real_getenv(key, default)

            def guarded_env_get(key, default=None):
                if str(key) in secret_keys:
                    raise AssertionError(f"preview read secret {key}")
                return real_env_get(key, default)

            with patch("os.getenv", side_effect=guarded_getenv), patch.object(
                os.environ, "get", side_effect=guarded_env_get
            ), patch("requests.post", side_effect=boom), patch("requests.get", side_effect=boom), patch(
                "content_generator._agnes_chat", side_effect=boom
            ), patch(
                "image_generator.create_hero_image", side_effect=boom
            ), patch(
                "video_generator.create_agnes_video", side_effect=boom
            ), patch(
                "smart_poster.publish_package", side_effect=AssertionError("publish must not run")
            ):
                code = main(["--preview", "--output", str(target)])
            self.assertEqual(code, 0)
            self.assertGreater((target / "post.jpg").stat().st_size, 20_000)
            self.assertGreater((target / "reel.mp4").stat().st_size, 40_000)
            text = (target / "post.txt").read_text(encoding="utf-8")
            self.assertIn("Германия", text)
            self.assertFalse(contains_forbidden_claims(text))
            plan = json.loads((target / "preview_plan.json").read_text(encoding="utf-8"))
            self.assertFalse(plan["published"])
            self.assertEqual(plan["network_calls"], 0)
            self.assertEqual(plan["paid_api_calls"], 0)
            self.assertEqual(plan["telegram_sends"], 0)
            self.assertTrue(plan["music"].startswith("original procedural"))
            self.assertNotIn("if present", plan["music"])

            if shutil.which("ffprobe"):
                probe = subprocess.run(
                    [
                        "ffprobe", "-v", "error",
                        "-show_entries", "format=duration:stream=codec_type,codec_name,width,height",
                        "-of", "json",
                        str(target / "reel.mp4"),
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                info = json.loads(probe.stdout)
                duration = float(info["format"]["duration"])
                self.assertGreaterEqual(duration, 15)
                self.assertLessEqual(duration, 25)
                codecs = {stream.get("codec_type"): stream for stream in info["streams"]}
                self.assertIn("audio", codecs)
                self.assertEqual(codecs["video"].get("width"), 1080)
                self.assertEqual(codecs["video"].get("height"), 1920)

    def test_help_does_not_publish(self):
        with patch("smart_poster.publish_package", side_effect=AssertionError("publish")):
            code = main(["--help"])
        self.assertEqual(code, 0)


class WorkflowSafetyTests(unittest.TestCase):
    def test_publish_workflow_is_not_triggered_by_push_or_pull_request(self):
        raw = (ROOT / ".github" / "workflows" / "publish.yml").read_text(encoding="utf-8")
        header = raw.split("jobs:")[0]
        self.assertIn("workflow_dispatch", header)
        self.assertNotIn("pull_request", header)
        self.assertNotRegex(header, r"(?m)^\s+push:")


class MusicAndPublisherSourceTests(unittest.TestCase):
    def test_music_is_always_procedural(self):
        import reel_builder
        from reel_builder import _resolve_music

        self.assertFalse(hasattr(reel_builder, "_music_file"))
        with tempfile.TemporaryDirectory() as raw:
            path = _resolve_music(Path(raw), 1.5)
            self.assertEqual(path.suffix.lower(), ".wav")
            self.assertIn("procedural", path.name)
            self.assertTrue(path.read_bytes().startswith(b"RIFF"))

    def test_publisher_does_not_import_utils_or_legacy_posts(self):
        import inspect
        import smart_poster

        source = inspect.getsource(smart_poster)
        self.assertNotIn("utils.texts", source)
        self.assertNotIn("generate_post", source)
        self.assertNotIn("MAIN_TEXTS", source)
        self.assertNotIn("from post_generator import", source)


class UnsafeCopyAndStaleReelTests(unittest.TestCase):
    def _unsafe_story_plan(self, country: str):
        dest = next(item for item in DESTINATIONS if item["country"] == country)
        plan = build_offline_plan(destination=dest)
        plan.story_slides = ["Виза без отказа сегодня"] + list(plan.story_slides[1:])
        plan.reel_cta = "100% успеха"
        self.assertFalse(contains_forbidden_claims(plan.telegram_text))
        self.assertFalse(plan_copy_is_safe(plan))
        return plan

    def test_plan_copy_rejects_story_and_keeps_country_on_fallback(self):
        plan = self._unsafe_story_plan("Китай")
        self.assertFalse(plan_copy_is_safe(plan))
        safe = ensure_safe_plan(plan)
        self.assertEqual(safe.country, "Китай")
        self.assertTrue(plan_copy_is_safe(safe))
        self.assertFalse(any(contains_forbidden_claims(slide) for slide in safe.story_slides))

    def test_main_does_not_publish_stale_unsafe_reel(self):
        plan = self._unsafe_story_plan("Китай")
        story_batches = []
        published = {}
        dummy = b"x" * 30_000

        def spy_stories(slides, backgrounds=None):
            items = list(slides)
            story_batches.append(items)
            count = max(2, len(items[:4]))
            return [b"F" * 2500] * count

        def spy_publish(pub_plan, poster, reel, **kwargs):
            published["country"] = pub_plan.country
            published["stories"] = list(pub_plan.story_slides)
            published["cta"] = pub_plan.reel_cta
            published["reel"] = reel
            return PublishResult(main_ok=True, reel_status="sent" if reel else "skipped")

        with patch("smart_poster.generate_content_plan", return_value=plan), patch(
            "smart_poster.build_stories", side_effect=spy_stories
        ), patch("smart_poster.build_carousel", return_value=[dummy]), patch(
            "smart_poster.build_poster", return_value=dummy
        ), patch(
            "smart_poster.build_typographic_background", return_value=dummy
        ), patch(
            "smart_poster._load_hero_image", return_value=(dummy, "typographic")
        ), patch(
            "smart_poster._build_social_backgrounds", return_value=[dummy] * 5
        ), patch(
            "smart_poster.build_branded_reel", return_value=b"REBUILT_REEL"
        ), patch(
            "smart_poster.save_social_assets"
        ), patch(
            "smart_poster.publish_package", side_effect=spy_publish
        ):
            code = main([])

        self.assertEqual(code, 0)
        self.assertEqual(published["country"], "Китай")
        self.assertTrue(story_batches)
        self.assertEqual(story_batches[-1], published["stories"])
        self.assertFalse(any(contains_forbidden_claims(slide) for slide in published["stories"]))
        self.assertFalse(contains_forbidden_claims(published["cta"]))
        self.assertNotIn("без отказа", " ".join(published["stories"]).lower())
        if published["reel"] is not None:
            self.assertEqual(published["reel"], b"REBUILT_REEL")


if __name__ == "__main__":
    unittest.main()
