# Lead Qualifier

Score and qualify new leads from Dynamics 365 CRM.

## When to use
- Lead-check cron job (every 2 hours, 8am-6pm weekdays)
- When a new vo_client record appears in D365
- When a contact submits a form (webhook from n8n)

## Process
1. Query D365 for new/updated vo_client records since last check
2. Score each lead based on: industry, company size (if available), engagement history
3. Assign tags: `new_lead`, `qualified`, `high_priority`
4. For qualified leads: trigger onboarding email sequence via n8n webhook
5. For high-priority leads: add to priority list for same-day follow-up

## Scoring Rules
- Has email + phone = +20 points
- Industry matches target verticals = +30 points
- Has active engagement = +25 points
- Status is "Active" = +15 points
- Score >= 60 = qualified
- Score >= 80 = high_priority

## API References
- **D365 new clients**: `GET {DYNAMICS365_URL}/api/data/v9.2/vo_clients?$filter=createdon gt {last_check}&$orderby=createdon desc`
- **n8n trigger onboarding**: `POST http://localhost:5678/webhook/onboarding-sequence` with `{ "contact_email": "...", "score": N }`
- **SendGrid add to list**: `PUT https://api.sendgrid.com/v3/marketing/contacts` with list_ids
