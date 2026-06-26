import ddt
import pytest
from django.contrib.auth.models import ContentType, Permission
from django.test import TestCase

from course_discovery.apps.catalogs.models import Catalog
from course_discovery.apps.catalogs.tests import factories
from course_discovery.apps.core.tests.factories import UserFactory
from course_discovery.apps.core.tests.mixins import ElasticsearchTestMixin
from course_discovery.apps.course_metadata.tests.factories import CourseFactory, CourseRunFactory

HistoricalCatalog = Catalog.history.model  # pylint: disable=no-member


@ddt.ddt
class CatalogTests(ElasticsearchTestMixin, TestCase):
    """ Catalog model tests. """

    def setUp(self):
        super().setUp()
        self.catalog = factories.CatalogFactory(query='title:abc*')
        self.catalog_with_incorrect_query = factories.CatalogFactory(query='title:')

        self.course = CourseFactory(key='a/b/c', title='ABCs of Ͳҽʂէìղց')
        self.refresh_index()

    def test_unicode(self):
        """ Validate the output of the __unicode__ method. """
        name = 'test'
        self.catalog.name = name
        self.catalog.save()

        expected = f'Catalog #{self.catalog.id}: {name}'
        assert str(self.catalog) == expected

    def test_courses(self):
        """ Verify the method returns a QuerySet of courses contained in the catalog. """
        assert list(self.catalog.courses()) == [self.course]

    def test_contains(self):
        """ Verify the method returns a mapping of course IDs to booleans. """
        uncontained_course = CourseFactory(key='d/e/f', title='ABDEF')
        self.assertDictEqual(
            self.catalog.contains([self.course.key, uncontained_course.key]),
            {self.course.key: True, uncontained_course.key: False}
        )

    def test_contains_course_runs(self):
        """ Verify the method returns a mapping of course run IDs to booleans. """
        course_run = CourseRunFactory(course=self.course)
        uncontained_course_run = CourseRunFactory(title_override='ABD')
        self.assertDictEqual(
            self.catalog.contains_course_runs([course_run.key, uncontained_course_run.key]),
            {course_run.key: True, uncontained_course_run.key: False}
        )

    def test_contains_course_runs_if_query_is_incorrect(self):
        """ Verify the method returns a mapping of course run IDs to booleans. """
        course_run = CourseRunFactory(course=self.course)
        self.assertDictEqual(
            self.catalog_with_incorrect_query.contains_course_runs([course_run.key]),
            {course_run.key: False}
        )

    def test_courses_count(self):
        """ Verify the method returns the number of courses contained in the Catalog. """
        assert self.catalog.courses_count == 1

        # Create a new course that should NOT be contained in the catalog, and one that should
        CourseFactory()
        CourseFactory(title='ABCDEF')
        assert self.catalog.courses_count == 2

    def test_courses_count_if_query_is_incorrect(self):
        """ Verify the method returns the number of courses contained in the Catalog. """
        CourseFactory(title='ABCDEF')
        assert self.catalog_with_incorrect_query.courses_count == 0

    def test_get_viewers(self):
        """ Verify the method returns a QuerySet of individuals with explicit permission to view a Catalog. """
        catalog = self.catalog
        assert not catalog.viewers.exists()

        user = UserFactory()
        user.add_obj_perm(Catalog.VIEW_PERMISSION, catalog)
        self.assertListEqual(list(catalog.viewers), [user])

    def test_set_viewers(self):
        """ Verify the method updates the set of users with permission to view a Catalog. """
        users = UserFactory.create_batch(2)
        permission = 'catalogs.' + Catalog.VIEW_PERMISSION

        for user in users:
            assert not user.has_perm(permission, self.catalog)

        # Verify a list of users can be added as viewers
        self.catalog.viewers = users
        for user in users:
            assert user.has_perm(permission, self.catalog)

        # Verify existing users, not in the list, have their access revoked.
        permitted = users[0]
        revoked = users[1]
        self.catalog.viewers = [permitted]
        assert permitted.has_perm(permission, self.catalog)
        assert not revoked.has_perm(permission, self.catalog)

        # Verify all users have their access revoked when passing in an empty list
        self.catalog.viewers = []
        for user in users:
            assert not user.has_perm(permission, self.catalog)

    @ddt.data(None, 35, 'a')
    def test_set_viewers_with_invalid_argument(self, viewers):
        """ Verify the method raises a `TypeError` if the passed value is not iterable, or is a string. """
        with pytest.raises(TypeError) as context:
            self.catalog.viewers = viewers
        assert context.value.args[0] == 'Viewers must be a non-string iterable containing User objects.'

    @ddt.data('add_catalog', 'change_catalog', 'view_catalog', 'delete_catalog')
    def test_catalogs_permissions(self, perm):
        """ Validate that model has the all four permissions. """
        cont_type = ContentType.objects.get(app_label='catalogs', model='catalog')
        assert Permission.objects.get(content_type=cont_type, codename=perm)


class CatalogHistoryTrackingTests(TestCase):
    """
    Tests for Catalog model history tracking via django-simple-history.

    Verifies that:
    - Historical records (snapshots) are created on create/update/delete operations
    - History metadata (history_type, history_date, history_user) are populated correctly
    - Users can audit and traverse Catalog change history
    """

    def test_history_record_created_on_catalog_creation(self):
        """Verify a history record is created when a Catalog is created."""
        # Create a new catalog
        catalog = factories.CatalogFactory(
            name='Test Catalog',
            query='title:test*'
        )

        # Verify at least one history record exists for this catalog with correct snapshot values
        assert HistoricalCatalog.objects.filter(
            id=catalog.id,
            name='Test Catalog',
            query='title:test*',
            history_type='+',
        ).exists(), "History should contain record with correct snapshot data for creation"

    def test_history_record_created_on_catalog_update(self):
        """Verify a history record is created when a Catalog is updated."""
        catalog = factories.CatalogFactory(
            name='Original Name',
            query='title:original*'
        )
        initial_history_count = HistoricalCatalog.objects.filter(id=catalog.id).count()

        # Update the catalog
        catalog.name = 'Updated Name'
        catalog.query = 'title:updated*'
        catalog.save()

        # Verify new history record was created
        assert HistoricalCatalog.objects.filter(id=catalog.id).count() == initial_history_count + 1

        # Verify the new history record contains updated snapshot data
        latest_history = HistoricalCatalog.objects.filter(id=catalog.id).latest()
        assert latest_history.name == 'Updated Name'
        assert latest_history.query == 'title:updated*'
        assert latest_history.history_type == '~'  # '~' denotes change

    def test_history_records_include_create_update_delete_types(self):
        """Verify create/update/delete operations produce +, ~, - history types."""
        catalog = factories.CatalogFactory(name='CRUD Types', query='title:crud*')
        catalog_id = catalog.id

        catalog.query = 'title:crud-updated*'
        catalog.save()
        catalog.delete()

        history_types = set(HistoricalCatalog.objects.filter(id=catalog_id).values_list('history_type', flat=True))
        assert {'+', '~', '-'} <= history_types

    def test_history_record_created_on_catalog_deletion(self):
        """Verify a history record is created when a Catalog is deleted."""
        catalog = factories.CatalogFactory(name='To Delete')
        catalog_id = catalog.id
        history_count_before_delete = HistoricalCatalog.objects.filter(id=catalog_id).count()

        # Delete the catalog
        catalog.delete()

        # Verify history record for deletion was created
        history_count_after_delete = HistoricalCatalog.objects.filter(id=catalog_id).count()
        assert history_count_after_delete == history_count_before_delete + 1

        # Verify the deletion history record has correct type
        deletion_record = HistoricalCatalog.objects.filter(id=catalog_id).latest()
        assert deletion_record.history_type == '-'  # '-' denotes deletion

    def test_history_metadata_fields_populated_correctly(self):
        """Verify history metadata columns are populated (history_id, history_date, history_user)."""
        user = UserFactory(username='history_user')

        # Create and update catalog while setting history user explicitly
        catalog = factories.CatalogFactory(name='Metadata Test')
        catalog._history_user = user  # pylint: disable=protected-access
        catalog.name = 'Metadata Test Updated'
        catalog.save()

        # Retrieve the history record
        history_record = HistoricalCatalog.objects.filter(id=catalog.id).latest()

        # Verify metadata fields are present and have values
        assert history_record.history_id is not None  # Unique history record ID
        assert history_record.history_date is not None  # Timestamp of change
        assert history_record.history_type in ['+', '~', '-']  # Valid operation type
        assert history_record.history_user == user

    def test_history_change_reason_field_exists(self):
        """Verify the history_change_reason field exists on history records."""
        catalog = factories.CatalogFactory(name='Original')

        # Update the catalog
        catalog.name = 'Updated'
        catalog.save()

        # Verify history_change_reason field exists (even if None)
        latest_history = HistoricalCatalog.objects.filter(id=catalog.id).latest()
        assert hasattr(latest_history, 'history_change_reason')
        # Field should be populated (or None) - just verify it exists and is accessible
        assert latest_history.history_change_reason is None or isinstance(latest_history.history_change_reason, str)

    def test_historical_model_table_structure(self):
        """Verify catalogs_historicalcatalog table has expected structure (snapshot + meta columns)."""
        catalog = factories.CatalogFactory()
        history_record = HistoricalCatalog.objects.filter(id=catalog.id).latest()

        # Snapshot columns (copy of Catalog model fields)
        assert hasattr(history_record, 'id')
        assert hasattr(history_record, 'name')
        assert hasattr(history_record, 'query')
        assert hasattr(history_record, 'program_query')
        assert hasattr(history_record, 'include_archived')
        assert hasattr(history_record, 'created')
        assert hasattr(history_record, 'modified')

        # Meta columns (history tracking fields)
        assert hasattr(history_record, 'history_id')
        assert hasattr(history_record, 'history_date')
        assert hasattr(history_record, 'history_type')
        assert hasattr(history_record, 'history_user')
        assert hasattr(history_record, 'history_change_reason')
