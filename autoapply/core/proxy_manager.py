"""
Proxy Manager Module
====================
Handles proxy rotation for avoiding IP-based blocking and rate limiting.

Supports:
- Static proxy lists (free or purchased)
- Rotating proxy services (Bright Data, Oxylabs, SmartProxy, etc.)
- Automatic rotation on failures
- Health checking and blacklisting
- Geo-targeting (US, UK, etc.)

Usage:
    proxy_manager = ProxyManager()
    proxy_manager.add_proxies(["http://user:pass@proxy1:8080", ...])

    # Get a proxy for requests
    proxy = proxy_manager.get_proxy()
    requests.get(url, proxies={"http": proxy, "https": proxy})

    # Mark proxy as failed (will be rotated out)
    proxy_manager.mark_failed(proxy)
"""

import os
import time
import random
import logging
import threading
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
from urllib.parse import urlparse

import requests

logger = logging.getLogger("autoapply.proxy")


class ProxyType(Enum):
    """Types of proxy protocols."""
    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


class ProxyProvider(Enum):
    """Supported proxy service providers."""
    STATIC = "static"  # User-provided list
    BRIGHT_DATA = "bright_data"  # brightdata.com (formerly Luminati)
    OXYLABS = "oxylabs"  # oxylabs.io
    SMARTPROXY = "smartproxy"  # smartproxy.com
    WEBSHARE = "webshare"  # webshare.io (good free tier)
    PROXY_CHEAP = "proxy_cheap"  # proxy-cheap.com
    FREE = "free"  # Free proxy lists (less reliable)


@dataclass
class Proxy:
    """Represents a single proxy."""
    url: str
    proxy_type: ProxyType = ProxyType.HTTP
    country: str = ""
    provider: ProxyProvider = ProxyProvider.STATIC

    # Stats
    success_count: int = 0
    fail_count: int = 0
    last_used: float = 0
    last_success: float = 0
    response_times: List[float] = field(default_factory=list)

    # State
    is_blacklisted: bool = False
    blacklist_until: float = 0

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        return self.success_count / total if total > 0 else 1.0

    @property
    def avg_response_time(self) -> float:
        if not self.response_times:
            return 0
        return sum(self.response_times[-10:]) / len(self.response_times[-10:])

    def to_dict(self) -> Dict[str, str]:
        """Return proxy dict for requests library."""
        return {
            "http": self.url,
            "https": self.url,
        }


class ProxyManager:
    """
    Manages proxy rotation with health checking and automatic failover.

    Features:
    - Round-robin and weighted rotation strategies
    - Automatic blacklisting of failing proxies
    - Health checks to verify proxy connectivity
    - Support for multiple proxy providers
    - Geo-targeting support
    """

    # Test URLs for health checks
    TEST_URLS = [
        "https://httpbin.org/ip",
        "https://api.ipify.org?format=json",
        "https://ifconfig.me/ip",
    ]

    # Free proxy list sources (less reliable but free)
    FREE_PROXY_SOURCES = [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    ]

    def __init__(
        self,
        rotation_strategy: str = "round_robin",  # "round_robin", "random", "weighted"
        max_fails_before_blacklist: int = 3,
        blacklist_duration_sec: int = 300,  # 5 minutes
        health_check_interval_sec: int = 60,
    ):
        self.rotation_strategy = rotation_strategy
        self.max_fails = max_fails_before_blacklist
        self.blacklist_duration = blacklist_duration_sec
        self.health_check_interval = health_check_interval_sec

        self._proxies: List[Proxy] = []
        self._current_index = 0
        self._lock = threading.Lock()
        self._no_proxy_mode = False  # If True, return None (direct connection)

        # Provider credentials (from env vars)
        self._provider_configs: Dict[ProxyProvider, Dict] = {}
        self._load_provider_configs()

    def _load_provider_configs(self):
        """Load proxy provider credentials from environment variables."""
        # Bright Data (formerly Luminati)
        if os.environ.get("BRIGHT_DATA_USERNAME"):
            self._provider_configs[ProxyProvider.BRIGHT_DATA] = {
                "username": os.environ.get("BRIGHT_DATA_USERNAME"),
                "password": os.environ.get("BRIGHT_DATA_PASSWORD"),
                "host": os.environ.get("BRIGHT_DATA_HOST", "brd.superproxy.io"),
                "port": os.environ.get("BRIGHT_DATA_PORT", "22225"),
            }

        # Oxylabs
        if os.environ.get("OXYLABS_USERNAME"):
            self._provider_configs[ProxyProvider.OXYLABS] = {
                "username": os.environ.get("OXYLABS_USERNAME"),
                "password": os.environ.get("OXYLABS_PASSWORD"),
                "host": os.environ.get("OXYLABS_HOST", "pr.oxylabs.io"),
                "port": os.environ.get("OXYLABS_PORT", "7777"),
            }

        # SmartProxy
        if os.environ.get("SMARTPROXY_USERNAME"):
            self._provider_configs[ProxyProvider.SMARTPROXY] = {
                "username": os.environ.get("SMARTPROXY_USERNAME"),
                "password": os.environ.get("SMARTPROXY_PASSWORD"),
                "host": os.environ.get("SMARTPROXY_HOST", "gate.smartproxy.com"),
                "port": os.environ.get("SMARTPROXY_PORT", "7000"),
            }

        # Webshare (has free tier)
        if os.environ.get("WEBSHARE_API_KEY"):
            self._provider_configs[ProxyProvider.WEBSHARE] = {
                "api_key": os.environ.get("WEBSHARE_API_KEY"),
            }

    def add_proxy(self, proxy_url: str, country: str = "", provider: ProxyProvider = ProxyProvider.STATIC):
        """Add a single proxy to the pool."""
        proxy = Proxy(
            url=proxy_url,
            country=country,
            provider=provider,
        )
        with self._lock:
            self._proxies.append(proxy)
        logger.debug(f"Added proxy: {proxy_url[:30]}...")

    def add_proxies(self, proxy_urls: List[str], country: str = ""):
        """Add multiple proxies to the pool."""
        for url in proxy_urls:
            self.add_proxy(url, country)
        logger.info(f"Added {len(proxy_urls)} proxies to pool")

    def add_from_provider(self, provider: ProxyProvider, country: str = "us", count: int = 10):
        """
        Add proxies from a rotating proxy provider.

        For rotating providers (Bright Data, Oxylabs), we add the same endpoint
        multiple times - each request through it gets a different IP.
        """
        if provider not in self._provider_configs:
            logger.warning(f"No credentials configured for {provider.value}")
            return

        config = self._provider_configs[provider]

        if provider == ProxyProvider.BRIGHT_DATA:
            # Bright Data format: http://user-country-us:pass@host:port
            proxy_url = (
                f"http://{config['username']}-country-{country}:"
                f"{config['password']}@{config['host']}:{config['port']}"
            )
            for _ in range(count):
                self.add_proxy(proxy_url, country, provider)

        elif provider == ProxyProvider.OXYLABS:
            # Oxylabs format: http://user-country-us:pass@host:port
            proxy_url = (
                f"http://customer-{config['username']}-cc-{country}:"
                f"{config['password']}@{config['host']}:{config['port']}"
            )
            for _ in range(count):
                self.add_proxy(proxy_url, country, provider)

        elif provider == ProxyProvider.SMARTPROXY:
            # SmartProxy format
            proxy_url = (
                f"http://{config['username']}:{config['password']}"
                f"@{config['host']}:{config['port']}"
            )
            for _ in range(count):
                self.add_proxy(proxy_url, country, provider)

        elif provider == ProxyProvider.WEBSHARE:
            # Webshare - fetch proxy list from API
            self._fetch_webshare_proxies(config["api_key"], count)

    def _fetch_webshare_proxies(self, api_key: str, count: int):
        """Fetch proxies from Webshare API."""
        try:
            response = requests.get(
                "https://proxy.webshare.io/api/v2/proxy/list/",
                headers={"Authorization": f"Token {api_key}"},
                params={"mode": "direct", "page_size": count},
            )
            response.raise_for_status()
            data = response.json()

            for proxy_data in data.get("results", []):
                proxy_url = (
                    f"http://{proxy_data['username']}:{proxy_data['password']}"
                    f"@{proxy_data['proxy_address']}:{proxy_data['port']}"
                )
                self.add_proxy(
                    proxy_url,
                    country=proxy_data.get("country_code", ""),
                    provider=ProxyProvider.WEBSHARE,
                )

            logger.info(f"Fetched {len(data.get('results', []))} proxies from Webshare")

        except Exception as e:
            logger.error(f"Failed to fetch Webshare proxies: {e}")

    def load_free_proxies(self, max_proxies: int = 50):
        """
        Load free proxies from public lists.

        Warning: Free proxies are unreliable and may be slow or compromised.
        Only use for testing or non-sensitive scraping.
        """
        logger.info("Loading free proxies (these may be unreliable)...")
        proxies_added = 0

        for source_url in self.FREE_PROXY_SOURCES:
            if proxies_added >= max_proxies:
                break

            try:
                response = requests.get(source_url, timeout=10)
                response.raise_for_status()

                for line in response.text.strip().split("\n"):
                    if proxies_added >= max_proxies:
                        break

                    line = line.strip()
                    if line and ":" in line:
                        # Format: ip:port
                        proxy_url = f"http://{line}"
                        self.add_proxy(proxy_url, provider=ProxyProvider.FREE)
                        proxies_added += 1

            except Exception as e:
                logger.debug(f"Failed to load from {source_url}: {e}")

        logger.info(f"Loaded {proxies_added} free proxies")

    def get_proxy(self, country: str = None) -> Optional[Proxy]:
        """
        Get the next proxy based on rotation strategy.

        Args:
            country: Optional country filter (e.g., "us", "uk")

        Returns:
            Proxy object or None if no proxies available
        """
        if self._no_proxy_mode:
            return None

        with self._lock:
            # Filter available proxies
            available = [
                p for p in self._proxies
                if not p.is_blacklisted or time.time() > p.blacklist_until
            ]

            # Apply country filter
            if country:
                country_proxies = [p for p in available if p.country.lower() == country.lower()]
                if country_proxies:
                    available = country_proxies

            if not available:
                logger.warning("No available proxies")
                return None

            # Select based on strategy
            if self.rotation_strategy == "random":
                proxy = random.choice(available)

            elif self.rotation_strategy == "weighted":
                # Weight by success rate and response time
                weights = []
                for p in available:
                    weight = p.success_rate * 100
                    if p.avg_response_time > 0:
                        weight /= (1 + p.avg_response_time)
                    weights.append(max(weight, 0.1))

                proxy = random.choices(available, weights=weights, k=1)[0]

            else:  # round_robin
                self._current_index = self._current_index % len(available)
                proxy = available[self._current_index]
                self._current_index += 1

            proxy.last_used = time.time()
            return proxy

    def get_proxy_dict(self, country: str = None) -> Optional[Dict[str, str]]:
        """Get proxy in requests-compatible format."""
        proxy = self.get_proxy(country)
        return proxy.to_dict() if proxy else None

    def mark_success(self, proxy: Proxy, response_time: float = 0):
        """Mark a proxy request as successful."""
        with self._lock:
            proxy.success_count += 1
            proxy.last_success = time.time()
            if response_time > 0:
                proxy.response_times.append(response_time)
                # Keep only last 20 response times
                proxy.response_times = proxy.response_times[-20:]

            # Un-blacklist if it was blacklisted
            if proxy.is_blacklisted:
                proxy.is_blacklisted = False
                proxy.fail_count = 0
                logger.info(f"Proxy un-blacklisted after success: {proxy.url[:30]}...")

    def mark_failed(self, proxy: Proxy, error: str = ""):
        """Mark a proxy request as failed."""
        with self._lock:
            proxy.fail_count += 1

            if proxy.fail_count >= self.max_fails:
                proxy.is_blacklisted = True
                proxy.blacklist_until = time.time() + self.blacklist_duration
                logger.warning(f"Proxy blacklisted ({proxy.fail_count} fails): {proxy.url[:30]}...")

    def health_check(self, proxy: Proxy, timeout: int = 10) -> bool:
        """
        Check if a proxy is working.

        Returns True if proxy successfully connects.
        """
        test_url = random.choice(self.TEST_URLS)

        try:
            start = time.time()
            response = requests.get(
                test_url,
                proxies=proxy.to_dict(),
                timeout=timeout,
            )
            response_time = time.time() - start

            if response.status_code == 200:
                self.mark_success(proxy, response_time)
                return True

        except Exception as e:
            logger.debug(f"Health check failed for {proxy.url[:30]}: {e}")

        self.mark_failed(proxy, "Health check failed")
        return False

    def health_check_all(self, timeout: int = 10) -> Dict[str, int]:
        """
        Run health check on all proxies.

        Returns dict with counts: {"healthy": N, "unhealthy": M}
        """
        results = {"healthy": 0, "unhealthy": 0}

        for proxy in self._proxies:
            if self.health_check(proxy, timeout):
                results["healthy"] += 1
            else:
                results["unhealthy"] += 1

        logger.info(f"Health check complete: {results['healthy']} healthy, {results['unhealthy']} unhealthy")
        return results

    def remove_blacklisted(self):
        """Remove all blacklisted proxies from the pool."""
        with self._lock:
            before = len(self._proxies)
            self._proxies = [p for p in self._proxies if not p.is_blacklisted]
            removed = before - len(self._proxies)
            if removed:
                logger.info(f"Removed {removed} blacklisted proxies")

    def get_stats(self) -> Dict[str, Any]:
        """Get proxy pool statistics."""
        with self._lock:
            total = len(self._proxies)
            blacklisted = sum(1 for p in self._proxies if p.is_blacklisted)
            by_provider = defaultdict(int)
            by_country = defaultdict(int)

            for p in self._proxies:
                by_provider[p.provider.value] += 1
                if p.country:
                    by_country[p.country] += 1

            avg_success_rate = 0
            if self._proxies:
                avg_success_rate = sum(p.success_rate for p in self._proxies) / total

            return {
                "total": total,
                "available": total - blacklisted,
                "blacklisted": blacklisted,
                "by_provider": dict(by_provider),
                "by_country": dict(by_country),
                "avg_success_rate": round(avg_success_rate * 100, 1),
            }

    def set_no_proxy_mode(self, enabled: bool):
        """Enable/disable no-proxy mode (direct connections)."""
        self._no_proxy_mode = enabled
        logger.info(f"No-proxy mode: {'enabled' if enabled else 'disabled'}")

    @property
    def has_proxies(self) -> bool:
        """Check if any proxies are available."""
        return len(self._proxies) > 0 and not self._no_proxy_mode


class ProxyRotator:
    """
    Context manager for automatic proxy rotation with requests.

    Usage:
        manager = ProxyManager()
        manager.add_proxies([...])

        with ProxyRotator(manager) as rotator:
            response = rotator.get("https://example.com")
    """

    def __init__(self, manager: ProxyManager, max_retries: int = 3):
        self.manager = manager
        self.max_retries = max_retries
        self.session = requests.Session()
        self._current_proxy: Optional[Proxy] = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

    def get(self, url: str, **kwargs) -> Optional[requests.Response]:
        """Make GET request with automatic proxy rotation on failure."""
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> Optional[requests.Response]:
        """Make POST request with automatic proxy rotation on failure."""
        return self._request("POST", url, **kwargs)

    def _request(self, method: str, url: str, **kwargs) -> Optional[requests.Response]:
        """Make request with automatic proxy rotation."""
        last_error = None

        for attempt in range(self.max_retries):
            self._current_proxy = self.manager.get_proxy()

            proxies = self._current_proxy.to_dict() if self._current_proxy else None

            try:
                start = time.time()
                response = self.session.request(
                    method,
                    url,
                    proxies=proxies,
                    timeout=kwargs.pop("timeout", 30),
                    **kwargs,
                )
                response_time = time.time() - start

                # Check for blocking responses
                if response.status_code in [403, 429, 503]:
                    if self._current_proxy:
                        self.manager.mark_failed(self._current_proxy, f"HTTP {response.status_code}")
                    continue

                if self._current_proxy:
                    self.manager.mark_success(self._current_proxy, response_time)

                return response

            except requests.exceptions.RequestException as e:
                last_error = e
                if self._current_proxy:
                    self.manager.mark_failed(self._current_proxy, str(e))
                logger.debug(f"Request failed (attempt {attempt + 1}): {e}")

        logger.error(f"All {self.max_retries} attempts failed for {url}: {last_error}")
        return None


# Global proxy manager instance
_default_manager: Optional[ProxyManager] = None


def get_proxy_manager() -> ProxyManager:
    """Get or create the default proxy manager."""
    global _default_manager
    if _default_manager is None:
        _default_manager = ProxyManager()
    return _default_manager


def setup_proxies(
    proxy_list: List[str] = None,
    provider: str = None,
    use_free: bool = False,
    country: str = "us",
) -> ProxyManager:
    """
    Convenience function to set up proxy manager.

    Args:
        proxy_list: List of proxy URLs
        provider: Provider name ("bright_data", "oxylabs", "smartproxy", "webshare")
        use_free: Whether to load free proxies
        country: Country for geo-targeting

    Returns:
        Configured ProxyManager
    """
    manager = get_proxy_manager()

    if proxy_list:
        manager.add_proxies(proxy_list)

    if provider:
        try:
            provider_enum = ProxyProvider(provider)
            manager.add_from_provider(provider_enum, country)
        except ValueError:
            logger.warning(f"Unknown provider: {provider}")

    if use_free:
        manager.load_free_proxies()

    return manager
