Feature: Product metadata API behavior
  Course Discovery manages canonical metadata for courses, course runs, programs, people, organizations, and supporting reference data.

  Background:
    Given Course Discovery is configured with a partner site
    And I am an authenticated API user

  Scenario: List partner-scoped courses
    Given published courses exist for the current partner
    And published courses exist for another partner
    When I request "GET /api/v1/courses/"
    Then the response status should be 200
    And the response should include only courses for the current partner

  Scenario: Search courses by query string
    Given courses are indexed in Elasticsearch
    When I request "GET /api/v1/courses/?q=python"
    Then the response status should be 200
    And the returned courses should come from course search results
    And restricted course runs should be excluded from nested course run data

  Scenario: Reject incompatible editable course search
    When I request "GET /api/v1/courses/?editable=true&q=python"
    Then the response status should be 400
    And the response should explain that editable mode and q search are unsupported together

  Scenario: Deny editable course access to unauthorized users
    Given I am not a staff user
    And I am not a Publisher user
    When I request "GET /api/v1/courses/?editable=true"
    Then the response status should be 403

  Scenario: Retrieve a course by key
    Given a course exists with key "edX+DemoX"
    When I request "GET /api/v1/courses/edX+DemoX/"
    Then the response status should be 200
    And the response should describe course "edX+DemoX"

  Scenario: Retrieve an editable course and create a missing entitlement
    Given a draft course exists without entitlements
    When I request "GET /api/v1/courses/<course-key>/?editable=true"
    Then the response status should be 200
    And a missing course entitlement should be created for the course
    And the response should include entitlement data

  Scenario: Create a draft course with required metadata
    Given an organization exists with key "edX"
    And a course type exists
    And a product source exists with slug "edx"
    When I request "POST /api/v1/courses/" with valid course creation data
    Then the response status should be 201
    And a draft course should be created
    And the course key should be derived from organization and course number
    And course entitlements should be created for the course type
    And the requester should be assigned as a course editor

  Scenario: Reject course creation when required values are missing
    When I request "POST /api/v1/courses/" without title, number, org, type, or product_source
    Then the response status should be 400
    And the response should identify the missing values

  Scenario: Reject course creation for an unknown organization
    Given no organization exists with key "unknown-org"
    When I request "POST /api/v1/courses/" with org "unknown-org"
    Then the response status should be 400
    And the response should identify the unknown organization

  Scenario: Reject duplicate official course creation
    Given an official course already exists for the current partner with key "edX+DemoX"
    When I request "POST /api/v1/courses/" for organization "edX" and number "DemoX"
    Then the response status should be 400
    And no duplicate course should be created

  Scenario: Reject duplicate manual course URL slug
    Given a course URL slug "demo-course" already exists for the current partner
    When I request "POST /api/v1/courses/" with url_slug "demo-course"
    Then the response status should be 400
    And the response should explain that the slug is already in use

  Scenario: Create a course and initial run atomically
    Given valid course creation data includes initial course_run data
    When I request "POST /api/v1/courses/"
    Then the response status should be 201
    And a draft course should be created
    And a draft course run should be created for the course
    And the course run should have seats created from the supplied prices

  Scenario: Update draft course metadata
    Given a draft course exists
    When I request "PATCH /api/v1/courses/<course-key>/" with changed course metadata
    Then the response status should be 200
    And the draft course should contain the updated metadata

  Scenario: Revert reviewed runs when reviewable course data changes
    Given a course has a reviewed course run
    When I update a reviewable field on the course
    Then the response status should be 200
    And the reviewed course run should be reverted to unpublished
    And the official version of the course run should be reverted to unpublished

  Scenario: Reject unsupported entitlement type switching after review
    Given a reviewed course has an entitlement type other than Audit
    When I request "PATCH /api/v1/courses/<course-key>/" with an unsupported entitlement type change
    Then the response status should be 400
    And the entitlement type should not be changed

  Scenario: Reject course deletion
    Given a course exists
    When I request "DELETE /api/v1/courses/<course-key>/"
    Then the response status should be 405

  Scenario: List course runs by active state
    Given active and inactive course runs exist for the current partner
    When I request "GET /api/v1/course_runs/?active=true"
    Then the response status should be 200
    And every returned course run should be active

  Scenario: List course runs by marketable state
    Given marketable and non-marketable course runs exist for the current partner
    When I request "GET /api/v1/course_runs/?marketable=true"
    Then the response status should be 200
    And every returned course run should be marketable

  Scenario: Search course runs by query string
    Given course runs are indexed in Elasticsearch
    When I request "GET /api/v1/course_runs/?q=data"
    Then the response status should be 200
    And the returned course runs should come from Elasticsearch-backed results
    And restricted course run types should be excluded

  Scenario: Create a draft course run
    Given a draft course exists
    When I request "POST /api/v1/course_runs/" with valid run data
    Then the response status should be 201
    And a draft course run should be created
    And the run pacing type should default to "instructor_paced" when omitted
    And seats should be created or updated from supplied prices

  Scenario: Reject course run creation without a course key
    When I request "POST /api/v1/course_runs/" without a course field
    Then the response status should be 400
    And the response should identify course as required

  Scenario: Create a rerun by copying selected metadata from an old run
    Given an old draft course run exists
    When I request "POST /api/v1/course_runs/" with a rerun key
    Then the response status should be 201
    And language, effort, weeks to complete, staff, and transcript languages should be copied from the old run

  Scenario: Deny non-internal updates while a course run is in review
    Given a course run is in review
    When I request "PATCH /api/v1/course_runs/<run-key>/" with non-internal review data
    Then the response status should be 403
    And the response should explain that editing is disabled

  Scenario: Allow staff internal review transition
    Given I am a staff user
    And a course run is in review
    When I request "PATCH /api/v1/course_runs/<run-key>/" with an allowed internal status transition
    Then the response status should be 200
    And the course run review fields should be updated

  Scenario: Reject invalid course run type for course type
    Given a course run belongs to a course type with limited run types
    When I request "PATCH /api/v1/course_runs/<run-key>/" with an unsupported course run type
    Then the response status should be 400
    And the course run type should not be changed

  Scenario: Move unpublished course run into legal review when submitted
    Given an unpublished draft course run exists
    When I request "PATCH /api/v1/course_runs/<run-key>/" with draft set to false
    Then the response status should be 200
    And the course run should enter legal review

  Scenario: Reject course run deletion
    Given a course run exists
    When I request "DELETE /api/v1/course_runs/<run-key>/"
    Then the response status should be 405

  Scenario: Retrieve minimal programs
    Given programs exist for the current partner
    When I request "GET /api/v1/programs/"
    Then the response status should be 200
    And the response should contain minimal program payloads

  Scenario: Retrieve extended programs
    Given programs exist for the current partner
    When I request "GET /api/v1/programs/?extended=true"
    Then the response status should be 200
    And the response should contain extended program list payloads

  Scenario: Retrieve program UUIDs only
    Given programs exist for the current partner
    When I request "GET /api/v1/programs/?uuids_only=true"
    Then the response status should be 200
    And the response should be a flat list of program UUIDs

  Scenario: Deny program card image update to non-staff users
    Given I am not a staff user
    When I request "POST /api/v1/programs/<program-uuid>/update_card_image/" with image data
    Then the response status should be 403

  Scenario: Reject invalid program card image data
    Given I am a staff user
    When I request "POST /api/v1/programs/<program-uuid>/update_card_image/" with invalid image data
    Then the response status should be 400
