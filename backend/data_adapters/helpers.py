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