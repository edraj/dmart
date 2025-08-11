import re

def mask_sensitive_text(log_text: str) -> str:

    
    if not log_text:
        return log_text

    sensitive_keys = (
        "password", "pass", "access_token", "refresh_token",
        "auth_token", "otp", "authorization", "token", "jwt",
        "cookie", "set-cookie"
    )
    keys_alt = "|".join(map(re.escape, sensitive_keys))

    auth_pattern = re.compile(r'(?is)\b(authorization)\b\s*[:=]\s*(?:("|\')\s*)?(Bearer|Basic)\b\s*([^\s,"\';]+)(?(2)\2)?')
    cookie_line_pattern = re.compile(r'(?im)^\s*(?:set-cookie|cookie)\s*[:=]\s*[^\r\n]+')
    kv_pattern = re.compile(
        rf'(?is)(?P<prefix>["\']?(?:{keys_alt})["\']?\s*[:=]\s*)'
        r'(?P<val>"[^"]*"|\'[^\']*\'|[^\s,;]+)'
    )
    jwt_pattern = re.compile(r'\b[A-Za-z0-9-_]{10,}\.[A-Za-z0-9-_]{10,}\.[A-Za-z0-9-_]{10,}\b')

    text = log_text

    # 1) Authorization: Bearer
    def _auth_sub(m: re.Match) -> str:
        key = m.group(1)
        quote = m.group(2) or ""
        scheme = m.group(3)
        return f"{key}: {quote}{scheme} ******{quote}"
    text = auth_pattern.sub(_auth_sub, text)

    # 2) cookie/set-cookie
    def _cookie_line_sub(m: re.Match) -> str:
        line = m.group(0)
        if ':' in line:
            k, _ = line.split(':', 1)
            return f"{k}: ******"
        if '=' in line:
            k, _ = line.split('=', 1)
            return f"{k}=******"
        return "******"
    text = cookie_line_pattern.sub(_cookie_line_sub, text)

    # 3) key:value 
    def _kv_sub(m: re.Match) -> str:
        prefix, val = m.group('prefix'), m.group('val')
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            return f"{prefix}{val[0]}******{val[-1]}"
        return f"{prefix}******"
    text = kv_pattern.sub(_kv_sub, text)

    # 4) JWT
    text = jwt_pattern.sub("******", text)

    return text
