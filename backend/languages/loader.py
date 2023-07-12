import glob
import json


languages: dict[str, dict[str, str]] = {}
def load_langs():
    language_list = glob.glob("languages/*.json")
    for lang in language_list:
        filename = lang.split('/')
        lang_code = filename[1].split('.')[0]
        with open(lang, 'r', encoding='utf8') as file:
            languages[lang_code] = json.load(file)