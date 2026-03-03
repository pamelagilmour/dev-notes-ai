# Dev Notes AI

A full-stack application that helps developers organize and query their technical knowledge using AI. Built with custom MCP server integration, Redis caching, and background job processing.

![Screenshot](./docs/screenshots/dashboard.png)

## Key Features

- **AI-powered search and knowledge retrieval** - Natural language queries across your knowledge base
- **Custom MCP server for tool integration** - Extensible architecture for adding new capabilities
- **Redis caching** - Fast query responses and optimized performance
- **Background job processing** - Async indexing and data processing
- **Modern tech stack** - Next.js, TypeScript, FastAPI, PostgreSQL

## Demo

- **[Live Demo](https://p-11-one.vercel.app/)** - Try it out (rate-limited for security)
- **[Video Walkthrough](youtube-link)** - 2-minute feature overview

## Tech Stack

**Frontend:**
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- React Context (auth state management)


**Backend:**
- Python 3.10+
- FastAPI
- SQLAlchemy
- PostgreSQL
- JWT Authentication


**AI/Integration:**
- Anthropic Claude API
- Custom MCP Server (FastMCP) implementation
- Agentic tool loop

## Architecture

- User submits query through Next.js frontend
- Request reaches FastAPI backend
- Redis cache checks for existing results
- If cache miss, MCP server processes query with Claude API
- Background jobs handle indexing and data updates
- Results returned and cached for future queries

## Local Development

### Prerequisites
- Node.js 18+
- Python 3.11+
- PostgreSQL
- Redis

### Setup
Clone the repository
```bash
git clone https://github.com/pamelagilmour/dev-notes-ai.git
cd dev-notes-ai
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

### Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### MCP Server Setup
```bash
cd mcp-server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python knowledge_base_server.py
```

### Environment Variables

**backend/.env**
```
DATABASE_URL=postgresql://localhost:5432/knowledge_base
SECRET_KEY=your-secret-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

## 🧪 Testing
```bash
# Backend tests (coming soon)
pytest

# Test MCP server
mcp dev mcp-server/knowledge_base_server.py

# API docs (auto-generated)
http://localhost:8000/docs
```

## 📈 System Design Highlights

**Current:**
- RESTful API with proper status codes and error handling
- JWT authentication with 24hr token expiration
- Password hashing with bcrypt
- Database indexes for query performance
- Input validation with Pydantic models
- CORS configuration
- Agentic AI loop with tool orchestration
- Redis caching (target: 80%+ cache hit rate)
- Rate limiting

## Security Features

- Rate limiting on AI queries
- API key management


---

Built by [Pam Gilmour](https://my-next-app.sodalitemix.workers.dev/) | [LinkedIn](https://www.linkedin.com/in/pamela-gilmour/) | [GitHub](https://github.com/pamelagilmour)

