"""Shared limits for untrusted public HTTP inputs.

Keep these at the API boundary as well as in lower-level parsers. Reverse
proxies usually impose their own limits, but the application must remain safe
when it is run directly (which is common for self-hosted DevRadar installs).
"""

MAX_REQUEST_BODY_BYTES = 1_048_576  # 1 MiB
MAX_SEARCH_QUERY_LENGTH = 200
MAX_FILTER_VALUE_LENGTH = 100
MAX_STATUS_PARAM_LENGTH = 200
MAX_TAGS_PARAM_LENGTH = 500
MAX_TAG_FILTERS = 10
MAX_CURSOR_LENGTH = 512
MAX_SLUG_LENGTH = 300
MAX_TRACKING_ID_LENGTH = 128
MAX_IDEMPOTENCY_KEY_LENGTH = 200
MAX_ALERT_TOKEN_LENGTH = 256
MAX_TRACE_ID_LENGTH = 128
