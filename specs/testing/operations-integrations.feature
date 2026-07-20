Feature: Operations, ingestion, indexing, and external integrations
  Course Discovery supports operational commands, asynchronous tasks, search projection updates, and outbound system synchronization.

  Background:
    Given Course Discovery is configured with a partner site

  Scenario: Refresh course metadata for all partners
    Given partner API URLs are configured for courses, ecommerce, programs, and analytics
    When an operator runs "manage.py refresh_course_metadata"
    Then each configured data loader stage should run
    And upstream metadata should be normalized into Discovery models
    And API cache invalidation should be restored after the pipeline completes

  Scenario: Refresh course metadata for one partner
    Given a partner exists with short code "edx"
    When an operator runs "manage.py refresh_course_metadata --partner_code edx"
    Then metadata should be refreshed only for partner "edx"

  Scenario: Reject refresh for an invalid data loader stage
    When an operator runs "manage.py refresh_course_metadata --data_loader_stage 99"
    Then the command should fail
    And the error should explain the valid stage range

  Scenario: Process a bulk course creation task successfully
    Given a pending BulkOperationTask exists for course creation
    When the Celery task "process_bulk_operation" runs for that task
    Then the task status should become "Processing"
    And the CourseLoader should ingest the CSV file
    And the task status should become "Completed"
    And the task summary should be stored

  Scenario: Mark a bulk operation task failed when ingestion raises an exception
    Given a pending BulkOperationTask exists
    And its selected loader raises an exception
    When the Celery task "process_bulk_operation" runs for that task
    Then the task status should become "Failed"
    And the exception should be raised for task retry or monitoring

  Scenario: Propagate organization enterprise inclusion to child products
    Given an organization is saved with enterprise subscription inclusion set to false
    When the Celery task "update_org_program_and_courses_ent_sub_inclusion" runs
    Then eligible child courses should inherit the organization inclusion value
    And eligible child programs should be saved to refresh derived state

  Scenario: Send a course deadline email
    Given a course and course run exist
    And recipients are configured
    When the Celery task "process_send_course_deadline_email" runs
    Then a course deadline email should be sent to the recipients

  Scenario: Fail course deadline email task when product records are missing
    Given the referenced course or course run does not exist
    When the Celery task "process_send_course_deadline_email" runs
    Then the task should raise an object-not-found error

  Scenario: Rebuild Elasticsearch indexes with sanity checks
    Given registered Elasticsearch documents exist
    When an operator runs "manage.py update_index"
    Then a new timestamped index should be populated
    And record count and mapping sanity checks should run
    And the alias should move to the new index when sanity checks pass

  Scenario: Reject Elasticsearch alias switch when sanity checks fail
    Given a new Elasticsearch index has an unsafe record count change
    When an operator runs "manage.py update_index"
    Then the command should fail
    And the alias should not move to the unsafe index

  Scenario: Skip real-time indexing for draft courses and course runs
    Given a draft course or course run is saved
    When the real-time search signal processor handles the save
    Then the document should not be indexed in Elasticsearch

  Scenario: Skip real-time indexing for non-marketable course runs
    Given a non-marketable course run is saved
    When the real-time search signal processor handles the save
    Then the course run document should not be indexed in Elasticsearch

  Scenario: Update Elasticsearch for indexable models
    Given an indexable published and marketable product is saved
    When the real-time search signal processor handles the save
    Then the Elasticsearch registry should update the product document
    And related documents should be updated

  Scenario: Push a new course run to Studio
    Given a partner has a Studio URL
    And a course run is created through the API
    When the course run creation completes
    Then Discovery should call the Studio course_runs endpoint
    And the Studio payload should include title, org, number, run, team, pacing, and schedule data

  Scenario: Skip Studio push when partner has no Studio URL
    Given a partner has no Studio URL
    When a course run is created through the API
    Then Discovery should not call Studio
    And the course run should still be saved in Discovery

  Scenario: Update a course run image in Studio
    Given a course run exists for a course with an image
    And the partner has a Studio URL
    When the course run image update hook runs
    Then Discovery should post the card image to Studio

  Scenario: Cache LMS catalog API access responses
    Given a user requests catalog courses
    And the LMS API returns an approved catalog API access request
    When Discovery checks catalog API access
    Then the result should be cached for subsequent checks

  Scenario: Store sentinel when LMS catalog API access returns no result
    Given a user requests catalog courses
    And the LMS API returns no catalog API access requests
    When Discovery checks catalog API access
    Then a sentinel no-result value should be cached
    And subsequent checks should not call LMS until the cache expires

  Scenario: Create Salesforce records for newly saved products
    Given Salesforce is configured for the partner
    And an organization, course, or course run is saved without a Salesforce ID
    When the corresponding post-save signal runs
    Then Discovery should create the matching Salesforce object
    And the Salesforce ID should be stored on the Discovery record

  Scenario: Update Salesforce records when relevant fields change
    Given Salesforce is configured for the partner
    And a course run with a Salesforce ID changes a Salesforce-relevant field
    When the course run post-save signal runs
    Then Discovery should update the matching Salesforce Course_Run__c record

  Scenario: Skip Salesforce sync when Salesforce is not configured
    Given Salesforce is not configured for the partner
    When an organization, course, or course run is saved
    Then Discovery should not call Salesforce

  Scenario: Return an affiliate course catalog feed
    Given a catalog contains active marketable verified or professional seats
    When I request "GET /api/v1/partners/affiliate_window/catalogs/<catalog-id>/"
    Then the response status should be 200
    And the response content type should be XML
    And the response should contain eligible seat data

  Scenario: Return an affiliate program catalog feed
    Given a catalog contains marketable programs
    When I request "GET /api/v1/partners/affiliate_window/programs/catalogs/<catalog-id>/"
    Then the response status should be 200
    And the response content type should be XML
    And excluded program types should not appear in the feed

  Scenario: Return a program fixture for staff users
    Given the catalog extensions app is installed
    And I am a staff user
    When I request "GET /extensions/api/v1/program-fixture/?programs=<program-uuid>"
    Then the response status should be 200
    And the response should contain a Django fixture for the requested program

  Scenario: Reject program fixture request with too many programs
    Given the catalog extensions app is installed
    And I am a staff user
    When I request "GET /extensions/api/v1/program-fixture/?programs=<more-than-ten-program-uuids>"
    Then the response status should be 422
    And the response should explain that only ten programs are allowed
