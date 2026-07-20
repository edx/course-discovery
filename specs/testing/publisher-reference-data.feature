Feature: Publisher support and reference data APIs
  Course Discovery supports Publisher workflows, staff administration, people metadata, organizations, and translated reference data.

  Background:
    Given Course Discovery is configured with a partner site
    And I am an authenticated API user

  Scenario: List Publisher organization roles by UUID
    Given I have Publisher access
    And an organization exists with UUID "<organization-uuid>"
    When I request "GET /publisher/api/admins/organizations/<organization-uuid>/roles/"
    Then the response status should be 200
    And the response should contain roles for that organization

  Scenario: List Publisher organization group users by numeric ID
    Given I have Publisher access
    And an organization extension exists for organization ID "123"
    When I request "GET /publisher/api/admins/organizations/123/users/"
    Then the response status should be 200
    And the response should contain users in the organization extension group

  Scenario: Staff user lists all Publisher organization users for partner
    Given I am a staff user
    And organization extensions exist for the current partner
    When I request "GET /publisher/api/admins/organizations/users/"
    Then the response status should be 200
    And the response should contain users across all current partner organization extensions

  Scenario: Non-staff Publisher user lists users from own organization groups
    Given I have Publisher access
    And I am not a staff user
    When I request "GET /publisher/api/admins/organizations/users/"
    Then the response status should be 200
    And the response should contain only users from my organization groups

  Scenario: Deny Publisher organization users to users without Publisher permission
    Given I do not have Publisher access
    When I request "GET /publisher/api/admins/organizations/users/"
    Then the response status should be 403

  Scenario: Create a course editor from an authoring organization
    Given I can appoint course editors
    And a draft course exists with an authoring organization
    And the target user belongs to that authoring organization
    When I request "POST /api/v1/course_editors/" with the course UUID and target user ID
    Then the response status should be 201
    And the target user should be assigned as a course editor

  Scenario: Reject course editor assignment outside authoring organization
    Given I can appoint course editors
    And a draft course exists with an authoring organization
    And the target user does not belong to that authoring organization
    When I request "POST /api/v1/course_editors/" with the course UUID and target user ID
    Then the response status should be 403
    And the target user should not be assigned as a course editor

  Scenario: List Salesforce-backed comments for a course
    Given a draft course exists for the current partner
    And I am staff or belong to one of the course authoring organizations
    And Salesforce is configured for the partner
    When I request "GET /api/v1/comments/?course_uuid=<course-uuid>"
    Then the response status should be 200
    And the response should contain comments for the course

  Scenario: Reject comment listing without course UUID
    When I request "GET /api/v1/comments/"
    Then the response status should be 400
    And the response should explain that course_uuid is required

  Scenario: Create a Salesforce-backed comment for an editable course
    Given a draft course exists for the current partner
    And I can edit the course
    And Salesforce is configured for the partner
    When I request "POST /api/v1/comments/" with course_uuid and comment
    Then the response status should be 201
    And a Salesforce course case comment should be created
    And a comment notification email should be sent

  Scenario: Reject comment creation without required values
    When I request "POST /api/v1/comments/" without course_uuid or comment
    Then the response status should be 400
    And the response should identify the missing values

  Scenario: Manage person profile metadata
    Given I have access to the people API
    When I request "POST /api/v1/people/" with valid person profile data
    Then the response status should be 201
    And the person profile should be created

  Scenario: List organizations by tag
    Given organizations exist with tags
    When I request "GET /api/v1/organizations/?tags=partner"
    Then the response status should be 200
    And every returned organization should match the requested tag filter

  Scenario: Return translated subject fields for a requested language
    Given subject translations exist for language code "es"
    When I request "GET /api/v1/subjects/?language_code=es"
    Then the response status should be 200
    And translated subject fields should be resolved in Spanish when available

  Scenario: Return translated topic fields for a requested language
    Given topic translations exist for language code "fr"
    When I request "GET /api/v1/topics/?language_code=fr"
    Then the response status should be 200
    And translated topic fields should be resolved in French when available

  Scenario: Return translated program type fields for a requested language
    Given program type translations exist for language code "es"
    When I request "GET /api/v1/program_types/?language_code=es"
    Then the response status should be 200
    And translated program type fields should be resolved in Spanish when available
