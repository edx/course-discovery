Feature: Catalog and search behavior
  Course Discovery exposes query-defined catalogs and Elasticsearch-backed product discovery.

  Background:
    Given Course Discovery is configured with a partner site
    And I am an authenticated API user

  Scenario: Create a catalog with comma-separated viewers
    Given users "alice" and "bob" do not need to exist before catalog creation
    When I request "POST /api/v1/catalogs/" with viewers "alice,bob"
    Then the response status should be 201
    And user records should exist for "alice" and "bob"
    And the catalog should grant viewer access to "alice" and "bob"

  Scenario: List catalogs visible to a user
    Given catalogs exist with viewer permissions
    When I request "GET /api/v1/catalogs/?username=alice"
    Then the response status should be 200
    And the response should include catalogs visible to "alice"

  Scenario: Retrieve catalog courses without archived content
    Given a catalog has include_archived set to false
    And the catalog query matches available and archived courses
    When I request "GET /api/v1/catalogs/<catalog-id>/courses/"
    Then the response status should be 200
    And archived courses should be excluded
    And nested course runs should be active, enrollable, and marketable

  Scenario: Exclude restricted run types from catalog course results
    Given a catalog query matches courses with restricted course runs
    When I request "GET /api/v1/catalogs/<catalog-id>/courses/"
    Then the response status should be 200
    And course runs with excluded restriction types should not be returned

  Scenario: Exclude selected 2U products for approved catalog API access users
    Given my LMS catalog API access request is approved
    And a catalog query matches executive education and bootcamp 2U courses
    When I request "GET /api/v1/catalogs/<catalog-id>/courses/"
    Then the response status should be 200
    And executive education 2U courses should be excluded
    And bootcamp 2U courses should be excluded

  Scenario: Check catalog membership for course IDs
    Given a catalog query contains course "edX+DemoX"
    When I request "GET /api/v1/catalogs/<catalog-id>/contains/?course_id=edX+DemoX,edX+OtherX"
    Then the response status should be 200
    And the response should map "edX+DemoX" to true
    And the response should map "edX+OtherX" to false

  Scenario: Check catalog membership for course run IDs
    Given a catalog query contains course run "course-v1:edX+DemoX+2026"
    When I request "GET /api/v1/catalogs/<catalog-id>/contains/?course_run_id=course-v1:edX+DemoX+2026"
    Then the response status should be 200
    And the response should map "course-v1:edX+DemoX+2026" to true

  Scenario: Export catalog course runs as CSV
    Given a catalog query matches active marketable course runs
    When I request "GET /api/v1/catalogs/<catalog-id>/csv/"
    Then the response status should be 200
    And the response content type should be "text/csv"
    And the CSV should contain active marketable course runs

  Scenario: Check query membership through catalog query endpoint
    Given Elasticsearch contains matching courses and course runs
    When I request "GET /api/v1/catalog/query_contains?query=org:edX&course_run_ids=course-v1:edX+DemoX+2026&course_uuids=<course-uuid>"
    Then the response status should be 200
    And the response should contain a boolean value for each requested identifier

  Scenario: Reject catalog query membership without identifiers
    When I request "GET /api/v1/catalog/query_contains?query=org:edX"
    Then the response status should be 400
    And the response should explain that query and identifier lists are required

  Scenario: Check course run query membership
    Given Elasticsearch contains course run "course-v1:edX+DemoX+2026" for the current partner
    When I request "GET /api/v1/course_runs/contains/?query=org:edX&course_run_ids=course-v1:edX+DemoX+2026"
    Then the response status should be 200
    And the response should map "course-v1:edX+DemoX+2026" to true

  Scenario: Reject course run query membership without query
    When I request "GET /api/v1/course_runs/contains/?course_run_ids=course-v1:edX+DemoX+2026"
    Then the response status should be 400

  Scenario: Search all aggregate products
    Given courses, course runs, programs, people, and pathways are indexed
    When I request "GET /api/v1/search/all/?q=data"
    Then the response status should be 200
    And the response should include Elasticsearch-backed search results

  Scenario: Return aggregate search facets
    Given aggregate search documents are indexed
    When I request "GET /api/v1/search/all/facets/"
    Then the response status should be 200
    And the response should include configured facet buckets

  Scenario: Search course runs and exclude restricted types
    Given restricted and unrestricted course run documents are indexed
    When I request "GET /api/v1/search/course_runs/?q=data"
    Then the response status should be 200
    And restricted course run types should be excluded for the requester

  Scenario: Return typeahead suggestions
    Given matching course run and program documents are indexed
    When I request "GET /api/v1/search/typeahead?q=data"
    Then the response status should be 200
    And the response should contain matching course run suggestions
    And the response should contain matching program suggestions

  Scenario: Return person typeahead suggestions
    Given matching people documents are indexed
    When I request "GET /api/v1/search/person_typeahead/?q=Smith"
    Then the response status should be 200
    And the response should contain matching people suggestions

  Scenario: Use v2 aggregate search with search_after pagination
    Given aggregate search documents are indexed
    When I request "GET /api/v2/search/all/?q=data&search_after=<sort-token>"
    Then the response status should be 200
    And the response should contain Elasticsearch-backed search results

  Scenario: Return distinct aggregate facets from catalog extensions
    Given the catalog extensions app is installed
    When I request "GET /extensions/api/v1/search/all/facets"
    Then the response status should be 200
    And the response should include distinct hit and facet counts
