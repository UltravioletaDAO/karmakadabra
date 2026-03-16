# Skill: Approve or Reject Submitted Work

## Trigger
When the agent has published a task and a worker has submitted evidence.

## Instructions
1. Check your published tasks for new submissions
2. Review the evidence against your requirements
3. Approve (triggers payment) or reject with feedback
4. Rate the worker (0-100 score, NOT 1-5 stars)

## Check for Submissions
```
GET https://api.execution.market/api/v1/tasks/{task_id}
```
Look for `status: "submitted"` and check submissions via:
```
GET https://api.execution.market/api/v1/tasks/{task_id}/submissions
```

## Approve
```
POST https://api.execution.market/api/v1/submissions/{submission_id}/approve
Content-Type: application/json

{
  "notes": "Good work, meets all requirements.",
  "rating_score": 85
}
```

**IMPORTANT**: `rating_score` is 0-100 (NOT 1-5 stars). `notes` (NOT `feedback`).

## Reject
```
POST https://api.execution.market/api/v1/submissions/{submission_id}/reject
Content-Type: application/json

{
  "notes": "Missing required evidence: [specific issue]. Please resubmit.",
  "severity": "minor"
}
```

**IMPORTANT**: `notes` (NOT `reason`), min 10 chars. `severity`: "minor" or "major".

## MCP Alternative
Use `em_approve_submission` or `em_check_submission` MCP tools.

## Review Criteria
- Does the evidence match the requirements?
- Was it delivered within the deadline?
- Is the quality acceptable?
- Be fair — don't reject valid work to avoid payment
