"""
SQLModel Data Models for SALES_BOT
Defines 5 core business entities with robust relational mappings.
All IDs are UUID4 generated on Python side (not database auto-increment).
"""

import uuid
from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship, Index


# ============================================================================
# 1. COMPANY - The B2B Account Entity
# ============================================================================
class Company(SQLModel, table=True):
    """
    Represents a B2B company/organization in the system.
    Domain field serves as the primary deduplication key.
    """
    
    __tablename__ = "companies"
    
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )
    name: str = Field(
        index=True,
        description="Company name"
    )
    domain: Optional[str] = Field(
        default=None,
        unique=True,
        index=True,
        nullable=True,
        description="Primary deduplication key (e.g., 'comarch.pl'); optional — not every source knows the domain"
    )
    industry: Optional[str] = Field(
        default=None,
        index=True,
        nullable=True,
        description="Industry classification"
    )
    size_range: Optional[str] = Field(
        default=None,
        nullable=True,
        description="Company size (e.g., '50-249', '250+')"
    )
    location: Optional[str] = Field(
        default=None,
        nullable=True,
        description="Comma-separated unique cities aggregated from this company's leads"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when company was created"
    )
    
    # Relationships
    leads: List["Lead"] = Relationship(
        back_populates="company",
        cascade_delete=True,
    )


# ============================================================================
# 2. USER - The Salesperson/Handler
# ============================================================================
class User(SQLModel, table=True):
    """
    Represents a salesperson or handler in the system.
    Email is used for SMTP/IMAP authentication in Phase 2.
    """
    
    __tablename__ = "users"
    
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )
    email: str = Field(
        unique=True,
        index=True,
        description="User email (used for SMTP/IMAP authentication)"
    )
    first_name: str = Field(
        description="User's first name"
    )
    last_name: str = Field(
        description="User's last name"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when user was created"
    )
    
    # Relationships
    campaigns: List["Campaign"] = Relationship(
        back_populates="user",
        cascade_delete=True,
    )


# ============================================================================
# 3. CAMPAIGN - The Outbound Campaign Container
# ============================================================================
class Campaign(SQLModel, table=True):
    """
    Represents an outbound email campaign.
    Linked to a User (salesperson) and contains multiple Leads.
    """
    
    __tablename__ = "campaigns"
    
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )
    title: str = Field(
        description="Campaign title/name"
    )
    status: str = Field(
        default="draft",
        description="Campaign status (draft, active, paused, completed)"
    )
    user_id: uuid.UUID = Field(
        foreign_key="users.id",
        description="Foreign key to the User running this campaign"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when campaign was created"
    )
    
    # Relationships
    user: User = Relationship(back_populates="campaigns")
    leads: List["Lead"] = Relationship(
        back_populates="campaign",
        cascade_delete=True,
    )


# ============================================================================
# 4. LEAD - The Recipient/Attendee Profile
# ============================================================================
class Lead(SQLModel, table=True):
    """
    Represents a prospect/lead/recipient in the system.
    Email serves as system-wide deduplication point.
    Can be linked to a Company and Campaign.
    """
    
    __tablename__ = "leads"
    
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )
    email: str = Field(
        unique=True,
        index=True,
        description="Lead email (system-wide deduplication key)"
    )
    first_name: Optional[str] = Field(
        default=None,
        nullable=True,
        description="Lead's first name"
    )
    last_name: Optional[str] = Field(
        default=None,
        nullable=True,
        description="Lead's last name"
    )
    position: Optional[str] = Field(
        default=None,
        nullable=True,
        description="Job position (e.g., CISO, Developer, HR Manager)"
    )
    lead_type: str = Field(
        default="attendee",
        description="Lead type (attendee, partner_decision_maker, etc.)"
    )
    eventory_id: Optional[str] = Field(
        default=None,
        index=True,
        nullable=True,
        description="External ID from Eventory API"
    )
    livespace_id: Optional[str] = Field(
        default=None,
        index=True,
        nullable=True,
        description="External ID from Livespace CRM for bidirectional sync"
    )
    status: str = Field(
        default="new",
        description="Lead status (new, sent, opened, replied, bounced)"
    )
    notes: Optional[str] = Field(
        default=None,
        nullable=True,
        description="Operational notes added manually by the salesperson"
    )
    location: Optional[str] = Field(
        default=None,
        nullable=True,
        index=True,
        description="Lead's city or location (e.g., Warsaw, Krakow)"
    )
    linkedin_url: Optional[str] = Field(
        default=None,
        nullable=True,
        description="LinkedIn profile URL"
    )
    tags: Optional[str] = Field(
        default=None,
        nullable=True,
        description="Comma-separated event tags e.g. 'OMH,JDD,CONFIDENCE'"
    )
    company_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="companies.id",
        nullable=True,
        description="Foreign key to Company (optional)"
    )
    campaign_id: Optional[uuid.UUID] = Field(
        default=None,
        foreign_key="campaigns.id",
        nullable=True,
        description="Foreign key to Campaign (optional)"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when lead was created"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when lead was last updated"
    )
    
    # Relationships
    company: Optional[Company] = Relationship(back_populates="leads")
    campaign: Optional[Campaign] = Relationship(back_populates="leads")
    activity_logs: List["ActivityLog"] = Relationship(
        back_populates="lead",
        cascade_delete=True,
    )


# ============================================================================
# 5. ACTIVITYLOG - The History Log for Behavioral Triggers & Follow-ups
# ============================================================================
class ActivityLog(SQLModel, table=True):
    """
    Represents an activity/event in the system.
    Used for tracking email sends, opens, replies, and other behavioral events.
    """
    
    __tablename__ = "activity_logs"
    
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )
    activity_type: str = Field(
        description="Type of activity (email_sent, email_opened, reply_received, etc.)"
    )
    description: Optional[str] = Field(
        default=None,
        nullable=True,
        description="Additional description/details of the activity"
    )
    lead_id: uuid.UUID = Field(
        foreign_key="leads.id",
        description="Foreign key to the Lead this activity is associated with"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when activity was logged"
    )
    
    # Relationships
    lead: Lead = Relationship(back_populates="activity_logs")
