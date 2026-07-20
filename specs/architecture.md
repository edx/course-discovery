# Course Discovery Architecture

## Scope

This document describes the runtime architecture, major components, data stores, integrations, and key interaction flows for Course Discovery. It is derived from the Django URL configuration, DRF viewsets, domain models, search index code, Celery tasks, management commands, and existing repository documentation.

Course Discovery is the Open edX metadata aggregation and catalog service. It consolidates course, course run, program, catalog, organization, people, pathway, taxonomy, and commerce-facing metadata from multiple systems and exposes it through REST APIs, search indexes, admin tools, and operational jobs.

## Architectural Summary

Course Discovery is a Django service with DRF APIs at the edge, relational domain storage as the source of truth, Elasticsearch as the query/search projection, Celery for asynchronous jobs, and management commands for batch ingestion and operational maintenance.

The core architectural pattern is a metadata hub:

- Upstream systems provide course, run, program, ecommerce, analytics, LMS, and marketing metadata.
- Discovery normalizes the metadata into domain models under `course_metadata`, `catalogs`, `learner_pathway`, `taxonomy_support`, `tagging`, `publisher`, and `core` apps.
- Search index documents project selected data into Elasticsearch for search, facets, typeahead, and catalog membership queries.
- API consumers, Publisher, affiliate feeds, and downstream services read or mutate metadata through REST endpoints.
- Signals, tasks, commands, and integration utilities synchronize selected changes to Studio, Salesforce, Drupal, LMS, and search indexes.

## System Context

```mermaid
flowchart LR
    Publisher[Publisher MFE / Admin Users]
    ApiConsumer[API Consumers]
    CatalogConsumer[Catalog and Affiliate Consumers]
    Operator[Operators / Scheduled Jobs]

    Discovery[Course Discovery Service\nDjango + DRF]
    DB[(Relational DB\nCourse Metadata)]
    ES[(Elasticsearch\nSearch Indexes)]
    Cache[(Cache\nAPI timestamps, LMS lookups)]
    Celery[Celery Workers]

    Studio[Studio]
    LMS[LMS]
    Ecommerce[Ecommerce]
    Analytics[Analytics API]
    Drupal[Drupal Marketing]
    Salesforce[Salesforce]
    Email[Email Service]

    Publisher -->|REST writes/reads| Discovery
    ApiConsumer -->|REST reads/search| Discovery
    CatalogConsumer -->|Catalog, XML, fixture feeds| Discovery
    Operator -->|management commands| Discovery

    Discovery --> DB
    Discovery --> ES
    Discovery --> Cache
    Discovery --> Celery
    Celery --> DB
    Celery --> Email

    Discovery -->|course run create/update| Studio
    Discovery -->|catalog API access checks, blocks| LMS
    Discovery -->|comments, cases, product sync| Salesforce
    Discovery -->|publish UUIDs/nodes| Drupal
    Discovery -->|metadata ingestion| Ecommerce
    Discovery -->|metadata ingestion| Analytics
    Discovery -->|metadata ingestion| Studio
```

## Container View

```mermaid
flowchart TB
    subgraph Clients
        Browser[Browser / Publisher]
        Internal[Internal Services]
        External[External Catalog Consumers]
        Jobs[Schedulers / Operators]
    end

    subgraph Discovery[Course Discovery]
        URLConf[URL Routing\ncourse_discovery/urls.py]
        DRF[DRF Viewsets and APIViews]
        Admin[Django Admin]
        Domain[Domain Models\ncourse_metadata, catalogs, pathways]
        Serializers[Serializers / Filters]
        SearchDocs[Search Documents]
        Signals[Django Signals]
        Commands[Management Commands]
        Tasks[Celery Tasks]
        Integrations[Integration Utilities]
    end

    DB[(Relational DB)]
    ES[(Elasticsearch)]
    Cache[(Django Cache)]
    Broker[(Celery Broker)]
    ExternalSystems[Studio, LMS, Ecommerce, Analytics, Drupal, Salesforce]

    Browser --> URLConf
    Internal --> URLConf
    External --> URLConf
    URLConf --> DRF
    URLConf --> Admin
    DRF --> Serializers
    DRF --> Domain
    DRF --> SearchDocs
    DRF --> Integrations
    Admin --> Domain
    Domain --> DB
    Domain --> Signals
    Signals --> SearchDocs
    Signals --> Integrations
    SearchDocs --> ES
    DRF --> Cache
    Jobs --> Commands
    Commands --> Domain
    Commands --> SearchDocs
    Commands --> Integrations
    DRF --> Tasks
    Tasks --> Broker
    Broker --> Tasks
    Tasks --> Domain
    Tasks --> Integrations
    Integrations --> ExternalSystems
```

## Logical Components

| Component | Responsibility | Primary code anchors |
| --- | --- | --- |
| API edge | Routes HTTP traffic to REST APIs, admin, schema docs, Publisher APIs, taxonomy APIs, learner pathway APIs, and optional extensions. | `course_discovery/urls.py`, `course_discovery/apps/api/**/urls.py`, `course_discovery/apps/publisher/api/urls.py` |
| Core metadata domain | Owns canonical course, course run, program, degree, organization, people, pricing, restriction, and review metadata. | `course_discovery/apps/course_metadata/models.py` |
| Catalog domain | Defines dynamic catalogs using Elasticsearch query strings and viewer permissions. | `course_discovery/apps/catalogs/models.py`, `CatalogViewSet` |
| Search projection | Maintains Elasticsearch documents for courses, course runs, programs, people, and learner pathways. | `course_discovery/apps/course_metadata/search_indexes/` |
| Publisher support | Supports Publisher authoring, organization roles, comments, course editors, reviews, and draft/live workflows. | `course_discovery/apps/publisher/`, `course_discovery/apps/api/v1/views/courses.py`, `course_runs.py` |
| Taxonomy and pathways | Stores subjects, topics, verticals, recommendations, and structured learner pathways. | `taxonomy_support`, `tagging`, `learner_pathway` apps |
| Integration layer | Encapsulates calls to Studio, LMS, Salesforce, Drupal, and partner API endpoints. | `StudioAPI`, `LMSAPIClient`, `salesforce.py`, `publishers.py`, data loaders |
| Batch operations | Runs imports, refreshes, indexing, publishing, backfills, archiving, and data repair. | management commands under `course_discovery/apps/**/management/commands/` |
| Async operations | Processes bulk uploads, enterprise inclusion propagation, and deadline email jobs. | `course_discovery/apps/course_metadata/tasks.py`, `course_discovery/celery.py` |

## Data Architecture

```mermaid
erDiagram
    Partner ||--o{ Course : owns
    Partner ||--o{ Program : owns
    Partner ||--o{ Catalog : scopes
    Organization ||--o{ Course : authors
    Organization ||--o{ Program : sponsors
    Course ||--o{ CourseRun : has
    Course ||--o{ CourseEntitlement : has
    CourseRun ||--o{ Seat : has
    Course ||--o{ CourseEditor : editable_by
    Course ||--o{ CourseReview : reviewed_by
    Program }o--o{ Course : contains
    Program ||--o{ Curriculum : structures
    Curriculum ||--o{ CurriculumCourseMembership : includes
    Catalog ||..o{ Course : query_contains
    Catalog ||..o{ Program : program_query_contains
    LearnerPathway ||--o{ LearnerPathwayStep : contains
    LearnerPathwayStep ||--o{ LearnerPathwayCourse : course_node
    LearnerPathwayStep ||--o{ LearnerPathwayProgram : program_node
    Course ||--o{ CourseRecommendation : recommends
    Course ||--o{ CourseVertical : categorized_as
```

The relational database remains the canonical store. Elasticsearch is a derived projection that supports search, facets, typeahead, aggregate search, and catalog query membership. Cache entries are used for API response timestamping and selected external lookups, such as LMS catalog API access checks and block metadata.

## Runtime Flow Overview

```mermaid
flowchart LR
    Request[HTTP Request]
    Auth[Authentication and Permissions]
    Router[URL Router]
    View[DRF View/ViewSet]
    Filter[Filters / Query Params]
    Serializer[Serializer]
    Domain[Domain Models]
    Search[Elasticsearch]
    Integrations[External Integration]
    Response[HTTP Response]

    Request --> Router --> Auth --> View
    View --> Filter
    View --> Serializer
    View --> Domain
    View --> Search
    View --> Integrations
    Domain --> Serializer
    Search --> Serializer
    Serializer --> Response
```

## Key Design Decisions Observed

- Discovery separates reusable `Course` identity from scheduled `CourseRun` offerings.
- Course and course run write flows use draft records and publish/update official versions only at defined transition points.
- Public read flows are partner-scoped through `request.site.partner`.
- Public product responses exclude restricted run types unless explicitly included by query parameter.
- Catalogs are query-defined instead of static membership lists.
- Search and catalog membership depend on Elasticsearch projections, not only relational queries.
- Data loaders and search index commands are operationally important and should be treated as architecture entry points, not incidental scripts.
- Signals synchronize selected model changes to Salesforce and Elasticsearch, but with business gates such as draft and marketability checks.

## Sequence Diagrams

### 1. Authenticated API Read

```mermaid
sequenceDiagram
    actor Client
    participant URL as Django URL Router
    participant View as DRF ViewSet
    participant Perms as Auth/Permissions
    participant DB as Relational DB
    participant ES as Elasticsearch
    participant Ser as Serializer

    Client->>URL: GET /api/v1/courses/?q=python
    URL->>View: Route to CourseViewSet.list
    View->>Perms: Check authentication and object rules
    Perms-->>View: Allowed
    View->>ES: Course.search(q) when q is supplied
    ES-->>View: Matching course identifiers/documents
    View->>DB: Prefetch partner-scoped related data
    DB-->>View: Courses, runs, programs, orgs
    View->>Ser: Serialize response
    Ser-->>Client: 200 JSON list
```

### 2. Course Creation With Optional Initial Run

```mermaid
sequenceDiagram
    actor Publisher
    participant CourseAPI as CourseViewSet
    participant DB as Relational DB
    participant RunAPI as CourseRunViewSet
    participant Studio as Studio API
    participant SF as Salesforce Signals

    Publisher->>CourseAPI: POST /api/v1/courses/ with course and course_run
    CourseAPI->>CourseAPI: Validate org, type, source, course number, slug
    CourseAPI->>DB: Create draft Course
    CourseAPI->>DB: Add authoring org, collaborators, entitlements
    CourseAPI->>DB: Create CourseEditor for requester
    alt course_run included
        CourseAPI->>RunAPI: create_run_helper(course_run)
        RunAPI->>DB: Ensure draft course world
        RunAPI->>DB: Create draft CourseRun, seats, restrictions
        RunAPI->>Studio: POST course_runs or rerun endpoint
        Studio-->>RunAPI: Created/accepted
    end
    DB-->>SF: post_save/m2m signals may create Salesforce records
    CourseAPI-->>Publisher: 201 Course JSON
```

### 3. Course Run Update And Review Transition

```mermaid
sequenceDiagram
    actor Publisher
    participant RunAPI as CourseRunViewSet
    participant DB as Relational DB
    participant Studio as Studio API
    participant SF as Salesforce

    Publisher->>RunAPI: PATCH /api/v1/course_runs/{key}/
    RunAPI->>DB: Load and ensure draft CourseRun
    RunAPI->>RunAPI: Validate run type and review restrictions
    RunAPI->>RunAPI: Detect reviewable field changes
    alt run is in review and update is not internal
        RunAPI-->>Publisher: 403 Editing disabled
    else valid update
        RunAPI->>DB: Save draft run
        RunAPI->>DB: Update seats and restrictions
        RunAPI->>Studio: PATCH course_runs/{key}/
        RunAPI->>Studio: POST course_runs/{key}/images/
        alt published or reviewed
            RunAPI->>DB: Update or create official version
        end
        DB-->>SF: post_save signal creates/updates Course_Run__c
        RunAPI-->>Publisher: 200 CourseRun JSON
    end
```

### 4. Search Request

```mermaid
sequenceDiagram
    actor Consumer
    participant SearchAPI as AggregateSearchViewSet
    participant Backend as Search Filter Backends
    participant ES as Elasticsearch
    participant Ser as Search Serializer

    Consumer->>SearchAPI: GET /api/v1/search/all/?q=data&subjects=Business
    SearchAPI->>Backend: Apply multi-match, filters, ordering, facets
    Backend->>ES: Execute query against aggregate documents
    ES-->>Backend: Hits and facet data
    Backend-->>SearchAPI: Search result page
    SearchAPI->>Ser: Serialize documents/facets
    Ser-->>Consumer: 200 Search JSON
```

### 5. Catalog Membership Check

```mermaid
sequenceDiagram
    actor Consumer
    participant CatalogAPI as CatalogViewSet
    participant Catalog as Catalog Model
    participant ES as Elasticsearch

    Consumer->>CatalogAPI: GET /api/v1/catalogs/{id}/contains/?course_id=edX+DemoX
    CatalogAPI->>Catalog: Load catalog and query
    Catalog->>ES: Search catalog query for requested identifiers
    ES-->>Catalog: Matching course/run keys
    Catalog-->>CatalogAPI: Boolean membership map
    CatalogAPI-->>Consumer: 200 {courses: {...}}
```

### 6. Catalog Courses With LMS Access Check

```mermaid
sequenceDiagram
    actor Consumer
    participant CatalogAPI as CatalogViewSet
    participant LMS as LMSAPIClient
    participant Cache as Cache
    participant ES as Elasticsearch
    participant DB as Relational DB

    Consumer->>CatalogAPI: GET /api/v1/catalogs/{id}/courses/
    CatalogAPI->>LMS: Check catalog API access for requester
    LMS->>Cache: Read cached ApiAccessRequest
    alt cache miss
        LMS->>LMS: GET LMS api_access_request endpoint
        LMS->>Cache: Store result or sentinel
    end
    CatalogAPI->>ES: Resolve catalog query to courses
    CatalogAPI->>DB: Prefetch active/enrollable/marketable runs
    CatalogAPI-->>Consumer: 200 CatalogCourse list
```

### 7. Metadata Refresh Pipeline

```mermaid
sequenceDiagram
    actor Operator
    participant Command as refresh_course_metadata
    participant Partner as Partner Config
    participant Loaders as Data Loaders
    participant Upstream as Studio/LMS/Ecommerce/Analytics APIs
    participant DB as Relational DB
    participant Cache as API Cache Timestamp

    Operator->>Command: manage.py refresh_course_metadata
    Command->>Partner: Load partners or partner_code
    Command->>Command: Disconnect repeated cache invalidation signals
    loop pipeline stages
        Command->>Loaders: Execute loader for configured API URL
        Loaders->>Upstream: Fetch upstream metadata
        Upstream-->>Loaders: Course/run/program/commerce/analytics data
        Loaders->>DB: Upsert normalized metadata
    end
    Command->>DB: Delete orphan images/videos
    Command->>Cache: Set API timestamp / reconnect receiver
    Command-->>Operator: Success or command error
```

### 8. Bulk Operation Task Processing

```mermaid
sequenceDiagram
    actor Staff
    participant API as BulkOperationTaskViewSet
    participant DB as Relational DB
    participant Celery as Celery Worker
    participant Loader as CSV/Data Loader

    Staff->>API: POST /api/v1/bulk_operation_tasks/
    API->>DB: Create BulkOperationTask(uploaded_by=request.user)
    API-->>Staff: 201 Task JSON
    Staff->>Celery: process_bulk_operation(task_id) scheduled
    Celery->>DB: Load task and mark Processing
    Celery->>Loader: Select CourseLoader, CourseRunDataLoader, or CourseEditorsLoader
    Loader->>DB: Ingest CSV and apply changes
    Loader-->>Celery: Summary
    Celery->>DB: Store summary and mark Completed
    alt loader raises exception
        Celery->>DB: Mark Failed
    end
```

### 9. Elasticsearch Index Update

```mermaid
sequenceDiagram
    actor Operator
    participant Command as update_index/search_index
    participant Registry as Document Registry
    participant ES as Elasticsearch

    Operator->>Command: manage.py update_index
    Command->>Registry: Resolve registered documents
    Command->>ES: Create timestamped backing index
    Command->>ES: Populate documents
    Command->>ES: Sanity check record count and mapping
    alt sanity passes or disabled
        Command->>ES: Move alias to new index
        Command->>ES: Update max result window
        Command-->>Operator: Success
    else sanity fails
        Command-->>Operator: CommandError
    end
```

### 10. Real-Time Search Projection Update

```mermaid
sequenceDiagram
    participant DB as Relational DB
    participant Signal as RealTimeSignalProcessor
    participant Market as MarketableHandler
    participant Draft as DraftHandler
    participant Registry as ES Registry
    participant ES as Elasticsearch

    DB-->>Signal: post_save Course/CourseRun/etc.
    Signal->>Market: Check marketability for CourseRun
    alt non-marketable run
        Market-->>Signal: Skip indexing
    else marketable or other model
        Market->>Draft: Continue
        alt draft Course/CourseRun
            Draft-->>Signal: Skip indexing
        else indexable
            Draft->>Registry: update(instance), update_related(instance)
            Registry->>ES: Update documents
        end
    end
```

### 11. Salesforce Synchronization

```mermaid
sequenceDiagram
    participant DB as Relational DB
    participant Signal as course_metadata.signals
    participant SFUtil as SalesforceUtil
    participant SF as Salesforce

    DB-->>Signal: post_save Organization/Course/CourseRun
    Signal->>SFUtil: get_salesforce_util(partner)
    alt Salesforce configured
        SFUtil->>SF: Login or reuse session
        alt missing Salesforce ID
            SFUtil->>SF: Create Publisher_Organization__c / Course__c / Course_Run__c
            SF-->>SFUtil: Salesforce ID
            SFUtil->>DB: Store Salesforce ID
        else relevant fields changed
            SFUtil->>SF: Update matching Salesforce object
        end
    else not configured
        Signal-->>DB: No external sync
    end
```

### 12. Publisher Comment Flow

```mermaid
sequenceDiagram
    actor Publisher
    participant Comments as CommentViewSet
    participant DB as Relational DB
    participant SFUtil as SalesforceUtil
    participant SF as Salesforce
    participant Email as Email Sender

    Publisher->>Comments: POST /api/v1/comments/ course_uuid + comment
    Comments->>DB: Load draft course for partner
    Comments->>Comments: Check course edit permission
    Comments->>SFUtil: Get Salesforce utility
    SFUtil->>SF: Create comment on course case
    SF-->>SFUtil: Comment payload
    Comments->>Email: send_email_for_comment
    Comments-->>Publisher: 201 Comment JSON
```

## API Surface

Discovery exposes these REST endpoint groups:

- Core API: `/api/v1/*` and `/api/v2/*`.
- Learner pathway API: mounted under `/api/v1/learner-pathway*`.
- Publisher API: `/publisher/api/admins/organizations/*`.
- Taxonomy API: `/taxonomy/api/v1/course_recommendations/*`.
- Optional catalog extension API: `/extensions/api/v1/*` when the extension app is installed.
- Admin and schema UI: `/admin/` and `/api-docs/`.

See `specs/openapi.yaml` for the generated route inventory.

## Integration Architecture

| Integration | Direction | Mechanism | Usage |
| --- | --- | --- | --- |
| Studio | Outbound | OAuth API client via `StudioAPI` | Create/rerun/update course runs and course run images. |
| LMS | Outbound | `LMSAPIClient` | Catalog API access checks, course block data, translations/transcriptions. |
| Ecommerce | Inbound pull | Data loader APIs | Load commerce and seat metadata into Discovery. |
| Analytics | Inbound pull | Data loader APIs | Load analytics-enriched metadata. |
| Drupal | Outbound | Publisher utilities and management commands | Publish marketing nodes and UUIDs. |
| Salesforce | Outbound | Signals and `SalesforceUtil` | Sync publisher organizations, courses, course runs, cases, and comments. |
| Elasticsearch | Bidirectional projection/query | django-elasticsearch-dsl documents and DRF search viewsets | Search, facets, typeahead, catalog query membership. |
| Email | Outbound | Celery task and email helpers | Course deadline and comment notifications. |

## Deployment And Runtime Concerns

- The web process serves Django, DRF, Swagger UI, admin, static/media in development, and optional extension routes.
- Celery workers discover tasks from installed Django apps through `course_discovery/celery.py`.
- Operators rely on management commands for data refresh, search index maintenance, backfills, archiving, external publishing, and CSV imports.
- Partner configuration controls external API URLs such as LMS, Studio, Ecommerce, Programs, Courses, Analytics, Publisher, and Salesforce.
- Elasticsearch index updates use alias switching and sanity checks to reduce the risk of pointing search traffic at an incomplete index.
- API response cache invalidation is intentionally suppressed during metadata refresh and restored after the pipeline completes to avoid repeated churn.

## Quality Attributes

| Attribute | Architectural support |
| --- | --- |
| Availability | Read APIs can serve from relational data and Elasticsearch projections; index aliases support safer search rebuilds. |
| Performance | Search and catalog membership use Elasticsearch; serializers prefetch related data; cache stores API timestamps and LMS lookup results. |
| Consistency | Relational models are canonical; draft/live separation controls publishing; search is eventually consistent through signals and commands. |
| Operability | Management commands cover refresh, indexing, archiving, publishing, backfills, and data repair. |
| Security | Primary API surfaces require authentication; edit flows use staff, Publisher, object-level, and course-editor permissions. |
| Extensibility | Data loader framework, optional catalog extension app, DRF routers, and search document registrations allow additional surfaces. |

## Architectural Risks And Notes

- Search and catalog behavior depends on Elasticsearch index freshness. Draft and non-marketable product changes may intentionally not appear in indexes.
- Signals create side effects to Salesforce and search projections; failures can be operationally subtle if logs are not monitored.
- Some workflows use management commands rather than API endpoints, so production behavior depends on scheduler and operator discipline.
- OpenAPI route coverage is generated manually from code in `specs/openapi.yaml`; schema-level request/response shapes remain generic because many serializers are dynamic and context-sensitive.
- Course and course run write flows rely on draft/live semantics. Changes that bypass those flows can break Publisher review expectations.

## Source Evidence

- `docs/introduction.rst` describes Discovery as a data aggregator for Studio, LMS, Ecommerce, Drupal, search, catalogs, and programs.
- `course_discovery/urls.py` defines the service entry points, API docs, admin, publisher, taxonomy, learner pathway, tagging, and optional extension routes.
- `course_discovery/apps/course_metadata/models.py` contains the central metadata domain.
- `course_discovery/apps/api/v1/views/courses.py` and `course_runs.py` implement draft/live write flows and Studio pushes.
- `course_discovery/apps/catalogs/models.py` and `course_discovery/apps/api/v1/views/catalogs.py` implement query-defined catalogs.
- `course_discovery/apps/course_metadata/search_indexes/` and `course_discovery/apps/edx_elasticsearch_dsl_extensions/` implement search projections and index update behavior.
- `course_discovery/apps/course_metadata/tasks.py` defines Celery-backed bulk operations and email tasks.
- `course_discovery/apps/course_metadata/management/commands/refresh_course_metadata.py` defines the staged metadata refresh pipeline.
- `course_discovery/apps/course_metadata/signals.py` and `salesforce.py` implement Salesforce synchronization.
- `course_discovery/apps/api/utils.py` and `course_discovery/apps/core/api_client/lms.py` implement Studio and LMS integration helpers.