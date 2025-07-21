#!/usr/bin/env python3
"""
Generate RTPlanDB Schema JSON
Connects to the actual RTPlanDB.sqlite database and generates a complete schema JSON
Uses config.py for database path configuration
"""

import sqlite3
import json
import os
import sys
from datetime import datetime
from config import Config

class RTPlanDBSchemaGenerator:
    def __init__(self, db_path=None):
        """Initialize with database path from config or parameter"""
        if db_path:
            self.db_path = db_path
        else:
            # Use config to get database path
            try:
                config = Config()
                self.db_path = config.get_database_path()
                print(f"Using database path from config: {self.db_path}")
            except ValueError as e:
                print(f"Error: {e}")
                print("Please run: python config.py set-db-path <path_to_database>")
                sys.exit(1)
    
    def analyze_database(self):
        """Connect to database and analyze complete structure"""
        try:
            print(f"Connecting to database: {self.db_path}")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            
            if not tables:
                print("Warning: No tables found in database")
                return None
            
            schema = {
                "database_info": {
                    "name": "RTPlanDB",
                    "path": self.db_path,
                    "analyzed_on": datetime.now().isoformat(),
                    "total_tables": len(tables)
                },
                "tables": {}
            }
            
            print(f"Analyzing {len(tables)} tables...")
            
            for table in tables:
                print(f"  Analyzing table: {table}")
                
                # Get table structure
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                
                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                row_count = cursor.fetchone()[0]
                
                # Get sample data from first 3 rows to understand data types
                cursor.execute(f"SELECT * FROM {table} LIMIT 3")
                sample_data = cursor.fetchall()
                
                # Get indexes
                cursor.execute(f"PRAGMA index_list({table})")
                indexes = cursor.fetchall()
                
                # Get foreign key info
                cursor.execute(f"PRAGMA foreign_key_list({table})")
                foreign_keys = cursor.fetchall()
                
                # Build column info with actual data examples
                column_info = {}
                for i, col in enumerate(columns):
                    col_name = col[1]
                    col_type = col[2]
                    not_null = bool(col[3])
                    default_val = col[4]
                    is_pk = bool(col[5])
                    
                    # Get sample values from actual data
                    sample_values = []
                    for row in sample_data:
                        if i < len(row) and row[i] is not None:
                            sample_values.append(str(row[i])[:100])  # Limit length
                    
                    column_info[col_name] = {
                        "type": col_type,
                        "not_null": not_null,
                        "primary_key": is_pk,
                        "default_value": default_val,
                        "sample_values": sample_values[:3] if sample_values else []
                    }
                
                # Build foreign key info
                fk_info = []
                for fk in foreign_keys:
                    fk_info.append({
                        "from_column": fk[3],
                        "to_table": fk[2], 
                        "to_column": fk[4],
                        "on_update": fk[5],
                        "on_delete": fk[6]
                    })
                
                # Build index info
                index_info = []
                for idx in indexes:
                    if not idx[1].startswith('sqlite_autoindex'):  # Skip auto indexes
                        index_info.append({
                            "name": idx[1],
                            "unique": bool(idx[2])
                        })
                
                schema["tables"][table] = {
                    "row_count": row_count,
                    "columns": column_info,
                    "foreign_keys": fk_info,
                    "indexes": index_info
                }
                
                print(f"    Rows: {row_count:,}, Columns: {len(columns)}")
            
            conn.close()
            return schema
            
        except Exception as e:
            print(f"Error analyzing database: {e}")
            return None
    
    def generate_schema_json(self):
        """Generate complete schema JSON file"""
        if not os.path.exists(self.db_path):
            print(f"ERROR: Database file not found: {self.db_path}")
            return None
        
        schema = self.analyze_database()
        if not schema:
            return None
        
        # Write JSON file
        output_file = "rtplandb_schema.json"
        with open(output_file, 'w') as f:
            json.dump(schema, f, indent=2)
        
        print(f"\n✅ Schema generated: {output_file}")
        
        # Print summary
        total_tables = schema["database_info"]["total_tables"] 
        total_rows = sum(table["row_count"] for table in schema["tables"].values())
        total_columns = sum(len(table["columns"]) for table in schema["tables"].values())
        
        print(f"\n📊 Database Summary:")
        print(f"  Tables: {total_tables}")
        print(f"  Total rows: {total_rows:,}")
        print(f"  Total columns: {total_columns}")
        
        # Show table breakdown
        print(f"\n📋 Table breakdown:")
        for table_name, table_info in schema["tables"].items():
            print(f"  {table_name}: {table_info['row_count']:,} rows, {len(table_info['columns'])} columns")
        
        return output_file

def main():
    """Main function with flexible path handling"""
    db_path = None
    
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
        # Convert Windows path to WSL path if needed
        if db_path.startswith("C:\\"):
            db_path = db_path.replace("C:\\", "/mnt/c/").replace("\\", "/")
            print(f"Converted Windows path to WSL path: {db_path}")
    
    generator = RTPlanDBSchemaGenerator(db_path)
    
    result = generator.generate_schema_json()
    if result:
        print(f"\n🎉 Success! Schema JSON generated: {result}")
        print("\nThis JSON file contains the complete structure of your RTPlanDB database.")
    else:
        print("\n❌ Failed to generate schema JSON")
        sys.exit(1)

if __name__ == "__main__":
    main()