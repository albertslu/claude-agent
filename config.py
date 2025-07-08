#!/usr/bin/env python3
"""
Configuration management for MCP client
Handles API key storage and retrieval
"""

import os
import json
from pathlib import Path
from typing import Optional

class Config:
    def __init__(self):
        self.config_dir = Path.home() / ".vista3d"
        self.config_file = self.config_dir / "config.json"
        self.config_dir.mkdir(exist_ok=True)
        
    def get_openai_key(self) -> Optional[str]:
        """Get OpenAI API key from environment or config file"""
        # First check environment variable
        key = os.getenv("OPENAI_API_KEY")
        if key:
            return key
            
        # Then check config file
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    return config.get("openai_api_key")
            except:
                pass
        
        return None
    
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

def main():
    """CLI for managing configuration"""
    import sys
    
    config = Config()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 config.py set-key <your_openai_key>")
        print("  python3 config.py get-key")
        print("  python3 config.py clear-key")
        print("  python3 config.py test-key")
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
            
    else:
        print(f"❌ Unknown command: {command}")

if __name__ == "__main__":
    main()