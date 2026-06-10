"""
Asynchronous Database Initialization Script for SALES_BOT
Creates all tables in PostgreSQL database from SQLModel metadata.
"""

import asyncio
import sys
from sqlalchemy import text
from sqlmodel import SQLModel

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import engine
from app.models import Company, User, Campaign, Lead, ActivityLog


async def init_db():
    """
    Asynchronously creates all tables in the database.
    Uses run_sync to execute synchronous SQLAlchemy metadata operations.
    """
    
    print("=" * 80)
    print("SALES_BOT Database Initialization")
    print("=" * 80)
    
    try:
        print("\n📋 Starting table creation process...\n")
        
        # Create all tables defined in SQLModel metadata
        async with engine.begin() as conn:
            print("   ✓ Connected to PostgreSQL")
            
            # Run synchronous metadata.create_all in async context
            await conn.run_sync(SQLModel.metadata.create_all)
            
            print("   ✓ Tables created successfully")
        
        # Verify tables were created
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    ORDER BY table_name
                """)
            )
            tables = result.fetchall()
            
            print("\n✅ Database initialization complete!")
            print("\n📊 Created tables:")
            for table in tables:
                print(f"   • {table[0]}")
        
        print("\n" + "=" * 80)
        print("Status: SUCCESS - All tables initialized")
        print("=" * 80)
        
        return True
    
    except Exception as e:
        print(f"\n❌ ERROR during database initialization:")
        print(f"   {type(e).__name__}: {str(e)}")
        print("\n" + "=" * 80)
        print("Status: FAILED - Check your DATABASE_URL and PostgreSQL connection")
        print("=" * 80)
        return False
    
    finally:
        # Close the engine connection pool
        await engine.dispose()


async def drop_all_tables():
    """
    Asynchronously drops all tables from the database.
    Useful for resetting the database during development.
    """
    
    print("\n⚠️  Dropping all tables...\n")
    
    try:
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)
            print("✓ All tables dropped successfully")
        
        return True
    
    except Exception as e:
        print(f"❌ ERROR dropping tables: {str(e)}")
        return False
    
    finally:
        await engine.dispose()


async def reset_db():
    """
    Resets the database by dropping all tables and recreating them.
    """
    
    print("=" * 80)
    print("SALES_BOT Database Reset")
    print("=" * 80)
    
    if await drop_all_tables():
        print("\nRecreating tables...\n")
        await init_db()
    else:
        print("\nReset failed during drop phase")


def main():
    """
    Main entry point for the initialization script.
    Accepts command-line arguments:
      - (no args): Initialize database
      - --reset: Drop all tables and reinitialize
      - --drop: Drop all tables only
    """
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "--reset":
            asyncio.run(reset_db())
        elif command == "--drop":
            asyncio.run(drop_all_tables())
        else:
            print(f"Unknown command: {command}")
            print("\nUsage:")
            print("  python scripts/init_db.py              # Initialize database")
            print("  python scripts/init_db.py --reset      # Drop and reinitialize")
            print("  python scripts/init_db.py --drop       # Drop all tables")
    else:
        asyncio.run(init_db())


if __name__ == "__main__":
    main()
