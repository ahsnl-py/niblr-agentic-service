"""BigQuery client configuration and utilities."""

from google.cloud import bigquery
from google.cloud.exceptions import GoogleCloudError
from typing import Optional, List, Dict, Any
from .config import PROJECT_ID


def get_bigquery_client() -> bigquery.Client:
    """Get a BigQuery client instance.
    
    Uses Application Default Credentials (ADC) which works on Cloud Run
    and locally with gcloud auth application-default login.
    
    Returns:
        BigQuery client instance
    """
    return bigquery.Client(project=PROJECT_ID)


def get_catalog_item_from_bigquery(
    catalog_name: str,
    catalog_item_id: str
) -> Optional[Dict[str, Any]]:
    """Fetch a catalog item from BigQuery based on catalog name and item ID.
    
    Args:
        catalog_name: Name of the catalog ('property', 'job', etc.)
        catalog_item_id: ID of the item (property_id, job_id, etc.)
        
    Returns:
        Dictionary with item data or None if not found
        
    Raises:
        GoogleCloudError: If BigQuery query fails
    """
    client = get_bigquery_client()
    
    # Map catalog_name to BigQuery table
    table_mapping = {
        "property_listing": {
            "table_name": "niblr-agentic-service.interm_layer.property_listings_view",
            "id_column": "property_id"
        },
        "job_listing": {
            "table_name": "niblr-agentic-service.interm_layer.job_listing_view",
            "id_column": "job_id"
        }
    }
    
    table_info = table_mapping.get(catalog_name.lower())
    if not table_info:
        raise ValueError(f"Unknown catalog_name: {catalog_name}")
    
    # Build query
    query = f"""
        SELECT *
        FROM `{table_info['table_name']}`
        WHERE {table_info['id_column']} = @item_id
        LIMIT 1
    """
    
    # Use parameterized query for safety
    # Try both STRING and INT64 types since IDs can be either
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("item_id", "STRING", str(catalog_item_id))
        ]
    )
    
    try:
        query_job = client.query(query, job_config=job_config)
        results = query_job.result()
        
        # Convert first row to dictionary
        for row in results:
            return dict(row)
        
        # If no results with STRING, try with INT64 if catalog_item_id is numeric
        try:
            int_id = int(catalog_item_id)
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("item_id", "INT64", int_id)
                ]
            )
            query_job = client.query(query, job_config=job_config)
            results = query_job.result()
            
            for row in results:
                return dict(row)
        except ValueError:
            pass  # Not a number, skip INT64 attempt
        
        return None
    except GoogleCloudError as e:
        raise GoogleCloudError(f"BigQuery error: {str(e)}")


def get_catalog_items_from_bigquery(
    catalog_name: str,
    catalog_item_ids: List[str]
) -> List[Dict[str, Any]]:
    """Fetch multiple catalog items from BigQuery.
    
    Args:
        catalog_name: Name of the catalog ('property', 'job', etc.)
        catalog_item_ids: List of item IDs
        
    Returns:
        List of dictionaries with item data
    """
    if not catalog_item_ids:
        return []
    
    client = get_bigquery_client()
    
    # Map catalog_name to BigQuery table
    table_mapping = {
        "property_listing": {
            "table_name": "niblr-agentic-service.interm_layer.property_listings_view",
            "id_column": "property_id"
        },
        "job_listing": {
            "table_name": "niblr-agentic-service.interm_layer.job_listing_view",
            "id_column": "job_id"
        }
    }
    
    table_info = table_mapping.get(catalog_name.lower())
    if not table_info:
        raise ValueError(f"Unknown catalog_name: {catalog_name}")
    
    # Build query with IN clause
    # Convert list to string format for BigQuery
    ids_str = ", ".join([f"'{id}'" for id in catalog_item_ids])
    
    query = f"""
        SELECT *
        FROM `{table_info['table_name']}`
        WHERE {table_info['id_column']} IN ({ids_str})
    """
    
    try:
        query_job = client.query(query)
        results = query_job.result()
        
        # Convert rows to list of dictionaries
        items = []
        for row in results:
            items.append(dict(row))
        
        return items
    except GoogleCloudError as e:
        raise GoogleCloudError(f"BigQuery error: {str(e)}")

