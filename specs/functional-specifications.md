# Course Discovery Functional Specifications

## Scope

This specification describes the externally visible and operator-visible behavior implemented by Course Discovery. It is derived from the Django URL configuration, REST API viewsets, serializers, filters, models, search documents, management commands, and repository documentation.

Course Discovery functions as the consolidated metadata service for Open edX learning products. It stores and exposes metadata for courses, course runs, programs, degrees, catalogs, people, organizations, learner pathways, taxonomy, recommendations, and operational data synchronization.

## Actors

| Actor | Functional role |
| --- | --- |
| Authenticated API consumer | Reads course, course run, program, organization, person, catalog, search, pathway, and taxonomy metadata. |
| Catalog API consumer | Reads scoped catalog data and catalog membership results. |
| Publisher user | Creates and edits course and course run metadata through Publisher-facing API behavior. |
| Course editor | Edits the subset of courses and course runs assigned to them. |
| Staff user | Performs privileged updates, review transitions, image updates, organization user lookups, and operational admin actions. |
| External integration | Consumes affiliate feeds, program fixtures, catalog extension APIs, search indexes, or published metadata updates. |
| Operator | Runs management commands for imports, refreshes, publishing, index maintenance, backfills, and data repair. |

## Cross-Cutting Functional Rules

1. API requests require authentication for the primary v1 API surfaces, search APIs, publisher APIs, learner pathway APIs, and taxonomy recommendation APIs unless a view explicitly mixes in anonymous throttled behavior.
2. All course and course run write operations work against draft records through `ensure_draft_world` before data is saved.
3. The `editable` query parameter switches course and course run reads into draft/edit mode. Edit mode is also inferred for unsafe HTTP methods.
4. `editable` mode and Elasticsearch query parameter `q` are mutually exclusive for courses and course runs.
5. Non-staff, non-Publisher users are denied edit-mode access for courses and course runs.
6. Location restriction filters are applied to public course, course run, program, catalog, and learner pathway responses through `get_excluded_restriction_types`.
7. Destroy operations are not supported for courses or course runs and return HTTP 405.
8. Most list endpoints use proxied pagination compatible with page-number and limit-offset access patterns.
9. Search-backed endpoints use Elasticsearch query strings and facets. If `q` is supplied on product APIs, search takes precedence over other database filters.
10. Cache response compression is applied to major read-heavy resources such as courses, course runs, programs, people, organizations, collaborators, recommendations, and source metadata.

## Functional Areas

### 1. Course Management

Primary endpoint: `api/v1/courses`

Primary code anchors: `CourseViewSet`, `Course`, `CourseEditor`, `CourseEntitlement`, `CourseUrlSlug`, `CourseRunViewSet`

#### List Courses

Functional behavior:

- The system lists courses for the requesting site partner.
- The system supports filtering by course keys, UUIDs, course run statuses, editors, course type, and timestamp.
- The system supports Elasticsearch search through `q`; when supplied, search results are used instead of regular database filtering.
- The system supports draft/edit listing through `editable` and Publisher lookup through `pubq`.
- The system excludes hidden course runs unless `include_hidden_course_runs` is supplied.
- The system can restrict nested course runs to marketable, enrollable, published, or non-retired records based on query parameters.
- The system excludes retired course types on GET requests unless `include_retired_course_types` is supplied.

Acceptance criteria:

- Given a non-edit GET request, only courses for the request site partner are returned.
- Given `q`, the returned course set is based on course search results and excludes restricted course runs.
- Given `editable=true` and a user without staff or Publisher access, the request is denied.
- Given both `editable=true` and `q`, the request fails with the editable/query unsupported error.

#### Retrieve Course

Functional behavior:

- The system retrieves a course by course key or UUID.
- If `editable` is requested and a course has no entitlements, the system creates a missing entitlement as a one-time migration aid before serializing the response.

Acceptance criteria:

- Given a valid course key, the matching course is returned.
- Given a valid course UUID, the matching course is returned.
- Given an editable course with no entitlements, a missing entitlement is created and included in subsequent reads.

#### Create Course

Functional behavior:

- The system creates a draft course using title, number, org, course type, and product source.
- The system validates that organization, course type, and product source exist.
- The system derives the course key from organization key and course number.
- The system validates the course number.
- The system prevents creation when an official course already exists for the partner and key.
- The system optionally validates and assigns a manually supplied URL slug.
- The system associates the authoring organization.
- The system optionally associates collaborators.
- The system creates draft course entitlements for the course type entitlement modes and incoming prices.
- The system creates a `CourseEditor` record for the creating user.
- The system can atomically create an initial course run when `course_run` data is included.

Acceptance criteria:

- Given missing required creation fields, the API returns HTTP 400 with missing field details.
- Given an unknown organization, course type, or product source, the API returns HTTP 400.
- Given an existing official course with the same partner/key, creation fails.
- Given a duplicate manual URL slug for the partner, creation fails.
- Given valid course and initial run data, both course and run are created in one transaction.

#### Update Course

Functional behavior:

- The system always updates the draft version of a course.
- The system supports full and partial updates.
- The system decodes base64 course images and organization logo overrides.
- The system creates, changes, or removes video associations based on incoming video data.
- The system updates course entitlements when course type or prices are provided.
- The system allows entitlement type transition from Audit to Verified after review but blocks other reviewed entitlement type changes.
- The system validates URL slug format and uniqueness before assigning it.
- If `draft=false`, the system propagates updates to published active course runs and updates official versions.
- If configured, relevant course field changes fire the taxonomy course skill update signal.
- If reviewable course data changes, reviewed course runs are reverted to unpublished in both draft and official versions.

Acceptance criteria:

- Given a changed reviewable field on a reviewed course run's course, reviewed course runs return to unpublished state.
- Given `draft=false` on a published active course run, the official course run version is updated.
- Given a duplicate slug, the update is rejected.
- Given unsupported entitlement type switching after review, the update is rejected.

#### Delete Course

Functional behavior:

- The system rejects course deletion.

Acceptance criteria:

- Any DELETE request to a course resource returns HTTP 405.

### 2. Course Run Management

Primary endpoint: `api/v1/course_runs`

Primary code anchors: `CourseRunViewSet`, `CourseRun`, `CourseEditor`, `CourseRunType`, `StudioAPI`

#### List Course Runs

Functional behavior:

- The system lists course runs for the request site partner.
- The system supports filtering by keys, active state, marketable state, license, and ordering by start date.
- The system supports search through `q`; search takes precedence over regular filters.
- The system excludes restricted run types for public GET responses.
- The system excludes retired run types unless `include_retired_run_types` is supplied.
- The system can include deleted, unpublished, or retired associated programs through query parameters.

Acceptance criteria:

- Given `active=true`, only active course runs are returned.
- Given `marketable=true`, only marketable course runs are returned.
- Given `q`, Elasticsearch-backed results are returned for the request partner.
- Given edit mode with an unauthorized user, access is denied.

#### Create Course Run

Functional behavior:

- The system creates course runs in draft state.
- The system requires a course key.
- The system defaults `pacing_type` to `instructor_paced` when not supplied.
- The system ignores incoming `draft` values during creation.
- The system validates incoming data through the course run serializer.
- The system creates seats from run type and prices.
- The system creates or updates location restriction data when supplied.
- The system sets the course canonical course run if one is not already set.
- For reruns, the system copies selected metadata from the old run: language, effort, weeks to complete, staff, and transcript languages.
- The system pushes course run data to Studio when the partner has a Studio URL.
- After a direct create succeeds, the system updates the course run image in Studio.

Acceptance criteria:

- Given no course key, creation fails with validation error.
- Given a valid course and run payload, a draft run is created and seats are created or updated.
- Given a rerun key, supported run metadata is copied from the prior draft run.
- Given a partner without Studio URL, the run is created and Studio push is skipped.

#### Update Course Run

Functional behavior:

- The system always updates the draft version of a course run.
- The system validates that the selected course run type is allowed by the parent course type.
- The system removes incoming `status` from regular update payloads because status is model-managed.
- Staff users may update internal review fields while a course run is in review if the requested status transition is valid.
- Non-internal updates are blocked while a course run is in review.
- Internal review fields are rejected when the course run is not in review.
- If non-exempt fields change after review, the course run and official version return to unpublished.
- If `draft=false` and the run is unpublished or changed after review, the run enters legal review.
- If a published or reviewed run is saved, the official version is updated.
- The system updates seats, restrictions, Studio data, and Studio image data after successful update.

Acceptance criteria:

- Given a course run in review and a non-internal update, the request returns HTTP 403.
- Given an invalid course run type for the course type, the request returns HTTP 400.
- Given a staff internal review update with an allowed transition, the update succeeds.
- Given `draft=false` from unpublished state, the run moves into legal review.
- Given a non-exempt change after review, both draft and official statuses return to unpublished.

#### Course Run Membership Check

Functional behavior:

- The system accepts a query string and comma-separated course run IDs.
- The system searches course runs for the request partner and returns a boolean map of requested run keys to query membership.

Acceptance criteria:

- Given both `query` and `course_run_ids`, the response contains `course_runs` with boolean values.
- Given either parameter missing, the endpoint returns HTTP 400.

#### Delete Course Run

Functional behavior:

- The system rejects course run deletion.

Acceptance criteria:

- Any DELETE request to a course run resource returns HTTP 405.

### 3. Program And Degree Metadata

Primary endpoint: `api/v1/programs`

Primary code anchors: `ProgramViewSet`, `Program`, `Degree`, `Curriculum`, `ProgramSubscription`

Functional behavior:

- The system exposes programs as read-only API resources.
- The system lists programs for the request site partner.
- The system retrieves programs by UUID.
- The system supports Elasticsearch search through `q`.
- The system supports filtering by marketable state, status, type, types, UUIDs, and timestamp.
- The system can return only UUIDs through `uuids_only`.
- The system can return extended list payloads through `extended`.
- The system can include full course serialization, published-only course runs, marketable enrollable course runs with archived courses, and UTM-stripped marketing URLs through query parameters.
- Staff users can update a program card image with base64 image data.

Acceptance criteria:

- Given a list request without `extended`, minimal program payloads are returned.
- Given `extended=true`, extended minimal program payloads are returned.
- Given `uuids_only=true`, the response is a flat UUID list.
- Given a non-staff card image update request, access is denied.
- Given invalid image data for card image update, the endpoint returns HTTP 400.

### 4. Catalog Management

Primary endpoint: `api/v1/catalogs`

Primary code anchors: `CatalogViewSet`, `Catalog`, `CatalogSerializer`, `CourseRunCSVRenderer`

Functional behavior:

- The system creates, lists, retrieves, updates, partially updates, and deletes catalog records subject to DRY permissions.
- A catalog contains a course query, optional program query, name, archived-content flag, and viewer list.
- On create, the system accepts viewer usernames as either a list or comma-separated string.
- On create, the system creates missing user records for supplied viewer usernames before saving permissions.
- Catalog courses are resolved dynamically from Elasticsearch-backed catalog queries.
- The `courses` action returns catalog courses and nested course runs.
- If `include_archived` is false, `courses` returns available courses and active, enrollable, marketable course runs.
- If the requesting user has approved catalog API access, certain 2U course types are excluded from catalog course results.
- The `contains` action returns a boolean map for supplied course IDs and course run IDs.
- The `csv` action returns a streaming CSV of active, marketable course runs in the catalog.

Acceptance criteria:

- Given viewer usernames as a comma-separated string, catalog creation assigns those viewers.
- Given catalog `include_archived=false`, archived courses are excluded from catalog course results.
- Given course IDs or run IDs to `contains`, the response maps each supplied ID to true or false.
- Given `csv`, the response content type is `text/csv` and contains active marketable course runs.

### 5. Search And Discovery

Primary endpoints: `api/v1/search/*`, `api/v2/search/all`, `api/v1/search/typeahead`, `api/v1/search/person_typeahead`

Primary code anchors: `CourseSearchViewSet`, `CourseRunSearchViewSet`, `ProgramSearchViewSet`, `AggregateSearchViewSet`, `LimitedAggregateSearchView`, `PersonSearchViewSet`, search index documents

Functional behavior:

- The system provides search over course, course run, program, person, and aggregate product indexes.
- The system exposes facets for fields including content type, course type, product source, price, active state, language, level, mobile availability, organizations, pacing, seat types, subjects, status, transcript languages, and program type.
- The system supports availability facet queries for current, starting soon, upcoming, and archived products.
- Course run search excludes restricted run types for the requesting user.
- Aggregate search can include learner pathways when enabled by request parameters and configured feature behavior.
- Typeahead search returns completion-style results for product discovery.
- Person typeahead and person search expose indexed people profile data.

Acceptance criteria:

- Given valid authenticated search requests, search results are returned from Elasticsearch-backed documents.
- Given facet requests, configured facet buckets are returned.
- Given restricted course run types for the user context, those runs are excluded from course run search.
- Given typeahead input, the response returns matching course run and program suggestions.

### 6. People, Organizations, And Reference Metadata

Primary endpoints: `api/v1/people`, `api/v1/organizations`, `api/v1/subjects`, `api/v1/topics`, `api/v1/level_types`, `api/v1/program_types`, `api/v1/sources`, `api/v1/collaborators`

Primary code anchors: `PersonViewSet`, `OrganizationViewSet`, `SubjectViewSet`, `TopicViewSet`, `LevelTypeViewSet`, `ProgramTypeViewSet`, `SourceViewSet`, `CollaboratorViewSet`

Functional behavior:

- The system exposes people, organizations, collaborators, subjects, topics, level types, program types, and sources through API resources.
- People can be created, read, updated, and deleted through a model viewset.
- Organizations, subjects, topics, level types, program types, and sources are read-only API resources.
- Organization filters include tags, UUIDs, and timestamp.
- Subject, topic, level type, and program type filters can set response language via `language_code`.

Acceptance criteria:

- Given `language_code` on translated reference endpoints, translated fields are resolved for that language.
- Given organization `tags`, only organizations matching those tags are returned.
- Given people API write access, person profile metadata can be managed.

### 7. Publisher Support

Primary endpoints: `publisher/api/admins/organizations/*`

Primary code anchors: `OrganizationUserRoleView`, `OrganizationGroupUserView`, `OrganizationUserView`, publisher permissions

Functional behavior:

- The system exposes organization user roles to authenticated Publisher users.
- Organization lookup accepts either numeric organization ID or organization UUID.
- The system lists users in an organization extension group.
- Staff users can list users across all organization extensions for the current partner.
- Non-staff users can list users belonging to the requester's organization groups.
- Publisher APIs use dedicated Publisher user permission checks.

Acceptance criteria:

- Given an organization UUID, role and group-user endpoints resolve the organization extension by UUID.
- Given a staff requester, organization users are drawn from all organization extensions for the partner.
- Given a non-staff requester, organization users are limited to the requester's groups.

### 8. Learner Pathways

Primary endpoints: `api/v1/learner-pathway*`

Primary code anchors: `LearnerPathwayViewSet`, `LearnerPathwayStepViewSet`, `LearnerPathwayCourseViewSet`, `LearnerPathwayProgramViewSet`, `LearnerPathwayBlocViewSet`

Functional behavior:

- The system exposes learner pathways as read-only resources.
- Only active learner pathways are returned by the top-level pathway endpoint.
- Pathway serialization prefetches published, non-restricted course runs for linked courses and programs.
- The `snapshot` action returns the serialized state of one active pathway by UUID.
- The `uuids` action returns pathway UUIDs associated with supplied course keys, course run keys, or program UUIDs.
- Steps, course nodes, program nodes, and block nodes are exposed as read-only resources.

Acceptance criteria:

- Given inactive pathways, they are excluded from top-level pathway list results.
- Given a course key linked to a pathway course node, `uuids` returns that pathway UUID.
- Given a program UUID linked to a pathway program node, `uuids` returns that pathway UUID.
- Given pathway responses, linked course runs are published and exclude restricted types.

### 9. Recommendations And Taxonomy Support

Primary endpoint: `taxonomy/api/v1/course_recommendations/{course_key}/`

Primary code anchors: `CourseRecommendationsAPIView`, `CourseRecommendation`, taxonomy support serializers

Functional behavior:

- The system retrieves recommendations for a source course.
- Recommendations are ordered by skill intersection ratio, skill intersection length, subject intersection ratio, subject intersection length, and recommended course enrollment count.
- The system returns two recommendation groups: all recommendations and same-partner recommendations.
- Same-partner recommendations are filtered to recommended courses sharing authoring organizations with the source course.
- Recommendation responses are limited to the top 100 records per group.

Acceptance criteria:

- Given a valid source course key, the response includes `all_recommendations` and `same_partner_recommendations`.
- Given more than 100 recommendations, each group is capped at 100.
- Given same-partner filtering, only courses with overlapping authoring organizations appear in that group.

### 10. Tagging, Vertical Categorization, And Language Tags

Primary endpoints: `tagging/`, `language-tags/`, taxonomy-related management commands

Primary code anchors: `Vertical`, `SubVertical`, `CourseVertical`, `ietf_language_tags`, `update_course_verticals`

Functional behavior:

- The system stores vertical and sub-vertical taxonomy values.
- The system assigns one vertical/sub-vertical pair to a draft-disabled course through `CourseVertical`.
- Deactivating a vertical automatically deactivates related sub-verticals.
- Course vertical assignment validates that the selected sub-vertical belongs to the selected vertical.
- If only sub-vertical is supplied, the system derives the vertical from it.
- The system supports bulk vertical updates through CSV-backed configuration and management commands.

Acceptance criteria:

- Given a sub-vertical that belongs to a different vertical, validation fails.
- Given a vertical changed from active to inactive, related sub-verticals become inactive.
- Given only a valid sub-vertical, the course vertical assignment derives the parent vertical.

### 11. Affiliate And Catalog Extension Feeds

Primary endpoints: `api/v1/partners/affiliate_window/catalogs`, `api/v1/partners/affiliate_window/programs/catalogs`, `extensions/api/v1/search/all/facets`, `extensions/api/v1/program-fixture/`

Primary code anchors: `AffiliateWindowViewSet`, `ProgramsAffiliateWindowViewSet`, `DistinctCountsAggregateSearchViewSet`, `ProgramFixtureView`

Functional behavior:

- The system exposes affiliate window catalog data for courses and programs.
- The system exposes extension search facets with distinct count behavior.
- The system exposes a program fixture endpoint for downstream consumers.
- Extension URLs are only registered when the catalog extension app is installed.

Acceptance criteria:

- Given catalog extensions are installed, extension endpoints are routable.
- Given catalog extensions are not installed, extension endpoints are not registered.

### 12. Data Loading And Operational Commands

Primary code anchors: management commands under `course_discovery/apps/**/management/commands/`

Functional behavior:

- Operators can refresh course metadata from upstream services.
- Operators can import course metadata, degree data, geolocation data, geotargeting data, product value data, and GetSmarter data.
- Operators can bulk upload tags, update course verticals, and update course recommendations.
- Operators can archive courses, publish live course runs, unpublish inactive runs, backfill course types, backfill URL slugs, and repair/deduplicate metadata history.
- Operators can publish UUIDs to Drupal and update course runs in Salesforce.
- Operators can create, rebuild, populate, update, and remove unused Elasticsearch indexes.

Acceptance criteria:

- Given valid command configuration, import commands load or update corresponding metadata records.
- Given search index commands, indexes can be created, populated, rebuilt, updated, and cleaned up.
- Given archiving or publishing commands, product visibility state changes according to command-specific criteria.

## Endpoint Inventory

| Area | Endpoint pattern | Methods/behavior |
| --- | --- | --- |
| Courses | `api/v1/courses` | List, retrieve, create, update, partial update; delete rejected. |
| Course runs | `api/v1/course_runs` | List, retrieve, create, update; contains action; delete rejected. |
| Programs | `api/v1/programs` | Read-only list/retrieve; UUID list; staff card image update. |
| Catalogs | `api/v1/catalogs` | CRUD; courses action; contains action; CSV export. |
| Search | `api/v1/search/*`, `api/v2/search/all` | Product search, aggregate search, facets, typeahead, person search. |
| People and organizations | `api/v1/people`, `api/v1/organizations` | People CRUD; organization read-only. |
| Reference metadata | `api/v1/subjects`, `api/v1/topics`, `api/v1/level_types`, `api/v1/program_types`, `api/v1/sources` | Read-only reference metadata. |
| Publisher | `publisher/api/admins/organizations/*` | Organization roles and users for Publisher. |
| Learner pathways | `api/v1/learner-pathway*` | Read-only pathways, steps, nodes, snapshot, UUID association lookup. |
| Recommendations | `taxonomy/api/v1/course_recommendations/{course_key}/` | Course recommendation groups. |
| Extensions | `extensions/api/v1/*` | Distinct facets and program fixture when installed. |

## Non-Functional Behavior Observed In Code

- Authentication and object-level permissions protect sensitive metadata and edit workflows.
- Partner scoping is central: most product queries are filtered by `request.site.partner`.
- Draft/live separation protects publishing workflows and official metadata state.
- Elasticsearch supports high-volume discovery use cases and catalog membership checks.
- Prefetching and response caching are used to reduce query count and response size for read-heavy endpoints.
- Management commands provide repeatable operational pathways for imports, migrations, and search maintenance.

## Out Of Scope

- Studio-owned course content authoring.
- LMS-owned enrollment, learner progress, completion, and credential awarding.
- Ecommerce-owned payment processing, order fulfillment, and coupon redemption.
- Registrar-owned enrollment workflow, despite Discovery storing supporting identifiers and program metadata.
- Full search infrastructure hosting beyond index and document management commands.

## Source Evidence

- URL registrations: `course_discovery/urls.py`, `course_discovery/apps/api/v1/urls.py`, `course_discovery/apps/api/v2/urls.py`, `course_discovery/apps/learner_pathway/api/v1/urls.py`, `course_discovery/apps/taxonomy_support/api/v1/urls.py`, `course_discovery/apps/publisher/api/urls.py`.
- Primary API behavior: `course_discovery/apps/api/v1/views/courses.py`, `course_discovery/apps/api/v1/views/course_runs.py`, `course_discovery/apps/api/v1/views/programs.py`, `course_discovery/apps/api/v1/views/catalogs.py`, `course_discovery/apps/api/v1/views/search.py`.
- Domain models: `course_discovery/apps/course_metadata/models.py`, `course_discovery/apps/catalogs/models.py`, `course_discovery/apps/learner_pathway/models.py`, `course_discovery/apps/taxonomy_support/models.py`, `course_discovery/apps/tagging/models.py`.
- Filters and serializers: `course_discovery/apps/api/filters.py`, `course_discovery/apps/api/serializers.py`, `course_discovery/apps/learner_pathway/api/serializers.py`, `course_discovery/apps/taxonomy_support/api/v1/serializers.py`.
- Search documents: `course_discovery/apps/course_metadata/search_indexes/documents/` and `course_discovery/apps/course_metadata/search_indexes/serializers/`.
- Operations: `course_discovery/apps/**/management/commands/`.