"""Client HTTP rispettoso: User-Agent descrittivo, timeout, una richiesta ogni
2-3 secondi per sito (o il Crawl-delay di robots.txt, se maggiore) e rispetto
di robots.txt."""
from __future__ import annotations

import logging
import random
import time
from urllib import robotparser
from urllib.parse import urlsplit

import requests

USER_AGENT = (
    "BalticVolunteerWatcher/0.1 "
    "(+https://github.com/insula-sito/volontariato; uso personale, non commerciale)"
)
log = logging.getLogger(__name__)


class RobotsDisallowed(Exception):
    """L'URL è vietato da robots.txt: non lo scarichiamo."""


class PoliteSession:
    def __init__(self, min_delay: float = 2.5, timeout: float = 30, user_agent: str = USER_AGENT):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept-Language": "en,it;q=0.8",
        })
        self.user_agent = user_agent
        self.min_delay = min_delay
        self.timeout = timeout
        self._last: dict[str, float] = {}
        self._robots: dict[str, robotparser.RobotFileParser] = {}

    # --- robots.txt -------------------------------------------------------
    def _robots_for(self, base: str) -> robotparser.RobotFileParser:
        if base in self._robots:
            return self._robots[base]
        rp = robotparser.RobotFileParser()
        self._throttle(base, 0)
        try:
            r = self.session.get(base + "/robots.txt", timeout=self.timeout)
            if r.status_code in (401, 403):
                rp.disallow_all = True          # stessa semantica di urllib
            elif r.status_code >= 400:
                rp.allow_all = True
            else:
                rp.parse(r.text.splitlines())
        except requests.RequestException as exc:
            log.warning("robots.txt non leggibile per %s (%s): procedo con cautela", base, exc)
            rp.allow_all = True
        finally:
            self._last[base] = time.monotonic()
        self._robots[base] = rp
        return rp

    def _check(self, url: str) -> str:
        parts = urlsplit(url)
        base = f"{parts.scheme}://{parts.netloc}"
        rp = self._robots_for(base)
        if not rp.can_fetch(self.user_agent, url):
            raise RobotsDisallowed(url)
        return base

    # --- ritmo ------------------------------------------------------------
    def _throttle(self, base: str, extra_delay: float | None = None) -> None:
        delay = self.min_delay
        rp = self._robots.get(base)
        if rp is not None:
            try:
                cd = rp.crawl_delay(self.user_agent)
            except Exception:  # pragma: no cover - robotparser difettoso
                cd = None
            if cd:
                delay = max(delay, float(cd))
        if extra_delay is not None:
            delay = max(delay, extra_delay)
        last = self._last.get(base)
        if last is not None:
            wait = last + delay + random.uniform(0, 0.5) - time.monotonic()
            if wait > 0:
                time.sleep(wait)

    # --- richieste --------------------------------------------------------
    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        base = self._check(url)
        kwargs.setdefault("timeout", self.timeout)
        last_exc: Exception | None = None
        for attempt in range(2):
            self._throttle(base, 5.0 if attempt else None)
            try:
                r = self.session.request(method, url, **kwargs)
            except requests.RequestException as exc:
                last_exc = exc
                log.warning("Errore di rete su %s (tentativo %d): %s", url, attempt + 1, exc)
                continue
            finally:
                self._last[base] = time.monotonic()
            if r.status_code >= 500 and attempt == 0:
                log.warning("HTTP %s su %s, riprovo", r.status_code, url)
                continue
            r.raise_for_status()
            return r
        if last_exc:
            raise last_exc
        r.raise_for_status()
        return r

    def get(self, url: str, **kwargs) -> requests.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        return self.request("POST", url, **kwargs)
