from fastapi import FastAPI, HTTPException, status, Depends, Request
from fastapi.responses import JSONResponse
from rate_limiter import check_rate_limit, rate_limiter, check_daily_ai_limit, check_auth_rate_limit
import time
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv
from typing import List
from cache_service import (
    get_cache, set_cache, delete_cache, 
    delete_cache_pattern, clear_user_cache, get_cache_stats,
    redis_client
)

# Import new modules
from models import (
    UserRegister, UserLogin, TokenResponse, UserResponse,
    KnowledgeEntryCreate, KnowledgeEntryUpdate, KnowledgeEntryResponse,
    ChatMessage

)
from auth import hash_password, verify_password, create_access_token, get_current_user
from ai_service import chat_with_knowledge_base
from audit_service import audit_logger

# Load environment vars
load_dotenv()

# Initialize app
app = FastAPI(title="AI Knowledge Base API")


# Security headers middleware
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    
    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    
    # Enable XSS protection
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # Strict Transport Security (HTTPS only)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    # Content Security Policy
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    )
    
    # Referrer Policy
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Permissions Policy (formerly Feature Policy)
    response.headers["Permissions-Policy"] = (
        "geolocation=(), "
        "microphone=(), "
        "camera=(), "
        "payment=(), "
        "usb=(), "
        "magnetometer=(), "
        "gyroscope=(), "
        "accelerometer=()"
    )
    
    return response

# Add middleware to track rate limits on all requests
@app.middleware("http")
async def global_rate_limit_middleware(request: Request, call_next):
    """Rate limit by IP address globally"""

    # ALWAYS allow OPTIONS requests (CORS preflight)
    if request.method == "OPTIONS":
        return await call_next(request)
    
    client_ip = request.client.host
    
    # Skip for health check
    if request.url.path in ["/", "/api/health", "/docs", "/openapi.json"]:
        return await call_next(request)
    
    # Rate limit: 300 requests per hour per IP
    key = f"global_rate_limit:ip:{client_ip}"
    count = redis_client.get(key)
    count = int(count) if count else 0
    
    if count >= 300:
        # Log rate limit violation
        audit_logger.log_rate_limit(
            event_type=audit_logger.RATE_LIMIT_EXCEEDED,
            ip_address=client_ip,
            details={"endpoint": str(request.url.path)}
        )
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."},
            headers={"Retry-After": "3600"}
        )
    
    if count == 0:
        redis_client.setex(key, 3600, 1)
    else:
        redis_client.incr(key)
    
    return await call_next(request)

# Create dependency for rate limiting
def rate_limit_dependency(current_user: dict = Depends(get_current_user)):
    """
    Dependency that checks rate limit for authenticated user
    Use this in endpoints: Depends(rate_limit_dependency)
    """
    check_rate_limit(current_user['user_id'])
    return current_user

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://p-11-one.vercel.app",
        "https://p-11-one.vercel.app/",
        "https://*.vercel.app",  # Allow all Vercel preview deployments
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Database connection helper
def get_db_connection():
    """Create a database connection"""

    # Use DATABASE_URL from environment (Railway sets this automatically)
    database_url = os.getenv("DATABASE_URL")

    if database_url:
        # Railway/Production - use DATABASE_URL
        conn = psycopg2.connect(
            database_url,
            cursor_factory=RealDictCursor
        )
    else:
        # Local development - use individual params
        conn = psycopg2.connect(
            host="localhost",
            database="knowledge_base",
            user="",  # Your Mac username for local
            password="",
            cursor_factory=RealDictCursor
        )
    
    return conn

# Health check endpoint
@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "AI Knowledge Base API",
        "version": "0.0.0",
        "status": "running"
    }

@app.get("/api/health")
def health_check():
    """Health check endpoint, verify the server is running"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        return {
            "status": "healthy",
            "database": "connected"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": f"error: {str(e)}"
        }

# Auth Endpoints

@app.post("/api/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user: UserRegister, request: Request):
    """Register a new user"""
    # Rate limit by IP to prevent spam registrations
    client_ip = request.client.host
    check_auth_rate_limit(f"register:{client_ip}")
    
    # Check honeypot
    if user.website:
        raise HTTPException(status_code=400, detail="Invalid registration")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if user already exists
        cursor.execute("SELECT id FROM users WHERE email = %s", (user.email,))
        existing = cursor.fetchone()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Hash password and create user
        hashed_password = hash_password(user.password)
        
        cursor.execute(
            "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id, email, created_at",
            (user.email, hashed_password)
        )
        new_user = cursor.fetchone()
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Log successful registration
        audit_logger.log(
            event_type=audit_logger.REGISTER_SUCCESS,
            event_category=audit_logger.CATEGORY_AUTH,
            severity=audit_logger.SEVERITY_INFO,
            status=audit_logger.STATUS_SUCCESS,
            user_id=new_user['id'],
            user_email=new_user['email'],
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent")
        )
        
        return UserResponse(
            id=new_user['id'],
            email=new_user['email'],
            created_at=str(new_user['created_at'])
        )
    
    except HTTPException as he:
        # Log failed registration
        audit_logger.log(
            event_type=audit_logger.REGISTER_FAILED,
            event_category=audit_logger.CATEGORY_AUTH,
            severity=audit_logger.SEVERITY_WARNING,
            status=audit_logger.STATUS_FAILURE,
            user_email=user.email,
            ip_address=client_ip,
            details={"reason": str(he.detail)},
            user_agent=request.headers.get("user-agent")
        )
        raise
    except Exception as e:
        # Log failed registration
        audit_logger.log(
            event_type=audit_logger.REGISTER_FAILED,
            event_category=audit_logger.CATEGORY_AUTH,
            severity=audit_logger.SEVERITY_ERROR,
            status=audit_logger.STATUS_FAILURE,
            user_email=user.email,
            ip_address=client_ip,
            details={"error": "system_error"},
            user_agent=request.headers.get("user-agent")
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@app.post("/api/auth/login", response_model=TokenResponse)
def login(user: UserLogin, request: Request):
    """Login and get access token"""
    # Rate limit by IP + email to prevent brute force
    client_ip = request.client.host
    rate_limit_key = f"login:{client_ip}:{user.email}"
    check_auth_rate_limit(rate_limit_key)
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Find user by email
        cursor.execute(
            "SELECT id, email, password_hash, created_at FROM users WHERE email = %s",
            (user.email,)
        )
        db_user = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        # Verify user exists and password is correct
        if not db_user or not verify_password(user.password, db_user['password_hash']):
            # Log failed login
            audit_logger.log_auth_failure(
                user_email=user.email,
                ip_address=client_ip,
                reason="invalid_credentials",
                user_agent=request.headers.get("user-agent")
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Create access token
        access_token = create_access_token(
            data={"user_id": db_user['id'], "email": db_user['email']}
        )
        
        # Log successful login
        audit_logger.log_auth_success(
            user_id=db_user['id'],
            user_email=db_user['email'],
            ip_address=client_ip,
            user_agent=request.headers.get("user-agent")
        )
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse(
                id=db_user['id'],
                email=db_user['email'],
                created_at=str(db_user['created_at'])
            )
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/api/auth/me", response_model=UserResponse)
def get_me(current_user: dict = Depends(get_current_user)):
    """
    Get current authenticated user
    This endpoint is PROTECTED - requires valid JWT token
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get user from database using user_id from token
        cursor.execute(
            "SELECT id, email, created_at FROM users WHERE id = %s",
            (current_user['user_id'],)
        )
        user = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserResponse(
            id=user['id'],
            email=user['email'],
            created_at=str(user['created_at'])
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Protected endpoint, entries
# Update get_entries endpoint with caching
@app.get("/api/entries", response_model=List[KnowledgeEntryResponse])
def get_entries(current_user: dict = Depends(rate_limit_dependency)):
    """Get all knowledge entries (cached + rate limited)"""
    
    # Check cache first
    cache_key = f"entries:user:{current_user['user_id']}:all"
    cached = get_cache(cache_key)
    if cached:
        return cached
    
    # Cache miss - fetch from database
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """SELECT id, user_id, title, content, tags, created_at, updated_at 
               FROM knowledge_entries 
               WHERE user_id = %s 
               ORDER BY created_at DESC""",
            (current_user['user_id'],)
        )
        entries = cursor.fetchall()
        cursor.close()
        conn.close()
        
        result = []
        for entry in entries:
            tags = entry['tags'] if entry['tags'] else []
            
            result.append(KnowledgeEntryResponse(
                id=entry['id'],
                user_id=entry['user_id'],
                title=entry['title'],
                content=entry['content'],
                tags=tags,
                created_at=str(entry['created_at']),
                updated_at=str(entry['updated_at'])
            ))
        
        # Convert to dict for caching
        result_dict = [
            {
                "id": e.id,
                "user_id": e.user_id,
                "title": e.title,
                "content": e.content,
                "tags": e.tags,
                "created_at": e.created_at,
                "updated_at": e.updated_at
            }
            for e in result
        ]
        
        # Cache for 15 minutes
        set_cache(cache_key, result_dict, ttl=900)
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch entries"
        )

# Knowledge entries endpoints

# Update create_entry to invalidate cache
@app.post("/api/entries", response_model=KnowledgeEntryResponse, status_code=status.HTTP_201_CREATED)
def create_entry(
    entry: KnowledgeEntryCreate,
    current_user: dict = Depends(rate_limit_dependency)
):
    """Create a new knowledge entry (invalidates cache)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """INSERT INTO knowledge_entries (user_id, title, content, tags)
               VALUES (%s, %s, %s, %s)
               RETURNING id, user_id, title, content, tags, created_at, updated_at""",
            (current_user['user_id'], entry.title, entry.content, entry.tags)
        )
        new_entry = cursor.fetchone()
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Invalidate cache for this user
        clear_user_cache(current_user['user_id'])
        
        return KnowledgeEntryResponse(
            id=new_entry['id'],
            user_id=new_entry['user_id'],
            title=new_entry['title'],
            content=new_entry['content'],
            tags=new_entry['tags'] or [],
            created_at=str(new_entry['created_at']),
            updated_at=str(new_entry['updated_at'])
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/entries/{entry_id}", response_model=KnowledgeEntryResponse)
def get_entry(entry_id: int, current_user: dict = Depends(rate_limit_dependency)):
    """Get a specific knowledge entry"""
    
    cache_key = f"entry:{entry_id}:user:{current_user['user_id']}"
    cached = get_cache(cache_key)
    if cached:
        return cached

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, user_id, title, content, tags, created_at, updated_at
               FROM knowledge_entries
               WHERE id = %s AND user_id = %s""",
            (entry_id, current_user['user_id'])
        )
        entry = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")
        
        result = KnowledgeEntryResponse(
            id=entry['id'],
            user_id=entry['user_id'],
            title=entry['title'],
            content=entry['content'],
            tags=entry['tags'] or [],
            created_at=str(entry['created_at']),
            updated_at=str(entry['updated_at'])
        )
        
        set_cache(cache_key, result.model_dump(), ttl=300)
        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Update update_entry to invalidate cache
@app.put("/api/entries/{entry_id}", response_model=KnowledgeEntryResponse)
def update_entry(
    entry_id: int,
    entry_update: KnowledgeEntryUpdate,
    current_user: dict = Depends(rate_limit_dependency)
):
    """Update a knowledge entry (invalidates cache)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id FROM knowledge_entries WHERE id = %s AND user_id = %s",
            (entry_id, current_user['user_id'])
        )
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entry not found"
            )
        
        update_fields = []
        update_values = []
        
        if entry_update.title is not None:
            update_fields.append("title = %s")
            update_values.append(entry_update.title)
        
        if entry_update.content is not None:
            update_fields.append("content = %s")
            update_values.append(entry_update.content)
        
        if entry_update.tags is not None:
            update_fields.append("tags = %s")
            update_values.append(entry_update.tags)
        
        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        
        update_values.append(entry_id)
        update_values.append(current_user['user_id'])
        
        query = f"""
            UPDATE knowledge_entries 
            SET {', '.join(update_fields)}
            WHERE id = %s AND user_id = %s
            RETURNING id, user_id, title, content, tags, created_at, updated_at
        """
        
        cursor.execute(query, update_values)
        updated_entry = cursor.fetchone()
        
        conn.commit()
        cursor.close()
        conn.close()
        
        # Invalidate cache for this user
        clear_user_cache(current_user['user_id'])
        
        # Log entry update
        audit_logger.log_resource_action(
            action="update",
            resource=f"entry:{entry_id}",
            user_id=current_user['user_id'],
            ip_address="system"
        )
        
        return KnowledgeEntryResponse(
            id=updated_entry['id'],
            user_id=updated_entry['user_id'],
            title=updated_entry['title'],
            content=updated_entry['content'],
            tags=updated_entry['tags'] or [],
            created_at=str(updated_entry['created_at']),
            updated_at=str(updated_entry['updated_at'])
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Update delete_entry to invalidate cache
@app.delete("/api/entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: int, current_user: dict = Depends(rate_limit_dependency)):
    """Delete a knowledge entry (invalidates cache)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "DELETE FROM knowledge_entries WHERE id = %s AND user_id = %s RETURNING id",
            (entry_id, current_user['user_id'])
        )
        deleted = cursor.fetchone()
        
        conn.commit()
        cursor.close()
        conn.close()
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entry not found"
            )
        
        # Invalidate cache for this user
        clear_user_cache(current_user['user_id'])
        
        # Log entry deletion
        audit_logger.log_resource_action(
            action="delete",
            resource=f"entry:{entry_id}",
            user_id=current_user['user_id'],
            ip_address="system"
        )
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Add cache stats endpoint
@app.get("/api/cache/stats")
def cache_stats(current_user: dict = Depends(get_current_user)):
    """Get Redis cache statistics (admin endpoint)"""
    return get_cache_stats()


@app.post("/api/chat")
def chat(
    request: Request,
    chat_message: ChatMessage,
    current_user: dict = Depends(rate_limit_dependency)
):
    """Send a message to Claude with knowledge base tools"""
    
    # Check if AI chat is enabled (controlled via ENABLE_AI_CHAT env var)
    if os.getenv("ENABLE_AI_CHAT", "false").lower() != "true":
        return {
            "response": "AI chat is currently disabled. Please contact the administrator."
        }
    
    # Apply strict rate limiting for AI chat (expensive operation)
    # Daily limit: 7 requests per day
    check_daily_ai_limit(current_user['user_id'], limit=7)
    
    # Hourly limit: 10 requests per hour (prevents rapid-fire abuse)
    from rate_limiter import chat_rate_limiter
    client_ip = request.client.host
    chat_limit_key = f"chat:user:{current_user['user_id']}"
    
    chat_result = chat_rate_limiter.check_rate_limit(chat_limit_key)
    if not chat_result["allowed"]:
        minutes_remaining = (chat_result["reset_time"] - int(time.time())) // 60
        
        # Log rate limit violation
        audit_logger.log_rate_limit(
            event_type=audit_logger.RATE_LIMIT_EXCEEDED,
            ip_address=client_ip,
            user_id=current_user['user_id'],
            details={"endpoint": "/api/chat", "limit_type": "hourly"}
        )
        
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"AI chat rate limit exceeded (10 per hour). Try again in {minutes_remaining} minutes.",
            headers={
                "X-RateLimit-Limit": str(chat_result["limit"]),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(chat_result["reset_time"]),
                "Retry-After": str(chat_result["reset_time"] - int(time.time()))
            }
        )

    try:
        # Log AI chat request
        audit_logger.log(
            event_type=audit_logger.AI_CHAT_REQUEST,
            event_category=audit_logger.CATEGORY_API,
            severity=audit_logger.SEVERITY_INFO,
            status=audit_logger.STATUS_SUCCESS,
            user_id=current_user['user_id'],
            ip_address=client_ip,
            details={
                "message_length": len(chat_message.message),
                "requests_remaining_daily": 7 - int(redis_client.get(f"ai_limit:user:{current_user['user_id']}:daily") or 0),
                "requests_remaining_hourly": chat_result["remaining"]
            },
            user_agent=request.headers.get("user-agent")
        )
        
        response = chat_with_knowledge_base(
            message=chat_message.message,
            user_id=current_user['user_id']
        )
        return {"response": response}
        
    except HTTPException:
        raise
    except Exception as e:
        # Log AI error
        audit_logger.log(
            event_type="ai_chat_error",
            event_category=audit_logger.CATEGORY_SYSTEM,
            severity=audit_logger.SEVERITY_ERROR,
            status=audit_logger.STATUS_FAILURE,
            user_id=current_user['user_id'],
            ip_address=client_ip,
            details={"error": "ai_service_error"}
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI service temporarily unavailable"
        )

@app.get("/api/rate-limit/status")
def rate_limit_status(current_user: dict = Depends(get_current_user)):
    """Get current rate limit status for user"""
    result = rate_limiter.check_rate_limit(current_user['user_id'])
    return {
        "user_id": current_user['user_id'],
        "requests_remaining": result['remaining'],
        "requests_limit": result['limit'],
        "reset_time": result['reset_time'],
        "reset_in_seconds": result['reset_time'] - int(time.time())
    }

@app.get("/api/ai-limit/status")
def ai_limit_status(current_user: dict = Depends(get_current_user)):
    """Get current AI request limit status for user"""
    from cache_service import redis_client
    
    # Daily limit
    daily_key = f"ai_limit:user:{current_user['user_id']}:daily"
    daily_count = redis_client.get(daily_key)
    daily_ttl = redis_client.ttl(daily_key)
    daily_count = int(daily_count) if daily_count else 0
    daily_limit = 7
    daily_remaining = max(0, daily_limit - daily_count)
    
    # Hourly limit
    hourly_key = f"rate_limit:user:chat:user:{current_user['user_id']}"
    hourly_count = redis_client.get(hourly_key)
    hourly_ttl = redis_client.ttl(hourly_key)
    hourly_count = int(hourly_count) if hourly_count else 0
    hourly_limit = 10
    hourly_remaining = max(0, hourly_limit - hourly_count)
    
    return {
        "user_id": current_user['user_id'],
        "daily": {
            "used": daily_count,
            "remaining": daily_remaining,
            "limit": daily_limit,
            "resets_in_seconds": daily_ttl if daily_ttl > 0 else 86400,
            "resets_in_hours": (daily_ttl // 3600) if daily_ttl > 0 else 24
        },
        "hourly": {
            "used": hourly_count,
            "remaining": hourly_remaining,
            "limit": hourly_limit,
            "resets_in_seconds": hourly_ttl if hourly_ttl > 0 else 3600,
            "resets_in_minutes": (hourly_ttl // 60) if hourly_ttl > 0 else 60
        },
        "can_chat": daily_remaining > 0 and hourly_remaining > 0
    }

@app.get("/api/admin/usage")
def admin_usage(current_user: dict = Depends(get_current_user)):
    """Get usage stats"""
    
    # Count total users
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM knowledge_entries")
    entry_count = cursor.fetchone()[0]
    
    cursor.close()
    conn.close()
    
    return {
        "total_users": user_count,
        "total_entries": entry_count,
        "cache_stats": get_cache_stats()
    }

@app.get("/api/admin/audit-logs")
def get_audit_logs(
    current_user: dict = Depends(get_current_user),
    limit: int = 100,
    severity: str = None,
    user_id: int = None
):
    """
    Get recent audit logs (admin endpoint)
    
    Query params:
        - limit: Number of logs to return (default 100, max 500)
        - severity: Filter by severity (info, warning, error, critical)
        - user_id: Filter by user ID
    """
    # Limit the limit to prevent abuse
    limit = min(limit, 500)
    
    logs = audit_logger.get_recent_logs(
        limit=limit,
        user_id=user_id,
        severity=severity
    )
    
    return {
        "count": len(logs),
        "logs": logs
    }

@app.get("/api/admin/security-summary")
def get_security_summary(
    current_user: dict = Depends(get_current_user),
    hours: int = 24
):
    """
    Get security event summary for the last N hours
    Shows counts of failed logins, rate limits, etc.
    """
    hours = min(hours, 168)  # Max 1 week
    
    summary = audit_logger.get_security_summary(hours=hours)
    
    return {
        "period_hours": hours,
        "events": summary
    }

@app.get("/api/my/audit-logs")
def get_my_audit_logs(
    current_user: dict = Depends(get_current_user),
    limit: int = 50
):
    """
    Get your own audit logs (user endpoint)
    Allows users to see their own activity history
    """
    limit = min(limit, 100)
    
    logs = audit_logger.get_recent_logs(
        limit=limit,
        user_id=current_user['user_id']
    )
    
    return {
        "count": len(logs),
        "logs": logs
    }