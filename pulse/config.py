"""Settings shared across the pipeline."""

from pathlib import Path

# City of Toronto Open Data runs on CKAN. package_show returns the dataset's
# metadata, including one downloadable resource (a ZIP file) per year.
CKAN_BASE_URL = "https://ckan0.cf.opendata.inter.prod-toronto.ca"
PACKAGE_ID = "311-service-requests-customer-initiated"

# Where raw downloads land. This folder is git-ignored.
RAW_DIR = Path("data/raw")

# Years loaded by default.
DEFAULT_YEARS = [2023, 2024, 2025, 2026]

# Seconds to wait on a network request: (connect, read). The server answers
# fast when it's down, but package_show can take 90+ seconds when it's busy,
# so the read timeout is much longer than the connect timeout.
REQUEST_TIMEOUT = (10, 180)

# How many times to retry a failed request, and the backoff factor between
# tries (urllib3 waits backoff * 2^(try - 1) seconds: 0, 4, 8...).
REQUEST_RETRIES = 3
RETRY_BACKOFF = 2
