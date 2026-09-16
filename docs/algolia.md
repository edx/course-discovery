# How course-discovery integrates with Algolia

## Overview

course-discovery uses the [`algoliasearch-django`](https://github.com/algolia/algoliasearch-django) library to push records to Algolia. Two files carry almost all of it:

- `course_discovery/apps/course_metadata/algolia_models.py`, the model layer
- `course_discovery/apps/course_metadata/index.py`, index configuration and registration

The rest is `algolia_forms.py` and the `SearchDefaultResultsConfiguration` admin, which manage promoted empty-query results, plus the `ALGOLIA` settings block in `settings/base.py`.

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

### Real-time (per-object): there isn't one

Editing a course or program does not update Algolia. Records change only on a full reindex. This surprises people, so it's worth knowing why.

`algoliasearch_django` installs `post_save` and `pre_delete` handlers for whatever model you pass to `register()`, which here is `AlgoliaProxyProduct`. Django sends those signals with the sender set to the class of the saved instance, so saving a `Course` or a `Program` never reaches the handler. Nothing constructs an `AlgoliaProxyProduct` and saves it either: it's built only inside `get_queryset`, and its `__init__` takes `(product, language, contentful_data)` rather than normal model kwargs.

`ProductMetaIndex.update_obj_index` exists and fans out to both language indexes, but nothing in this repo calls it.

### Full reindex

`BaseProductIndex.reindex_all()` triggers a complete rebuild of an index. It:

1. Calls `get_queryset()`, which builds the full list of `AlgoliaProxyProduct` wrappers from `AlgoliaProxyCourse.prefetch_queryset()` and `AlgoliaProxyProgram.prefetch_queryset()`, merging Contentful degree data into the program wrappers at this point. Courses get no Contentful enrichment.
2. Pushes all records to Algolia via the parent `AlgoliaIndex.reindex_all()`.
3. Restores query rules (empty-query promoted results from `SearchDefaultResultsConfiguration`) which a plain reindex would otherwise wipe.

This is invoked via the `algolia_reindex` management command provided by `algoliasearch_django`:

```bash
python manage.py algolia_reindex
```

This is executed via a cronjob, see our private configuration repo for each environment's schedule.

### Index settings sync

Index settings (`searchableAttributes`, `attributesForFaceting`, `customRanking`) are pushed to Algolia separately from record data, via:

```bash
python manage.py algolia_applysettings
```

This must be run any time the `settings` dict on `EnglishProductIndex` or `SpanishProductIndex` changes. It does not happen automatically on deploy.

`algoliasearch_django` also ships `algolia_clearindex`, which empties an index without repopulating it.

---

## What controls whether a record is indexed

Each proxy model implements a `should_index` property. `algoliasearch_django` checks it before indexing, via `should_index = 'should_index'` on `EnglishProductIndex` and `should_index = 'should_index_spanish'` on `SpanishProductIndex`.

A course is excluded when any of these hold:

- It has no owners with logo images (`get_owners` drops organizations without one)
- It has no advertised run, or that run is hidden
- Its partner is not `edX`
- It has no `active_url_slug` or no `availability_level`
- Its type is in `settings.RETIRED_COURSE_TYPES`
- Its product source is in `settings.ALGOLIA_INDEX_EXCLUDED_SOURCES`
- It's an ExecEd course with `ExternalProductStatus.Archived`

The Spanish index drops Boot Camps (`CourseType.BOOTCAMP_2U`) on top of everything above.

Drafts never reach `should_index`: `prefetch_queryset` uses `Course.objects`, which already excludes them.

`excluded_from_search` is a field on `Course` and `Program`, but nothing in the Algolia path reads it; it feeds the Elasticsearch program index. For degrees, a separate `excluded_from_search` value does reach Algolia, sourced from Contentful and nested under `contentful_fields`.

---

## Configuration points

| Setting | Where | Purpose |
|---|---|---|
| `ALGOLIA['APPLICATION_ID']` | `settings/base.py` | Algolia app credential |
| `ALGOLIA['API_KEY']` | `settings/base.py` | Algolia admin API key |
| `ALGOLIA['TAXONOMY_INDEX_NAME']` | `settings/base.py` | Separate skills/taxonomy index, read by taxonomy-connector. Nothing in this repo reads it |
| `ALGOLIA_INDEX_EXCLUDED_SOURCES` | `settings/base.py` | List of product source slugs to exclude from indexing entirely (e.g. Emeritus) |
| `RETIRED_COURSE_TYPES` | `settings/base.py` | Course type slugs that should never be indexed |
| `index_name` on `EnglishProductIndex` | `index.py` | Algolia index name — `"product"` |
| `index_name` on `SpanishProductIndex` | `index.py` | Algolia index name — `"spanish_product"` |
| `SearchDefaultResultsConfiguration` | Django admin / DB | Promoted courses and programs for empty-query rules, per index name |

## Adding a new Course field to the Algolia index

### 1. DB migration (if needed)
Add a `BooleanField` (or whatever type) to `Course` in `models.py` and generate a migration. Already done for `b2c_subscription_inclusion`.

### 2. `AlgoliaProxyCourse` in `algolia_models.py` (optional)
Add a `@property` *only* if you need to transform or rename the value. A plain DB field needs nothing here: `delegate_attributes` reads it off the course with `getattr(self.product, name, None)`.

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
