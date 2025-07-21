#!/usr/bin/env python3
"""
Test the updated query_patient_images function
"""

import sys
import json
from vista3d_mcp_server import Vista3DMCPServer

def test_query_function():
    """Test the query function with actual schema"""
    
    # Initialize server
    server = Vista3DMCPServer()
    
    print(f"Testing query_patient_images with schema-based approach...")
    print(f"Database path: {server.db_path}")
    
    # Test 1: Query MR images for a specific patient
    print("\n=== Test 1: Query MR images for patient GammaKnife-Hippocampal-001 ===")
    results = server.query_patient_images(
        patient_id="GammaKnife-Hippocampal-001",
        modality="MR"
    )
    
    print(f"Results: {len(results)} items")
    if results and "error" not in results[0]:
        print("✅ Success! Sample result:")
        sample = results[0]
        for key, value in sample.items():
            if isinstance(value, str) and len(str(value)) > 50:
                print(f"  {key}: {str(value)[:50]}...")
            else:
                print(f"  {key}: {value}")
    elif results:
        print(f"❌ Error: {results[0]}")
    else:
        print("❌ No results returned")
    
    # Test 2: Query CT images
    print("\n=== Test 2: Query CT images (first patient only) ===")
    ct_results = server.query_patient_images(
        modality="CT",
        patient_id="GammaKnife-Hippocampal-001"
    )
    
    print(f"CT Results: {len(ct_results)} items")
    if ct_results and "error" not in ct_results[0]:
        print("✅ CT query successful!")
        print(f"Sample CT result keys: {list(ct_results[0].keys())}")
    elif ct_results:
        print(f"❌ CT Error: {ct_results[0]}")
    
    # Test 3: Test with sequence type filtering
    print("\n=== Test 3: Query T1 sequences ===")
    t1_results = server.query_patient_images(
        modality="MR",
        sequence_type="T1",
        patient_id="GammaKnife-Hippocampal-001"
    )
    
    print(f"T1 Results: {len(t1_results)} items")
    if t1_results and "error" not in t1_results[0]:
        print("✅ T1 sequence filtering successful!")
        if 'classified_sequences' in t1_results[0]:
            print(f"Sample classification: {t1_results[0]['classified_sequences']}")
    elif t1_results:
        print(f"❌ T1 Error: {t1_results[0]}")

if __name__ == "__main__":
    test_query_function()