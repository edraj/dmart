from hashlib import blake2b, md5
import sys


SECURED_FIELDS = [
    "name",
    "email",
    "ip",
    "pin",
    "shortname",
    "pin",
    "msisdn",
    "imsi",
    "old_username",
    "firstname",
    "first_name",
    "lastname",
    "last_name",
    "password",
]

def hashing_data(data: str):
    hash = blake2b(salt=md5(data.encode()).digest())
    hash.update(data.encode())
    hashed_val = md5(hash.digest()).hexdigest()
    return hashed_val


def exit_with_error(msg: str):
    print("ERROR!!", msg)
    sys.exit(1)


def validate_config(config_obj: dict):
    if (
        not config_obj.get("space")
        or not config_obj.get("subpath")
        or not config_obj.get("resource_type")
    ):
        print(f"Not valid {config_obj}")
        return False
    return True


def remove_fields(src: dict, restricted_keys: list):
    for k in list(src.keys()):
        if type(src[k]) == list:
            for item in src[k]:
                if type(item) == dict:
                    item = remove_fields(item, restricted_keys)
        elif type(src[k]) == dict:
            src[k] = remove_fields(src[k], restricted_keys)

        if k in restricted_keys:
            del src[k]

    return src


def enc_dict(d: dict):
    for k, v in d.items():
        if type(v) is dict:
            d[k] = enc_dict(v)
        elif type(d[k]) == list:
            for item in d[k]:
                if type(item) == dict:
                    item = enc_dict(item)
        elif k in SECURED_FIELDS:
            d[k] = hashing_data(str(v))

    return d


def prepare_output(
    meta: dict,
    payload: dict,
    included_meta_fields: dict,
    excluded_payload_fields: dict,
):
    out = payload
    for field_meta in included_meta_fields:
        field_name = field_meta.get("field_name")
        rename_to = field_meta.get("rename_to")
        if not field_name:
            continue
        if rename_to:
            out[rename_to] = meta.get(field_name, "")
        else:
            out[field_name] = meta.get(field_name, "")
    out = remove_fields(out, [field["field_name"] for field in excluded_payload_fields])
    return out
