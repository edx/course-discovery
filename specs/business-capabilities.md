# Course Discovery Business Capabilities

## Scope

This document identifies the business capabilities supported by the Course Discovery service. The analysis is based on the repository structure, Django apps, model layer, API routes, search documents, management commands, and local documentation.

Course Discovery is a metadata aggregation and catalog service for Open edX. It consolidates learning product data from Studio, LMS, Ecommerce, Drupal, and related systems, then exposes that data through REST APIs, search indexes, admin tooling, and operational data loaders.

## Capability Map

| Capability | Business outcome | Primary code anchors |
| --- | --- | --- |
| Product metadata management | Maintain the canonical marketing and discovery metadata for learning products. | `course_discovery/apps/course_metadata/models.py`, `course_discovery/apps/api/v1/urls.py`, `course_discovery/apps/api/serializers.py` |
| Course and course run lifecycle management | Create, edit, publish, archive, restrict, price, and expose courses and their scheduled runs. | `Course`, `CourseRun`, `Seat`, `CourseEntitlement`, `RestrictedCourseRun`, `CourseReview`, `CourseEditor`, `BulkOperationTask` |
| Program and degree management | Model fixed collections of courses that lead to credentials, including degrees, curricula, subscriptions, costs, and deadlines. | `Program`, `Degree`, `Curriculum`, `CurriculumCourseMembership`, `CurriculumProgramMembership`, `ProgramSubscription`, `ProgramSubscriptionPrice` |
| Catalog segmentation and access control | Define dynamic product collections using search queries and grant scoped catalog visibility to users or external consumers. | `course_discovery/apps/catalogs/models.py`, `CatalogViewSet`, `CatalogQueryContainsViewSet` |
| Search and discovery | Index and query courses, course runs, programs, people, and learner pathways with facets, typeahead, and aggregate search. | `course_discovery/apps/course_metadata/search_indexes/`, `search/all`, `search/courses`, `search/course_runs`, `search/programs`, `search/people`, `search/typeahead` |
| Publisher workflow support | Support Publisher MFE and admin workflows for product authoring, editing, review, comments, staff roles, and organization-specific permissions. | `course_discovery/apps/publisher/`, `course_discovery/apps/publisher_comments/`, `CourseEditorViewSet`, `CourseReviewViewSet`, `CommentViewSet` |
| Organization and partner management | Represent institutions, partners, organization mappings, logos, users, and role assignments. | `Organization`, `OrganizationMapping`, `OrganizationUserRoleView`, `OrganizationGroupUserView`, `create_or_update_partner`, `create_sites_and_partners` |
| People and staff profile management | Manage instructor, staff, collaborator, position, bio, profile image, and social network metadata. | `Person`, `Position`, `Collaborator`, `PersonSocialNetwork`, `PersonViewSet`, `PersonSearchViewSet` |
| Taxonomy, topics, and categorization | Classify products by subject, topic, level, type, source, vertical, sub-vertical, language, skill, and product value. | `Subject`, `Topic`, `LevelType`, `ProgramType`, `CourseType`, `Source`, `Vertical`, `SubVertical`, `CourseVertical`, `ietf_language_tags` |
| Recommendations and pathways | Provide related course recommendations and structured learner pathways composed of courses, programs, and course blocks. | `CourseRecommendation`, `LearnerPathway`, `LearnerPathwayStep`, `LearnerPathwayCourse`, `LearnerPathwayProgram`, `LearnerPathwayBlock` |
| Pricing, seats, and commerce metadata | Store and expose seat types, modes, tracks, SKUs, entitlement data, fixed pricing, upgrade deadlines, and program subscription prices. | `SeatType`, `Mode`, `Track`, `Seat`, `CourseEntitlement`, `ProgramSubscriptionPrice`, `CurrencyView` |
| Availability, restriction, and marketability control | Determine where, when, and whether products appear in search, catalogs, organization pages, mobile, SEO, and geo-targeted experiences. | `CourseLocationRestriction`, `ProgramLocationRestriction`, `GeoLocation`, `AdditionalMetadata`, `ProductMeta`, `CourseUrlSlug`, `CourseUrlRedirect` |
| Data ingestion and synchronization | Load, refresh, migrate, and backfill product metadata from upstream systems and curated CSV sources. | `refresh_course_metadata`, `import_course_metadata`, `import_degree_data`, `ingest_getsmarter_data`, `bulk_upload_tags`, `import_geolocation_data`, `import_geotargeting_data` |
| Publishing and downstream integration | Publish metadata changes and identifiers to external systems such as Drupal, Salesforce, search indexes, and event consumers. | `publish_uuids_to_drupal`, `update_course_run_in_salesforce`, `publish_live_course_runs`, `update_index`, `remove_unused_indexes`, `search_index` |
| Affiliate and external catalog feeds | Provide catalog and program data formatted for partner, affiliate, and external marketplace consumption. | `AffiliateWindowViewSet`, `ProgramsAffiliateWindowViewSet`, `edx_catalog_extensions`, `ProgramFixtureView` |
| Administration, configuration, and operations | Configure singleton jobs, operational migrations, health checks, admin autocomplete, bulk tasks, and service-level support tools. | `ConfigurationModel` and `SingletonModel` classes in `course_metadata/models.py`, `health/`, admin URLs, management commands |

## Core Domain Objects

The central domain object is a learning product. In this service, learning products appear as:

- Courses, which group one or more course runs and carry shared marketing metadata.
- Course runs, which represent scheduled or externally sourced offerings with dates, pacing, seats, enrollability, pricing, and publication state.
- Programs, which group courses into credential-bearing collections.
- Degrees, which specialize programs with admissions, curricula, deadlines, costs, and degree-specific metadata.
- Learner pathways, which organize courses, programs, or course blocks into step-based learning journeys.
- Catalogs, which dynamically group courses and programs through Elasticsearch query definitions.

Supporting domain objects include organizations, people, subjects, topics, product types, verticals, language tags, geolocations, media assets, comments, reviews, and operational configuration.

## Capability Details

### Product Metadata Management

Course Discovery owns the consolidated marketing metadata used to present learning products across Open edX. It stores titles, descriptions, media, organizations, product sources, taxonomy, staff, outcomes, prerequisites, FAQs, endorsements, SEO fields, slugs, redirects, and additional metadata. This capability is centered in the `course_metadata` app and surfaced through v1 REST APIs and Django admin.

### Course And Course Run Lifecycle Management

The service manages both reusable course identity and concrete course run offerings. Business behavior includes draft/live models, publication status, archived state, hidden state, run dates, enrollability, effort, pacing, language, seats, entitlements, restrictions, reviews, editors, and bulk operations.

### Program And Degree Management

Programs are fixed product bundles whose metadata is managed here while credential awarding remains outside Discovery. Degree support extends programs with degree-specific metadata, curricula, course memberships, program memberships, deadlines, costs, rankings, specializations, and subscription pricing.

### Catalog Segmentation And Access Control

Catalogs are dynamic collections defined by Elasticsearch queries. They are used to provide scoped content views for external parties, ecommerce coupons, partner integrations, and catalog membership checks for courses and course runs. Catalogs also support explicit viewer permissions.

### Search And Discovery

Discovery builds Elasticsearch documents for courses, course runs, programs, people, and learner pathways. APIs expose aggregate search, limited search, typeahead, person typeahead, facets, and content-specific search endpoints. Search documents normalize product metadata into queryable fields such as organization, subject, seat type, skill, language, run dates, price, and availability.

### Publisher Workflow Support

Publisher-facing APIs allow users and internal teams to create and edit course, course run, and staff metadata. Related business behavior includes role-based access, course editors, course reviews, comments, organization admin/user lookups, and protection of sensitive metadata such as price and schedule dates.

### Organization And Partner Management

Discovery represents partner institutions and organizational metadata used in catalog display, search facets, authoring rights, logos, and external integrations. Management commands create or update partners and sites, while publisher APIs expose organization user and role relationships.

### People And Staff Profile Management

The service stores people metadata for instructors, course staff, collaborators, and subject matter profiles. This includes biographies, positions, areas of expertise, social profiles, images, and organization associations. People are exposed through CRUD APIs and indexed for search.

### Taxonomy, Topics, And Categorization

Discovery categorizes products by subjects, topics, product types, program types, course types, levels, sources, verticals, sub-verticals, skills, languages, and product values. This supports search filtering, recommendation logic, marketing pages, reporting, and enterprise/catalog segmentation.

### Recommendations And Pathways

Taxonomy support stores related course recommendations derived from skill and subject similarity. Learner pathway models provide structured learning journeys made of steps with minimum requirements and nodes linked to courses, programs, or blocks. These capabilities help learners discover next-best or structured learning opportunities.

### Pricing, Seats, And Commerce Metadata

Discovery stores the metadata needed by downstream commerce and marketing experiences, including seat types, modes, tracks, SKUs, entitlements, fixed USD pricing, paid seat enrollment windows, upgrade deadlines, and program subscription pricing. Currency data is exposed through an API endpoint.

### Availability, Restriction, And Marketability Control

The service controls visibility and availability for products across markets and experiences. It models location restrictions, geo data, active and hidden status, external-course organization-page display, search and SEO exclusion, mobile availability, slugs, redirects, and affiliate visibility.

### Data Ingestion And Synchronization

Management commands and Celery tasks load and refresh course metadata from upstream and curated sources. These include course metadata import, degree import, GetSmarter ingestion, geolocation/geotargeting import, product value import, image updates, slug migration, backfills, and deduplication jobs.

### Publishing And Downstream Integration

Discovery publishes metadata and identifiers to downstream systems and maintains search infrastructure. Commands and integrations update Elasticsearch indexes, remove unused indexes, publish UUIDs to Drupal, update Salesforce course run data, publish live course runs, and maintain event-facing metadata state.

### Affiliate And External Catalog Feeds

Partner and extension APIs produce catalog and program data for affiliate windows, external catalog consumers, and program fixture generation. This capability supports marketplace-style content distribution outside the core product API.

### Administration, Configuration, And Operations

The service includes extensive operational controls through Django admin, singleton/configuration models, management commands, health checks, autocomplete endpoints, and bulk operation task tracking. These capabilities let operators safely run migrations, imports, archive jobs, search index jobs, and metadata repair tasks.

## Capability Boundaries

Discovery stores and exposes metadata. It does not appear to own these adjacent business capabilities:

- Course content authoring, which lives in Studio or LMS content systems.
- Learner enrollment, progress, completion, and credential awarding.
- Payment processing and coupon redemption, although it supplies catalog, SKU, and pricing metadata.
- Full ecommerce product fulfillment.
- Registrar-specific enrollment workflows, although it stores identifiers and metadata used by registrar integrations.
- Search engine infrastructure operations beyond index creation, population, and cleanup commands.

## Suggested Bounded Contexts

The current codebase can be understood through these bounded contexts:

1. Product Metadata Context: courses, course runs, programs, degrees, people, organizations, media, and marketing attributes.
2. Catalog And Search Context: catalogs, query membership, Elasticsearch documents, facets, typeahead, and aggregate search.
3. Publisher Operations Context: authoring permissions, comments, reviews, editors, organization roles, and draft/live workflows.
4. Taxonomy And Recommendation Context: subjects, topics, skills, verticals, language tags, recommendations, and learner pathways.
5. Data Operations Context: data loaders, import commands, migrations, backfills, index jobs, and downstream synchronization.

## Source Evidence

- `docs/introduction.rst` describes Discovery as a data aggregator and metadata access service for courses, course runs, catalogs, programs, data loading, search, and API access.
- `course_discovery/urls.py` exposes admin, API, publisher, language tags, taxonomy, learner pathway, tagging, search docs, health, and extension routes.
- `course_discovery/apps/api/v1/urls.py` registers public API resources for catalogs, courses, course runs, programs, people, organizations, subjects, topics, search, comments, collaborators, course review, and bulk operations.
- `course_discovery/apps/course_metadata/models.py` contains the core metadata models and most operational configuration models.
- `course_discovery/apps/catalogs/models.py` defines catalogs as Elasticsearch-backed dynamic collections with viewer permissions.
- `course_discovery/apps/learner_pathway/models.py`, `taxonomy_support/models.py`, and `tagging/models.py` define pathway, recommendation, and vertical categorization models.
- `course_discovery/apps/course_metadata/search_indexes/` defines searchable documents for courses, course runs, programs, people, and learner pathways.
- Management commands under `course_discovery/apps/**/management/commands/` implement ingestion, publishing, archiving, backfill, tagging, recommendation, and search index operations.