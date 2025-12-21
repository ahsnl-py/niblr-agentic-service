"""Catalog management endpoints for saving items from agent responses."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from .database import get_db
from .db_models import User, CatalogItem
from .models import (
    CatalogItemCreate,
    CatalogItemResponse,
    CatalogItemDeleteRequest,
)
from .auth import get_current_user
from .bigquery_client import get_catalog_item_from_bigquery, get_catalog_items_from_bigquery

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.post("", response_model=CatalogItemResponse, status_code=status.HTTP_201_CREATED)
async def create_catalog_item(
    item_data: CatalogItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save an item from an agent response to the user's catalog.
    
    The catalog_item_id should be the property_id or job_id from the agent's
    structured_data response. The item data will be fetched from BigQuery
    when the user views it.
    
    Args:
        item_data: Catalog item creation data
        current_user: Authenticated user
        db: Database session
        
    Returns:
        Created catalog item (without item_data, fetch separately)
    """
    # Create catalog item
    catalog_item = CatalogItem(
        user_id=current_user.id,
        catalog_item_id=item_data.catalog_item_id,
        catalog_name=item_data.catalog_name,
        agent_name=item_data.agent_name,
        source_message_id=item_data.source_message_id,
        session_id=item_data.session_id
    )
    
    try:
        db.add(catalog_item)
        db.commit()
        db.refresh(catalog_item)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Item already saved to catalog"
        )
    
    return CatalogItemResponse(
        id=catalog_item.id,
        user_id=catalog_item.user_id,
        catalog_item_id=catalog_item.catalog_item_id,
        catalog_name=catalog_item.catalog_name,
        saved_at=catalog_item.saved_at,
        updated_at=catalog_item.updated_at,
        agent_name=catalog_item.agent_name,
        source_message_id=catalog_item.source_message_id,
        session_id=catalog_item.session_id,
        item_data=None  # Don't fetch on create
    )


@router.get("", response_model=List[CatalogItemResponse])
async def list_catalog_items(
    catalog_name: Optional[str] = Query(None, description="Filter by catalog name (e.g., 'property', 'job')"),
    include_data: bool = Query(False, description="Include item data from BigQuery"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all catalog items for the current user.
    
    Args:
        catalog_name: Optional filter by catalog name
        include_data: If True, fetch item data from BigQuery for each item
        current_user: Authenticated user
        db: Database session
        
    Returns:
        List of catalog items, optionally with item_data from BigQuery
    """
    query = db.query(CatalogItem).filter(CatalogItem.user_id == current_user.id)
    
    if catalog_name:
        query = query.filter(CatalogItem.catalog_name == catalog_name)
    
    items = query.order_by(CatalogItem.saved_at.desc()).all()
    
    # If include_data is True, fetch from BigQuery
    if include_data and items:
        # Group items by catalog_name for batch fetching
        items_by_catalog = {}
        for item in items:
            if item.catalog_name not in items_by_catalog:
                items_by_catalog[item.catalog_name] = []
            items_by_catalog[item.catalog_name].append(item)
        
        # Fetch data from BigQuery for each catalog
        for catalog_name_key, catalog_items in items_by_catalog.items():
            try:
                item_ids = [item.catalog_item_id for item in catalog_items]
                bigquery_data = get_catalog_items_from_bigquery(catalog_name_key, item_ids)
                
                # Create a lookup dictionary
                data_lookup = {}
                # Determine ID column based on catalog_name
                if "property" in catalog_name_key.lower():
                    id_column = "property_id"
                elif "job" in catalog_name_key.lower():
                    id_column = "job_id"
                else:
                    id_column = "id"  # Fallback
                
                for data_item in bigquery_data:
                    item_id = str(data_item.get(id_column, ""))
                    data_lookup[item_id] = data_item
                
                # Attach data to items
                for item in catalog_items:
                    item.item_data = data_lookup.get(item.catalog_item_id)
            except Exception as e:
                # If BigQuery fetch fails, continue without data
                for item in catalog_items:
                    item.item_data = None
    
    # Convert to response models
    response_items = []
    for item in items:
        response_items.append(CatalogItemResponse(
            id=item.id,
            user_id=item.user_id,
            catalog_item_id=item.catalog_item_id,
            catalog_name=item.catalog_name,
            saved_at=item.saved_at,
            updated_at=item.updated_at,
            agent_name=item.agent_name,
            source_message_id=item.source_message_id,
            session_id=item.session_id,
            item_data=getattr(item, 'item_data', None) if include_data else None
        ))
    
    return response_items


@router.delete("", status_code=status.HTTP_200_OK)
async def delete_catalog_items(
    delete_request: CatalogItemDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete multiple catalog items.
    
    Args:
        delete_request: Request containing list of item IDs to delete
        current_user: Authenticated user
        db: Database session
        
    Returns:
        Dictionary with deleted count and failed item IDs (if any)
    """
    if not delete_request.item_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="item_ids list cannot be empty"
        )
    
    # Find all items that belong to the user
    items = db.query(CatalogItem).filter(
        CatalogItem.id.in_(delete_request.item_ids),
        CatalogItem.user_id == current_user.id
    ).all()
    
    # Get IDs of items that were found
    found_ids = [item.id for item in items]
    
    # Check if any requested IDs were not found or don't belong to user
    not_found_ids = [item_id for item_id in delete_request.item_ids if item_id not in found_ids]
    
    # Delete found items
    deleted_count = 0
    for item in items:
        db.delete(item)
        deleted_count += 1
    
    db.commit()
    
    # Return result
    result = {
        "deleted_count": deleted_count,
        "deleted_ids": found_ids
    }
    
    if not_found_ids:
        result["not_found_ids"] = not_found_ids
    
    return result

