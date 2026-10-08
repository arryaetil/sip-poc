"""The lead search: Serper for Google results, public company pages, the model in between.

SIP runs the steps itself and calls the model through `get_assistant()` for the parts
that need judgement (search queries, picking companies, reading a page). That keeps the
provider seam intact and lets SIP enforce what the model cannot be trusted with: the
maximum, the per-cell sources and the contact rules (see app/leads.py).

What the search may do (docs/specs/2026-10-07-lead-intelligence-design.md, section 5):
public pages only, robots.txt respected, never LinkedIn itself â€” the LinkedIn company
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
import time
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.assistants import AssistantUnavailable
from app.leads import (
    BATCH_SIZE,
    LeadBrief,
    LeadCandidate,
    LeadQuery,
    LeadFact,
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
RETRY_SECONDS = 20
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
# One page per kind, so the extra pages cover contact details, locations and the company.
PAGE_KINDS = (
    ("vestiging", "locatie", "location", "filiale", "standort", "showroom", "onze-bedrijven", "bedrijven"),
    ("contact", "kontakt", "impressum"),
    ("over-ons", "overons", "about", "wie-zijn-wij", "ueber-uns", "uber-uns", "over"),
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

    def places(self, name: str, city: str, country: str = "nl") -> list[dict]:
        response = self.http.post("https://google.serper.dev/places", headers={"X-API-KEY": self.key}, json={"q": f"{name} {city}", "gl": country, "hl": "nl"})
        if response.status_code in (401, 403):
            raise SearchUnavailable("Serper refused the API key")
        response.raise_for_status()
        # Retain aggregates only, never review text or reviewer data.
        return [{key: item.get(key) for key in ("website", "rating", "ratingCount", "cid")} for item in response.json().get("places", [])]

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


@dataclass
class Fetched:
    url: str
    status: int
    content_type: str
    text: str


class PageFetcher:
    def __init__(self, http: httpx.Client | None = None, resolver=socket.getaddrinfo) -> None:
        self.http = http or httpx.Client(timeout=12, follow_redirects=False, headers={"User-Agent": USER_AGENT})
        self.resolver = resolver
        self._robots: dict[str, RobotFileParser | None] = {}
        self._lock = threading.Lock()

    def _get(self, url: str) -> Fetched | None:
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
                # iter_bytes already undoes gzip/brotli; keep the decoded text, not a
                # second response that would try to decompress it again.
                body = b""
                for chunk in response.iter_bytes():
                    body += chunk
                    if len(body) > MAX_BYTES:
                        return None  # incomplete HTML cannot prove absence of a chat widget
                return Fetched(
                    url=str(response.request.url),
                    status=response.status_code,
                    content_type=response.headers.get("content-type", ""),
                    text=body.decode(response.encoding or "utf-8", errors="replace"),
                )
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
                if response is not None and response.status == 200:
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
        if response is None or response.status != 200 or "html" not in response.content_type:
            return None
        return response.url, page_text(response.text), response.text

    def site_pages(self, website: str, *, with_html: bool = False):
        """The home page plus the contact, location and about pages it links to."""
        start = website if "://" in website else f"https://{website}"
        home = self.fetch(start)
        if home is None:
            return ({}, "") if with_html else {}
        url, text, markup = home
        pages = {url: text}
        site = domain_of(url)
        best: dict[int, tuple[int, str]] = {}
        for href, label in HREFS.findall(markup):
            target = urljoin(url, href.strip()).split("#")[0].split("?")[0]
            if domain_of(target) != site or target.rstrip("/") == url.rstrip("/"):
                continue
            path = urlparse(target).path.casefold()
            depth = len([part for part in path.split("/") if part])
            if depth > 3:
                continue  # a deep page (an advert, an article), not the company's own page
            haystack = f"{path} {TAGS.sub(' ', label).casefold()}"
            for kind, hints in enumerate(PAGE_KINDS):
                if any(hint in haystack for hint in hints):
                    # The shallowest link of each kind: /vestigingen over /vestigingen/heerlen.
                    if kind not in best or (depth, len(path)) < (best[kind][0], len(urlparse(best[kind][1]).path)):
                        best[kind] = (depth, target)
                    break
        for kind in sorted(best):
            if len(pages) >= PAGE_LIMIT:
                break
            page = self.fetch(best[kind][1])
            if page and page[0] not in pages:
                pages[page[0]] = page[1]
        return (pages, markup) if with_html else pages


# --------------------------------------------------------------------------- the run


def brief_for_model(brief: LeadBrief, context_text: str) -> str:
    return json.dumps(
        {
            "business_context": context_text,
            "description": brief.description,
            "industries": brief.industries,
            "regions": brief.regions,
            "size": brief.size,
            "exclude": brief.exclude,
            "extra_columns": [column.model_dump() for column in brief.extra_columns],
        },
        ensure_ascii=False,
    )


COUNTRY_NAMES = {"neder": "nl", "nether": "nl", "holland": "nl", "belg": "be", "duits": "de", "deutsch": "de", "germ": "de"}


CHAT_MARKERS = {
    "Intercom": ("widget.intercom.io", "intercomcdn.com"), "LiveChat": ("cdn.livechatinc.com",),
    "Tawk": ("embed.tawk.to",), "Zendesk": ("static.zdassets.com", "zopim.com"),
    "HubSpot chat": ("conversations-embed",), "Drift": ("js.driftt.com",),
    "Crisp": ("client.crisp.chat",), "Tidio": ("code.tidio.co",),
    "Trengo": ("widget.trengo.eu", "widget.trengo.com"), "Userlike": ("userlike-cdn", "userlike.com/widget"),
    "Watermelon": ("watermelon.ai", "watermelon.co/widget"), "Smartsupp": ("smartsuppchat.com",),
    "Freshchat": ("wchat.freshchat.com",), "Olark": ("static.olark.com",),
    "WhatsApp": ("wa.me/", "api.whatsapp.com/send"),
}


def detect_chat(markup: str, source: str) -> LeadFact:
    if not markup:
        return LeadFact()
    folded = markup.casefold()
    names = [name for name, markers in CHAT_MARKERS.items() if any(marker in folded for marker in markers)]
    return LeadFact(value=", ".join(names) if names else "Niet gedetecteerd", source=source)


def classify_vacancy(text: str) -> set[str]:
    folded = text.casefold()
    categories = {"receptie": ("receptionist", "receptiemedewerker", "medewerker receptie", "reception", "empfang"), "klantenservice": ("klantenservice", "customer service", "klantcontact", "kundenservice"), "serviceadviseur": ("serviceadviseur", "service adviseur", "service advisor", "serviceberater")}
    return {name for name, terms in categories.items() if any(re.search(r"\b" + re.escape(term) + r"\b", folded) for term in terms)}


def places_signals(places: list[dict], website: str) -> dict[str, LeadFact]:
    matched = {}
    for item in places:
        cid = str(item.get("cid") or "")
        if domain_of(str(item.get("website") or "")) != domain_of(website) or not cid.isdigit():
            continue
        try:
            count, rating = int(item.get("ratingCount")), float(item.get("rating"))
        except (ValueError, TypeError):
            continue
        if count > 0 and 1 <= rating <= 5:
            matched.setdefault(cid, (count, rating))
    if not matched:
        return {}
    total = sum(count for count, _ in matched.values())
    rating = sum(count * rating for count, rating in matched.values()) / total
    source = "https://www.google.com/maps?cid=" + next(iter(matched))
    signals = {"reviews": LeadFact(value=str(total), source=source), "rating": LeadFact(value=str(rating), source=source)}
    for cid, (count, rating) in matched.items():
        signals["place_" + cid] = LeadFact(value=f"{count} reviews; rating {rating}", source="https://www.google.com/maps?cid=" + cid)
    return signals


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
            if brief.scoring == "sam_points":
                pages, markup = self.fetcher.site_pages(candidate.website, with_html=True)
            else:
                pages = self.fetcher.site_pages(candidate.website)
            if not pages:
                return
            company = json.dumps(candidate.model_dump(), ensure_ascii=False)
            extraction = self._extract(list_id, payload, company, _pages_text(pages), language, owner_id)
            if extraction is None:
                return
            if not extraction.fits:
                return
            row = build_row(candidate, pages, extraction, brief.extra_columns)
            if brief.scoring == "sam_points":
                self._sam_signals(row, markup)
            row.linkedin = self._linkedin(row.name, row.country.value, row.website)
        except SearchUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - one company failing must not stop the list
            logger.warning("lead_search list=%s site=%s skipped: %s", list_id, site, type(exc).__name__)
            return
        with self._lock:
            if self._found(list_id) < target:
                self.store.add_lead_row(list_id, row)

    def _extract(self, list_id, payload, company, pages, language, owner_id):
        """Read one company's pages. When the AI service is busy (Dify's free plan limit),
        wait and try again once; if it is still busy, count the company as skipped so the
        list says so instead of quietly coming up short."""
        for attempt in range(2):
            try:
                return self.assistant.lead_extract(payload, company, pages, language, owner_id)
            except AssistantUnavailable:
                if attempt == 0:
                    time.sleep(RETRY_SECONDS)
        self.store.add_lead_skip(list_id)
        return None

    def _sam_signals(self, row, markup):
        row.signals["chat"] = detect_chat(markup, row.website)
        try:
            row.signals.update(places_signals(self.serper.places(row.name, row.city.value or "", country_code(row.country.value)), row.website))
        except SearchUnavailable:
            raise
        except (httpx.HTTPError, ValueError, TypeError):
            pass  # unavailable is unknown, never zero reviews
        vacancy_urls = []
        for href, label in HREFS.findall(markup):
            target = urljoin(row.website, href)
            if domain_of(target) == domain_of(row.website) and any(hint in (target + " " + label).casefold() for hint in ("vacature", "werken-bij", "careers", "jobs", "karriere")):
                vacancy_urls.append(target)
        if not vacancy_urls:
            try:
                for item in self.serper.search(f"site:{domain_of(row.website)} vacatures receptie klantenservice serviceadviseur", country_code(row.country.value), num=3):
                    if domain_of(item.link) == domain_of(row.website):
                        vacancy_urls.append(item.link)
            except SearchUnavailable:
                raise
            except (httpx.HTTPError, RuntimeError):
                pass
        categories = set()
        evidence = []
        fetched_jobs = set()
        # Only explicit vacancy titles linked from the company's own careers page.
        # General careers copy is insufficient evidence of a current vacancy.
        for target in list(dict.fromkeys(vacancy_urls))[:2]:
            page = self.fetcher.fetch(target)
            if not page or domain_of(page[0]) != domain_of(row.website):
                continue
            titles = re.findall(r"<h1\b[^>]*>(.*?)</h1>", page[2], re.IGNORECASE | re.DOTALL)
            links = HREFS.findall(page[2])
            # A result may be the job page itself; require an explicit vacancy action.
            if titles and any(term in page[1].casefold() for term in ("solliciteer", "solliciteren", "apply now", "bewerben")):
                links = [(page[0], titles[0]), *links]
            for href, label in links:
                job_url = urljoin(page[0], href)
                if domain_of(job_url) != domain_of(row.website):
                    continue
                found = classify_vacancy(page_text(label))
                if not found:
                    continue
                if job_url in fetched_jobs or len(fetched_jobs) >= 6:
                    continue
                fetched_jobs.add(job_url)
                job = page if job_url == page[0] else self.fetcher.fetch(job_url)
                if job and domain_of(job[0]) == domain_of(row.website) and not any(term in job[1].casefold() for term in ("vacature is vervuld", "vacature gesloten", "position filled", "niet meer beschikbaar")):
                    job_titles = re.findall(r"<h1\b[^>]*>(.*?)</h1>", job[2], re.IGNORECASE | re.DOTALL)
                    confirmed = found.intersection(classify_vacancy(" ".join(page_text(title) for title in job_titles)))
                    if not any(term in job[1].casefold() for term in ("solliciteer", "solliciteren", "apply now", "bewerben")):
                        confirmed = set()
                    if confirmed:
                        categories.update(confirmed)
                        evidence.append(job[0])
        if categories:
            row.signals["vacancies"] = LeadFact(value=", ".join(sorted(categories)), source=evidence[0])
        row.sources = list(dict.fromkeys([*row.sources, *evidence, *(fact.source for fact in row.signals.values() if fact.source)]))

    def _linkedin(self, name: str, country: str | None, website: str = "") -> str | None:
        """Keep a company link only when the search evidence names its exact website.

        A matching company name alone can belong to an unrelated organisation in
        another country. LinkedIn itself is never fetched; missing evidence is unknown.
        """
        domain = domain_of(website) if website else ""
        if not domain:
            return None
        evidence = re.compile(r"(?<![a-z0-9.-])(?:www\.)?" + re.escape(domain) + r"(?![a-z0-9.-])", re.IGNORECASE)
        queries = [f'"{name}" "{domain}" site:linkedin.com/company',
                   f'"{domain}" site:linkedin.com/company']
        for query in queries:
            for item in self.serper.search(query, country_code(country), num=5):
                page = linkedin_people_page(item.link)
                if page and evidence.search(item.title + " " + item.snippet):
                    return page
        return None
