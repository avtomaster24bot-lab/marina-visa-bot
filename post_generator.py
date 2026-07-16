import io
import os
import random
import re
import requests
from datetime import datetime
from urllib.parse import quote
from PIL import Image, ImageDraw, ImageFont

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID")

if not BOT_TOKEN or not CHANNEL_ID:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID")

# ========== РАЗВЁРНУТЫЕ ТЕКСТЫ (с лайфхаками и цитатами) ==========
MAIN_TEXTS = [
    """**Как обидно, когда из-за маленькой помарки в документах рушатся планы на поездку!**  
Вы когда‑нибудь пробовали подать на визу самостоятельно? Это как собирать пазл, где каждая деталь на своём месте. Одна лишняя запятая в анкете или старая справка о доходах — и вместо визы вы получаете отказ. Ко мне приходят люди, которые уже через это прошли. И почти всегда причина одна — документы были оформлены не совсем правильно. Консульство Германии внимательно к мелочам. Но я знаю, как собрать пазл идеально.  

Я, Марина, за 26 лет работы с визами знаю все тонкости. Моя задача — подготовить документы так, чтобы у консула не осталось сомнений. Я проверяю каждую справку, каждую бронь, каждое поле анкеты.  

Готовы доверить визу профессионалу? Переходите в бот и оставьте заявку. Я свяжусь с вами в течение часа.
""",
    """**Срочная виза в Германию: реально ли за неделю?**  
Многие думают, что срочная виза — это миф. Но я знаю, как ускорить процесс, если правильно подготовить документы и записаться на ближайшую дату. Даже при стандартном сроке рассмотрения (до 15 дней) можно выиграть время за счёт чёткой организации.  

Я помогаю клиентам, которые внезапно получили приглашение на работу, срочную командировку или неожиданно решили поехать к родственникам. Моя схема: консультация → сбор документов за 1 день → проверка → запись на подачу. Всё дистанционно.  

💡 **Лайфхак:** если у вас есть приглашение от работодателя или гостя, укажите в анкете дату поездки как можно раньше — консульство старается уложиться в заявленные сроки.  

*«Срочность не должна означать спешку. Только спокойная, быстрая подготовка приводит к результату.»*  

У вас срочная поездка? Не рискуйте — доверьтесь эксперту. Переходите в бот.
""",
    """**Ausbildung в Германии: виза для вашего будущего**  
Обучение с практикой в Германии — это шанс получить профессию и остаться в Европе. Но виза на Ausbildung — одна из самых сложных. Нужно подтвердить цель, финансовую состоятельность, знание языка и мотивацию.  

Я оформляю такие визы регулярно. Знаю, какие документы требуют особого внимания: договор с работодателем, подтверждение уровня языка B1/B2, мотивационное письмо. Без грамотной подготовки отказ неизбежен.  

💡 **Лайфхак:** мотивационное письмо должно быть персонализированным. Не пишите общими фразами. Расскажите, почему вы выбрали именно эту профессию и эту компанию. Консульство ценит искренность.  

*«Инвестиция в визу — это инвестиция в ваше будущее. Не экономьте на качестве подготовки.»*  

Хотите получить визу на Ausbildung? Я помогу. Переходите в бот.
""",
    """**Шенген для туризма: как получить мультивизу с первого раза?**  
Туристическая виза в Шенген — самая популярная, но и самая отказная. Почему? Потому что многие ошибочно считают, что её легко получить самостоятельно. На самом деле консульства проверяют каждую деталь: маршрут, брони, финансовые гарантии.  

Я оформляю туристические визы для поездок в Германию, Францию, Италию, Испанию, Грецию и другие страны. Моя задача — собрать такой пакет, который убедит консула в ваших намерениях вернуться.  

💡 **Лайфхак:** если вы планируете посетить несколько стран, подавайте визу в консульство страны, где проведёте больше всего времени. Если дни равны — в страну первого въезда.  

*«Путешествия начинаются с правильной визы. Сделайте этот шаг с профессионалом.»*  

Планируете отпуск? Давайте подготовим документы вместе. Переходите в бот.
""",
    """**Гостевая виза в Германию: приглашение — не гарантия**  
Многие думают: если есть приглашение от родственников или друзей, виза будет 100%. Но консульство смотрит не только на приглашение, но и на ваши связи с родиной, финансовую обеспеченность и цель поездки.  

Я помогаю правильно оформить гостевую визу: проверяю приглашение (оно должно быть оформлено по форме), советую, какие справки приложить, чтобы доказать, что вы вернётесь.  

💡 **Лайфхак:** если приглашающий — не близкий родственник, лучше приложить его документы о доходах и гражданстве. Это повышает доверие.  

*«Приглашение — это ключ, но открыть дверь нужно правильно.»*  

Есть приглашение в Германию? Не рискуйте отказом. Переходите в бот.
""",
    """**Водительские визы в Китай: сложно, но реально**  
Китай — отдельная история. Водительские визы (коммерческие) требуют особого подхода: приглашение от китайской компании, подтверждение деловой цели, иногда собеседование.  

Я работаю с Китаем более 25 лет, говорю по-китайски и знаю все требования консульства. Помогаю водителям, логистам, коммерческим перевозчикам получить визу без лишних проблем.  

💡 **Лайфхак:** при подаче на китайскую визу важно, чтобы даты поездки точно совпадали с указанными в приглашении. Любое несоответствие — риск отказа.  

*«Китай любит точность. В документах — тоже.»*  

Нужна виза в Китай? Обращайтесь — я помогу.
"""
]

LIFEHACKS = [
    "📌 **Лайфхак:** Всегда делайте копии всех документов перед подачей — они могут пригодиться для следующей визы.",
    "📌 **Лайфхак:** Если у вас есть недвижимость или бизнес в Казахстане, обязательно приложите подтверждающие документы — это сильный аргумент для возвращения.",
    "📌 **Лайфхак:** Заполняя анкету, используйте только английский или немецкий язык (для Германии) — перевод ошибок может быть фатальным.",
    "📌 **Лайфхак:** При подаче на шенгенскую визу брони отелей и авиабилетов должны быть оплачены. Лучше выбирать возвратные тарифы, но показывать именно оплату.",
    "📌 **Лайфхак:** Если вы работаете неофициально, подтвердите доход выпиской с карты или спонсорским письмом от родственника. Консульство это принимает.",
    "📌 **Лайфхак:** Запись в визовый центр лучше делать за 2–3 недели до планируемой поездки, а не за месяц — больше шансов получить удобное время.",
    "📌 **Лайфхак:** В мотивационном письме избегайте штампов «очень хочу посмотреть Европу». Пишите конкретно: какие музеи, мероприятия, встречи вас ждут.",
]

QUOTES = [
    "✨ *«Терпение и подготовка — вот два главных инструмента успешной визы.»*",
    "✨ *«Визовый офицер — не враг, он просто проверяет факты. Предоставьте факты — и получите визу.»*",
    "✨ *«Правильная виза — это не удача, это результат работы эксперта.»*",
    "✨ *«Визу дают не за красивые глаза, а за правильно оформленные документы.»*",
    "✨ *«Каждая поездка начинается с одного правильного шага — обращения к профессионалу.»*",
    "✨ *«26 лет практики: я знаю, что работает, а что — нет.»*",
]

# ========== КОРОТКИЕ ШАБЛОНЫ (старые) ==========
TEMPLATES = [
    """✅ **Виза в Германию — 100% успеха!**

Марина, профессиональный визовый эксперт с 26-летним опытом, поможет вам получить любую категорию немецкой визы:
• Туризм
• Гостевая (по приглашению)
• Рабочая
• Языковые курсы
• Ausbildung

🗣 Свободно владею русским, казахским, немецким, китайским и английским.

📍 Работаю по всему Казахстану дистанционно.
📲 Звоните: +7 777 562 2205

#виза #германия #шенген #казахстан #маринавизы""",
    """🚗 **Водительские визы в Китай**

Профессиональное оформление коммерческих и водительских виз в Китай. 
Опыт более 25 лет, индивидуальный подход.

✅ Помощь с документами
✅ Консультация на русском, казахском, китайском
✅ 100% результат

📞 Записывайтесь на консультацию: +7 777 562 2205

#визавкитай #китай #водительскаявиза #маринавизы""",
    """🌍 **Шенген в любые страны**

Оформляем Шенгенские визы во все страны зоны: Франция, Италия, Испания, Греция, Нидерланды и другие.

✅ Полное сопровождение
✅ Дистанционная подготовка документов
✅ Честные цены

Подробности по телефону: +7 777 562 2205

#шенген #визавевропу #туризм #маринавизы""",
    """✈️ **Виза в США, Англию, Индию, Вьетнам, Корею и другие направления**

Марина — ваш надёжный партнёр по визовым вопросам. Помогаем с любыми типами виз, сложными случаями, срочными поездками.

26 лет в туризме, лучший туроператор 2019 года.

📲 Звоните прямо сейчас: +7 777 562 2205
Работаем по всему Казахстану!

#визавсша #визаванглию #визавиндию #маринавизы""",
    """🇩🇪 **Ausbildung в Германии — ваш путь к профессии**

Поможем оформить визу для обучения с практикой (Ausbildung). Полное сопровождение, подготовка документов, запись в визовый центр.

🔥 100% успешных кейсов
🔥 Индивидуальный подход
🔥 Знание всех требований консульства

Свяжитесь со мной для консультации: +7 777 562 2205

#ausbildung #обучениевгермании #виза #маринавизы""",
    """📄 **Срочное оформление визы? Есть решение!**

Марина оказывает экспресс-подготовку документов для срочных поездок. 
Работаем дистанционно по всему Казахстану.

✅ Заполнение анкеты
✅ Проверка броней и справок
✅ Запись на подачу в Алматы и Астане

Звоните: +7 777 562 2205

#срочнаявиза #визабыстро #маринавизы""",
    """💼 **Деловая виза в Германию**

Для командировок, переговоров, участия в выставках. Поможем правильно оформить документы, чтобы избежать отказов.

🗣 Консультации на 5 языках.
📍 Работаем со всеми регионами Казахстана.

📞 +7 777 562 2205

#деловаявиза #германия #бизнес #маринавизы"""
]

# ========== ФУНКЦИИ ГЕНЕРАЦИИ ==========
def generate_long_post():
    """Собирает развёрнутый пост из MAIN_TEXTS + LIFEHACK + QUOTE."""
    main = random.choice(MAIN_TEXTS)
    # Лайфхак добавляем с вероятностью 70%
    if random.random() < 0.7:
        lifehack = random.choice(LIFEHACKS)
    else:
        lifehack = ""
    quote = random.choice(QUOTES)

    parts = [main]
    if lifehack:
        parts.append(f"\n\n{lifehack}")
    parts.append(f"\n\n{quote}")
    parts.append(f"\n\n👉 [Перейти в бот](https://t.me/MarinaLiderTourBot)")
    return "".join(parts)

def generate_short_post():
    """Возвращает короткий пост из TEMPLATES."""
    template = random.choice(TEMPLATES)
    return template  # в коротких уже есть ссылка или телефон

def generate_post():
    """Случайно выбирает тип поста: длинный (с лайфхаками) или короткий."""
    today = datetime.now().strftime("%d.%m.%Y")
    # 50% на длинный, 50% на короткий
    if random.random() < 0.5:
        post_body = generate_long_post()
    else:
        post_body = generate_short_post()
    return f"📅 {today}\n\n{post_body}"

def send_to_telegram(text):
    """Отправляет текст в Telegram канал (fallback, без изображения)."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }
    try:
        response = requests.post(url, json=payload, timeout=30)
    except requests.RequestException as e:
        print(f"Error sending message: {e}")
        return False
    if response.status_code != 200:
        print(f"Error sending message: {response.text}")
        return False
    print("Post sent successfully!")
    return True

# ========== ГЕНЕРАЦИЯ ИЗОБРАЖЕНИЙ (Pollinations.AI) ==========
def clean_text_for_prompt(text):
    """Убирает markdown, ссылки, хэштеги и дату — оставляет чистый текст для промпта."""
    text = re.sub(r'\*\*|\*|_', '', text)
    text = re.sub(r'\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'#\S+', '', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'^\s*📅?\s*\d{2}\.\d{2}\.\d{4}\s*', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def translate_to_english(text):
    """Переводит текст на английский через бесплатный MyMemory API (без ключа)."""
    try:
        response = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": text, "langpair": "ru|en"},
            timeout=10,
        )
        if response.status_code == 200:
            translated = response.json().get("responseData", {}).get("translatedText")
            if translated:
                return translated
    except requests.RequestException as e:
        print(f"Translation failed: {e}")
    return text

def generate_image_prompt(post_text):
    """Строит промпт для изображения из первых 100 символов текста поста."""
    snippet = clean_text_for_prompt(post_text)[:100]
    translated = translate_to_english(snippet)
    return f"{translated}, professional photo, visa and travel consulting theme, high quality"

def fetch_pollinations_image(prompt):
    """Запрашивает изображение у Pollinations.AI. Возвращает bytes или None при ошибке."""
    try:
        url = f"https://image.pollinations.ai/prompt/{quote(prompt)}"
        response = requests.get(url, timeout=30)
        if response.status_code == 200 and response.headers.get("content-type", "").startswith("image"):
            return response.content
        print(f"Image generation failed: status {response.status_code}")
    except requests.RequestException as e:
        print(f"Image generation error: {e}")
    return None

# ========== НАЛОЖЕНИЕ ТЕКСТА НА ИЗОБРАЖЕНИЕ (Pillow) ==========
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # ubuntu-latest (GitHub Actions)
    "C:/Windows/Fonts/arialbd.ttf",                          # Windows (локальный тест)
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",     # macOS
]

def _load_font(size):
    """Подбирает жирный шрифт с поддержкой кириллицы; иначе — дефолтный PIL-шрифт."""
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()

def extract_image_title(post_text):
    """Берёт первое предложение поста, ограничивая его 60 символами."""
    cleaned = clean_text_for_prompt(post_text)
    match = re.search(r'[.!?]', cleaned)
    first_sentence = cleaned[:match.start() + 1].strip() if match else cleaned.strip()
    if len(first_sentence) > 60:
        return first_sentence[:60].rsplit(" ", 1)[0] + "…"
    return first_sentence

def _wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        w = draw.textbbox((0, 0), candidate, font=font)[2]
        if w <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines

def add_text_overlay(image_bytes, title):
    """
    Накладывает заголовок на нижние 35% картинки: жирный белый текст
    на затемнённой полупрозрачной подложке. Возвращает JPEG bytes или
    None при любой ошибке (вызывающий код должен использовать исходную
    картинку как fallback).
    """
    try:
        base = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        width, height = base.size

        overlay_height = int(height * 0.35)
        overlay_top = height - overlay_height

        rgba = base.convert("RGBA")
        shade = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
        shade_draw = ImageDraw.Draw(shade)
        shade_draw.rectangle([(0, overlay_top), (width, height)], fill=(0, 0, 0, 160))
        composed = Image.alpha_composite(rgba, shade)

        draw = ImageDraw.Draw(composed)
        font_size = max(28, width // 16)
        font = _load_font(font_size)

        padding = int(width * 0.06)
        max_text_width = width - 2 * padding
        lines = _wrap_text(draw, title, font, max_text_width)

        line_height = font.getbbox("Ай")[3] + 10
        text_block_height = line_height * len(lines)
        text_y = overlay_top + (overlay_height - text_block_height) // 2

        for line in lines:
            line_width = draw.textbbox((0, 0), line, font=font)[2]
            text_x = (width - line_width) // 2
            draw.text((text_x, text_y), line, font=font, fill=(255, 255, 255, 255))
            text_y += line_height

        result = composed.convert("RGB")
        output = io.BytesIO()
        result.save(output, format="JPEG", quality=90)
        return output.getvalue()
    except Exception as e:
        print(f"Text overlay failed: {e}")
        return None

def send_photo_to_telegram(image_bytes, caption):
    """Отправляет изображение с подписью в Telegram канал. Возвращает True/False."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    caption_text = caption if len(caption) <= 1024 else caption[:1021] + "..."
    files = {"photo": ("post.jpg", image_bytes)}
    data = {
        "chat_id": CHANNEL_ID,
        "caption": caption_text,
        "parse_mode": "Markdown",
    }
    try:
        response = requests.post(url, data=data, files=files, timeout=30)
    except requests.RequestException as e:
        print(f"Error sending photo: {e}")
        return False
    if response.status_code != 200:
        print(f"Error sending photo: {response.text}")
        return False
    print("Post with image sent successfully!")
    return True

if __name__ == "__main__":
    post_text = generate_post()
    image_prompt = generate_image_prompt(post_text)
    image_bytes = fetch_pollinations_image(image_prompt)

    if image_bytes:
        title = extract_image_title(post_text)
        overlaid_bytes = add_text_overlay(image_bytes, title)
        final_image = overlaid_bytes if overlaid_bytes else image_bytes
        if send_photo_to_telegram(final_image, post_text):
            pass
        else:
            send_to_telegram(post_text)
    else:
        send_to_telegram(post_text)
