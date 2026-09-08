import asyncio
import re
import time
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from .decision import SecurityDecision


CONTROL_URL = "URL"
ACTION_ALLOW = "ALLOW"
ACTION_BLOCK_MESSAGE = "BLOCK_MESSAGE"
REASON_URL_REPUTATION_OK = "URL_REPUTATION_OK"
REASON_URL_REPUTATION_UNKNOWN = "URL_REPUTATION_UNKNOWN"
REASON_URL_CHECK_UNAVAILABLE = "URL_CHECK_UNAVAILABLE"
REASON_URL_MALICIOUS = "URL_MALICIOUS"
REASON_URL_HIGH_RISK = "URL_HIGH_RISK"
REASON_MALICIOUS_URL = "MALICIOUS_URL"
REASON_SUSPICIOUS_URL = "SUSPICIOUS_URL"
REASON_UNKNOWN_URL = "UNKNOWN_URL"
REASON_VT_URL_CHECK_FAILED = "VT_URL_CHECK_FAILED"

URL_PATTERN = re.compile(r"https?://[^\s<>\"'\]]+", re.IGNORECASE)
BARE_DOMAIN_PATTERN = re.compile(
    r"(?<![@\w.-])"
    r"((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63})"
    r"(?![\w-])",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ExtractedURL:
    url: str
    domain: str


@dataclass(frozen=True)
class URLReputationResult:
    decision: SecurityDecision
    domain: str | None = None
    url: str | None = None
    malicious: int | None = None
    suspicious: int | None = None
    harmless: int | None = None
    undetected: int | None = None


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


def extract_urls(message):
    if not isinstance(message, str):
        return []

    urls = []
    seen = set()
    for match in URL_PATTERN.finditer(message):
        url = match.group(0).rstrip(".,!?;:)]}")
        domain = _domain_for_url(url)
        if domain is None or url in seen:
            continue
        seen.add(url)
        urls.append(ExtractedURL(url=url, domain=domain))

    return urls


def extract_domains(message):
    if not isinstance(message, str):
        return []

    domains = []
    seen = set()
    for extracted_url in extract_urls(message):
        domain = extracted_url.domain
        if domain not in seen:
            seen.add(domain)
            domains.append(domain)

    message_without_urls = URL_PATTERN.sub(" ", message)
    for match in BARE_DOMAIN_PATTERN.finditer(message_without_urls):
        domain = normalize_domain(match.group(1))
        if domain is not None and domain not in seen:
            seen.add(domain)
            domains.append(domain)

    return domains


def redact_url_for_log(url):
    try:
        parsed = urlsplit(url)
        domain = normalize_domain(parsed.hostname)
        port = parsed.port
    except (TypeError, ValueError):
        return None

    if domain is None:
        return None

    host = f"[{domain}]" if ":" in domain else domain
    netloc = f"{host}:{port}" if port is not None else host
    return urlunsplit(
        (
            parsed.scheme.lower(),
            netloc,
            parsed.path,
            "REDACTED" if parsed.query else "",
            "REDACTED" if parsed.fragment else "",
        )
    )


def _domain_for_url(url):
    try:
        parsed = urlsplit(url)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            return None
        parsed.port
        return normalize_domain(parsed.hostname)
    except (AttributeError, TypeError, ValueError):
        return None


class URLReputationChecker:
    def __init__(self, client, cache_ttl_seconds=600.0, clock=time.monotonic):
        if cache_ttl_seconds < 0:
            raise ValueError("cache_ttl_seconds cannot be negative")

        self.client = client
        self.cache_ttl_seconds = cache_ttl_seconds
        self.clock = clock
        self._cache: dict[str, tuple[float, URLReputationResult]] = {}
        self._url_cache: dict[str, tuple[float, URLReputationResult]] = {}

    async def check_message(self, message):
        urls = extract_urls(message)
        domains = extract_domains(message)
        if not urls and not domains:
            return URLReputationResult(_allow(REASON_URL_REPUTATION_OK))

        results = []
        checked_domains = set()

        for extracted_url in urls:
            if extracted_url.domain not in checked_domains:
                results.append(await self.check_domain(extracted_url.domain))
                checked_domains.add(extracted_url.domain)
            results.append(
                await self.check_url(extracted_url.url, extracted_url.domain)
            )

        for domain in domains:
            if domain not in checked_domains:
                results.append(await self.check_domain(domain))
                checked_domains.add(domain)

        return max(results, key=_result_priority)

    async def check_domain(self, domain):
        domain = normalize_domain(domain)
        if domain is None:
            return URLReputationResult(_allow(REASON_URL_REPUTATION_UNKNOWN))

        now = self.clock()
        cached = self._cache.get(domain)
        if cached is not None:
            expires_at, result = cached
            if expires_at > now:
                return result
            self._cache.pop(domain, None)

        try:
            report = await asyncio.to_thread(self.client.get_domain_report, domain)
            result = _result_for_report(
                _decision_for_domain_report(report),
                report,
                domain=domain,
            )
        except Exception:
            return URLReputationResult(
                _allow(REASON_URL_CHECK_UNAVAILABLE),
                domain,
            )

        self._cache[domain] = (
            self.clock() + self.cache_ttl_seconds,
            result,
        )
        return result

    async def check_url(self, url, domain=None):
        parsed_domain = _domain_for_url(url)
        if parsed_domain is None:
            return URLReputationResult(_allow(REASON_UNKNOWN_URL))
        domain = parsed_domain if domain is None else domain

        now = self.clock()
        cached = self._url_cache.get(url)
        if cached is not None:
            expires_at, result = cached
            if expires_at > now:
                return result
            self._url_cache.pop(url, None)

        try:
            report = await asyncio.to_thread(self.client.get_url_report, url)
            result = _result_for_report(
                _decision_for_url_report(report),
                report,
                domain=domain,
                url=url,
            )
        except Exception:
            return URLReputationResult(
                _allow(REASON_VT_URL_CHECK_FAILED),
                domain=domain,
                url=url,
            )

        self._url_cache[url] = (
            self.clock() + self.cache_ttl_seconds,
            result,
        )
        return result


def _decision_for_domain_report(report):
    if report is None:
        return _allow(REASON_URL_REPUTATION_UNKNOWN)

    malicious = int(report.get("malicious", 0))
    suspicious = int(report.get("suspicious", 0))

    if malicious >= 3:
        return _block(REASON_URL_MALICIOUS)
    if malicious >= 1 and suspicious >= 2:
        return _block(REASON_URL_HIGH_RISK)
    if malicious >= 1:
        return _block(REASON_URL_MALICIOUS)
    return _allow(REASON_URL_REPUTATION_OK)


def _decision_for_url_report(report):
    if report is None:
        return _allow(REASON_UNKNOWN_URL)

    malicious = int(report.get("malicious", 0))
    suspicious = int(report.get("suspicious", 0))

    if malicious >= 1:
        return _block(REASON_MALICIOUS_URL)
    if suspicious >= 1:
        return _allow(REASON_SUSPICIOUS_URL)
    return _allow(REASON_URL_REPUTATION_OK)


def _result_for_report(decision, report, domain=None, url=None):
    if report is None:
        return URLReputationResult(decision, domain=domain, url=url)
    return URLReputationResult(
        decision,
        domain=domain,
        url=url,
        malicious=int(report.get("malicious", 0)),
        suspicious=int(report.get("suspicious", 0)),
        harmless=int(report.get("harmless", 0)),
        undetected=int(report.get("undetected", 0)),
    )


def _result_priority(result):
    reason_priority = {
        REASON_URL_REPUTATION_OK: 0,
        REASON_SUSPICIOUS_URL: 10,
        REASON_URL_REPUTATION_UNKNOWN: 20,
        REASON_UNKNOWN_URL: 30,
        REASON_URL_CHECK_UNAVAILABLE: 40,
        REASON_VT_URL_CHECK_FAILED: 50,
        REASON_URL_HIGH_RISK: 100,
        REASON_URL_MALICIOUS: 110,
        REASON_MALICIOUS_URL: 110,
    }
    return (
        reason_priority[result.decision.reason_code],
        result.url is not None,
    )


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
