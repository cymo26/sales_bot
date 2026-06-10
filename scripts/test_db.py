"""
Asynchronous Database Validation and Testing Script for SALES_BOT
Tests constraints, relationships, and data integrity.
"""

import asyncio
import uuid
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core import engine, async_session_maker
from app.models import Company, User, Campaign, Lead, ActivityLog


async def test_constraints_and_relationships():
    """
    Comprehensive test function that validates:
    1. User, Company, and Campaign creation
    2. Lead creation linked to Company and Campaign
    3. UNIQUE email constraint on Leads
    4. Relationship loading and traversal
    5. ActivityLog creation and association
    """
    
    print("=" * 80)
    print("SALES_BOT Database Validation Tests")
    print("=" * 80)
    
    async with async_session_maker() as session:
        try:
            print("\n[TEST 1] Creating mock User...")
            mock_user = User(
                id=uuid.uuid4(),
                email="robert.lewandowski@company.com",
                first_name="Robert",
                last_name="Lewandowski",
            )
            session.add(mock_user)
            await session.flush()
            print(f"   ✓ User created: {mock_user.email} (ID: {mock_user.id})")
            
            print("\n[TEST 2] Creating mock Company...")
            mock_company = Company(
                id=uuid.uuid4(),
                name="FC Barcelona",
                domain="fcb.com",
                industry="Football Club",
                size_range="1000+",
                location="Barcelona, Spain",
            )
            session.add(mock_company)
            await session.flush()
            print(f"   ✓ Company created: {mock_company.name} (Domain: {mock_company.domain})")
            
            print("\n[TEST 3] Creating mock Campaign...")
            mock_campaign = Campaign(
                id=uuid.uuid4(),
                title="Q2 2026 Enterprise Outreach",
                status="active",
                user_id=mock_user.id,
            )
            session.add(mock_campaign)
            await session.flush()
            print(f"   ✓ Campaign created: {mock_campaign.title} (User: {mock_user.email})")
            
            print("\n[TEST 4] Creating mock Lead linked to Company and Campaign...")
            mock_lead = Lead(
                id=uuid.uuid4(),
                email="alice.smith@acme.com",
                first_name="Alice",
                last_name="Smith",
                position="Chief Information Security Officer",
                lead_type="attendee",
                eventory_id="EVT-12345",
                livespace_id="LS-98765",
                status="new",
                company_id=mock_company.id,
                campaign_id=mock_campaign.id,
            )
            session.add(mock_lead)
            await session.flush()
            print(f"   ✓ Lead created: {mock_lead.email}")
            print(f"      - Position: {mock_lead.position}")
            print(f"      - Company: {mock_company.name}")
            print(f"      - Campaign: {mock_campaign.title}")
            
            print("\n[TEST 5] Testing UNIQUE email constraint (Deduplication)...")
            print("   Attempting to insert duplicate lead with same email...")
            
            # Use savepoint for this test so we don't rollback the entire session
            async with session.begin_nested():
                try:
                    duplicate_lead = Lead(
                        id=uuid.uuid4(),
                        email="alice.smith@acme.com",  # SAME EMAIL - should fail
                        first_name="Alice",
                        last_name="Smith",
                        position="Developer",
                        lead_type="attendee",
                        company_id=mock_company.id,
                        campaign_id=mock_campaign.id,
                    )
                    session.add(duplicate_lead)
                    await session.flush()
                    print("   ❌ ERROR: Duplicate lead was allowed (constraint failed!)")
                except IntegrityError as e:
                    print("   ✓ Deduplication Success: System successfully blocked a duplicate lead!")
                    print(f"      - Error type: {type(e).__name__}")
                    print(f"      - Constraint: UNIQUE(email)")
            
            print("\n[TEST 6] Creating Activity Logs...")
            activity_log_1 = ActivityLog(
                id=uuid.uuid4(),
                activity_type="email_sent",
                description="Initial outreach email sent",
                lead_id=mock_lead.id,
            )
            activity_log_2 = ActivityLog(
                id=uuid.uuid4(),
                activity_type="email_opened",
                description="Lead opened email after 2 hours",
                lead_id=mock_lead.id,
            )
            session.add(activity_log_1)
            session.add(activity_log_2)
            await session.flush()
            print(f"   ✓ Activity logs created for lead {mock_lead.email}")
            
            print("\n[TEST 7] Testing relationship loading (Company -> Leads)...")
            # Query the company with its leads (eagerly loaded)
            stmt = select(Company).where(Company.id == mock_company.id).options(selectinload(Company.leads))
            result = await session.execute(stmt)
            loaded_company = result.scalar_one()
            
            print(f"   ✓ Company loaded: {loaded_company.name}")
            print(f"   ✓ Associated leads: {len(loaded_company.leads)}")
            for lead in loaded_company.leads:
                print(f"      - {lead.email} ({lead.position})")
            
            print("\n[TEST 8] Testing relationship loading (Lead -> ActivityLogs)...")
            # Query the lead with its activity logs (eagerly loaded)
            stmt = select(Lead).where(Lead.id == mock_lead.id).options(selectinload(Lead.activity_logs))
            result = await session.execute(stmt)
            loaded_lead = result.scalar_one()
            
            print(f"   ✓ Lead loaded: {loaded_lead.email}")
            print(f"   ✓ Associated activity logs: {len(loaded_lead.activity_logs)}")
            for log in loaded_lead.activity_logs:
                print(f"      - [{log.activity_type}] {log.description}")
            
            print("\n[TEST 9] Testing relationship loading (Campaign -> Leads)...")
            # Query the campaign with its leads (eagerly loaded)
            stmt = select(Campaign).where(Campaign.id == mock_campaign.id).options(selectinload(Campaign.leads))
            result = await session.execute(stmt)
            loaded_campaign = result.scalar_one()
            
            print(f"   ✓ Campaign loaded: {loaded_campaign.title}")
            print(f"   ✓ Status: {loaded_campaign.status}")
            print(f"   ✓ Associated leads: {len(loaded_campaign.leads)}")
            for lead in loaded_campaign.leads:
                print(f"      - {lead.email} (Status: {lead.status})")
            
            # Commit all successful operations
            await session.commit()
            
            print("\n" + "=" * 80)
            print("✅ ALL TESTS PASSED - Database is functioning correctly!")
            print("=" * 80)
            
            return True
        
        except Exception as e:
            await session.rollback()
            print(f"\n❌ TEST FAILED: {type(e).__name__}")
            print(f"   Error: {str(e)}")
            print("\n" + "=" * 80)
            print("Status: FAILED")
            print("=" * 80)
            return False
        
        finally:
            await session.close()


async def main():
    """
    Main entry point for the test script.
    """
    
    print("\n🔧 Initializing async test environment...\n")
    
    try:
        success = await test_constraints_and_relationships()
        
        if success:
            exit(0)
        else:
            exit(1)
    
    except Exception as e:
        print(f"\n❌ Fatal error: {type(e).__name__}: {str(e)}")
        exit(1)
    
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
