# Campaign Monitor

Monitor active marketing campaigns and report on performance.

## When to use
- Daily review cron job (6pm weekdays)
- When checking campaign health during heartbeat
- Ad-hoc performance queries

## Process
1. Query SendGrid stats for active single sends and email campaigns
2. Query Buffer for recent post engagement stats
3. Query D365 for campaign records and conversion events
4. Compile performance summary: open rates, click rates, social engagement, new leads
5. Flag any campaigns with below-average performance for attention
6. Write summary to memory for next-day planning

## Thresholds
- Email open rate < 15% = flag for review
- Email click rate < 2% = flag for review
- Social post with 0 engagement after 24h = flag
- No new leads in 48h = flag

## API References
- **SendGrid stats**: `GET https://api.sendgrid.com/v3/stats?start_date={date}`
- **SendGrid single send stats**: `GET https://api.sendgrid.com/v3/marketing/stats/singlesends/{id}`
- **Buffer post stats**: GraphQL `query { account { channels { posts(first: 10) { edges { node { statistics { ... } } } } } } }`
- **D365 campaigns**: `GET {DYNAMICS365_URL}/api/data/v9.2/vo_marketingcampaigns?$filter=vo_status eq 100000000`
