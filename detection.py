"""ClickFix clipboard detection — pure Python, no macOS dependencies."""
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
    # Windows cmd /c prefix (medium — common in cross-platform ClickFix payloads)
    (re.compile(r'\bcmd\s+/c\b', re.I), 'medium'),
    # Group C: suspicious payload URLs
    (re.compile(r'https?://\S+\.(ps1|sh|bat|exe)\b', re.I), 'medium'),
]


def check_for_suspicious_content(text):
    """Return a warning string if text looks like a ClickFix payload, else None."""
    if not text or len(text) > 10_000:
        return None
    high = any(p.search(text) for p, lvl in _SUSPICIOUS_PATTERNS if lvl == 'high')
    medium_count = sum(
        len(p.findall(text)) for p, lvl in _SUSPICIOUS_PATTERNS if lvl == 'medium'
    )
    if high or medium_count >= 2:
        return "Suspicious clipboard content detected — possible ClickFix attack. Do not paste in a terminal."
    return None
