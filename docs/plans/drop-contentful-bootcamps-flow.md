# Drop the bootcamp Contentful flow

Remove bootcamp Contentful fetching and transformation. Keep the degree Contentful path and the generic
`contentful_fields` plumbing in Algolia, which degrees still use.

Verified against `e752fa124`. Every reference below was confirmed by repo-wide grep for
`BOOTCAMP_CONTENTFUL_CONTENT_TYPE`, `fetch_and_transform_bootcamp_contentful_data`,
`get_bootcamp_curriculum_module`, `bootCampCurriculumModule`, `contentful_bootcamp_data_key`,
`MockContentfulBootcampResponse`, `create_bootcamp_mock_response_data`, `contentful_fields`.

## Behavior changes

Two, both intended:

1. Courses no longer get bootcamp Contentful data in Algolia. `contentful_fields` stays in the Algolia field
   list and search settings because degrees populate it.
2. `DiscoveryCourseMetadataProvider` sends `course.full_description` to taxonomy/EMSI instead of
   Contentful-aggregated text. Bootcamp course skill tagging loses that input.

## Edits

### 1. `course_metadata/index.py`

Drop the import of `fetch_and_transform_bootcamp_contentful_data`, the `bootcamp_contentful_data` local, and the
`contentful_data=` kwarg on the course proxy (lines 6-8, 24-25):

```python
qs1 = [AlgoliaProxyProduct(course, self.language)
       for course in AlgoliaProxyCourse.prefetch_queryset()]
```

Leave the degree branch and lines 101/117-118/161/178-179 alone.

### 2. `taxonomy_support/providers.py`

`get_courses()` (line 44) and `get_all_courses()` (line 61) each call
`fetch_and_transform_bootcamp_contentful_data()` and wrap `full_description` in `aggregate_contentful_data()`.
Delete both calls, collapse `full_description` to `course.full_description`, and drop
`fetch_and_transform_bootcamp_contentful_data` from the import at line 27-29. `aggregate_contentful_data` stays
imported: the program provider still uses it with degree data.

### 3. `course_metadata/contentful_utils.py`

Delete `fetch_and_transform_bootcamp_contentful_data()`, `get_bootcamp_curriculum_module()`,
`get_blurb_module()`, and `get_partnership_module()`. The last two are bootcamp-only despite their generic
names; the degree transform uses only `get_about_the_program_module`, `get_featured_products_module`,
`get_placement_about_section_module`, and `get_faq_module`.

Simplify `get_contentful_cache_key()` to the degree branch plus the `None` fallback.

Keep `aggregate_contentful_data()` as is. Its `hero_text_list` branch goes dead (degrees never set that key) but
removing it is churn with no payoff.

### 4. `settings/test.py`

Delete `BOOTCAMP_CONTENTFUL_CONTENT_TYPE` at line 92. That is the only definition in the repo. It is absent from
`base.py`, env templates, and docs.

### 5. `course_metadata/tests/contentful_utils/contentful_mock_data.py`

Delete `create_bootcamp_mock_response_data()` and `MockContentfulBootcampResponse`, including the
`bootCampCurriculumModule`, `partnershipModule`, and `blurbModule` entries they build.

`MockContenfulDegreeResponse` needs `total = 15` and `items = [entry]` so it can stand in for the bootcamp mock in
the two generic fetch tests below. Its module docstring also says "Bootcamp"; fix it.

### 6. `course_metadata/tests/test_contentful_utils.py`

Delete `test_transform_bootcamp_contentful_data` and `test_get_aggregated_data_from_contentful__bootcamp`. The
degree equivalents already cover both paths.

Repoint, do not delete, `test_get_data_from_contentful` and `test_get_cached_data_from_contentful`. They test the
generic pagination and caching in `get_data_from_contentful`, and only use the bootcamp mock as a fixture. Swap
them to `MockContenfulDegreeResponse` and `DEGREE_CONTENTFUL_CONTENT_TYPE`. The `len(contentful_data) == 2`
assertion holds as long as the degree mock keeps `total = 15` and one item.

### 7. `taxonomy_support/tests/test_providers.py`

Drop the `fetch_and_transform_bootcamp_contentful_data` mock patch on
`test_validate_course_metadata` (line 53) and its `_contentful_data` arg. The degree patch on
`test_validate_program_metadata` stays.

## Not in scope

Bootcamp course types, slug generation, CSV import, catalog export, migrations, toggles. Those are product and
data-model cleanup, not this pipeline.

## Order and verification

1. `index.py`
2. `providers.py`
3. `contentful_utils.py`
4. `settings/test.py`
5. tests and mocks
6. `pytest course_discovery/apps/course_metadata/tests/test_contentful_utils.py course_discovery/apps/taxonomy_support/tests/test_providers.py`
7. `make quality` (catches leftover unused imports)
8. final grep for the seven strings listed at the top

`AlgoliaProxyProduct` field access already defaults to `None` via `getattr` in `algolia_models.py:97-103`, so
courses missing `contentful_fields` serialize fine. That is true today for any course without a bootcamp entry,
so no new risk.
