import json
import os
import random
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional

import requests

AGNES_BASE_URL = "https://apihub.agnes-ai.com"
AGNES_TEXT_MODEL = "agnes-2.5-flash"
BOT_LINK = "https://t.me/MarinaLiderTourBot"
PHONE = "+7 777 562 2205"

DESTINATIONS = [
    {"country": "Германия", "service": "визы в Германию", "visual": "Berlin, modern European city, airport departure atmosphere, elegant German travel details"},
    {"country": "Шенген", "service": "шенгенские визы", "visual": "elegant European city streets, rail travel, airport departure board atmosphere, refined Europe travel mood"},
    {"country": "Китай", "service": "визы в Китай", "visual": "modern Shanghai or Beijing cityscape, business travel atmosphere, airport and premium travel details"},
    {"country": "Южная Корея", "service": "визовые консультации по Южной Корее", "visual": "modern Seoul cityscape, airport and premium urban travel atmosphere"},
    {"country": "Великобритания", "service": "визовые консультации по Великобритании", "visual": "London city atmosphere, elegant streets, travel departure mood, premium editorial photography"},
]

CONTENT_FORMATS = [
    ("recognition", "узнаваемая жизненная ситуация перед поездкой, без запугивания"),
    ("clarity", "показать, что визовую подготовку можно разложить на понятные шаги"),
    ("mistake_prevention", "объяснить ценность предварительной проверки без перечисления неподтвержденных требований"),
    ("service_explainer", "простым языком объяснить, что именно делает визовый специалист"),
    ("decision", "помочь человеку решить, разбираться самому или передать организацию специалисту"),
    ("travel_desire", "начать с привлекательного образа поездки и мягко перевести к визовой подготовке"),
]

VISUAL_ARCHETYPES = [
    "destination_landmark: destination architecture and travel atmosphere are the hero; no foreground face; if people appear they are small, from behind, or distant",
    "departure_moment: premium airport or railway departure scene with elegant luggage; traveler from behind at medium/wide distance; no visible hands close-up",
    "editorial_travel_objects: premium luggage, closed passport cover, map and destination objects arranged naturally; no hands, no readable data, no duplicate objects",
    "city_arrival: cinematic arrival in the destination, architecture dominant, traveler small in frame, crisp commercial photography, no beauty portrait",
]

_BAD_ENDINGS = {
    "в", "на", "за", "из", "с", "со", "к", "по", "о", "об", "от", "до", "для", "при", "без",
    "и", "а", "но", "или", "что", "как", "если", "чтобы", "это", "не"
}
_FORBIDDEN_SOCIAL = (
    "ссылка в шапке", "link in bio", "100%", "гарантия визы", "без отказа",
    "консульство точно", "вам одобрят", "марина разберётся за вас",
)


@dataclass
class ContentPlan:
    country: str
    service: str
    content_format: str
    angle: str
    goal: str
    headline: str
    subheadline: str
    telegram_text: str
    instagram_caption: str
    image_prompt: str
    video_prompt: str
    reel_hook: str
    reel_middle: str
    reel_cta: str
    carousel_slides: list[str]
    story_slides: list[str]
    social_visual_prompts: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('AGNES_API_KEY', '').strip()}",
        "Content-Type": "application/json",
    }


def _agnes_chat(system_prompt: str, user_prompt: str, max_tokens: int = 3000) -> Optional[str]:
    if not os.getenv("AGNES_API_KEY", "").strip():
        print("[content] AGNES_API_KEY is not set")
        return None
    payload = {
        "model": AGNES_TEXT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.62,
        "max_tokens": max_tokens,
        "stream": False,
    }
    try:
        r = requests.post(
            f"{AGNES_BASE_URL}/v1/chat/completions",
            headers=_headers(), json=payload, timeout=(15, 110)
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip() or None
    except Exception as exc:
        print(f"[content] Agnes failed: {exc}")
        return None


def _extract_json(text: str) -> Optional[dict]:
    if not text:
        return None
    cleaned = text.strip().replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", cleaned, flags=re.S)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None


def _clean_slide(text: str) -> str:
    s = re.sub(r"\s+", " ", str(text or "")).strip(" \t\n\r-–—:;,.!")
    s = s.replace("LIDER TOUR", "Lider Tour")
    return s


def _valid_slide(text: str, *, max_words: int, max_chars: int) -> bool:
    s = _clean_slide(text)
    if not s:
        return False
    low = s.lower()
    if any(x in low for x in _FORBIDDEN_SOCIAL):
        return False
    words = s.split()
    if len(words) < 2 or len(words) > max_words or len(s) > max_chars:
        return False
    if words[-1].lower().strip("?!.,:;") in _BAD_ENDINGS:
        return False
    # Reject obvious fragment endings and malformed mixed tokens.
    if s.endswith(":") or re.search(r"\b[А-Яа-яЁё]{1}$", s):
        return False
    return True


def _fallback_social(country: str) -> tuple[list[str], list[str]]:
    carousel = [
        f"ВИЗА В {country.upper()}: С ЧЕГО НАЧАТЬ?",
        "ИНФОРМАЦИИ МНОГО, А ЯСНОСТИ НЕТ",
        "СНАЧАЛА РАЗБЕРИТЕ СВОЮ СИТУАЦИЮ",
        "МАРИНА ПОМОЖЕТ СОБРАТЬ ПЛАН ДЕЙСТВИЙ",
        "ЕСТЬ ВОПРОСЫ? НАПИШИТЕ НАМ",
    ]
    stories = [
        f"ПЛАНИРУЕТЕ ПОЕЗДКУ В {country.upper()}?",
        "НЕ ЗНАЕТЕ, С ЧЕГО НАЧАТЬ?",
        "РАЗБЕРЁМ ВАШУ СИТУАЦИЮ ПО ШАГАМ",
        "НАПИШИТЕ МАРИНЕ",
    ]
    return carousel, stories




def _review_social_copy(country: str, carousel_raw, stories_raw) -> tuple[list[str], list[str]]:
    """Second Agnes pass used as a Russian copy editor before deterministic gates."""
    carousel = carousel_raw if isinstance(carousel_raw, list) else []
    stories = stories_raw if isinstance(stories_raw, list) else []
    prompt = f"""Ты строгий редактор русского рекламного текста. Исправь только короткие фразы карусели и Stories для визового сервиса.
Направление: {country}.

Проверь каждую фразу на:
- грамматику и согласование слов;
- естественный современный русский;
- законченность мысли;
- отсутствие обрыва;
- отсутствие канцелярита и бессмысленных абстракций;
- отсутствие обещаний результата;
- отсутствие CTA «ссылка в шапке профиля»;
- карусель: до 8 слов и до 58 символов;
- Stories: до 7 слов и до 46 символов.

Структуру сохрани:
карусель = hook -> проблема -> объяснение -> решение -> CTA;
stories = hook -> вопрос/напряжение -> решение -> CTA.

Исходная карусель: {json.dumps(carousel, ensure_ascii=False)}
Исходные Stories: {json.dumps(stories, ensure_ascii=False)}

Верни только JSON:
{{"carousel_slides":[ровно 5 строк],"story_slides":[ровно 4 строки]}}"""
    reviewed = _extract_json(_agnes_chat(
        "Ты безошибочный русскоязычный copy editor. Верни только JSON без markdown.",
        prompt,
        max_tokens=800,
    ) or "")
    if not reviewed:
        print("[content] social copy review unavailable; deterministic gate will be used")
        return carousel, stories
    return reviewed.get("carousel_slides", carousel), reviewed.get("story_slides", stories)


def _quality_gate_social(country: str, carousel_raw, stories_raw) -> tuple[list[str], list[str]]:
    fallback_car, fallback_sto = _fallback_social(country)

    carousel = []
    raw = carousel_raw if isinstance(carousel_raw, list) else []
    for i in range(5):
        candidate = _clean_slide(raw[i]) if i < len(raw) else ""
        carousel.append(candidate if _valid_slide(candidate, max_words=8, max_chars=58) else fallback_car[i])

    stories = []
    raw_s = stories_raw if isinstance(stories_raw, list) else []
    for i in range(4):
        candidate = _clean_slide(raw_s[i]) if i < len(raw_s) else ""
        stories.append(candidate if _valid_slide(candidate, max_words=7, max_chars=46) else fallback_sto[i])

    print(f"[content] social quality gate: carousel={len(carousel)} stories={len(stories)}")
    return carousel, stories


def _default_social_visuals(d: dict) -> list[str]:
    common = (
        f"{d['visual']}. Premium cinematic travel campaign photography, sharp crisp focus, realistic geometry, "
        "no readable text, no logos, no watermark, no close-up face, no close-up hands, vertical composition with safe negative space for typography. "
    )
    return [
        common + "Scene 1: iconic destination cityscape or architectural arrival view, destination is unmistakable, wide establishing shot, aspirational morning or golden-hour light.",
        common + "Scene 2: elegant airport or railway departure concourse, traveler small and seen from behind with one suitcase, strong leading lines, clean premium travel mood.",
        common + "Scene 3: editorial travel preparation still life with closed passport cover, map, luggage tag and neat travel folder, no personal data, no hands, sophisticated table composition.",
        common + "Scene 4: traveler from behind moving through the destination or terminal, architecture dominant, sense of progress and confidence, medium-wide shot.",
        common + "Scene 5: clean premium destination skyline or terminal window scene with generous negative space, elegant luggage detail, calm confident CTA-ready composition.",
    ]


def _fallback() -> ContentPlan:
    d = random.choice(DESTINATIONS)
    carousel, stories = _fallback_social(d["country"])
    return ContentPlan(
        country=d["country"], service=d["service"], content_format="clarity",
        angle="поездка уже в планах, а визовую подготовку хочется пройти спокойно",
        goal="получить заявку на консультацию",
        headline=f"{d['country'].upper()}: ПОЕЗДКА НАЧИНАЕТСЯ С ПЛАНА",
        subheadline="Разберём визовую подготовку по шагам",
        telegram_text=(
            f"📅 {datetime.now().strftime('%d.%m.%Y')}\n\n"
            f"Планируете поездку в {d['country']}? Самая неприятная часть подготовки начинается не с чемодана, а с десятков вкладок и противоречивых советов.\n\n"
            "Марина помогает разложить вашу визовую задачу по шагам: понять, что уже подготовлено, какие вопросы относятся именно к вашей ситуации и что стоит дополнительно проверить по официальным источникам. Без обещаний за консульство и без выдуманных требований.\n\n"
            "Вы сохраняете контроль над поездкой, но не тратите время на хаотичный поиск информации.\n\n"
            f"Напишите Марине: {PHONE}\nОставить заявку: {BOT_LINK}"
        ),
        instagram_caption=f"Поездка в {d['country']} уже в планах? Визовую подготовку легче проходить, когда она разложена по понятным шагам. Марина поможет структурировать вашу ситуацию и подготовиться без хаотичного поиска. Заявка: {BOT_LINK}",
        image_prompt=(f"Premium travel campaign photograph, {d['visual']}. Destination-first composition, cinematic natural light, sophisticated editorial travel advertising, subtle closed passport and travel folder in foreground, no readable data, no text, no logos, no watermark, no generic woman posing at desk, photorealistic, 4:5 vertical."),
        video_prompt=(f"Premium cinematic vertical travel commercial for {d['country']}. Open on a beautiful destination/departure moment, then a natural travel preparation detail, then traveler confidently moving toward departure. 3 distinct shots, elegant camera movement, premium lighting, aspirational not bureaucratic, no dialogue, no generated text, no logos, 9:16."),
        reel_hook=f"ПЛАНИРУЕТЕ {d['country'].upper()}?",
        reel_middle="ВИЗОВУЮ ПОДГОТОВКУ МОЖНО УПРОСТИТЬ",
        reel_cta="РАЗБЕРЁМ ВАШУ СИТУАЦИЮ",
        carousel_slides=carousel,
        story_slides=stories,
        social_visual_prompts=_default_social_visuals(d),
    )


def generate_content_plan() -> ContentPlan:
    d = random.choice(DESTINATIONS)
    fmt, angle = random.choice(CONTENT_FORMATS)
    archetype = random.choice(VISUAL_ARCHETYPES)

    system = """Ты креативный директор и senior performance-копирайтер премиального визового сервиса в Казахстане.
Создай цельную рекламную кампанию из одного сильного инсайта.

КРИТИЧЕСКИЕ ПРАВИЛА:
1. Никаких выдуманных визовых требований, сроков, сборов, списков документов, финансовых норм, вероятности одобрения или гарантий.
2. Не использовать страх, давление, «100%», «без отказа» и обещания за консульство.
3. Один пост = одна идея. Визуал, карусель, Stories и видео раскрывают ту же идею.
4. Визуал destination-first: страна, архитектура, аэропорт, дорога, поездка. Лица/руки не являются главным объектом.
5. Картинки резкие, premium editorial/commercial, realistic geometry, no blur.
6. На AI-видео и AI-картинках не проси генерировать надписи: текст накладывается программно.
7. Русский язык должен быть грамотным, естественным и законченным.
8. КАРУСЕЛЬ: ровно 5 самостоятельных законченных фраз. Каждая 2-8 слов и максимум 58 символов. Нельзя обрывать фразу. Нельзя заканчивать предлогом/союзом. Структура: hook -> проблема -> объяснение -> решение -> CTA.
9. STORIES: ровно 4 самостоятельных законченных фразы. Каждая 2-7 слов и максимум 46 символов. Структура: hook -> вопрос/напряжение -> решение -> CTA.
10. Запрещены CTA «ссылка в шапке профиля» и «link in bio». Используй универсально: «Напишите нам», «Напишите Марине», «Оставьте заявку».
11. social_visual_prompts: ровно 5 РАЗНЫХ сцен одной кампании. Все на английском. Сцены должны визуально отличаться, но сохранять одну страну/палитру/настроение. Каждая сцена безопасна для crop 4:5 и 9:16 и имеет negative space под текст.
Верни только валидный JSON без markdown."""

    user = f"""Создай кампанию для направления: {d['country']}.
Услуга: {d['service']}.
Формат: {fmt}. Угол: {angle}.
Визуальная стратегия: {archetype}.
Допустимый визуальный контекст: {d['visual']}.
Цель: заявка на консультацию.
Разрешенные бизнес-факты: специалист Марина; телефон {PHONE}; Telegram-бот {BOT_LINK}.

JSON строго такой структуры:
{{
 "country":"...",
 "service":"...",
 "content_format":"{fmt}",
 "angle":"...",
 "goal":"получить заявку на консультацию",
 "headline":"сильный рекламный заголовок 3-7 слов",
 "subheadline":"короткая расшифровка до 8 слов",
 "telegram_text":"130-190 слов: узнаваемая сцена -> задача -> как помогает Марина -> CTA; добавь телефон и ссылку",
 "instagram_caption":"70-110 слов",
 "image_prompt":"premium commercial/editorial travel prompt 4:5, destination-first, sharp crisp focus, no close-up faces/hands, no text/data/logos",
 "video_prompt":"vertical 9:16 premium travel commercial, 6-8 seconds, exactly 3 visual beats, no dialogue/captions/generated text/logos",
 "reel_hook":"2-5 слов",
 "reel_middle":"3-7 слов",
 "reel_cta":"2-6 слов",
 "carousel_slides":["ровно 5 коротких законченных фраз"],
 "story_slides":["ровно 4 коротких законченных фразы"],
 "social_visual_prompts":["ровно 5 разных English visual prompts for 5 different scenes of the same campaign"]
}}"""

    data = _extract_json(_agnes_chat(system, user) or "")
    if not data:
        return _fallback()

    try:
        tg = str(data["telegram_text"]).strip()
        if not tg.startswith("📅"):
            tg = f"📅 {datetime.now().strftime('%d.%m.%Y')}\n\n{tg}"

        country = str(data.get("country") or d["country"]).strip()
        reviewed_carousel, reviewed_stories = _review_social_copy(
            country,
            data.get("carousel_slides", []),
            data.get("story_slides", []),
        )
        carousel, stories = _quality_gate_social(
            country,
            reviewed_carousel,
            reviewed_stories,
        )

        prompts_raw = data.get("social_visual_prompts", [])
        prompts = [str(x).strip() for x in prompts_raw if str(x).strip()] if isinstance(prompts_raw, list) else []
        defaults = _default_social_visuals(d)
        while len(prompts) < 5:
            prompts.append(defaults[len(prompts)])
        prompts = prompts[:5]

        return ContentPlan(
            country=country,
            service=str(data.get("service") or d["service"]).strip(),
            content_format=str(data.get("content_format") or fmt).strip(),
            angle=str(data.get("angle") or angle).strip(),
            goal="получить заявку на консультацию",
            headline=str(data["headline"]).strip(),
            subheadline=str(data["subheadline"]).strip(),
            telegram_text=tg,
            instagram_caption=str(data["instagram_caption"]).strip(),
            image_prompt=str(data["image_prompt"]).strip(),
            video_prompt=str(data["video_prompt"]).strip(),
            reel_hook=str(data["reel_hook"]).strip(),
            reel_middle=str(data["reel_middle"]).strip(),
            reel_cta=str(data["reel_cta"]).strip(),
            carousel_slides=carousel,
            story_slides=stories,
            social_visual_prompts=prompts,
        )
    except Exception as exc:
        print(f"[content] invalid plan fields: {exc}")
        return _fallback()
