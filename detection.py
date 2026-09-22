"""Malicious clipboard detection — pure Python, no macOS dependencies."""
import re

# Detection patterns: (compiled_regex, confidence)
_SUSPICIOUS_PATTERNS = [
    # Group A: pipe-to-shell (sh, bash, or zsh)
    (re.compile(r'curl\s+\S+\s*\|\s*(ba|z)?sh', re.I), 'high'),
    (re.compile(r'wget\s+\S+\s*\|\s*(ba|z)?sh', re.I), 'high'),
    # base64 decode piped to shell — covers macOS (-D) and Linux (-d) flags
    (re.compile(r'base64\s+-[dD]\s*\|\s*(ba|z)?sh', re.I), 'high'),
    # pipe directly to osascript (with or without -e flag)
    (re.compile(r'\|\s*osascript\b', re.I), 'high'),
    # Group B: known malicious commands — require command-like context for high confidence
    # powershell: high with flags/operators; medium for bare mention
    (re.compile(r'\bpowershell\b\s+[-/]|\bpowershell\b\s*[|&;]|\|\s*powershell\b', re.I), 'high'),
    (re.compile(r'\bpowershell\b', re.I), 'medium'),
    # IEX/Invoke-Expression: high in execution context; medium for bare mention
    (re.compile(r'\bIEX\b\s*\(|\|\s*IEX\b', re.I), 'high'),
    (re.compile(r'Invoke-Expression\s+[\$\(\[]', re.I), 'high'),
    (re.compile(r'\bIEX\b|Invoke-Expression', re.I), 'medium'),
    # Invoke-WebRequest: high with flags; medium for bare mention
    (re.compile(r'Invoke-WebRequest\s+-', re.I), 'high'),
    (re.compile(r'Invoke-WebRequest', re.I), 'medium'),
    (re.compile(r'-EncodedCommand|-enc\s+[A-Za-z0-9+/]{20,}', re.I), 'high'),
    (re.compile(r'\bosascript\s+-e\b', re.I), 'high'),
    # mshta/certutil/bitsadmin: high with flags or URLs; medium for bare mention
    (re.compile(r'\b(mshta|certutil|bitsadmin)\b\s+[-/]|\b(mshta|certutil|bitsadmin)\b.*https?://', re.I), 'high'),
    (re.compile(r'\b(mshta|certutil|bitsadmin)\b', re.I), 'medium'),
    # Windows cmd /c prefix (medium — common in cross-platform ClickFix payloads); covers cmd and cmd.exe
    (re.compile(r'\bcmd(\.exe)?\s+/c\b', re.I), 'medium'),
    # finger.exe LOLBIN (CrashFix): high when used as data fetcher (user@host syntax); medium for bare .exe mention
    (re.compile(r'\bfinger(\.exe)?\s+\S+@\S+', re.I), 'high'),
    (re.compile(r'\bfinger\.exe\b', re.I), 'medium'),
    # Broader LOLBINs: rundll32, regsvr32, wscript, cscript — high with flags or URLs; medium for bare mention
    (re.compile(r'\b(rundll32|regsvr32|wscript|cscript)(\.exe)?\b\s+[-/]|\b(rundll32|regsvr32|wscript|cscript)(\.exe)?\b.*https?://', re.I), 'high'),
    (re.compile(r'\b(rundll32|regsvr32|wscript|cscript)(\.exe)?\b', re.I), 'medium'),
    # Charcode obfuscation: PowerShell [char] casting, JavaScript String.fromCharCode, numeric blobs
    (re.compile(r'\[char\]\s*\d{2,3}', re.I), 'medium'),
    (re.compile(r'String\.fromCharCode\s*\(', re.I), 'medium'),
    # Comma-separated numeric blob (10+ values) — typical charcode payload encoding
    (re.compile(r'(?:\b\d{2,3}\b\s*,\s*){9,}\b\d{2,3}\b'), 'medium'),
    # Group C: suspicious payload URLs
    (re.compile(r'https?://\S+\.(ps1|sh|bat|exe)\b', re.I), 'medium'),
]

_WARNING = "Suspicious clipboard content detected — possible malicious payload. Do not paste in a terminal."

# ASCII smuggling (issue #28): Unicode tag characters (U+E0000-U+E007F) are an
# invisible copy of ASCII. Their only legitimate use is subdivision flag emoji
# (black flag + 2-letter region + 1-4 letters/digits + CANCEL TAG).
_FLAG_TAG_SEQ = re.compile(
    '\U0001F3F4[\U000E0061-\U000E007A]{2}[\U000E0030-\U000E0039\U000E0061-\U000E007A]{1,4}\U000E007F'
)
_TAG_CHARS = re.compile('[\U000E0000-\U000E007F]')
# Invisible characters stripped before matching: soft hyphen, Mongolian vowel
# separator, zero-width chars, invisible operators, BOM, variation selectors, tags.
_INVISIBLE = re.compile(
    '[\U000000AD\U0000180E\U0000200B-\U0000200D\U00002060-\U00002064\U0000FEFF'
    '\U0000FE00-\U0000FE0F\U000E0000-\U000E007F\U000E0100-\U000E01EF]'
)


def check_for_suspicious_content(text):
    """Return a warning string if text looks like a malicious payload, else None."""
    if not text:
        return None
    # Checked before the length guard so padding cannot hide tag characters
    if _TAG_CHARS.search(_FLAG_TAG_SEQ.sub('', text)):
        return _WARNING
    text = _INVISIBLE.sub('', text)
    if len(text) > 10_000:
        return None
    high = any(p.search(text) for p, lvl in _SUSPICIOUS_PATTERNS if lvl == 'high')
    medium_count = sum(
        len(p.findall(text)) for p, lvl in _SUSPICIOUS_PATTERNS if lvl == 'medium'
    )
    if high or medium_count >= 2:
        return _WARNING
    return None
