Feature: Learner pathways, taxonomy, recommendations, and categorization
  Course Discovery exposes structured learner pathways, recommendation groups, and product categorization metadata.

  Background:
    Given Course Discovery is configured with a partner site
    And I am an authenticated API user

  Scenario: List only active learner pathways
    Given active and inactive learner pathways exist
    When I request "GET /api/v1/learner-pathway/"
    Then the response status should be 200
    And every returned learner pathway should be active
    And inactive learner pathways should be excluded

  Scenario: Retrieve a learner pathway snapshot
    Given an active learner pathway exists with UUID "<pathway-uuid>"
    When I request "GET /api/v1/learner-pathway/<pathway-uuid>/snapshot/"
    Then the response status should be 200
    And the response should contain the serialized learner pathway state

  Scenario: Find learner pathway UUIDs by course key
    Given a learner pathway contains a course node for course key "edX+DemoX"
    When I request "GET /api/v1/learner-pathway/uuids/?course_keys=edX+DemoX"
    Then the response status should be 200
    And the response should include the pathway UUID

  Scenario: Find learner pathway UUIDs by course run key
    Given a learner pathway contains a course with course run "course-v1:edX+DemoX+2026"
    When I request "GET /api/v1/learner-pathway/uuids/?course_keys=course-v1:edX+DemoX+2026"
    Then the response status should be 200
    And the response should include the pathway UUID

  Scenario: Find learner pathway UUIDs by program UUID
    Given a learner pathway contains a program node for program UUID "<program-uuid>"
    When I request "GET /api/v1/learner-pathway/uuids/?program_uuids=<program-uuid>"
    Then the response status should be 200
    And the response should include the pathway UUID

  Scenario: Exclude restricted course runs from pathway responses
    Given a learner pathway references courses with published course runs
    And some referenced course runs have excluded restriction types
    When I request "GET /api/v1/learner-pathway/<pathway-uuid>/"
    Then the response status should be 200
    And linked course runs should be published
    And linked course runs with excluded restriction types should not be returned

  Scenario: List learner pathway steps
    Given learner pathway steps exist
    When I request "GET /api/v1/learner-pathway-step/"
    Then the response status should be 200
    And the response should contain learner pathway steps

  Scenario: List learner pathway course nodes
    Given learner pathway course nodes exist
    When I request "GET /api/v1/learner-pathway-course/"
    Then the response status should be 200
    And the response should contain learner pathway course nodes

  Scenario: List learner pathway program nodes
    Given learner pathway program nodes exist
    When I request "GET /api/v1/learner-pathway-program/"
    Then the response status should be 200
    And the response should contain learner pathway program nodes

  Scenario: List learner pathway block nodes
    Given learner pathway block nodes exist
    When I request "GET /api/v1/learner-pathway-block/"
    Then the response status should be 200
    And the response should contain learner pathway block nodes

  Scenario: Return recommendation groups for a course
    Given a course exists with recommendation records
    When I request "GET /taxonomy/api/v1/course_recommendations/<course-key>/"
    Then the response status should be 200
    And the response should include "all_recommendations"
    And the response should include "same_partner_recommendations"

  Scenario: Limit recommendation groups to 100 records
    Given a course has more than 100 recommendation records
    When I request "GET /taxonomy/api/v1/course_recommendations/<course-key>/"
    Then the response status should be 200
    And "all_recommendations" should contain at most 100 records
    And "same_partner_recommendations" should contain at most 100 records

  Scenario: Filter same-partner recommendations by authoring organization
    Given a course has authoring organizations
    And recommendations exist for same-partner and different-partner courses
    When I request "GET /taxonomy/api/v1/course_recommendations/<course-key>/"
    Then the response status should be 200
    And same-partner recommendations should share an authoring organization with the source course

  Scenario: Reject invalid course vertical assignment
    Given a vertical "Business" exists
    And a sub-vertical "Data Science" belongs to a different vertical
    When I assign vertical "Business" and sub-vertical "Data Science" to a course
    Then validation should fail
    And the course vertical assignment should not be saved

  Scenario: Derive vertical from supplied sub-vertical
    Given sub-vertical "Finance" belongs to vertical "Business"
    When I assign only sub-vertical "Finance" to a course
    Then the course vertical assignment should be saved
    And the vertical should be set to "Business"

  Scenario: Deactivate sub-verticals when a vertical is deactivated
    Given vertical "Business" has active sub-verticals
    When I deactivate vertical "Business"
    Then all related sub-verticals should become inactive
