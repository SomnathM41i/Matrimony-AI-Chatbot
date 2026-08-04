import random
import threading
from app.services.schema_discovery import (
    get_all_castes, get_all_religions, get_all_cities,
    get_all_educations, get_all_occupations,
)


_examples_cache = None
_examples_lock = threading.Lock()


def _pick(values: list[str], n: int = 1) -> str | list[str]:
    if not values:
        return "" if n == 1 else []
    picked = random.sample(values, min(n, len(values)))
    return picked[0] if n == 1 else picked


def _generate_examples() -> str:
    castes = get_all_castes()
    cities = get_all_cities()
    religions = get_all_religions()
    educations = get_all_educations()
    occupations = get_all_occupations()

    c1, c2, c3 = _pick(castes, 3) if len(castes) >= 3 else (_pick(castes), _pick(castes), _pick(castes))
    city1, city2, city3 = _pick(cities, 3) if len(cities) >= 3 else (_pick(cities), _pick(cities), _pick(cities))
    rel1 = _pick(religions)
    edu1, edu2 = _pick(educations, 2) if len(educations) >= 2 else (_pick(educations), _pick(educations))
    occ1 = _pick(occupations)

    lines = [
        "EXAMPLES (generated from real database values):",
        "",
        f'User: show me 5 {c1} girls in {city1}',
        'JSON: {"intent": "profile_search", "filters": {"gender": "Female", "caste": "' + c1 + '", "city": "' + city1 + '"}, "limit": 5}',
        "",
        f'User: {c2} मुलगी हवी आहे {city2} मध्ये',
        'JSON: {"intent": "profile_search", "filters": {"gender": "Female", "caste": "' + c2 + '", "city": "' + city2 + '"}, "limit": 10}',
        "",
        f'User: {c3} {rel1} boy in {city3}',
        'JSON: {"intent": "profile_search", "filters": {"gender": "Male", "caste": "' + c3 + '", "religion": "' + rel1 + '", "city": "' + city3 + '"}, "limit": 10}',
        "",
        f'User: {edu1} {occ1} girl age below 30',
        'JSON: {"intent": "profile_search", "filters": {"gender": "Female", "education": "' + edu1 + '", "occupation": "' + occ1 + '", "age_max": 30}, "limit": 10}',
        "",
        f'User: unmarried {c1} girl {city1} age between 25 and 30',
        'JSON: {"intent": "profile_search", "filters": {"gender": "Female", "caste": "' + c1 + '", "city": "' + city1 + '", "marital_status": "Unmarried", "age_min": 25, "age_max": 30}, "limit": 10}',
        "",
        f'User: {city2} मध्ये {edu2} मुलगा दाखवा',
        'JSON: {"intent": "profile_search", "filters": {"gender": "Male", "education": "' + edu2 + '", "city": "' + city2 + '"}, "limit": 10}',
        "",
        'User: tell me about her family',
        'JSON: {"intent": "profile_detail", "fields": ["family"]}',
        "",
        'User: what is her education and income',
        'JSON: {"intent": "profile_detail", "fields": ["education", "income"]}',
        "",
        'User: show her horoscope',
        'JSON: {"intent": "profile_detail", "fields": ["horoscope"]}',
        "",
        'User: is she manglik',
        'JSON: {"intent": "profile_detail", "fields": ["manglik"]}',
        "",
        'User: तिचे शिक्षण काय आहे',
        'JSON: {"intent": "profile_detail", "fields": ["education"]}',
        "",
        'User: उसकी कुंडली दिखाओ',
        'JSON: {"intent": "profile_detail", "fields": ["horoscope"]}',
        "",
        'User: तिचे बायोडाटा दाखवा',
        'JSON: {"intent": "biodata", "fields": ["all"]}',
        "",
        'User: show me her biodata',
        'JSON: {"intent": "biodata", "fields": ["all"]}',
        "",
        'User: compare her with the first profile',
        'JSON: {"intent": "comparison", "selected_index": 1}',
        "",
        'User: पहिली आणि दुसरी यांची तुलना करा',
        'JSON: {"intent": "comparison", "selected_index": 1, "selected_reference": "second"}',
        "",
        'User: तुमच्या सदस्यत्व योजना काय आहेत',
        'JSON: {"intent": "membership"}',
        "",
        'User: membership ka price kitna hai',
        'JSON: {"intent": "membership"}',
        "",
        'User: नमस्कार',
        'JSON: {"intent": "greeting"}',
        "",
        'User: what about the second one',
        'JSON: {"intent": "follow_up", "selected_index": 2}',
        "",
        'User: उसकी फोटो दिखाओ',
        'JSON: {"intent": "follow_up"}',
        "",
        'User: आज किती नोंदणी झाली',
        'JSON: {"intent": "admin"}',
        "",
        'User: how can I contact the site admin',
        'JSON: {"intent": "admin"}',
        "",
        'User: hi',
        'JSON: {"intent": "greeting"}',
        "",
    ]

    return "\n".join(lines)


def generate_examples() -> str:
    global _examples_cache
    if _examples_cache is None:
        with _examples_lock:
            if _examples_cache is None:
                _examples_cache = _generate_examples()
    return _examples_cache


def refresh_examples():
    global _examples_cache
    with _examples_lock:
        _examples_cache = _generate_examples()
