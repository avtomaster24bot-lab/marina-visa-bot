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

    def to_dict(self) -> dict:
        return asdict(self)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('AGNES_API_KEY', '').strip()}",
        "Content-Type": "application/json",
    }


def _agnes_chat(system_prompt: str, user_prompt: str, max_tokens: int = 2400) -> Optional[str]:
    if not os.getenv("AGNES_API_KEY", "").strip():
        print("[content] AGNES_API_KEY is not set")
        return None
    payload = {
        "model": AGNES_TEXT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.78,
        "max_tokens": max_tokens,
        "stream": False,
    }
    try:
        r = requests.post(f"{AGNES_BASE_URL}/v1/chat/completions", headers=_headers(), json=payload, timeout=(15, 100))
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


def _fallback() -> ContentPlan:
    d = random.choice(DESTINATIONS)
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
        video_prompt=(f"Premium cinematic vertical travel commercial for {d['country']}. Open on a beautiful destination/departure moment, then a natural close-up of a closed passport and travel folder in hand, then traveler confidently moving toward departure. 3 distinct shots, elegant camera movement, premium lighting, aspirational not bureaucratic, no dialogue, no generated text, no logos, 9:16."),
        reel_hook=f"ПЛАНИРУЕТЕ {d['country'].upper()}?",
        reel_middle="ВИЗОВУЮ ПОДГОТОВКУ МОЖНО УПРОСТИТЬ",
        reel_cta="РАЗБЕРЁМ ВАШУ СИТУАЦИЮ",
        carousel_slides=["ПОЕЗДКА УЖЕ В ПЛАНАХ?", "НЕ НАЧИНАЙТЕ С ХАОТИЧНОГО ПОИСКА", "СНАЧАЛА РАЗБЕРИТЕ СВОЮ СИТУАЦИЮ", "ПРОВЕРЬТЕ ПОДГОТОВКУ ПО ШАГАМ", "НУЖНА ПОМОЩЬ? НАПИШИТЕ МАРИНЕ"],
        story_slides=["ПЛАНИРУЕТЕ ПОЕЗДКУ?", "ВИЗОВАЯ ЧАСТЬ ВЫЗЫВАЕТ ВОПРОСЫ?", "РАЗБЕРЁМ ПОДГОТОВКУ ПО ШАГАМ", "ЗАЯВКА В MARINA VISA BOT"],
    )


def generate_content_plan() -> ContentPlan:
    d = random.choice(DESTINATIONS)
    fmt, angle = random.choice(CONTENT_FORMATS)
    archetype = random.choice(VISUAL_ARCHETYPES)

    system = """Ты креативный директор и senior performance-копирайтер премиального визового сервиса в Казахстане.
Твоя задача: создавать не типичный скучный AI-пост, а цельную рекламную кампанию из одного сильного инсайта.

КРИТИЧЕСКИЕ ПРАВИЛА:
1. Никаких выдуманных визовых требований, сроков, сборов, списков документов, финансовых норм, вероятности одобрения или гарантий.
2. Не использовать страх, давление, фразы «консульство откажет», «ошибка = отказ», «100%».
3. Не писать банальности вроде «мечтаете о путешествии?» без конкретной жизненной сцены.
4. Один пост = одна идея. Визуал и видео должны раскрывать ту же идею.
5. Визуал должен быть destination-first и aspirational. Архитектура, город, аэропорт, поездка и атмосфера — главные герои.
6. Не ставь человеческое лицо крупным планом. Не делай руки, лицо или фигуру главным объектом. Если нужен человек — показывай со спины, сбоку на среднем/дальнем плане или как маленькую часть сцены.
7. Картинка должна выглядеть как резкая premium travel campaign/editorial, а не stock office photo: sharp focus, crisp detail, realistic geometry, no blur.
8. Видео должно иметь 3 понятных визуальных бита и движение. Не просто руки листают пустой блокнот.
9. На AI-видео НЕ проси генерировать надписи. Титры мы наложим программно.
10. Пиши естественным русским языком. Не использовать канцелярит и чрезмерное количество эмодзи.
11. image_prompt и video_prompt пиши на английском.
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
 "headline":"сильный рекламный заголовок 3-7 слов, БЕЗ точки, не повторяющий страну дважды",
 "subheadline":"короткая расшифровка до 8 слов",
 "telegram_text":"130-190 слов. Сцена узнавания -> внутреннее напряжение/задача -> как помогает Марина -> спокойный CTA. Никакой воды. Добавь телефон и ссылку.",
 "instagram_caption":"70-110 слов, короче и динамичнее Telegram",
 "image_prompt":"подробный premium commercial/editorial travel prompt 4:5; destination-first; architecture/environment dominant; sharp crisp focus; specify foreground/midground/background, lens feel, light, atmosphere; no close-up face, no close-up hands, people only distant/from behind when needed; no blur, no malformed anatomy, no duplicate objects, no readable text/data/logos",
 "video_prompt":"vertical 9:16 premium travel commercial, 6-8 seconds, exactly 3 visual beats/shots described in sequence, meaningful camera movement, destination + travel preparation, aspirational, no dialogue/no captions/no generated text/no logos",
 "reel_hook":"2-5 слов для первых 2 секунд",
 "reel_middle":"3-7 слов для середины",
 "reel_cta":"2-6 слов финального CTA",
 "carousel_slides":["5 слайдов, первый — сильный hook, остальные раскрывают одну мысль, каждый до 9 слов"],
 "story_slides":["4 экрана, каждый до 9 слов, hook -> tension -> solution -> CTA"]
}}"""

    data = _extract_json(_agnes_chat(system, user) or "")
    if not data:
        return _fallback()
    try:
        tg = str(data["telegram_text"]).strip()
        if not tg.startswith("📅"):
            tg = f"📅 {datetime.now().strftime('%d.%m.%Y')}\n\n{tg}"
        return ContentPlan(
            country=str(data.get("country") or d["country"]).strip(),
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
            carousel_slides=[str(x).strip() for x in data.get("carousel_slides", [])][:5],
            story_slides=[str(x).strip() for x in data.get("story_slides", [])][:4],
        )
    except Exception as exc:
        print(f"[content] invalid plan fields: {exc}")
        return _fallback()
