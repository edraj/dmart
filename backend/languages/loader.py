import json
from pathlib import Path


languages: dict[str, dict[str, str]] = {}
def load_langs() -> None:
    languages_dir = Path(__file__).resolve().parent
    language_list = list(languages_dir.glob("*.json"))
    for lang in language_list:
        lang_code = lang.stem
        with open(lang, 'r', encoding='utf8') as file:
            languages[lang_code] = json.load(file)
