# Marketing Content Generation

Generate marketing content for VisionOne Performance consulting.

## When to use
- Daily content planning (7am cron job)
- Drafting social media posts for Buffer
- Writing newsletter sections
- Creating case study summaries from D365 engagement data

## Process
1. Query D365 for recent engagements, client wins, and active campaigns
2. Draft content appropriate to the channel (LinkedIn = professional, email = detailed)
3. Include relevant hashtags and CTAs for social posts
4. For newsletters, compile a digest of recent activity + upcoming events

## API References
- **D365 engagements**: `GET {DYNAMICS365_URL}/api/data/v9.2/vo_engagements?$top=10&$orderby=createdon desc`
- **Buffer schedule post**: `POST https://api.buffer.com` with GraphQL mutation `PostCreate`
- **SendGrid single send**: `POST https://api.sendgrid.com/v3/marketing/singlesends`

## Content Guidelines
- VisionOne is a consulting firm — tone is professional but approachable
- Never make unverified claims about results
- Always include a CTA (book a call, read more, contact us)
- Social posts: 150-280 characters for LinkedIn, include 3-5 hashtags
- Email subject lines: under 50 characters, action-oriented
