from django.test import TestCase

from course_discovery.apps.course_metadata.choices import BulkOperationType
from course_discovery.apps.course_metadata.data_loaders.course_loader import CourseLoader
from course_discovery.apps.course_metadata.tests import factories


class CourseLoaderTests(TestCase):
    """
    Tests for CourseLoader.
    """

    def setUp(self):
        super().setUp()
        self.course = factories.CourseFactory()

    def _request_data_for_task_type(self, task_type, **course_data):
        loader = CourseLoader.__new__(CourseLoader)
        loader.task_type = task_type
        return loader.update_course_api_request_data(course_data, self.course, self.course.type, is_draft=True)

    def _course_create_request_data(self, **course_data):
        loader = CourseLoader.__new__(CourseLoader)
        source = factories.SourceFactory()
        data = {
            'organization': 'edX',
            'title': 'Test Course',
            'number': 'DemoX',
            'course_pacing': 'self-paced',
            'start_date': '2026-01-01',
            'end_date': '2026-12-31',
        }
        data.update(course_data)
        return loader.create_course_api_request_data(data, self.course.type, self.course.type.uuid, source)

    def test_create_course_api_request_data_includes_b2c_subscription_inclusion(self):
        """
        Verify b2c_subscription_inclusion is included in the initial course create API payload.
        """
        request_data = self._course_create_request_data(b2c_subscription_inclusion='true')

        self.assertIs(request_data['b2c_subscription_inclusion'], True)

    def test_create_course_api_request_data_omits_blank_b2c_subscription_inclusion(self):
        """
        Verify b2c_subscription_inclusion remains optional for initial course creation.
        """
        request_data = self._course_create_request_data(b2c_subscription_inclusion='')

        self.assertNotIn('b2c_subscription_inclusion', request_data)

    def test_update_course_api_request_data_includes_b2c_subscription_inclusion_for_course_create(self):
        """
        Verify b2c_subscription_inclusion is parsed from course create CSV data.
        """
        request_data = self._request_data_for_task_type(
            BulkOperationType.CourseCreate,
            b2c_subscription_inclusion='true',
        )

        self.assertIs(request_data['b2c_subscription_inclusion'], True)

    def test_update_course_api_request_data_includes_b2c_subscription_inclusion_for_partial_update(self):
        """
        Verify b2c_subscription_inclusion is parsed from partial update CSV data.
        """
        request_data = self._request_data_for_task_type(
            BulkOperationType.PartialUpdate,
            b2c_subscription_inclusion='false',
        )

        self.assertIs(request_data['b2c_subscription_inclusion'], False)

    def test_update_course_api_request_data_omits_blank_b2c_subscription_inclusion(self):
        """
        Verify b2c_subscription_inclusion remains optional.
        """
        request_data = self._request_data_for_task_type(
            BulkOperationType.PartialUpdate,
            b2c_subscription_inclusion='',
        )

        self.assertNotIn('b2c_subscription_inclusion', request_data)
