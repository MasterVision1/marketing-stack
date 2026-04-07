# Email Drip Sequences

Manage automated email drip sequences via SendGrid + n8n.

## When to use
- When lead-qualifier identifies a new qualified lead
- Weekly newsletter compilation (Monday 9am)
- Onboarding sequence triggers
- Re-engagement campaigns

## Sequence Types

### 1. Onboarding (14-day)
- Day 0: Welcome email (template: `d-welcome`)
- Day 2: Value proposition (template: `d-value-prop`)
- Day 5: Case study (template: `d-case-study`)
- Day 9: Free consultation offer (template: `d-consult-offer`)
- Day 14: Final touchpoint (template: `d-final-touch`)

### 2. Weekly Newsletter
- Compile from: recent D365 engagements, published social posts, industry insights
- Send via: SendGrid single send to newsletter list
- Template: `d-weekly-newsletter`

### 3. Re-engagement (for cold leads)
- Trigger: No email opens in 30 days
- Day 0: "We miss you" (template: `d-reactivation-nudge`)
- Day 7: Best content roundup
- Day 14: Last chance unsubscribe warning

## API References
- **SendGrid send with template**: `POST https://api.sendgrid.com/v3/mail/send` with `template_id` in body
- **SendGrid single send (marketing)**: `POST https://api.sendgrid.com/v3/marketing/singlesends`
- **n8n trigger drip step**: `POST http://localhost:5678/webhook/drip-step` with `{ "email": "...", "sequence": "onboarding", "step": 1 }`
- **SendGrid contacts**: `PUT https://api.sendgrid.com/v3/marketing/contacts`

## Rules
- Never send more than 1 email per contact per day
- Always check suppression list before sending
- Include unsubscribe link (SendGrid handles this automatically with `{{{unsubscribe}}}`)
- Track all sends in D365 via n8n workflow
