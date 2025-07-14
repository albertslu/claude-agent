#!/usr/bin/env python3
"""
Advanced database test queries for RTPlanDB
"""

import sqlite3
from pathlib import Path

def advanced_database_tests():
    db_path = '/mnt/c/ARTDaemon/Segman/Imports/Dcm/GK-Hippo/DataBase/plandb/RTPlanDB.sqlite'
    
    if not Path(db_path).exists():
        print(f"❌ Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    print('=== Advanced RTPlanDB Database Queries ===\n')

    # Test 1: Find patients by gender and count their studies
    print('1. Patient demographics with study counts:')
    cursor.execute('''
        SELECT p.PatientID, p.PatientSex, COUNT(DISTINCT s.StudyInstanceUID) as study_count
        FROM PATIENT p
        LEFT JOIN STUDY s ON p.PatientID = s.PatientID
        WHERE p.PatientID LIKE '%Hippocampal%'
        GROUP BY p.PatientID, p.PatientSex
        ORDER BY study_count DESC
        LIMIT 5
    ''')
    for row in cursor.fetchall():
        print(f'   {row[0]} | {row[1]} | {row[2]} studies')

    print()

    # Test 2: Find MR sequences by manufacturer and date range
    print('2. MR sequences by manufacturer (2008-2009):')
    cursor.execute('''
        SELECT Manufacturer, SeriesDescription, COUNT(*) as count
        FROM MR
        WHERE StudyDate BETWEEN '20080101' AND '20091231'
        AND PatientID LIKE '%Hippocampal%'
        GROUP BY Manufacturer, SeriesDescription
        ORDER BY count DESC
        LIMIT 5
    ''')
    for row in cursor.fetchall():
        manufacturer = row[0][:20] + '...' if len(row[0]) > 20 else row[0]
        description = row[1][:30] + '...' if len(row[1]) > 30 else row[1]
        print(f'   {manufacturer} | {description} | {row[2]} series')

    print()

    # Test 3: Find studies with multiple modalities
    print('3. Studies with both MR and CT data:')
    cursor.execute('''
        SELECT s.StudyInstanceUID, s.PatientID, s.StudyDate, s.StudyDescription,
               COUNT(DISTINCT mr.SeriesInstanceUID) as mr_series,
               COUNT(DISTINCT ct.SeriesInstanceUID) as ct_series
        FROM STUDY s
        LEFT JOIN MR mr ON s.StudyInstanceUID = mr.StudyInstanceUID
        LEFT JOIN CT ct ON s.StudyInstanceUID = ct.StudyInstanceUID
        WHERE s.PatientID LIKE '%Hippocampal%'
        GROUP BY s.StudyInstanceUID, s.PatientID, s.StudyDate, s.StudyDescription
        HAVING mr_series > 0 AND ct_series > 0
        ORDER BY s.StudyDate DESC
        LIMIT 3
    ''')
    for row in cursor.fetchall():
        study_uid = row[0][:30] + '...'
        desc = row[3][:40] + '...' if len(row[3]) > 40 else row[3]
        print(f'   {study_uid} | {row[1]} | {row[2]} | {desc} | MR:{row[4]} CT:{row[5]}')

    print()

    # Test 4: Find T1 vs T2 sequence distribution by year
    print('4. T1 vs T2 sequence distribution by year:')
    cursor.execute('''
        SELECT 
            SUBSTR(StudyDate, 1, 4) as year,
            SUM(CASE WHEN (SeriesDescription LIKE '%T1%' OR ProtocolName LIKE '%T1%') THEN 1 ELSE 0 END) as t1_count,
            SUM(CASE WHEN (SeriesDescription LIKE '%T2%' OR ProtocolName LIKE '%T2%') THEN 1 ELSE 0 END) as t2_count
        FROM MR
        WHERE PatientID LIKE '%Hippocampal%'
        AND StudyDate IS NOT NULL AND StudyDate != ''
        GROUP BY SUBSTR(StudyDate, 1, 4)
        ORDER BY year
    ''')
    for row in cursor.fetchall():
        print(f'   {row[0]} | T1: {row[1]} series | T2: {row[2]} series')

    print()

    # Test 5: Find contrast vs non-contrast studies
    print('5. Contrast agent usage patterns:')
    cursor.execute('''
        SELECT 
            CASE 
                WHEN (SeriesDescription LIKE '%contrast%' OR SeriesDescription LIKE '%post%' 
                      OR SeriesDescription LIKE '%Gd%' OR SeriesDescription LIKE '%gadolinium%') 
                THEN 'With Contrast'
                ELSE 'No Contrast'
            END as contrast_status,
            COUNT(*) as series_count
        FROM MR
        WHERE PatientID LIKE '%Hippocampal%'
        AND (SeriesDescription LIKE '%T1%' OR ProtocolName LIKE '%T1%')
        GROUP BY contrast_status
    ''')
    for row in cursor.fetchall():
        print(f'   {row[0]}: {row[1]} T1 series')

    print()

    # Test 6: Find sequences with specific slice parameters
    print('6. Slice thickness analysis:')
    cursor.execute('''
        SELECT 
            SliceThickness,
            COUNT(*) as series_count,
            MIN(NumberOfSlices) as min_slices,
            MAX(NumberOfSlices) as max_slices
        FROM MR
        WHERE PatientID LIKE '%Hippocampal%'
        AND SliceThickness IS NOT NULL AND SliceThickness != ''
        GROUP BY SliceThickness
        ORDER BY CAST(SliceThickness AS REAL)
        LIMIT 5
    ''')
    for row in cursor.fetchall():
        print(f'   {row[0]}mm thickness | {row[1]} series | {row[2]}-{row[3]} slices')

    print()

    # Test 7: Find longitudinal patient data (multiple time points)
    print('7. Patients with longitudinal follow-up (multiple study dates):')
    cursor.execute('''
        SELECT PatientID, 
               COUNT(DISTINCT StudyDate) as study_dates,
               MIN(StudyDate) as first_study,
               MAX(StudyDate) as last_study,
               COUNT(*) as total_mr_series
        FROM MR
        WHERE PatientID LIKE '%Hippocampal%'
        GROUP BY PatientID
        HAVING COUNT(DISTINCT StudyDate) > 1
        ORDER BY study_dates DESC
        LIMIT 3
    ''')
    for row in cursor.fetchall():
        print(f'   {row[0]} | {row[1]} time points | {row[2]} to {row[3]} | {row[4]} MR series')

    print()

    # Test 8: Search for specific anatomical regions
    print('8. Find brain-specific sequences:')
    cursor.execute('''
        SELECT PatientID, StudyDate, SeriesDescription, BodyPartExamined
        FROM MR
        WHERE PatientID LIKE '%Hippocampal%'
        AND (SeriesDescription LIKE '%brain%' 
             OR SeriesDescription LIKE '%head%'
             OR SeriesDescription LIKE '%axial%'
             OR BodyPartExamined LIKE '%BRAIN%')
        ORDER BY StudyDate DESC
        LIMIT 5
    ''')
    for row in cursor.fetchall():
        desc = row[2][:50] + '...' if len(row[2]) > 50 else row[2]
        body_part = row[3] if row[3] else 'N/A'
        print(f'   {row[0]} | {row[1]} | {desc} | {body_part}')

    print()

    # Test 9: Find patients with treatment planning data
    print('9. Patients with RT planning data:')
    cursor.execute('''
        SELECT DISTINCT p.PatientID, p.PatientSex,
               COUNT(DISTINCT rt.SOPInstanceUID) as rt_plans
        FROM PATIENT p
        JOIN RTPLANDB rt ON p.PatientID = rt.PatientID
        WHERE p.PatientID LIKE '%Hippocampal%'
        GROUP BY p.PatientID, p.PatientSex
        ORDER BY rt_plans DESC
        LIMIT 5
    ''')
    for row in cursor.fetchall():
        print(f'   {row[0]} | {row[1]} | {row[2]} RT plans')

    print()

    # Test 10: Advanced sequence pattern matching
    print('10. Advanced sequence pattern detection:')
    sequences = {
        'T1 MPRAGE': "SeriesDescription LIKE '%MPRAGE%'",
        'T1 FSPGR': "SeriesDescription LIKE '%FSPGR%'", 
        'T1 TFL3D': "SequenceName LIKE '%tfl3d%'",
        'T2 TSE': "SequenceName LIKE '%tse%' OR SeriesDescription LIKE '%TSE%'",
        'FIESTA': "SeriesDescription LIKE '%FIESTA%'"
    }
    
    for seq_name, condition in sequences.items():
        cursor.execute(f'''
            SELECT COUNT(*) 
            FROM MR 
            WHERE PatientID LIKE '%Hippocampal%' 
            AND ({condition})
        ''')
        count = cursor.fetchone()[0]
        print(f'   {seq_name}: {count} series found')

    conn.close()
    print('\n✅ Advanced database queries completed successfully!')

if __name__ == "__main__":
    advanced_database_tests()