#!/usr/bin/env python3
"""
Test script to query the RTPlanDB database directly
"""

import sqlite3
from pathlib import Path

def test_database_queries():
    # Connect to the database
    db_path = '/mnt/c/ARTDaemon/Segman/Imports/Dcm/GK-Hippo/DataBase/plandb/RTPlanDB.sqlite'
    
    if not Path(db_path).exists():
        print(f"❌ Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print('=== Testing RTPlanDB Database Queries ===\n')

    # Test 1: Find all patients with 'Hippocampal' in name
    print('1. Find patients with "Hippocampal" in name:')
    cursor.execute('SELECT PatientID, PatientName, PatientSex FROM PATIENT WHERE PatientID LIKE ? LIMIT 5', ('%Hippocampal%',))
    patients = cursor.fetchall()
    for patient in patients:
        print(f'   {patient[0]} | {patient[1]} | {patient[2]}')

    print()

    # Test 2: Find MR images for specific patient
    print('2. Find MR images for patient GammaKnife-Hippocampal-001-VS:')
    cursor.execute('''
        SELECT SeriesInstanceUID, StudyDate, SeriesDate, SeriesDescription, SequenceName
        FROM MR 
        WHERE PatientID = ?
        ORDER BY StudyDate DESC, SeriesDate DESC
        LIMIT 5
    ''', ('GammaKnife-Hippocampal-001-VS',))
    mr_images = cursor.fetchall()
    for img in mr_images:
        uid_short = img[0][:30] + '...' if len(img[0]) > 30 else img[0]
        desc_short = img[3][:40] + '...' if len(img[3]) > 40 else img[3]
        seq_name = img[4] if img[4] else 'N/A'
        print(f'   {uid_short} | {img[1]} | {img[2]} | {desc_short} | {seq_name}')

    print()

    # Test 3: Find T1 sequences
    print('3. Find T1 sequences (looking for T1 in description):')
    cursor.execute('''
        SELECT PatientID, StudyDate, SeriesDescription, ProtocolName
        FROM MR 
        WHERE (SeriesDescription LIKE ? OR ProtocolName LIKE ?)
        AND PatientID LIKE ?
        LIMIT 3
    ''', ('%T1%', '%T1%', '%Hippocampal-001%'))
    t1_images = cursor.fetchall()
    for img in t1_images:
        desc_short = img[2][:50] + '...' if len(img[2]) > 50 else img[2]
        protocol_short = img[3][:30] + '...' if img[3] and len(img[3]) > 30 else (img[3] or 'N/A')
        print(f'   {img[0]} | {img[1]} | {desc_short} | {protocol_short}')

    print()

    # Test 4: Count images by modality
    print('4. Count images by modality:')
    cursor.execute('SELECT COUNT(*) FROM MR')
    mr_count = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM CT')  
    ct_count = cursor.fetchone()[0]
    print(f'   MR images: {mr_count}')
    print(f'   CT images: {ct_count}')

    print()

    # Test 5: Show date range of studies
    print('5. Date range of studies:')
    cursor.execute('SELECT MIN(StudyDate), MAX(StudyDate) FROM STUDY WHERE StudyDate IS NOT NULL AND StudyDate != ""')
    date_range = cursor.fetchone()
    print(f'   Earliest study: {date_range[0]}')
    print(f'   Latest study: {date_range[1]}')

    print()

    # Test 6: Test sequence detection patterns
    print('6. Test sequence type detection:')
    patterns = [
        ('T1 patterns', '%T1%'),
        ('T2 patterns', '%T2%'),
        ('FLAIR patterns', '%FLAIR%'),
        ('FIESTA patterns', '%FIESTA%')
    ]

    for name, pattern in patterns:
        cursor.execute('SELECT COUNT(*) FROM MR WHERE SeriesDescription LIKE ? AND PatientID LIKE ?', (pattern, '%Hippocampal%'))
        count = cursor.fetchone()[0]
        print(f'   {name}: {count} series found')

    print()

    # Test 7: Show actual file path construction
    print('7. Construct file paths for patient 001:')
    cursor.execute('''
        SELECT PatientID, SeriesInstanceUID, StudyDate, SeriesDescription
        FROM MR 
        WHERE PatientID LIKE ?
        ORDER BY StudyDate DESC
        LIMIT 3
    ''', ('%Hippocampal-001%',))
    
    for row in cursor.fetchall():
        patient_id = row[0]
        series_uid = row[1]
        study_date = row[2]
        desc = row[3][:40] + '...' if len(row[3]) > 40 else row[3]
        
        # Construct file path
        constructed_path = f"C:\\ARTDaemon\\Segman\\dcm2nifti\\{patient_id}\\{series_uid}\\image.nii.gz"
        output_path = f"C:\\ARTDaemon\\Segman\\dcm2nifti\\{patient_id}\\{series_uid}\\Vista3D\\"
        
        print(f'   Study: {study_date} | {desc}')
        print(f'   Input:  {constructed_path}')
        print(f'   Output: {output_path}')
        print()

    conn.close()
    print('✅ Database queries completed successfully!')

if __name__ == "__main__":
    test_database_queries()