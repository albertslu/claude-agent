#!/usr/bin/env python3
"""
Configuration management for MCP client
Handles API key storage and retrieval
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict

class Config:
    def __init__(self):
        self.config_dir = Path.home() / ".vista3d"
        self.config_file = self.config_dir / "config.json"
        self.config_dir.mkdir(exist_ok=True)
        
    def get_openai_key(self) -> Optional[str]:
        """Get OpenAI API key from config file or environment"""
        # First check config file
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    key = config.get("openai_api_key")
                    if key:
                        return key
            except:
                pass
        
        # Then check environment variable
        key = os.getenv("OPENAI_API_KEY")
        if key:
            return key
        
        return None
    
    def get_base_paths(self) -> Dict[str, str]:
        """Get base paths from config file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    base_paths = config.get("base_paths", {})
                    if base_paths:
                        return base_paths
            except:
                pass
        
        raise ValueError("No base_paths found in config file. Please run: python config.py set-paths")
    
    def get_database_path(self) -> str:
        """Get database path from config file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    db_path = config.get("database_path")
                    if db_path:
                        return db_path
            except:
                pass
        
        raise ValueError("No database_path found in config file. Please run: python config.py set-db-path")
    
    def set_openai_key(self, key: str):
        """Save OpenAI API key to config file"""
        config = {}
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
            except:
                pass
        
        config["openai_api_key"] = key
        
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        # Set secure permissions
        os.chmod(self.config_file, 0o600)
        
    def clear_openai_key(self):
        """Remove OpenAI API key from config"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                
                if "openai_api_key" in config:
                    del config["openai_api_key"]
                    
                with open(self.config_file, 'w') as f:
                    json.dump(config, f, indent=2)
            except:
                pass
    
    def set_database_path(self, path: str):
        """Save database path to config file"""
        config = {}
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
            except:
                pass
        
        config["database_path"] = path
        
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    def set_base_paths(self, paths: Dict[str, str]):
        """Save base paths to config file"""
        config = {}
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
            except:
                pass
        
        config["base_paths"] = paths
        
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)

def main():
    """CLI for managing configuration"""
    import sys
    
    config = Config()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python config.py set-key <your_openai_key>")
        print("  python config.py get-key")
        print("  python config.py clear-key")
        print("  python config.py test-key")
        print("  python config.py set-db-path <path_to_database>")
        print("  python config.py set-paths")
        print("  python config.py show-config")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "set-key":
        if len(sys.argv) < 3:
            print("Usage: python3 config.py set-key <your_openai_key>")
            sys.exit(1)
        
        key = sys.argv[2]
        config.set_openai_key(key)
        print(f"✅ OpenAI API key saved to {config.config_file}")
        print("🔒 File permissions set to 600 (owner read/write only)")
        
    elif command == "get-key":
        key = config.get_openai_key()
        if key:
            # Show only first 10 and last 4 characters for security
            masked_key = key[:10] + "..." + key[-4:]
            print(f"🔑 OpenAI API key: {masked_key}")
        else:
            print("❌ No OpenAI API key found")
            
    elif command == "clear-key":
        config.clear_openai_key()
        print("✅ OpenAI API key cleared")
        
    elif command == "test-key":
        key = config.get_openai_key()
        if not key:
            print("❌ No OpenAI API key found")
            sys.exit(1)
        
        print("🧪 Testing OpenAI API key...")
        try:
            from openai import OpenAI
            client = OpenAI(api_key=key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=5
            )
            print("✅ OpenAI API key is working!")
            print(f"📝 Response: {response.choices[0].message.content}")
        except Exception as e:
            print(f"❌ OpenAI API key test failed: {e}")
    
    elif command == "set-db-path":
        if len(sys.argv) < 3:
            print("Usage: python config.py set-db-path <path_to_database>")
            sys.exit(1)
        
        db_path = sys.argv[2]
        config.set_database_path(db_path)
        print(f"✅ Database path saved: {db_path}")
    
    elif command == "set-paths":
        print("Setting up base paths...")
        print("Enter paths for your system:")
        
        dcm2nifti_base = input("DCM2NIFTI base path (e.g., C:\\ARTDaemon\\Segman\\dcm2nifti): ")
        tasks_base = input("Tasks base path (e.g., C:\\ARTDaemon\\Segman\\Tasks): ")
        tasks_history = input("Tasks history path (e.g., C:\\ARTDaemon\\Segman\\TasksHistory): ")
        
        paths = {
            "dcm2nifti_base": dcm2nifti_base,
            "tasks_base": tasks_base,
            "tasks_history": tasks_history
        }
        
        config.set_base_paths(paths)
        print("✅ Base paths saved!")
    
    elif command == "show-config":
        print("Current configuration:")
        print(f"Config file: {config.config_file}")
        
        if config.config_file.exists():
            with open(config.config_file, 'r') as f:
                config_data = json.load(f)
                print(json.dumps(config_data, indent=2))
        else:
            print("❌ Config file not found")
            
    else:
        print(f"❌ Unknown command: {command}")

if __name__ == "__main__":
    main()