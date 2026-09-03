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

SAFE_TOPICS = [
    {
        "country": "Германия",
        "service": "визы в Германию",
        "angles": [
            "человек планирует поездку и не хочет запутаться в подготовке документов",
            "поездка важна, а времени разбираться в процессе самостоятельно мало",
            "клиент хочет заранее проверить пакет документов перед подачей",
        ],
    },
    {
        "country": "Шенген",
        "service": "шенгенские визы",
        "angles": [
            "семья планирует европейскую поездку и хочет спокойно пройти подготовку",
            "путешественник хочет собрать документы без хаоса и лишней спешки",
            "клиент уже выбрал маршрут и хочет профессиональную проверку подготовки",
        ],
    },
    {
        "country": "Китай",
        "service": "визы в Китай",
        "angles": [
            "предстоит деловая или рабочая поездка и важно организовать подготовку заранее",
            "клиенту нужен понятный порядок действий по своей визовой ситуации",
            "поездка связана с работой, поэтому ошибки и потеря времени особенно нежелательны",
        ],
    },
    {
        "country": "Другие страны",
        "service": "визы в США, Великобританию, Индию, Вьетнам, Корею и другие направления",
        "angles": [
            "человек выбрал страну, но не понимает, с чего начинать визовую подготовку",
            "поездка уже запланирована, а визовую часть хочется передать специалисту",
            "клиент хочет получить персональный разбор своей ситуации вместо общих советов из интернета",
        ],
    },
]

LOCAL_POSTS = [
    """✈️ Поездка уже в планах, а документы ещё нет?

Когда билеты, маршрут и даты начинают складываться, визовая часть часто остаётся самым непонятным пунктом. В интернете десятки советов, но они не учитывают вашу конкретную ситуацию, цель поездки и документы.

Проще начать не с случайных списков, а с персональной проверки: что уже есть, чего не хватает и что лучше подготовить заранее. Марина помогает разобрать ситуацию и организовать подготовку документов без лишней суеты.

Не обещаем результат за консульство и не заменяем официальные требования догадками. Задача — аккуратно подготовить вашу часть процесса и вовремя заметить вопросы, которые стоит уточнить до подачи.

📲 Оставьте заявку в боте: {bot_link}
📞 {phone}""",
    """🌍 Виза не должна превращать подготовку к поездке в второй рабочий день

Знакомая ситуация: страна уже выбрана, маршрут интересный, но вместо предвкушения поездки вы открываете десятую вкладку с документами и всё равно не уверены, что информация относится именно к вашему случаю.

В такой момент полезнее не собирать ещё больше советов, а разобрать конкретную поездку. Марина помогает структурировать подготовку, проверить комплектность ваших материалов и понять, какие вопросы требуют уточнения по официальным требованиям.

Без обещаний «100% визы» и без выдуманных сроков. Только понятная подготовка и сопровождение вашей визовой задачи.

📲 Оставьте заявку: {bot_link}
📞 {phone}""",
]


@dataclass
class ContentPlan:
    country: str
    service: str
    angle: str
    goal: str
    headline: str
    telegram_text: str
    image_prompt: str
    video_prompt: str
    instagram_caption: str
    carousel_slides: list[str]
    story_slides: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _headers() -> dict:
    api_key = os.getenv("AGNES_API_KEY", "").strip()
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _agnes_chat(system_prompt: str, user_prompt: str, max_tokens: int = 1800) -> Optional[str]:
    if not os.getenv("AGNES_API_KEY", "").strip():
        print("[content] AGNES_API_KEY is not set; using local fallback")
        return None

    payload = {
        "model": AGNES_TEXT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.65,
        "max_tokens": max_tokens,
        "stream": False,
    }
    try:
        response = requests.post(
            f"{AGNES_BASE_URL}/v1/chat/completions",
            headers=_headers(),
            json=payload,
            timeout=(15, 90),
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip() or None
    except Exception as exc:
        print(f"[content] Agnes generation failed: {exc}")
        return None


def _extract_json(text: str) -> Optional[dict]:
    if not text:
        return None
    cleaned = text.strip().replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
    return None


def _safe_local_plan() -> ContentPlan:
    item = random.choice(SAFE_TOPICS)
    angle = random.choice(item["angles"])
    post = random.choice(LOCAL_POSTS).format(bot_link=BOT_LINK, phone=PHONE)
    headline = post.splitlines()[0].strip()
    image_prompt = (
        f"Premium realistic travel consulting advertising photo for {item['country']}. "
        "An adult traveler at a clean desk reviewing passport and neatly arranged travel documents, "
        "subtle destination atmosphere in the background, calm professional mood, realistic photography, "
        "natural hands, elegant lighting, no readable text, no logos, no watermark, no visa stamp close-up."
    )
    video_prompt = (
        f"Five-second realistic vertical 9:16 commercial video about travel preparation for {item['country']}. "
        "One adult traveler calmly reviews passport and travel papers at a desk, then looks toward a travel destination image in the background. "
        "Natural realistic motion, premium cinematic lighting, no readable text, no generated logos, no dialogue, no voice-over."
    )
    return ContentPlan(
        country=item["country"], service=item["service"], angle=angle,
        goal="получить заявку на консультацию",
        headline=headline,
        telegram_text=f"📅 {datetime.now().strftime('%d.%m.%Y')}\n\n{post}",
        image_prompt=image_prompt,
        video_prompt=video_prompt,
        instagram_caption=post,
        carousel_slides=[
            "ВИЗА БЕЗ ХАОСА",
            "Начните с вашей конкретной поездки",
            "Проверьте, что уже подготовлено",
            "Уточняйте изменяемые требования по официальным источникам",
            "Нужна помощь? Оставьте заявку",
        ],
        story_slides=[
            "Поездка уже в планах?",
            "А визовые документы всё ещё вызывают вопросы?",
            "Разберём вашу ситуацию и подготовку",
            "Оставьте заявку в Marina Visa Bot",
        ],
    )


def generate_content_plan() -> ContentPlan:
    item = random.choice(SAFE_TOPICS)
    angle = random.choice(item["angles"])

    system_prompt = (
        "Ты контент-маркетолог визового сервиса в Казахстане. Создавай полезный продающий контент без выдуманных визовых фактов. "
        "КАТЕГОРИЧЕСКИ нельзя придумывать или утверждать: сроки рассмотрения, консульские сборы, точный список документов, "
        "финансовые требования, правила въезда, сроки действия паспорта, требования к фото, вероятность одобрения, гарантии визы, "
        "наличие записи, требования конкретного консульства или любые меняющиеся правила. Не обещай 100% результат. "
        "Можно говорить только об услуге: персональная консультация, структурирование подготовки, проверка предоставленных клиентом материалов, "
        "помощь в организации процесса и рекомендация сверять изменяемые правила с официальными источниками. "
        "Верни ТОЛЬКО валидный JSON, без markdown и пояснений. Пиши русский текст для публикаций, а image_prompt и video_prompt — на английском."
    )

    user_prompt = f"""
Создай единый content plan.
Направление: {item['country']}.
Услуга: {item['service']}.
Угол: {angle}.
Цель: заявка на консультацию.
Проверенные бизнес-данные, которые разрешено использовать:
- Имя специалиста: Марина.
- Телефон: {PHONE}.
- Telegram-бот для заявки: {BOT_LINK}.
- Работа с клиентами по Казахстану дистанционно указана в текущем проекте.

Нужен JSON строго такой структуры:
{{
  "country": "...",
  "service": "...",
  "angle": "...",
  "goal": "получить заявку на консультацию",
  "headline": "короткий заголовок без обещания результата",
  "telegram_text": "готовый пост 110-160 слов, разговорный, ситуация -> проблема -> помощь -> CTA; добавь телефон и ссылку на бота",
  "image_prompt": "realistic premium commercial photo prompt, 4:5, NO generated text, NO readable documents, NO logos",
  "video_prompt": "realistic premium vertical 9:16 five-second video prompt, one clear action, no dialogue, no captions, no generated text",
  "instagram_caption": "адаптированная более короткая версия 70-120 слов",
  "carousel_slides": ["5 коротких слайдов, каждый до 9 слов"],
  "story_slides": ["4 коротких story-экрана, каждый до 10 слов"]
}}
"""

    raw = _agnes_chat(system_prompt, user_prompt)
    data = _extract_json(raw or "")
    if not data:
        print("[content] invalid Agnes JSON; using local fallback")
        return _safe_local_plan()

    try:
        telegram_text = str(data["telegram_text"]).strip()
        if not telegram_text.startswith("📅"):
            telegram_text = f"📅 {datetime.now().strftime('%d.%m.%Y')}\n\n{telegram_text}"
        plan = ContentPlan(
            country=str(data.get("country") or item["country"]).strip(),
            service=str(data.get("service") or item["service"]).strip(),
            angle=str(data.get("angle") or angle).strip(),
            goal="получить заявку на консультацию",
            headline=str(data["headline"]).strip(),
            telegram_text=telegram_text,
            image_prompt=str(data["image_prompt"]).strip(),
            video_prompt=str(data["video_prompt"]).strip(),
            instagram_caption=str(data["instagram_caption"]).strip(),
            carousel_slides=[str(x).strip() for x in data.get("carousel_slides", [])][:6],
            story_slides=[str(x).strip() for x in data.get("story_slides", [])][:5],
        )
        if len(plan.carousel_slides) < 3 or len(plan.story_slides) < 3:
            raise ValueError("not enough social slides")
        print(f"[content] Agnes plan ready: {plan.country} / {plan.service}")
        return plan
    except Exception as exc:
        print(f"[content] Agnes plan validation failed: {exc}; using local fallback")
        return _safe_local_plan()
