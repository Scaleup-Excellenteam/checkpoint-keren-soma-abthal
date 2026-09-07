import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


VIRUSTOTAL_DOMAIN_ENDPOINT = "https://www.virustotal.com/api/v3/domains/{domain}"


class VirusTotalUnavailableError(Exception):
    pass


class VirusTotalClient:
    def __init__(self, api_key=None, timeout=5.0):
        self.api_key = api_key
        self.timeout = timeout

    def get_domain_report(self, domain):
        api_key = self.api_key or os.getenv("VIRUSTOTAL_API_KEY")
        if not api_key:
            raise VirusTotalUnavailableError("VirusTotal API key is unavailable")

        request = Request(
            VIRUSTOTAL_DOMAIN_ENDPOINT.format(domain=quote(domain, safe="")),
            headers={"x-apikey": api_key},
            method="GET",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except HTTPError as error:
            if error.code == 404:
                return None
            raise VirusTotalUnavailableError("VirusTotal request failed") from error
        except (OSError, TimeoutError, URLError, json.JSONDecodeError) as error:
            raise VirusTotalUnavailableError("VirusTotal request failed") from error

        try:
            stats = payload["data"]["attributes"]["last_analysis_stats"]
            return {
                "malicious": int(stats.get("malicious", 0)),
                "suspicious": int(stats.get("suspicious", 0)),
                "harmless": int(stats.get("harmless", 0)),
                "undetected": int(stats.get("undetected", 0)),
            }
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            raise VirusTotalUnavailableError("Invalid VirusTotal response") from error
