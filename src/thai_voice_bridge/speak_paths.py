"""Offline Thai spoken normalization for emails, URLs, and filesystem paths.

Expands '@', dots, slashes, and common TLDs into Thai-friendly spoken forms
purely offline without audio hardware, network requests, or GUI dependencies.
Does not alter the existing phonetic terminal command matcher in phrases.py.
"""

from __future__ import annotations

import re

# Default spoken Thai representations for common computing symbols
DEFAULT_AT_SPOKEN = "แอท"
DEFAULT_DOT_SPOKEN = "ดอท"
DEFAULT_SLASH_SPOKEN = "สแลช"
DEFAULT_BACKSLASH_SPOKEN = "แบ็กสแลช"
DEFAULT_COLON_SPOKEN = "โคลอน"
DEFAULT_TILDE_SPOKEN = "ทิลดา"
DEFAULT_DOUBLE_SLASH_SPOKEN = "สแลช สแลช"

# Common TLDs mapped to their canonical Thai spoken forms.
# Multi-segment country-code TLDs appear first to allow longest-match lookups.
COMMON_TLDS: dict[str, str] = {
    # Multi-segment ccTLDs (Thailand & common international)
    ".co.th": "ดอทโคดอททีเอช",
    ".ac.th": "ดอทเอซีดอททีเอช",
    ".go.th": "ดอทโกดอททีเอช",
    ".or.th": "ดอทออร์ดอททีเอช",
    ".in.th": "ดอทไอเอ็นดอททีเอช",
    ".net.th": "ดอทเน็ตดอททีเอช",
    ".mi.th": "ดอทเอ็มไอดอททีเอช",
    ".co.uk": "ดอทโคดอทยูเค",
    ".co.jp": "ดอทโคดอทเจพี",
    ".com.au": "ดอทคอมดอทเอยู",
    ".com.sg": "ดอทคอมดอทเอสจี",
    ".com.cn": "ดอทคอมดอทซีเอ็น",
    ".org.uk": "ดอทออร์กดอทยูเค",
    ".gov.uk": "ดอทกัฟดอทยูเค",
    ".edu.au": "ดอทเอดูดอทเอยู",
    # Single-segment generic & sponsored TLDs
    ".com": "ดอทคอม",
    ".org": "ดอทออร์ก",
    ".net": "ดอทเน็ต",
    ".edu": "ดอทเอดู",
    ".gov": "ดอทกัฟ",
    ".mil": "ดอทมิล",
    ".io": "ดอทไอโอ",
    ".dev": "ดอทเดฟ",
    ".ai": "ดอทเอไอ",
    ".app": "ดอทแอป",
    ".co": "ดอทโค",
    ".me": "ดอทมี",
    ".info": "ดอทอินโฟ",
    ".biz": "ดอทบิซ",
    ".xyz": "ดอทเอ็กซ์วายแซด",
    ".tech": "ดอทเทค",
    ".online": "ดอทออนไลน์",
    ".site": "ดอทไซต์",
    ".live": "ดอทไลฟ์",
    ".cloud": "ดอทคลาวด์",
    ".store": "ดอทสโตร์",
    ".shop": "ดอทช็อป",
    ".blog": "ดอทบล็อก",
    ".news": "ดอทนิวส์",
    ".tv": "ดอททีวี",
    ".cc": "ดอทซีซี",
    ".fm": "ดอทเอฟเอ็ม",
    ".pro": "ดอทโปร",
    ".club": "ดอทคลับ",
    ".design": "ดอทดีไซน์",
    ".space": "ดอทสเปซ",
    # Single-segment ccTLDs
    ".th": "ดอททีเอช",
    ".uk": "ดอทยูเค",
    ".us": "ดอทยูเอส",
    ".jp": "ดอทเจพี",
    ".cn": "ดอทซีเอ็น",
    ".de": "ดอทดีอี",
    ".fr": "ดอทเอฟอาร์",
    ".ru": "ดอทอาร์ยู",
    ".sg": "ดอทเอสจี",
    ".hk": "ดอทเอชเค",
    ".tw": "ดอททีดับเบิลยู",
    ".vn": "ดอทวีเอ็น",
    ".my": "ดอทเอ็มวาย",
    ".id": "ดอทไอดี",
    ".kr": "ดอทเคอาร์",
    ".ca": "ดอทซีเอ",
    ".au": "ดอทเอยู",
    ".nz": "ดอทเอ็นแซด",
    ".in": "ดอทไอเอ็น",
    ".eu": "ดอทยู",
}

# Sorted TLD tuples for longest-prefix matching (e.g. '.co.th' before '.th')
_SORTED_TLDS: tuple[str, ...] = tuple(
    sorted(COMMON_TLDS.keys(), key=len, reverse=True)
)

# Common file extensions for standalone filename detection
COMMON_EXTENSIONS: frozenset[str] = frozenset(
    {
        "txt", "py", "sh", "bash", "zsh", "json", "yaml", "yml", "md",
        "html", "htm", "css", "js", "ts", "jsx", "tsx", "csv", "tsv",
        "pdf", "png", "jpg", "jpeg", "gif", "svg", "ico", "exe", "dll",
        "so", "dylib", "log", "xml", "toml", "ini", "env", "sql", "tar",
        "gz", "zip", "rar", "7z", "bak", "tmp", "ps1", "bat", "cmd",
        "c", "cpp", "h", "hpp", "rs", "go", "java", "kt", "swift",
        "php", "rb", "lock", "cfg", "conf",
    }
)

_WHITESPACE_RE = re.compile(r"\s+")
_TRAILING_PUNCT_RE = re.compile(r"[\s,;!?:.\])}'\">]+$")

# Patterns for sentence-level entity scanning
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
    re.IGNORECASE,
)

_URL_SCHEME_RE = re.compile(
    r"(?:https?|ftp|file)://[^\s<>\"']+",
    re.IGNORECASE,
)

_URL_WWW_RE = re.compile(
    r"\bwww\.[a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z0-9/._\-~%&=?#:]+",
    re.IGNORECASE,
)

_WIN_PATH_RE = re.compile(
    r"\b[a-zA-Z]:[\\/][^\s<>\"'|?*]+",
    re.IGNORECASE,
)

_UNC_PATH_RE = re.compile(
    r"\\\\[a-zA-Z0-9_.-]+\\[^\s<>\"'|?*]+",
    re.IGNORECASE,
)

_REL_PATH_RE = re.compile(
    r"(?:(?:\.\./|\.\.\\|\./|\.\\|~/|~\\)[^\s<>\"'*]+)",
)

_UNIX_PATH_RE = re.compile(
    r"/(?:[a-zA-Z0-9_.-]+/)+[a-zA-Z0-9_.-]*"
    r"|/(?:bin|boot|dev|etc|home|lib|media|mnt|opt|proc|root|run|sbin|srv|sys|tmp|usr|var)(?:/[a-zA-Z0-9_.-]+)*\b"
    r"|/[a-zA-Z0-9_-]+\.(?:txt|py|sh|json|yaml|yml|md|html|css|js|ts|csv|pdf|png|jpg|ico|exe|log|xml|toml|ini|env|sql|tar|gz|zip|bak|ps1|conf)\b",
)

_DOTFILE_RE = re.compile(
    r"(?:^|(?<=\s))\.[a-zA-Z0-9_-]+\b",
)

_FILE_EXT_RE = re.compile(
    r"\b[a-zA-Z0-9_+-]+\.(?:" + "|".join(sorted(COMMON_EXTENSIONS)) + r")\b",
    re.IGNORECASE,
)


def _collapse_whitespace(text: str) -> str:
    """Collapse internal whitespace sequences to a single space and strip."""
    return _WHITESPACE_RE.sub(" ", text).strip()


def _strip_trailing_punct(token: str) -> tuple[str, str]:
    """Split token into clean core and trailing punctuation (sentence boundary)."""
    match = _TRAILING_PUNCT_RE.search(token)
    if match and match.start() > 0:
        return token[: match.start()], token[match.start() :]
    return token, ""


def _expand_domain(
    domain: str,
    *,
    dot_spoken: str = DEFAULT_DOT_SPOKEN,
    tld_map: dict[str, str] | None = None,
    compound_tld: bool = True,
) -> str:
    """Expand TLD and internal dots in domain name."""
    mapping = tld_map if tld_map is not None else COMMON_TLDS
    lowered = domain.lower()

    # Look for matching TLD (longest match first: .co.th before .th)
    for tld in _SORTED_TLDS:
        if lowered.endswith(tld):
            head = domain[: -len(tld)]
            spoken_tld = mapping.get(tld, "")
            if dot_spoken != DEFAULT_DOT_SPOKEN and spoken_tld.startswith(DEFAULT_DOT_SPOKEN):
                spoken_tld = dot_spoken + spoken_tld[len(DEFAULT_DOT_SPOKEN) :]
            if not compound_tld and spoken_tld.startswith(dot_spoken):
                rest_tld = spoken_tld[len(dot_spoken) :].strip()
                spoken_tld = f"{dot_spoken} {rest_tld}"
            if head:
                head_expanded = head.replace(".", f" {dot_spoken} ")
                return f"{head_expanded} {spoken_tld}"
            return spoken_tld

    # Fallback for unlisted domains: replace all dots with dot_spoken
    return domain.replace(".", f" {dot_spoken} ")


def _expand_filename_dots(
    filename: str,
    *,
    dot_spoken: str = DEFAULT_DOT_SPOKEN,
) -> str:
    """Expand dots in a filename or path token."""
    if not filename:
        return ""
    if filename == "..":
        return f"{dot_spoken} {dot_spoken}"
    if filename == ".":
        return dot_spoken
    if filename.startswith("."):
        # Dotfile like .bashrc or .env
        rest = filename[1:]
        if "." in rest:
            expanded_rest = rest.replace(".", f" {dot_spoken} ")
            return f"{dot_spoken} {expanded_rest}"
        return f"{dot_spoken} {rest}"

    return filename.replace(".", f" {dot_spoken} ")


def _normalize_host(
    host: str,
    *,
    dot_spoken: str = DEFAULT_DOT_SPOKEN,
    colon_spoken: str = DEFAULT_COLON_SPOKEN,
    tld_map: dict[str, str] | None = None,
    compound_tld: bool = True,
) -> str:
    """Expand domain and port in host component."""
    if not host:
        return ""
    if ":" in host:
        domain, port = host.split(":", 1)
        port_part = f" {colon_spoken} {port}"
    else:
        domain = host
        port_part = ""

    domain_expanded = _expand_domain(
        domain,
        dot_spoken=dot_spoken,
        tld_map=tld_map,
        compound_tld=compound_tld,
    )
    return f"{domain_expanded}{port_part}"


def _normalize_url_path(
    path: str,
    *,
    dot_spoken: str = DEFAULT_DOT_SPOKEN,
    slash_spoken: str = DEFAULT_SLASH_SPOKEN,
) -> str:
    """Expand slashes and extensions in URL path and query."""
    if not path:
        return ""
    query_fragment = ""
    for sep in ("?", "#"):
        if sep in path:
            idx = path.index(sep)
            query_fragment = path[idx:]
            path = path[:idx]
            break

    segments = path.split("/")
    spoken_parts: list[str] = []
    has_trailing = path.endswith("/") and len(path) > 1

    inner_segments = [s for s in segments if s]
    for s in inner_segments:
        seg = _expand_filename_dots(s, dot_spoken=dot_spoken)
        spoken_parts.append(f"{slash_spoken} {seg}")

    if has_trailing:
        spoken_parts.append(slash_spoken)

    result = " ".join(spoken_parts)
    if query_fragment:
        result = f"{result}{query_fragment}"
    return f" {result}" if result else ""


def _expand_path_segments(
    rest: str,
    *,
    sep: str,
    sep_spoken: str,
    prefix: str,
    dot_spoken: str = DEFAULT_DOT_SPOKEN,
) -> str:
    """Expand segments of a filesystem path separated by sep."""
    if not rest:
        return prefix.strip()
    segments = rest.split(sep)
    expanded_segments: list[str] = []
    for s in segments:
        if s == "":
            expanded_segments.append(sep_spoken)
        elif s == "..":
            expanded_segments.append(f"{dot_spoken} {dot_spoken}")
        elif s == ".":
            expanded_segments.append(dot_spoken)
        else:
            expanded_segments.append(_expand_filename_dots(s, dot_spoken=dot_spoken))

    joined = f" {sep_spoken} ".join(expanded_segments)
    return _collapse_whitespace(f"{prefix} {joined}")


def expand_at(
    text: str,
    spoken: str = DEFAULT_AT_SPOKEN,
) -> str:
    """Expand '@' symbol to Thai spoken form."""
    if not text:
        return ""
    return _collapse_whitespace(text.replace("@", f" {spoken} "))


def expand_dots(
    text: str,
    spoken: str = DEFAULT_DOT_SPOKEN,
) -> str:
    """Expand '.' symbol to Thai spoken form."""
    if not text:
        return ""
    return _collapse_whitespace(text.replace(".", f" {spoken} "))


def expand_slashes(
    text: str,
    slash_spoken: str = DEFAULT_SLASH_SPOKEN,
    backslash_spoken: str = DEFAULT_BACKSLASH_SPOKEN,
) -> str:
    """Expand '/' and '\\' symbols to Thai spoken forms."""
    if not text:
        return ""
    expanded = text.replace("/", f" {slash_spoken} ")
    expanded = expanded.replace("\\", f" {backslash_spoken} ")
    return _collapse_whitespace(expanded)


def expand_tlds(
    text: str,
    tld_map: dict[str, str] | None = None,
    compound_tld: bool = True,
    dot_spoken: str = DEFAULT_DOT_SPOKEN,
) -> str:
    """Expand common TLDs in text to Thai-friendly spoken forms."""
    if not text:
        return ""
    mapping = tld_map if tld_map is not None else COMMON_TLDS
    out = text
    for tld in _SORTED_TLDS:
        spoken = mapping.get(tld, "")
        if dot_spoken != DEFAULT_DOT_SPOKEN and spoken.startswith(DEFAULT_DOT_SPOKEN):
            spoken = dot_spoken + spoken[len(DEFAULT_DOT_SPOKEN) :]
        if not compound_tld and spoken.startswith(dot_spoken):
            rest_tld = spoken[len(dot_spoken) :].strip()
            spoken = f"{dot_spoken} {rest_tld}"
        # Case-insensitive replacement of TLD token
        pattern = re.compile(re.escape(tld) + r"(?=\b|[\s/\\.,;!?)]|$)", re.IGNORECASE)
        out = pattern.sub(f" {spoken} ", out)
    return _collapse_whitespace(out)


def speak_email(
    email: str | None,
    *,
    at_spoken: str = DEFAULT_AT_SPOKEN,
    dot_spoken: str = DEFAULT_DOT_SPOKEN,
    tld_map: dict[str, str] | None = None,
    compound_tld: bool = True,
) -> str:
    """Normalize an email address into spoken Thai form."""
    if not email:
        return ""
    text = str(email).strip()
    if not text or "@" not in text:
        return text

    local_part, domain_part = text.rsplit("@", 1)
    local_expanded = local_part.replace(".", f" {dot_spoken} ")
    domain_expanded = _expand_domain(
        domain_part,
        dot_spoken=dot_spoken,
        tld_map=tld_map,
        compound_tld=compound_tld,
    )

    return _collapse_whitespace(f"{local_expanded} {at_spoken} {domain_expanded}")


def speak_url(
    url: str | None,
    *,
    dot_spoken: str = DEFAULT_DOT_SPOKEN,
    slash_spoken: str = DEFAULT_SLASH_SPOKEN,
    colon_spoken: str = DEFAULT_COLON_SPOKEN,
    double_slash_spoken: str = DEFAULT_DOUBLE_SLASH_SPOKEN,
    tld_map: dict[str, str] | None = None,
    compound_tld: bool = True,
) -> str:
    """Normalize a URL string into spoken Thai form."""
    if not url:
        return ""
    text = str(url).strip()
    if not text:
        return ""

    scheme_match = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*)(://+|/)(.*)$", text)
    if scheme_match:
        scheme = scheme_match.group(1)
        sep = scheme_match.group(2)
        rest = scheme_match.group(3)

        if sep.startswith("://"):
            slash_count = len(sep) - 1
            if slash_count == 2:
                spoken_sep = f" {colon_spoken} {double_slash_spoken} "
            else:
                spoken_sep = f" {colon_spoken} " + " ".join([slash_spoken] * slash_count) + " "
        elif sep == "/":
            spoken_sep = f" {slash_spoken} "
        else:
            spoken_sep = f" {colon_spoken} {slash_spoken} "

        if "/" in rest:
            host_part, path_part = rest.split("/", 1)
            path_part = "/" + path_part
        else:
            host_part = rest
            path_part = ""

        host_expanded = _normalize_host(
            host_part,
            dot_spoken=dot_spoken,
            colon_spoken=colon_spoken,
            tld_map=tld_map,
            compound_tld=compound_tld,
        )
        path_expanded = _normalize_url_path(
            path_part,
            dot_spoken=dot_spoken,
            slash_spoken=slash_spoken,
        )
        return _collapse_whitespace(f"{scheme}{spoken_sep}{host_expanded}{path_expanded}")

    if "/" in text:
        host_part, path_part = text.split("/", 1)
        path_part = "/" + path_part
    else:
        host_part = text
        path_part = ""

    host_expanded = _normalize_host(
        host_part,
        dot_spoken=dot_spoken,
        colon_spoken=colon_spoken,
        tld_map=tld_map,
        compound_tld=compound_tld,
    )
    path_expanded = _normalize_url_path(
        path_part,
        dot_spoken=dot_spoken,
        slash_spoken=slash_spoken,
    )
    return _collapse_whitespace(f"{host_expanded}{path_expanded}")


def speak_filesystem_path(
    path: str | None,
    *,
    dot_spoken: str = DEFAULT_DOT_SPOKEN,
    slash_spoken: str = DEFAULT_SLASH_SPOKEN,
    backslash_spoken: str = DEFAULT_BACKSLASH_SPOKEN,
    tilde_spoken: str = DEFAULT_TILDE_SPOKEN,
    expand_tilde: bool = True,
) -> str:
    """Normalize a filesystem path into spoken Thai form."""
    if not path:
        return ""
    text = str(path).strip()
    if not text:
        return ""

    # Windows UNC path: \\server\share...
    if text.startswith("\\\\"):
        rest = text[2:]
        prefix = f"{backslash_spoken} {backslash_spoken}"
        return _expand_path_segments(
            rest,
            sep="\\",
            sep_spoken=backslash_spoken,
            prefix=prefix,
            dot_spoken=dot_spoken,
        )

    # Windows drive path: C:\... or C:/...
    drive_match = re.match(r"^([a-zA-Z]:)([\\/])(.*)$", text)
    if drive_match:
        drive = drive_match.group(1)
        sep_char = drive_match.group(2)
        rest = drive_match.group(3)
        sep_spk = backslash_spoken if sep_char == "\\" else slash_spoken
        prefix = f"{drive} {sep_spk}"
        return _expand_path_segments(
            rest,
            sep=sep_char,
            sep_spoken=sep_spk,
            prefix=prefix,
            dot_spoken=dot_spoken,
        )

    # Home path: ~/.bashrc or ~\Documents
    if text.startswith("~"):
        t_spk = tilde_spoken if expand_tilde else "~"
        if len(text) == 1:
            return t_spk
        sep_char = text[1]
        if sep_char in ("/\\"):
            rest = text[2:]
            sep_spk = backslash_spoken if sep_char == "\\" else slash_spoken
            prefix = f"{t_spk} {sep_spk}"
            return _expand_path_segments(
                rest,
                sep=sep_char,
                sep_spoken=sep_spk,
                prefix=prefix,
                dot_spoken=dot_spoken,
            )

    # Parent relative path: ../.. or ..\..
    if text.startswith(".."):
        if len(text) == 2:
            return f"{dot_spoken} {dot_spoken}"
        sep_char = text[2]
        if sep_char in ("/\\"):
            rest = text[3:]
            sep_spk = backslash_spoken if sep_char == "\\" else slash_spoken
            prefix = f"{dot_spoken} {dot_spoken} {sep_spk}"
            return _expand_path_segments(
                rest,
                sep=sep_char,
                sep_spoken=sep_spk,
                prefix=prefix,
                dot_spoken=dot_spoken,
            )

    # Current relative path: ./ or .\
    if text.startswith("."):
        if len(text) == 1:
            return dot_spoken
        sep_char = text[1]
        if sep_char in ("/\\"):
            rest = text[2:]
            sep_spk = backslash_spoken if sep_char == "\\" else slash_spoken
            prefix = f"{dot_spoken} {sep_spk}"
            return _expand_path_segments(
                rest,
                sep=sep_char,
                sep_spoken=sep_spk,
                prefix=prefix,
                dot_spoken=dot_spoken,
            )

    # Absolute Unix path starting with /
    if text.startswith("/"):
        if text == "/":
            return slash_spoken
        rest = text[1:]
        prefix = slash_spoken
        return _expand_path_segments(
            rest,
            sep="/",
            sep_spoken=slash_spoken,
            prefix=prefix,
            dot_spoken=dot_spoken,
        )

    # General path with slashes: e.g. foo/bar or foo\bar
    if "/" in text or "\\" in text:
        result_parts: list[str] = []
        raw_tokens = re.split(r"([/\\])", text)
        for tok in raw_tokens:
            if tok == "/":
                result_parts.append(slash_spoken)
            elif tok == "\\":
                result_parts.append(backslash_spoken)
            elif tok:
                result_parts.append(_expand_filename_dots(tok, dot_spoken=dot_spoken))
        return _collapse_whitespace(" ".join(result_parts))

    # Standalone file name
    return _expand_filename_dots(text, dot_spoken=dot_spoken)


def is_email(text: str | None) -> bool:
    """Return True if text is an email address."""
    if not text:
        return False
    cleaned = text.strip()
    return bool(re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", cleaned))


def is_url(text: str | None) -> bool:
    """Return True if text is a URL."""
    if not text:
        return False
    cleaned = text.strip()
    if re.match(r"^(?:https?|ftp|file)://", cleaned, re.IGNORECASE):
        return True
    if re.match(r"^www\.[a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z0-9]+", cleaned, re.IGNORECASE):
        return True
    return False


def is_filesystem_path(text: str | None) -> bool:
    """Return True if text is a filesystem path."""
    if not text:
        return False
    cleaned = text.strip()
    if re.match(r"^[a-zA-Z]:[\\/]", cleaned):
        return True
    if cleaned.startswith(("\\\\", "/", "./", ".\\", "../", "..\\", "~/", "~\\")):
        return True
    if "/" in cleaned or "\\" in cleaned:
        return True
    if cleaned.startswith(".") and len(cleaned) > 1:
        return True
    ext = cleaned.rsplit(".", 1)[-1].lower() if "." in cleaned else ""
    return ext in COMMON_EXTENSIONS


def speak_paths(
    text: str | None,
    *,
    dot_spoken: str = DEFAULT_DOT_SPOKEN,
    slash_spoken: str = DEFAULT_SLASH_SPOKEN,
    backslash_spoken: str = DEFAULT_BACKSLASH_SPOKEN,
    at_spoken: str = DEFAULT_AT_SPOKEN,
    colon_spoken: str = DEFAULT_COLON_SPOKEN,
    tilde_spoken: str = DEFAULT_TILDE_SPOKEN,
    double_slash_spoken: str = DEFAULT_DOUBLE_SLASH_SPOKEN,
    tld_map: dict[str, str] | None = None,
    compound_tld: bool = True,
    expand_tilde: bool = True,
) -> str:
    """Expand emails, URLs, and filesystem paths in text to spoken Thai forms."""
    if text is None:
        return ""
    raw = str(text)
    if not raw.strip():
        return ""

    placeholders: dict[str, str] = {}
    counter = 0

    # 1. URLs
    for pattern in (_URL_SCHEME_RE, _URL_WWW_RE):
        for match in pattern.finditer(raw):
            token = match.group(0)
            core, trailing = _strip_trailing_punct(token)
            if not core:
                continue
            spoken = speak_url(
                core,
                dot_spoken=dot_spoken,
                slash_spoken=slash_spoken,
                colon_spoken=colon_spoken,
                double_slash_spoken=double_slash_spoken,
                tld_map=tld_map,
                compound_tld=compound_tld,
            )
            key = f"\x00URL_{counter}\x00"
            counter += 1
            placeholders[key] = f"{spoken}{trailing}"
            raw = raw.replace(token, key, 1)

    # 2. Emails
    for match in _EMAIL_RE.finditer(raw):
        token = match.group(0)
        core, trailing = _strip_trailing_punct(token)
        if not core:
            continue
        spoken = speak_email(
            core,
            at_spoken=at_spoken,
            dot_spoken=dot_spoken,
            tld_map=tld_map,
            compound_tld=compound_tld,
        )
        key = f"\x00EMAIL_{counter}\x00"
        counter += 1
        placeholders[key] = f"{spoken}{trailing}"
        raw = raw.replace(token, key, 1)

    # 3. Filesystem Paths (Windows drive, UNC, relative, absolute Unix)
    for pattern in (_WIN_PATH_RE, _UNC_PATH_RE, _REL_PATH_RE, _UNIX_PATH_RE):
        for match in pattern.finditer(raw):
            token = match.group(0)
            core, trailing = _strip_trailing_punct(token)
            if not core:
                continue
            spoken = speak_filesystem_path(
                core,
                dot_spoken=dot_spoken,
                slash_spoken=slash_spoken,
                backslash_spoken=backslash_spoken,
                tilde_spoken=tilde_spoken,
                expand_tilde=expand_tilde,
            )
            key = f"\x00PATH_{counter}\x00"
            counter += 1
            placeholders[key] = f"{spoken}{trailing}"
            raw = raw.replace(token, key, 1)

    # 4. Dotfiles (e.g. .env, .gitignore)
    for match in _DOTFILE_RE.finditer(raw):
        token = match.group(0)
        core, trailing = _strip_trailing_punct(token)
        if not core:
            continue
        spoken = speak_filesystem_path(
            core,
            dot_spoken=dot_spoken,
            slash_spoken=slash_spoken,
            backslash_spoken=backslash_spoken,
            tilde_spoken=tilde_spoken,
            expand_tilde=expand_tilde,
        )
        key = f"\x00FILE_{counter}\x00"
        counter += 1
        placeholders[key] = f"{spoken}{trailing}"
        raw = raw.replace(token, key, 1)

    # 5. Standalone filenames with known extensions (e.g. app.py, report.pdf)
    for match in _FILE_EXT_RE.finditer(raw):
        token = match.group(0)
        core, trailing = _strip_trailing_punct(token)
        if not core:
            continue
        spoken = speak_filesystem_path(
            core,
            dot_spoken=dot_spoken,
            slash_spoken=slash_spoken,
            backslash_spoken=backslash_spoken,
            tilde_spoken=tilde_spoken,
            expand_tilde=expand_tilde,
        )
        key = f"\x00EXT_{counter}\x00"
        counter += 1
        placeholders[key] = f"{spoken}{trailing}"
        raw = raw.replace(token, key, 1)

    # Restore placeholders with boundary spacing for Thai/alphanumeric text
    for key, val in placeholders.items():
        escaped_key = re.escape(key)
        raw = re.sub(r"([ก-๙a-zA-Z0-9])" + escaped_key, r"\1 " + key, raw)
        raw = re.sub(escaped_key + r"([ก-๙a-zA-Z0-9])", key + r" \1", raw)
        raw = raw.replace(key, val)

    return _collapse_whitespace(raw)


# Aliases for convenience and backward/forward compatibility
normalize_spoken_paths = speak_paths
expand_spoken_forms = speak_paths
speak_path = speak_filesystem_path
normalize_email = speak_email
normalize_url = speak_url
normalize_path = speak_filesystem_path

__all__ = [
    "COMMON_EXTENSIONS",
    "COMMON_TLDS",
    "DEFAULT_AT_SPOKEN",
    "DEFAULT_BACKSLASH_SPOKEN",
    "DEFAULT_COLON_SPOKEN",
    "DEFAULT_DOT_SPOKEN",
    "DEFAULT_DOUBLE_SLASH_SPOKEN",
    "DEFAULT_SLASH_SPOKEN",
    "DEFAULT_TILDE_SPOKEN",
    "expand_at",
    "expand_dots",
    "expand_slashes",
    "expand_spoken_forms",
    "expand_tlds",
    "is_email",
    "is_filesystem_path",
    "is_url",
    "normalize_email",
    "normalize_path",
    "normalize_spoken_paths",
    "normalize_url",
    "speak_email",
    "speak_filesystem_path",
    "speak_path",
    "speak_paths",
    "speak_url",
]
