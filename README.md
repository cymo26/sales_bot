# SALES_BOT - Proprietary B2B Sales Automation Ecosystem

## Overview
SALES_BOT is a powerful, asynchronous internal IT ecosystem designed to automate B2B sales and cold mailing, replacing expensive external SaaS tools (Apollo.io, Clay, Lemlist).

## Project Phases
- **Phase 1 (Current)**: Data Architecture & 2-way sync with Livespace CRM and Eventory API
- **Phase 2**: Core Sending Engine (Background Tasks scheduling emails via secure SMTP/IMAP)
- **Phase 3**: Scaling & UI (Streamlit frontend and real-time tracking pixels)
- **Phase 4**: Autonomous Prospecting Engine

## Tech Stack
- Python 3.11+
- FastAPI
- SQLModel (SQLAlchemy + Pydantic)
- PostgreSQL
- AsyncPG

## Project Structure
```
sales_bot/
├── app/
│   ├── core/                    # Core configuration
│   │   ├── database.py          # Async PostgreSQL setup
│   │   └── config.py            # Future: Configuration management
│   ├── models/
│   │   └── models.py            # SQLModel entities (5 core business entities)
│   └── __init__.py
├── scripts/
│   ├── init_db.py               # Database initialization
│   └── test_db.py               # Database validation tests
├── tests/                        # Test suite (Phase 2+)
├── .env                          # Environment variables (gitignored)
├── requirements.txt              # Python dependencies
├── .gitignore
└── README.md
```

## Core Models
1. **Company** - B2B account entity with domain-based deduplication
2. **User** - Salesperson/handler with email for SMTP/IMAP auth
3. **Campaign** - Outbound campaign container
4. **Lead** - Prospect/recipient with email deduplication
5. **ActivityLog** - Behavioral history for triggers & follow-ups

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file:
```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/sales_bot
SQL_ECHO=False
```

### 3. Initialize Database
```bash
python scripts/init_db.py
```

### 4. Run Tests
```bash
python scripts/test_db.py
```

## Key Features
- ✅ All IDs generated as UUID4 on Python side (async-ready)
- ✅ Proper async/await support with SQLModel
- ✅ Bidirectional relationship loading
- ✅ Built-in deduplication via UNIQUE constraints
- ✅ Cascade delete for referential integrity
- ✅ FastAPI dependency injection ready

## Usage Examples

### Initialize Database
```bash
python scripts/init_db.py              # Initialize
python scripts/init_db.py --reset      # Drop and reinitialize
python scripts/init_db.py --drop       # Drop only
```

### Test Database Constraints
```bash
python scripts/test_db.py
```

## Notes
- All database connections are fully asynchronous for Phase 2 background tasks
- UUID4 generation on Python side enables better async control
- Domain field on Company serves as primary deduplication key
- Email field on Lead serves as system-wide deduplication point

## Development Status
🚧 **Phase 1 MVP** - Database foundation complete. Ready for Phase 2 (Sending Engine).
