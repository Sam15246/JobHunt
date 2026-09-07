from urllib.parse import urlparse, urlunparse, parse_qs, urlencode


class BaseScraper:
    """Base class for all scrapers. Provides URL normalization and shared utilities."""

    STRIP_PARAMS = frozenset({
        "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
        "ref", "source", "from", "fbclid", "gclid", "mc_cid", "mc_eid",
    })

    @staticmethod
    def normalize_url(url: str) -> str:
        """Normalize a URL for deduplication.

        - Lowercases scheme and host (preserves path case)
        - Strips tracking query parameters (utm_*, ref, source, etc.)
        - Removes trailing slashes from path
        - Drops URL fragments
        """
        parsed = urlparse(url)

        # Filter out tracking params
        params = parse_qs(parsed.query, keep_blank_values=False)
        filtered = {
            k: v for k, v in params.items()
            if k.lower() not in BaseScraper.STRIP_PARAMS
        }
        clean_query = urlencode(filtered, doseq=True)

        # Normalize components
        path = parsed.path.rstrip("/")
        normalized = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            "",           # params (rarely used)
            clean_query,
            "",           # drop fragment
        ))
        return normalized
