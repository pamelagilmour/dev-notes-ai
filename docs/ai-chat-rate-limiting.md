# AI Chat Rate Limiting Configuration

## Overview
AI chat is now enabled with comprehensive rate limiting to prevent abuse and control costs.

## Rate Limits

### Two-Tier Protection

| Limit Type | Requests | Window | Purpose |
|-----------|----------|--------|---------|
| **Daily** | 7 requests | 24 hours | Cost control |
| **Hourly** | 10 requests | 1 hour | Prevent rapid-fire abuse |

**Both limits must pass** for a chat request to succeed.

## Features

### 1. Environment Control
```bash
# Railway/Production
ENABLE_AI_CHAT=true   # Enable AI chat
ENABLE_AI_CHAT=false  # Disable AI chat
```

### 2. Rate Limit Tracking
- Per-user daily tracking (not IP-based)
- Per-user hourly tracking
- Redis-backed counters with auto-expiry
- Helpful error messages with time until reset

### 3. Audit Logging
Every AI chat request is logged with:
- User ID and IP address
- Message length
- Remaining requests (daily + hourly)
- Timestamp and user agent
- Success/failure status

### 4. Error Handling
- 429 Too Many Requests with retry time
- Clear error messages
- Audit log of violations
- Graceful degradation

## API Endpoints

### Check AI Limits
```bash
GET /api/ai-limit/status
Authorization: Bearer <token>
```

**Response:**
```json
{
  "user_id": 123,
  "daily": {
    "used": 3,
    "remaining": 4,
    "limit": 7,
    "resets_in_seconds": 43200,
    "resets_in_hours": 12
  },
  "hourly": {
    "used": 3,
    "remaining": 7,
    "limit": 10,
    "resets_in_seconds": 1800,
    "resets_in_minutes": 30
  },
  "can_chat": true
}
```

### Send Chat Message
```bash
POST /api/chat
Authorization: Bearer <token>
Content-Type: application/json

{
  "message": "What do I know about React?"
}
```

**Success Response:**
```json
{
  "response": "Based on your knowledge base, you have notes about React hooks..."
}
```

**Rate Limit Response (429):**
```json
{
  "detail": "AI chat rate limit exceeded (10 per hour). Try again in 25 minutes."
}
```

**Headers:**
```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1234567890
Retry-After: 1500
```

## Frontend Integration

### Check Before Sending
```javascript
// Check if user can chat
const response = await fetch('/api/ai-limit/status', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const limits = await response.json();

if (limits.can_chat) {
  // Show chat input
} else {
  // Show "limit reached" message with reset time
}
```

### Handle Rate Limit Errors
```javascript
try {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ message: userMessage })
  });

  if (response.status === 429) {
    const error = await response.json();
    // Show: "Rate limit exceeded. Try again in X minutes."
    const retryAfter = response.headers.get('Retry-After');
    // Update UI with countdown
  }
} catch (error) {
  // Handle network errors
}
```

### Display Remaining Requests
```javascript
// Fetch and display after each chat
const limits = await fetch('/api/ai-limit/status');
const data = await limits.json();

// Show badge: "15/20 requests remaining today"
console.log(`${data.daily.remaining}/${data.daily.limit} remaining`);
```

## Security Benefits

### Cost Control
- ✅ Maximum 7 AI requests per user per day
- ✅ Maximum cost per user: ~$0.14/day (7 requests × ~$0.02)
- ✅ Monthly cap: ~$4.20/user
- ✅ For 100 users: ~$420/month max

### Abuse Prevention
- ✅ Hourly limit prevents rapid-fire attacks
- ✅ Per-user tracking (not IP-based)
- ✅ Audit trail of all AI requests
- ✅ Can identify heavy users
- ✅ Can adjust limits per user if needed

### Monitoring
- ✅ Track AI usage per user
- ✅ See most active users
- ✅ Alert on unusual patterns
- ✅ Compliance audit trail

## Monitoring Queries

### Most Active AI Users (Last 24h)
```sql
SELECT 
  user_id, 
  user_email, 
  COUNT(*) as ai_requests
FROM audit_logs
WHERE event_type = 'ai_chat_request'
AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY user_id, user_email
ORDER BY ai_requests DESC
LIMIT 10;
```

### AI Usage by Hour
```sql
SELECT 
  DATE_TRUNC('hour', timestamp) as hour,
  COUNT(*) as requests
FROM audit_logs
WHERE event_type = 'ai_chat_request'
AND timestamp > NOW() - INTERVAL '7 days'
GROUP BY hour
ORDER BY hour DESC;
```

### Rate Limit Violations
```sql
SELECT 
  user_id,
  user_email,
  ip_address,
  COUNT(*) as violations
FROM audit_logs
WHERE event_type = 'rate_limit_exceeded'
AND details->>'endpoint' = '/api/chat'
AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY user_id, user_email, ip_address
ORDER BY violations DESC;
```

## Adjusting Limits

### Per-User Adjustments (Future)
```python
# Increase limit for premium users
check_daily_ai_limit(current_user['user_id'], limit=20)

# Or get from user profile
user_limit = get_user_ai_limit(current_user['user_id'])
check_daily_ai_limit(current_user['user_id'], limit=user_limit)
```

### Global Adjustments
Edit `backend/main.py`:
```python
# Daily limit (line ~698)
check_daily_ai_limit(current_user['user_id'], limit=7)  # Change 7

# Hourly limit (defined in rate_limiter.py)
chat_rate_limiter = RateLimiter(max_requests=10, window_seconds=3600)  # Change 10
```

## Testing

### Test Rate Limits Locally
```bash
# Set ENABLE_AI_CHAT=true in backend/.env
# Start server
uvicorn main:app --reload

# Make 11 requests rapidly (should block on 11th)
for i in {1..11}; do
  echo "Request $i"
  curl -X POST http://localhost:8000/api/chat \
    -H "Authorization: Bearer YOUR_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"message":"test"}'
  echo ""
done
```

### Check Audit Logs
```bash
curl http://localhost:8000/api/admin/audit-logs?limit=10 \
  -H "Authorization: Bearer YOUR_TOKEN" \
  | jq '.logs[] | select(.event_type == "ai_chat_request")'
```

## Deployment Checklist

- [x] Set `ENABLE_AI_CHAT=true` in Railway
- [x] Verify `ANTHROPIC_API_KEY` is set
- [x] Run audit logs migration
- [x] Push code to Railway
- [ ] Test AI chat in production
- [ ] Monitor audit logs for usage patterns
- [ ] Set up alerts for high usage

## Cost Projection

**Assumptions:**
- Claude API: ~$0.02 per request (varies by prompt/response length)
- 100 active users
- Each user uses 5 requests/day on average

**Monthly Cost:**
```
100 users × 5 requests/day × 30 days × $0.02 = $300/month
```

**With 7/day limit:**
```
100 users × 7 requests/day × 30 days × $0.02 = $420/month (worst case)
```

**Actual usage likely lower:**
- Not all users will hit daily limit
- Weekend usage typically lower
- Some users may not use AI at all

**Realistic projection: $150-300/month for 100 users**

## Future Enhancements

- [ ] User tier system (free/premium)
- [ ] Usage dashboard for users
- [ ] Real-time usage alerts
- [ ] Cost tracking per user
- [ ] Model selection (faster/cheaper vs better/expensive)
- [ ] Cached responses for common questions
- [ ] Batch processing for similar questions
