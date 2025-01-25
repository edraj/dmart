from utils.settings import settings


def get_nested_value(data, key):
    keys = key.split('.')
    if len(keys) == 0:
        return None
    for k in keys:
        if k in data:
            data = data[k]
        else:
            return None
    return data


def trans_magic_words(subpath: str, user_shortname: str):
    subpath = subpath.replace(settings.current_user_mw, user_shortname)
    subpath = subpath.replace("//", "/")

    if len(subpath) == 0:
        subpath = "/"
    if subpath[0] == "/" and len(subpath) > 1:
        subpath = subpath[1:]
    if subpath[-1] == "/" and len(subpath) > 1:
        subpath = subpath[:-1]
    return subpath

