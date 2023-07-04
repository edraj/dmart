import glob
import json

from utils.helpers import pp


languages: dict[str, dict[str, str]] = {}
def load_langs():
    language_list = glob.glob("languages/*.json")
    pp(language_list=language_list)
    for lang in language_list:
        filename = lang.split('/')
        pp(filename=filename)
        lang_code = filename[1].split('.')[0]
        pp(LOADER_lang_code=lang_code)
        with open(lang, 'r', encoding='utf8') as file:
            languages[lang_code] = json.load(file)