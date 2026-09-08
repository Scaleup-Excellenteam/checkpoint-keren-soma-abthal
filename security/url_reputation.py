import asyncio
import re
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

from .decision import SecurityDecision


CONTROL_URL = "URL"
ACTION_ALLOW = "ALLOW"
ACTION_BLOCK_MESSAGE = "BLOCK_MESSAGE"
REASON_URL_REPUTATION_OK = "URL_REPUTATION_OK"
REASON_URL_REPUTATION_UNKNOWN = "URL_REPUTATION_UNKNOWN"
REASON_URL_CHECK_UNAVAILABLE = "URL_CHECK_UNAVAILABLE"
REASON_URL_MALICIOUS = "URL_MALICIOUS"
REASON_URL_HIGH_RISK = "URL_HIGH_RISK"

URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
BARE_DOMAIN_PATTERN = re.compile(
    r"(?<![@\w.-])"
    r"((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63})"
    r"(?![\w-])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class URLReputationResult:
    decision: SecurityDecision
    domain: str | None = None


def normalize_domain(hostname):
    if not isinstance(hostname, str):
        return None

    hostname = hostname.strip().rstrip(".").lower()
    if not hostname:
        return None

    try:
        return hostname.encode("idna").decode("ascii")
    except UnicodeError:
        return None


def extract_domains(message):
    if not isinstance(message, str):
        return []

    domains = []
    seen = set()
    message_without_urls = message

    for match in URL_PATTERN.finditer(message):
        url = match.group(0).rstrip(".,!?;:)]}")
        try:
            domain = normalize_domain(urlsplit(url).hostname)
        except ValueError:
            continue
        if domain is not None and domain not in seen:
            seen.add(domain)
            domains.append(domain)

    message_without_urls = URL_PATTERN.sub(" ", message_without_urls)
    for match in BARE_DOMAIN_PATTERN.finditer(message_without_urls):
        domain = normalize_domain(match.group(1))
        if domain is not None and domain not in seen:
            seen.add(domain)
            domains.append(domain)

    return domains


class URLReputationChecker:
    def __init__(self, client, cache_ttl_seconds=600.0, clock=time.monotonic, timeout_seconds=1.5):
        if cache_ttl_seconds < 0:
            raise ValueError("cache_ttl_seconds cannot be negative")

        self.client = client
        self.cache_ttl_seconds = cache_ttl_seconds
        self.clock = clock
        self.timeout_seconds = timeout_seconds
        self._cache: dict[str, tuple[float, SecurityDecision]] = {}

    async def check_message(self, message):
        domains = extract_domains(message)
        if not domains:
            return URLReputationResult(_allow(REASON_URL_REPUTATION_OK))

        # בדיקת כל הדומיינים במקביל במקום בלולאה סדרתית
        results = await asyncio.gather(*(self.check_domain(domain) for domain in domains))

        # אם יש דומיין שנחסם, מחזירים אותו מיד
        for result in results:
            if not result.decision.allowed:
                return result

        priority = {
            REASON_URL_REPUTATION_OK: 0,
            REASON_URL_REPUTATION_UNKNOWN: 1,
            REASON_URL_CHECK_UNAVAILABLE: 2,
        }

        best_result = results[0]
        for result in results[1:]:
            if priority[result.decision.reason_code] > priority[best_result.decision.reason_code]:
                best_result = result

        return best_result

    async def check_domain(self, domain):
        domain = normalize_domain(domain)
        if domain is None:
            return URLReputationResult(_allow(REASON_URL_REPUTATION_UNKNOWN))

        now = self.clock()
        cached = self._cache.get(domain)
        if cached is not None:
            expires_at, decision = cached
            if expires_at > now:
                return URLReputationResult(decision, domain)
            self._cache.pop(domain, None)

        try:
            # הגבלת זמן תגובה למניעת תקיעת השרת אם ה-API מגיב לאט
            report = await asyncio.wait_for(
                asyncio.to_thread(self.client.get_domain_report, domain),
                timeout=self.timeout_seconds,
            )
            decision = _decision_for_report(report)
        except Exception:
            return URLReputationResult(
                _allow(REASON_URL_CHECK_UNAVAILABLE),
                domain,
            )

        self._cache[domain] = (
            self.clock() + self.cache_ttl_seconds,
            decision,
        )
        return URLReputationResult(decision, domain)


def _decision_for_report(report):
    if report is None:
        return _allow(REASON_URL_REPUTATION_UNKNOWN)

    malicious = int(report.get("malicious", 0))
    suspicious = int(report.get("suspicious", 0))

    if malicious >= 3:
        return _block(REASON_URL_MALICIOUS)
    if malicious >= 1 and suspicious >= 2:
        return _block(REASON_URL_HIGH_RISK)
    return _allow(REASON_URL_REPUTATION_OK)


def _allow(reason_code):
    return SecurityDecision(
        allowed=True,
        control=CONTROL_URL,
        action=ACTION_ALLOW,
        reason_code=reason_code,
    )


def _block(reason_code):
    return SecurityDecision(
        allowed=False,
        control=CONTROL_URL,
        action=ACTION_BLOCK_MESSAGE,
        reason_code=reason_code,
    )