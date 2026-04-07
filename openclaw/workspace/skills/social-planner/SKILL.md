# Social Planner

Plan and schedule social media posts via Buffer GraphQL API.

## When to use
- Daily content planning cron job
- When marketing-content skill generates social post drafts
- Weekly batch scheduling

## Process
1. Check Buffer for connected channels: `query { account { channels { id name service } } }`
2. Review what's already queued: `query { account { channels { posts(first: 5, status: PENDING) { edges { node { text scheduledAt } } } } } }`
3. Identify gaps in the posting schedule
4. Create posts using the `PostCreate` mutation
5. Optimal posting times: LinkedIn (Tue-Thu 10am-12pm), general (weekdays 9am-11am, 1pm-3pm)

## Buffer GraphQL API
- **Endpoint**: `https://api.buffer.com`
- **Auth**: `Authorization: Bearer {BUFFER_ACCESS_TOKEN}`

### Key Mutations
```graphql
mutation PostCreate($input: PostCreateInput!) {
  postCreate(input: $input) {
    post { id text scheduledAt status }
  }
}
```

### Post Input Shape
```json
{
  "input": {
    "channelIds": ["..."],
    "text": "Post content here #hashtag",
    "scheduledAt": "2025-01-15T10:00:00Z"
  }
}
```

## Rules
- Never schedule more than 3 posts per day per channel
- Always include a CTA or question to drive engagement
- Space posts at least 3 hours apart
- No weekend posts unless specifically requested
