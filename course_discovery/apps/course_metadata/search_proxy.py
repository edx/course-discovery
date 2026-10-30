"""
Server-side proxy for B2C course and program search backed by Algolia.

Browsers never call Algolia directly. Credentials stay on the server, and every upstream
query is scoped to the B2C subscription catalog regardless of what the caller sends.
"""
import logging
import time

from algoliasearch.client import Client
from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError

log = logging.getLogger(__name__)

B2C_SUBSCRIPTION_INCLUSION_ATTRIBUTE = 'b2c_subscription_inclusion'
B2C_SUBSCRIPTION_INCLUSION_FILTER = 'b2c_subscription_inclusion:true'

# Parameters a caller may send. Anything else (indexName, filters, tagFilters, optionalFilters, ...)
# is dropped so the caller cannot redirect the query or bypass the B2C scope.
ALLOWED_PARAMS = frozenset({
    'query',
    'page',
    'hitsPerPage',
    'facets',
    'facetFilters',
    'numericFilters',
    'attributesToRetrieve',
    'attributesToHighlight',
    'highlightPreTag',
    'highlightPostTag',
    'removeWordsIfNoResults',
})
REMOVE_WORDS_IF_NO_RESULTS_OPTIONS = ('none', 'lastWords', 'firstWords', 'allOptional')

DEFAULT_HITS_PER_PAGE = 20
MAX_HITS_PER_PAGE = 100
MAX_PAGE = 1000
MAX_QUERY_LENGTH = 512
MAX_BATCH_REQUESTS = 10

CONNECT_TIMEOUT_SECONDS = 2
READ_TIMEOUT_SECONDS = 10
SEARCH_TIMEOUT_SECONDS = 5


class AlgoliaUpstreamError(APIException):
    """Raised when the Algolia upstream fails, times out, or rejects the request."""

    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = 'Search is temporarily unavailable. Please try again.'
    default_code = 'search_upstream_error'


def _build_client():
    client = Client(settings.ALGOLIA_APPLICATION_ID, settings.ALGOLIA_SEARCH_API_KEY)
    client.timeout = (CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS)
    client.search_timeout = (CONNECT_TIMEOUT_SECONDS, SEARCH_TIMEOUT_SECONDS)
    return client


def _mentions_b2c_attribute(clause):
    # Substring match on purpose: catches negated (-attr:...), case-varied and otherwise
    # malformed forms. Dropping a clause from an OR group only narrows that group.
    return B2C_SUBSCRIPTION_INCLUSION_ATTRIBUTE in clause.lower()


def _string_list(value, field):
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValidationError({field: f'{field} must be a list of strings.'})
    return value


def _bounded_int(value, field, default, maximum):
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError({field: f'{field} must be a non-negative integer.'})
    return min(value, maximum)


def _sanitize_facet_filters(facet_filters):
    """
    Remove every client clause that references b2c_subscription_inclusion.

    facetFilters groups are ANDed together and clauses within a group are ORed, so a client
    clause in its own group could be used to widen the result set. Stripping the attribute
    everywhere ensures the server-injected B2C group is the only one that mentions it.
    """
    if facet_filters is None:
        return []
    if isinstance(facet_filters, str):
        facet_filters = [facet_filters]
    if not isinstance(facet_filters, list):
        raise ValidationError({'facetFilters': 'facetFilters must be a list.'})

    groups = []
    for item in facet_filters:
        if isinstance(item, str):
            clauses = [item]
        elif isinstance(item, list) and all(isinstance(clause, str) for clause in item):
            clauses = item
        else:
            raise ValidationError({'facetFilters': 'facetFilters must contain strings or lists of strings.'})

        kept = [clause for clause in clauses if not _mentions_b2c_attribute(clause)]
        if kept:
            groups.append(kept)
    return groups


class AlgoliaSearchProxyService:
    """Validates caller search requests, enforces the B2C scope, and runs them against Algolia."""

    def __init__(self, client=None):
        self.client = client or _build_client()
        self.index_name = settings.ALGOLIA_PRODUCT_INDEX_NAME

    def search(self, requests_payload):
        """
        Run one or more search requests and return {'results': [...]}, one entry per request.

        Each entry is the raw Algolia response for that request, so InstantSearch-style
        consumers can read hits, nbHits, nbPages and facets directly.
        """
        if not isinstance(requests_payload, list) or not requests_payload:
            raise ValidationError({'requests': 'At least one search request is required.'})
        if len(requests_payload) > MAX_BATCH_REQUESTS:
            raise ValidationError({'requests': f'No more than {MAX_BATCH_REQUESTS} requests per batch.'})

        queries = [self._build_query(request_payload) for request_payload in requests_payload]

        started = time.perf_counter()
        try:
            response = self.client.multiple_queries(queries, index_name_key='indexName', strategy='none')
        except Exception as exc:
            # algoliasearch's transport raises a bare Exception for 5xx responses, so upstream
            # failures (timeouts, connection errors, client and server errors) cannot be narrowed.
            duration_ms = (time.perf_counter() - started) * 1000
            log.warning('b2c_search_proxy upstream_error duration_ms=%.2f error=%s', duration_ms, type(exc).__name__)
            raise AlgoliaUpstreamError() from exc

        duration_ms = (time.perf_counter() - started) * 1000
        results = response.get('results', [])
        self._log_metrics(results, duration_ms)
        return {'results': results}

    def _build_query(self, request_payload):
        if not isinstance(request_payload, dict):
            raise ValidationError({'requests': 'Each search request must be a JSON object.'})

        query = request_payload.get('query', '')
        if not isinstance(query, str):
            raise ValidationError({'query': 'query must be a string.'})
        query = query.strip()[:MAX_QUERY_LENGTH]

        params = {
            key: value for key, value in request_payload.items()
            if key in ALLOWED_PARAMS
        }
        params['query'] = query
        params['page'] = _bounded_int(request_payload.get('page'), 'page', 0, MAX_PAGE)
        params['hitsPerPage'] = _bounded_int(
            request_payload.get('hitsPerPage'), 'hitsPerPage', DEFAULT_HITS_PER_PAGE, MAX_HITS_PER_PAGE
        )
        params['facetFilters'] = [[B2C_SUBSCRIPTION_INCLUSION_FILTER]] + _sanitize_facet_filters(
            request_payload.get('facetFilters')
        )

        if 'facets' in params:
            params['facets'] = _string_list(params['facets'], 'facets')
        if 'attributesToRetrieve' in params:
            params['attributesToRetrieve'] = _string_list(params['attributesToRetrieve'], 'attributesToRetrieve')
        if 'attributesToHighlight' in params:
            params['attributesToHighlight'] = _string_list(params['attributesToHighlight'], 'attributesToHighlight')
        if 'numericFilters' in params and not isinstance(params['numericFilters'], list):
            raise ValidationError({'numericFilters': 'numericFilters must be a list.'})
        if 'removeWordsIfNoResults' in params and params['removeWordsIfNoResults'] not in (
                REMOVE_WORDS_IF_NO_RESULTS_OPTIONS
        ):
            raise ValidationError({'removeWordsIfNoResults': 'Unsupported removeWordsIfNoResults value.'})

        params['indexName'] = self.index_name
        return params

    def _log_metrics(self, results, duration_ms):
        hit_counts = [len(result.get('hits', [])) for result in results]
        nb_hits = [result.get('nbHits', 0) for result in results]
        log.info(
            'b2c_search_proxy duration_ms=%.2f request_count=%d hit_counts=%s nb_hits=%s',
            duration_ms, len(results), hit_counts, nb_hits,
        )
