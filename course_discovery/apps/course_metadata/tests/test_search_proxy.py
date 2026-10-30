"""Tests for the B2C catalog search proxy (service layer and REST endpoint)."""
from unittest import mock

import requests
from algoliasearch.helpers import AlgoliaException
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from course_discovery.apps.api.v1.views.search import B2CSearchAnonRateThrottle
from course_discovery.apps.course_metadata.search_proxy import (
    B2C_SUBSCRIPTION_INCLUSION_FILTER, MAX_HITS_PER_PAGE, AlgoliaSearchProxyService, AlgoliaUpstreamError
)

PROXY_CLIENT_PATH = 'course_discovery.apps.course_metadata.search_proxy.Client'
TEST_INDEX_NAME = 'test_product'


def _algolia_result(hits=None, nb_hits=None):
    hits = hits if hits is not None else [{'objectID': 'course-1'}]
    return {'hits': hits, 'nbHits': len(hits) if nb_hits is None else nb_hits, 'nbPages': 1, 'page': 0}


@override_settings(
    ALGOLIA_APPLICATION_ID='test-app-id',
    ALGOLIA_SEARCH_API_KEY='test-search-key',
    ALGOLIA_PRODUCT_INDEX_NAME=TEST_INDEX_NAME,
)
class AlgoliaSearchProxyServiceTests(TestCase):

    def setUp(self):
        super().setUp()
        self.algolia_client = mock.Mock()
        self.algolia_client.multiple_queries.return_value = {'results': [_algolia_result()]}
        self.service = AlgoliaSearchProxyService(client=self.algolia_client)

    def _sent_queries(self):
        return self.algolia_client.multiple_queries.call_args[0][0]

    def test_single_query_is_scoped_to_b2c_and_index(self):
        response = self.service.search([{'query': 'python', 'hitsPerPage': 5}])

        self.assertEqual(len(response['results']), 1)
        sent = self._sent_queries()
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]['indexName'], TEST_INDEX_NAME)
        self.assertEqual(sent[0]['query'], 'python')
        self.assertEqual(sent[0]['hitsPerPage'], 5)
        self.assertEqual(sent[0]['facetFilters'], [[B2C_SUBSCRIPTION_INCLUSION_FILTER]])

    def test_batch_requests_are_each_scoped(self):
        self.algolia_client.multiple_queries.return_value = {
            'results': [_algolia_result(), _algolia_result(hits=[])]
        }

        response = self.service.search([
            {'query': 'python', 'facetFilters': [['subject:AI']]},
            {'query': '', 'facetFilters': [['product:Course']]},
        ])

        self.assertEqual(len(response['results']), 2)
        sent = self._sent_queries()
        self.assertEqual(len(sent), 2)
        self.assertEqual(sent[0]['facetFilters'], [[B2C_SUBSCRIPTION_INCLUSION_FILTER], ['subject:AI']])
        self.assertEqual(sent[1]['facetFilters'], [[B2C_SUBSCRIPTION_INCLUSION_FILTER], ['product:Course']])
        for query in sent:
            self.assertEqual(query['indexName'], TEST_INDEX_NAME)

    def test_client_cannot_remove_or_negate_b2c_filter(self):
        self.service.search([{
            'facetFilters': [
                ['b2c_subscription_inclusion:false'],
                '-b2c_subscription_inclusion:true',
                ['subject:AI', 'b2c_subscription_inclusion:false'],
                ['B2C_Subscription_Inclusion:true'],
                ['product:Course'],
            ],
        }])

        facet_filters = self._sent_queries()[0]['facetFilters']
        self.assertEqual(facet_filters, [[B2C_SUBSCRIPTION_INCLUSION_FILTER], ['subject:AI'], ['product:Course']])
        for group in facet_filters[1:]:
            for clause in group:
                self.assertNotIn('b2c_subscription_inclusion', clause.lower())

    def test_client_cannot_override_index_or_add_raw_filters(self):
        self.service.search([{
            'indexName': 'other_index',
            'filters': 'b2c_subscription_inclusion:false OR owner:x',
            'tagFilters': ['anything'],
            'optionalFilters': ['b2c_subscription_inclusion:false'],
            'query': 'x',
        }])

        sent = self._sent_queries()[0]
        self.assertEqual(sent['indexName'], TEST_INDEX_NAME)
        self.assertNotIn('filters', sent)
        self.assertNotIn('tagFilters', sent)
        self.assertNotIn('optionalFilters', sent)
        self.assertEqual(sent['facetFilters'], [[B2C_SUBSCRIPTION_INCLUSION_FILTER]])

    def test_b2c_filter_is_strictly_present_in_every_outbound_request(self):
        payloads = [
            {},
            {'facetFilters': []},
            {'facetFilters': [['b2c_subscription_inclusion:false']]},
            {'facetFilters': 'b2c_subscription_inclusion:false'},
        ]

        self.service.search(payloads)

        for query in self._sent_queries():
            self.assertEqual(query['facetFilters'][0], [B2C_SUBSCRIPTION_INCLUSION_FILTER])

    def test_pagination_and_safe_params_are_forwarded(self):
        self.service.search([{
            'query': '  data science  ',
            'page': 3,
            'hitsPerPage': 1000,
            'facets': ['subject', 'skills.skill'],
            'numericFilters': ['weeks_to_complete>=4'],
            'attributesToRetrieve': ['title', 'objectID'],
            'attributesToHighlight': ['title'],
            'highlightPreTag': '<mark>',
            'highlightPostTag': '</mark>',
            'removeWordsIfNoResults': 'allOptional',
        }])

        sent = self._sent_queries()[0]
        self.assertEqual(sent['query'], 'data science')
        self.assertEqual(sent['page'], 3)
        self.assertEqual(sent['hitsPerPage'], MAX_HITS_PER_PAGE)
        self.assertEqual(sent['facets'], ['subject', 'skills.skill'])
        self.assertEqual(sent['numericFilters'], ['weeks_to_complete>=4'])
        self.assertEqual(sent['attributesToRetrieve'], ['title', 'objectID'])
        self.assertEqual(sent['attributesToHighlight'], ['title'])
        self.assertEqual(sent['highlightPreTag'], '<mark>')
        self.assertEqual(sent['highlightPostTag'], '</mark>')
        self.assertEqual(sent['removeWordsIfNoResults'], 'allOptional')

    def test_invalid_parameters_are_rejected(self):
        invalid_payloads = [
            [{'page': -1}],
            [{'hitsPerPage': 'many'}],
            [{'query': 42}],
            [{'facets': 'subject'}],
            [{'facetFilters': 'subject:AI', 'attributesToRetrieve': 'title'}],
            [{'facetFilters': [{'not': 'valid'}]}],
            [{'removeWordsIfNoResults': 'everything'}],
            ['not-an-object'],
            [],
            [{}] * 11,
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                self.service.search(payload)
        self.algolia_client.multiple_queries.assert_not_called()

    def test_hit_and_timing_metrics_are_logged(self):
        self.algolia_client.multiple_queries.return_value = {
            'results': [_algolia_result(hits=[{'objectID': 'a'}, {'objectID': 'b'}], nb_hits=42)]
        }

        with self.assertLogs('course_discovery.apps.course_metadata.search_proxy', level='INFO') as logs:
            self.service.search([{'query': 'x'}])

        message = logs.output[0]
        self.assertIn('duration_ms=', message)
        self.assertIn('request_count=1', message)
        self.assertIn('hit_counts=[2]', message)
        self.assertIn('nb_hits=[42]', message)

    def test_upstream_algolia_exception_maps_to_502(self):
        self.algolia_client.multiple_queries.side_effect = AlgoliaException('Bad request')

        with self.assertRaises(AlgoliaUpstreamError) as ctx:
            self.service.search([{'query': 'x'}])
        self.assertEqual(ctx.exception.status_code, status.HTTP_502_BAD_GATEWAY)

    def test_upstream_timeout_and_connection_errors_map_to_502(self):
        for error in (requests.exceptions.Timeout('timed out'), requests.exceptions.ConnectionError('refused')):
            with self.subTest(error=type(error).__name__):
                self.algolia_client.multiple_queries.side_effect = error
                with self.assertRaises(AlgoliaUpstreamError) as ctx:
                    self.service.search([{'query': 'x'}])
                self.assertEqual(ctx.exception.status_code, status.HTTP_502_BAD_GATEWAY)

    def test_upstream_server_error_maps_to_502(self):
        self.algolia_client.multiple_queries.side_effect = Exception('Algolia 503')

        with self.assertRaises(AlgoliaUpstreamError) as ctx:
            self.service.search([{'query': 'x'}])
        self.assertEqual(ctx.exception.status_code, status.HTTP_502_BAD_GATEWAY)


@override_settings(
    ALGOLIA_APPLICATION_ID='test-app-id',
    ALGOLIA_SEARCH_API_KEY='test-search-key',
    ALGOLIA_PRODUCT_INDEX_NAME=TEST_INDEX_NAME,
)
class B2CSearchProxyViewTests(TestCase):

    def setUp(self):
        super().setUp()
        cache.clear()
        self.url = reverse('api:v1:search-b2c-catalog')
        self.api_client = APIClient()

        patcher = mock.patch(PROXY_CLIENT_PATH)
        self.client_class = patcher.start()
        self.addCleanup(patcher.stop)
        self.algolia_client = self.client_class.return_value
        self.algolia_client.multiple_queries.return_value = {'results': [_algolia_result()]}

    def test_single_query_payload_is_accepted_anonymously(self):
        response = self.api_client.post(self.url, {'query': 'python'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['results'][0]['hits'], [{'objectID': 'course-1'}])
        sent = self.algolia_client.multiple_queries.call_args[0][0]
        self.assertEqual(sent[0]['facetFilters'], [[B2C_SUBSCRIPTION_INCLUSION_FILTER]])
        self.assertEqual(sent[0]['indexName'], TEST_INDEX_NAME)

    def test_batch_payload_returns_one_result_per_request(self):
        self.algolia_client.multiple_queries.return_value = {
            'results': [_algolia_result(), _algolia_result(hits=[{'objectID': 'program-1'}])]
        }

        response = self.api_client.post(
            self.url,
            {'requests': [{'query': 'python'}, {'query': '', 'facetFilters': [['product:Program']]}]},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.json()['results']), 2)
        sent = self.algolia_client.multiple_queries.call_args[0][0]
        self.assertEqual(len(sent), 2)
        for query in sent:
            self.assertEqual(query['facetFilters'][0], [B2C_SUBSCRIPTION_INCLUSION_FILTER])

    def test_client_supplied_b2c_override_is_ignored_end_to_end(self):
        self.api_client.post(
            self.url,
            {'requests': [{'facetFilters': [['b2c_subscription_inclusion:false']]}]},
            format='json',
        )

        sent = self.algolia_client.multiple_queries.call_args[0][0]
        self.assertEqual(sent[0]['facetFilters'], [[B2C_SUBSCRIPTION_INCLUSION_FILTER]])

    def test_invalid_body_returns_400(self):
        response = self.api_client.post(self.url, {'requests': 'not-a-list'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.algolia_client.multiple_queries.assert_not_called()

    def test_upstream_failure_returns_502_with_clean_json(self):
        self.algolia_client.multiple_queries.side_effect = requests.exceptions.Timeout('timed out')

        response = self.api_client.post(self.url, {'query': 'python'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.assertIn('detail', response.json())
        self.assertNotIn('timed out', response.content.decode())

    def test_anonymous_requests_are_throttled(self):
        cache.clear()
        with mock.patch.dict(B2CSearchAnonRateThrottle.THROTTLE_RATES, {'b2c_search_anon': '2/minute'}):
            statuses = [
                self.api_client.post(self.url, {'query': 'x'}, format='json').status_code for _ in range(3)
            ]

        self.assertEqual(statuses[:2], [status.HTTP_200_OK, status.HTTP_200_OK])
        self.assertEqual(statuses[2], status.HTTP_429_TOO_MANY_REQUESTS)
