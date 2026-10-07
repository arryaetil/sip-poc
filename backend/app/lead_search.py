"""The lead search: Serper for Google results, public company pages, the model in between.

SIP runs the steps itself and calls the model through `get_assistant()` for the parts
that need judgement (search queries, picking companies, reading a page). That keeps the
provider seam intact and lets SIP enforce what the model cannot be trusted with: the
maximum, the per-cell sources and the contact rules (see app/leads.py).

What the search may do (docs/specs/2026-10-07-lead-intelligence-design.md, section 5):
public pages only, robots.txt respected, never LinkedIn itself — the LinkedIn company
link comes from a Google result.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import html
import ipaddress
import json
import logging
import os
import re
import socket
import threading
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.leads import (
    BATCH_SIZE,
    LeadBrief,
    LeadCandidate,
    LeadQuery,
    build_row,
    domain_of,
    linkedin_people_page,
)

logger = logging.getLogger("sip.leads")

SERPER_URL = "https://google.serper.dev/search"
USER_AGENT = "SIP-LeadFinder/0.1 (ETIL Solutions; public company pages only)"
MAX_ROUNDS = 3
MAX_QUERIES_PER_ROUND = 6
WORKERS = 4
PAGE_LIMIT = 4
PAGE_TEXT = 8_000
MAX_BYTES = 1_500_000
# Sites that list companies or people rather than being a company's own site.
NOT_A_COMPANY_SITE = (
    "linkedin.com", "facebook.com", "instagram.com", "twitter.com", "x.com", "youtube.com", "tiktok.com",
    "wikipedia.org", "google.com", "indeed.com", "indeed.nl", "glassdoor.com", "glassdoor.nl", "kvk.nl",
    "kbopub.economie.fgov.be", "telefoonboek.nl", "detelefoongids.nl", "goudengids.nl", "goudengids.be",
    "openingstijden.nl", "cylex.nl", "cylex.be", "yelp.com", "trustpilot.com", "werkzoeken.nl",
    "nationalevacaturebank.nl", "companyinfo.nl", "drimble.nl", "northdata.com", "dnb.com", "bing.com",
    "gelbeseiten.de", "dasoertliche.de", "pagesdor.be", "tripadvisor.com", "autoscout24.nl", "autoscout24.be",
    "marktplaats.nl", "2dehands.be", "anwb.nl", "nu.nl", "telegraaf.nl", "nieuwsblad.be", "hln.be",
)
PAGE_HINTS = (
    "contact", "kontakt", "vestiging", "locatie", "location", "filiale", "standort", "over-ons", "overons",
    "about", "wie-zijn-wij", "impressum", "adres", "showroom",
)


class SearchUnavailable(RuntimeError):
    """Serper is not configured or refused the key; the list cannot start."""


def serper_key() -> str:
    return os.getenv("SERPER_API_KEY", "").strip()


@dataclass
class SearchResult:
    title: str
    link: str
    snippet: str


class Serper:
    def __init__(self, key: str, http: httpx.Client | None = None) -> None:
        if not key:
            raise SearchUnavailable("SERPER_API_KEY is not set")
        self.key = key
        self.http = http or httpx.Client(timeout=20)

    def search(self, query: str, country: str = "nl", num: int = 10) -> list[SearchResult]:
        country = country.casefold() if re.fullmatch(r"[a-zA-Z]{2}", country or "") else "nl"
        response = self.http.post(
            SERPER_URL,
            headers={"X-API-KEY": self.key, "Content-Type": "application/json"},
            json={"q": query, "gl": country, "hl": "nl" if country in ("nl", "be") else country, "num": num},
        )
        if response.status_code in (401, 403):
            raise SearchUnavailable("Serper refused the API key")
        if response.status_code >= 400:
            raise RuntimeError(f"Serper returned {response.status_code}")
        return [
            SearchResult(title=item.get("title", ""), link=item.get("link", ""), snippet=item.get("snippet", ""))
            for item in response.json().get("organic", [])
            if item.get("link", "").startswith(("http://", "https://"))
        ]


# --------------------------------------------------------------------------- pages


def _is_public_host(host: str, resolver=socket.getaddrinfo) -> bool:
    """Only internet addresses: no localhost, private ranges or cloud metadata (SSRF)."""
    if not host or host.casefold() in ("localhost",) or host.endswith((".local", ".internal")):
        return False
    try:
        return ipaddress.ip_address(host.strip("[]")).is_global  # an address in the url itself
    except ValueError:
        pass
    try:
        addresses = {info[4][0] for info in resolver(host, None)}
    except (socket.gaierror, UnicodeError):
        return False
    try:
        return bool(addresses) and all(ipaddress.ip_address(address.split("%")[0]).is_global for address in addresses)
    except ValueError:
        return False


SKIP_BLOCKS = re.compile(r"<(script|style|noscript|svg|template)[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
BREAKS = re.compile(r"<(br|/p|/li|/div|/h[1-6]|/tr|/td|/section|/address)[^>]*>", re.IGNORECASE)
TAGS = re.compile(r"<[^>]+>")
HREFS = re.compile(r"""<a\b[^>]*href\s*=\s*["']([^"'#]+)["'][^>]*>(.*?)</a>""", re.IGNORECASE | re.DOTALL)


def page_text(markup: str) -> str:
    """Readable text, with mailto: and tel: links kept: contact details often live only there."""
    contact_links = sorted({href for href, _ in HREFS.findall(markup) if href.lower().startswith(("mailto:", "tel:"))})
    text = BREAKS.sub("\n", SKIP_BLOCKS.sub(" ", markup))
    text = html.unescape(TAGS.sub(" ", text))
    text = "\n".join(" ".join(line.split()) for line in text.splitlines())
    text = re.sub(r"\n{2,}", "\n", text).strip()
    if contact_links:
        text += "\nContact links: " + " ".join(contact_links)
    return text[:PAGE_TEXT]


class PageFetcher:
    def __init__(self, http: httpx.Client | None = None, resolver=socket.getaddrinfo) -> None:
        self.http = http or httpx.Client(timeout=12, follow_redirects=False, headers={"User-Agent": USER_AGENT})
        self.resolver = resolver
        self._robots: dict[str, RobotFileParser | None] = {}
        self._lock = threading.Lock()

    def _get(self, url: str) -> httpx.Response | None:
        for _ in range(4):  # the request and at most three redirects, each checked
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https") or parsed.port not in (None, 80, 443):
                return None
            if not _is_public_host(parsed.hostname or "", self.resolver):
                return None
            with self.http.stream("GET", url) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers.get("location", ""))
                    continue
                body = b""
                for chunk in response.iter_bytes():
                    body += chunk
                    if len(body) > MAX_BYTES:
                        break
                return httpx.Response(response.status_code, headers=response.headers, content=body, request=response.request)
        return None

    def _allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        with self._lock:
            known = origin in self._robots
        if not known:
            parser: RobotFileParser | None = None
            try:
                response = self._get(f"{origin}/robots.txt")
                if response is not None and response.status_code == 200:
                    parser = RobotFileParser()
                    parser.parse(response.text.splitlines())
            except httpx.HTTPError:
                parser = None
            with self._lock:
                self._robots[origin] = parser
        parser = self._robots[origin]
        return parser is None or parser.can_fetch(USER_AGENT, url)

    def fetch(self, url: str) -> tuple[str, str, str] | None:
        """(final url, text, raw html) of one public page, or None."""
        if domain_of(url).endswith("linkedin.com") or not self._allowed(url):
            return None
        try:
            response = self._get(url)
        except httpx.HTTPError:
            return None
        if response is None or response.status_code != 200 or "html" not in response.headers.get("content-type", ""):
            return None
        markup = response.text
        return str(response.request.url), page_text(markup), markup

    def site_pages(self, website: str) -> dict[str, str]:
        """The home page plus the contact, location and about pages it links to."""
        start = website if "://" in website else f"https://{website}"
        home = self.fetch(start)
        if home is None:
            return {}
        url, text, markup = home
        pages = {url: text}
        site = domain_of(url)
        ranked: list[tuple[int, str]] = []
        for href, label in HREFS.findall(markup):
            target = urljoin(url, href.strip())
            if domain_of(target) != site or target.split("#")[0] in pages:
                continue
            haystack = f"{urlparse(target).path} {TAGS.sub(' ', label)}".casefold()
            rank = next((index for index, hint in enumerate(PAGE_HINTS) if hint in haystack), None)
            if rank is not None:
                ranked.append((rank, target.split("#")[0]))
        for _, target in sorted(set(ranked))[: PAGE_LIMIT * 2]:
            if len(pages) >= PAGE_LIMIT:
                break
            page = self.fetch(target)
            if page and page[0] not in pages:
                pages[page[0]] = page[1]
        return pages


# --------------------------------------------------------------------------- the run


def brief_for_model(brief: LeadBrief, context_text: str) -> str:
    return json.dumps(
        {
            "business_context": context_text,
            "description": brief.description,
            "industries": brief.industries,
            "regions": brief.regions,
            "extra_columns": [column.model_dump() for column in brief.extra_columns],
        },
        ensure_ascii=False,
    )


COUNTRY_NAMES = {"neder": "nl", "nether": "nl", "holland": "nl", "belg": "be", "duits": "de", "deutsch": "de", "germ": "de"}


def country_code(country: str | None) -> str:
    """A search-engine country code from what the page said ("Nederland", "BE", ...)."""
    folded = (country or "").strip().casefold()
    if re.fullmatch(r"[a-z]{2}", folded):
        return folded
    return next((code for prefix, code in COUNTRY_NAMES.items() if folded.startswith(prefix)), "nl")


def _results_text(results: list[SearchResult]) -> str:
    return "\n".join(f"- {item.title} | {item.link} | {item.snippet}" for item in results)


def _pages_text(pages: dict[str, str]) -> str:
    return "\n\n".join(f'<page url="{url}">\n{text}\n</page>' for url, text in pages.items())


class LeadSearch:
    """Fills one stored lead list. Runs in a background thread; the page polls the list."""

    def __init__(self, store, assistant, serper: Serper, fetcher: PageFetcher | None = None) -> None:
        self.store = store
        self.assistant = assistant
        self.serper = serper
        self.fetcher = fetcher or PageFetcher()
        self._lock = threading.Lock()

    def run(self, list_id: str, owner_id: str, language: str, context_text: str) -> None:
        try:
            self._run(list_id, owner_id, language, context_text)
        except SearchUnavailable as exc:
            logger.error("lead_search list=%s unavailable: %s", list_id, exc)
            self.store.finish_lead_list(list_id, "failed", "search_unavailable")
        except Exception:  # noqa: BLE001 - a background job must always settle its list
            logger.exception("lead_search list=%s failed", list_id)
            self.store.finish_lead_list(list_id, "failed", "search_failed")

    def _run(self, list_id: str, owner_id: str, language: str, context_text: str) -> None:
        record = self.store.get_lead_list(list_id)
        if record is None:
            return
        brief: LeadBrief = record.brief
        target = brief.count or 0
        payload = brief_for_model(brief, context_text)
        seen = {domain_of(row.website) for row in record.rows}
        previous: list[LeadQuery] = []
        for _ in range(MAX_ROUNDS):
            if self._found(list_id) >= target:
                break
            plan = self.assistant.lead_queries(payload, json.dumps([q.model_dump() for q in previous]), language, owner_id)
            queries = [q for q in plan.queries if q.query.strip()][:MAX_QUERIES_PER_ROUND]
            if not queries:
                break
            previous += queries
            results: dict[str, SearchResult] = {}
            for query in queries:
                for item in self.serper.search(query.query, query.country):
                    site = domain_of(item.link)
                    if site and site not in seen and not site.endswith(NOT_A_COMPANY_SITE):
                        results.setdefault(site, item)
            if not results:
                continue
            needed = target - self._found(list_id)
            picked = self.assistant.lead_select(payload, _results_text(list(results.values())), needed * 2, owner_id)
            candidates: list[LeadCandidate] = []
            for candidate in picked.candidates:
                site = domain_of(candidate.website)
                if site and site not in seen and not site.endswith(NOT_A_COMPANY_SITE):
                    seen.add(site)
                    candidates.append(candidate)
            for start in range(0, len(candidates), BATCH_SIZE):
                if self._found(list_id) >= target or not self.store.lead_list_running(list_id):
                    return self._finish(list_id)
                batch = candidates[start : start + BATCH_SIZE]
                with ThreadPoolExecutor(max_workers=WORKERS) as pool:
                    list(pool.map(lambda c: self._one(list_id, c, brief, payload, language, owner_id, target), batch))
        self._finish(list_id)

    def _finish(self, list_id: str) -> None:
        if self.store.lead_list_running(list_id):
            self.store.finish_lead_list(list_id, "done", None)

    def _found(self, list_id: str) -> int:
        return self.store.lead_row_count(list_id)

    def _one(self, list_id, candidate, brief, payload, language, owner_id, target) -> None:
        if self._found(list_id) >= target:
            return
        site = domain_of(candidate.website)
        try:
            pages = self.fetcher.site_pages(candidate.website)
            if not pages:
                return
            company = json.dumps(candidate.model_dump(), ensure_ascii=False)
            extraction = self.assistant.lead_extract(payload, company, _pages_text(pages), language, owner_id)
            if not extraction.fits:
                return
            row = build_row(candidate, pages, extraction, brief.extra_columns)
            row.linkedin = self._linkedin(row.name, row.country.value)
        except SearchUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - one company failing must not stop the list
            logger.warning("lead_search list=%s site=%s skipped: %s", list_id, site, type(exc).__name__)
            return
        with self._lock:
            if self._found(list_id) < target:
                self.store.add_lead_row(list_id, row)

    def _linkedin(self, name: str, country: str | None) -> str | None:
        """From a Google result only; SIP never opens LinkedIn itself."""
        for item in self.serper.search(f'"{name}" site:linkedin.com/company', country_code(country), num=5):
            page = linkedin_people_page(item.link)
            if page:
                return page
        return None
