# How course-discovery integrates with Algolia

## Overview

course-discovery uses the [`algoliasearch-django`](https://github.com/algolia/algoliasearch-django) library, which hooks into Django's model lifecycle to keep Algolia records in sync. The integration is entirely contained in two files:

- `course_discovery/apps/course_metadata/algolia_models.py` — model layer
- `course_discovery/apps/course_metadata/index.py` — index configuration

---

## Model and abstraction diagram

```
  DB models (Course, Program)
        |           |
        v           v
AlgoliaProxyCourse  AlgoliaProxyProgram     <- Django proxy models
(proxy of Course)   (proxy of Program)         with Algolia-specific
        |           |                           @property fields
        +-----------+
              |
              v
     AlgoliaProxyProduct                    <- Wrapper model
     (proxy of Program,                        registered with Algolia.
      @delegate_attributes)                    Holds a .product reference
              |                                to either proxy above and
              | .product = AlgoliaProxyCourse  delegates attribute access
              |          | AlgoliaProxyProgram through to it.
              |
    +---------+---------+
    |                   |
    v                   v
EnglishProductIndex  SpanishProductIndex    <- AlgoliaIndex subclasses
(index: "product")   (index: "spanish_product")
    |                   |
    +-------------------+
              |
              v
       ProductMetaIndex                     <- Fan-out wrapper registered
                                               with algoliasearch_django.
                                               Delegates all index ops to
                                               both language indexes.

register(AlgoliaProxyProduct, index_cls=ProductMetaIndex)
```

The reason for `AlgoliaProxyProduct` being a proxy of `Program` (rather than something neutral) is purely to trick `algoliasearch_django` into treating courses and programs as a single model type. No `Program` fields are actually used on it — all field access is delegated through `delegate_attributes` to `.product`.

---

## What triggers index updates

### Real-time (per-object)

`algoliasearch_django` installs a `post_save` signal handler on any model registered with `register()`. Because `AlgoliaProxyProduct` is what's registered, saves to that proxy would normally trigger it — but in practice, courses and programs are saved as `Course` / `Program` instances, not as `AlgoliaProxyProduct`.

The real-time path works because `algoliasearch_django` also hooks `update_obj_index` via `ProductMetaIndex`, which is called explicitly in code paths that need to push a single record update. When a course or program is modified and needs to reflect in Algolia immediately, `ProductMetaIndex.update_obj_index(instance)` fans out to both `EnglishProductIndex` and `SpanishProductIndex`.

### Full reindex

`BaseProductIndex.reindex_all()` triggers a complete rebuild of an index. It:

1. Calls `get_queryset()`, which builds the full list of `AlgoliaProxyProduct` wrappers from `AlgoliaProxyCourse.prefetch_queryset()` and `AlgoliaProxyProgram.prefetch_queryset()` — also merging in Contentful data for bootcamps and degrees at this point.
2. Pushes all records to Algolia via the parent `AlgoliaIndex.reindex_all()`.
3. Restores query rules (empty-query promoted results from `SearchDefaultResultsConfiguration`) which a plain reindex would otherwise wipe.

This is invoked via the `algolia_reindex` management command provided by `algoliasearch_django`:

```bash
python manage.py algolia_reindex
```

### Index settings sync

Index settings (`searchableAttributes`, `attributesForFaceting`, `customRanking`) are pushed to Algolia separately from record data, via:

```bash
python manage.py algolia_applysettings
```

This must be run any time the `settings` dict on `EnglishProductIndex` or `SpanishProductIndex` changes — it does not happen automatically on deploy.

---

## What controls whether a record is indexed

Each proxy model implements a `should_index` property (and `should_index_spanish` for the Spanish index). `algoliasearch_django` checks these before indexing. Key exclusion conditions:

- Course is a draft
- Course has no owners with logo images
- Course has no active, non-hidden advertised run
- Course type is in `settings.RETIRED_COURSE_TYPES`
- Course's product source is in `settings.ALGOLIA_INDEX_EXCLUDED_SOURCES`
- ExecEd course has `ExternalProductStatus.Archived`
- `excluded_from_search = True` on the course or program

---

## Configuration points

| Setting | Where | Purpose |
|---|---|---|
| `ALGOLIA['APPLICATION_ID']` | `settings/base.py` | Algolia app credential |
| `ALGOLIA['API_KEY']` | `settings/base.py` | Algolia admin API key |
| `ALGOLIA['TAXONOMY_INDEX_NAME']` | `settings/base.py` | Separate skills/taxonomy index (not the product index) |
| `ALGOLIA_INDEX_EXCLUDED_SOURCES` | `settings/base.py` | List of product source slugs to exclude from indexing entirely (e.g. Emeritus) |
| `RETIRED_COURSE_TYPES` | `settings/base.py` | Course type slugs that should never be indexed |
| `index_name` on `EnglishProductIndex` | `index.py` | Algolia index name — `"product"` |
| `index_name` on `SpanishProductIndex` | `index.py` | Algolia index name — `"spanish_product"` |
| `SearchDefaultResultsConfiguration` | Django admin / DB | Promoted courses and programs for empty-query rules, per index name |
| `excluded_from_search` | Course/Program model field | Per-record toggle, manageable in Django admin |

## Adding a new Course field to the Algolia index

### 1. DB migration (if needed)
Add a `BooleanField` (or whatever type) to `Course` in `models.py` and generate a migration. Already done for `b2c_subscription_inclusion`.

### 2. `AlgoliaProxyCourse` in `algolia_models.py` (optional)
Add a `@property` *only* if you need to transform or rename the value. For a simple DB field where the name doesn't conflict with anything on the parent `Course`/`Program` model, you can skip this — Django's MRO will find it directly. If the name *does* exist on `Program` (the base of `AlgoliaProxyProduct`), you need the proxy property to override it.

### 3. `AlgoliaProxyProgram` in `algolia_models.py`
Add an explicit `@property` returning a sensible default (`False`, `None`, `[]`, etc.) so programs don't accidentally inherit a `Program` model attribute that happens to have the same name.

### 4. `delegate_attributes` decorator in `algolia_models.py`
Add the field name to the appropriate list — `facet_fields`, `result_fields`, `search_fields`, or `ranking_fields`. This is what makes `AlgoliaProxyProduct` proxy the attribute through to the underlying course or program object.

### 5. `EnglishProductIndex` and `SpanishProductIndex` in `index.py`
Add the field to the corresponding tuple(s) — `facet_fields`, `result_fields`, etc. These control what actually gets serialized and sent to Algolia per record.

### 6. `settings` dict in both index classes
Depending on how you want Algolia to treat the field:
- `searchableAttributes` — if you want full-text search on it
- `attributesForFaceting` — if you want to filter/facet on it (use `filterOnly(field)` if you don't need facet counts)
- `customRanking` — if you want it to influence ranking order
