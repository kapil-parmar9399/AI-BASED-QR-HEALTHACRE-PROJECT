"""
Database backup utility for Swasthya Healthcare System
Provides automatic and manual backup functionality
"""
import os
import json
import gzip
from datetime import datetime
from pathlib import Path
from pymongo import MongoClient
from typing import Optional
from config import config

class DatabaseBackup:
    """Handle MongoDB backup and restore operations"""
    
    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        self.mongo_uri = config.MONGODB_URI
        self.database_name = config.DATABASE_NAME
    
    def backup(self) -> str:
        """
        Create a full database backup
        Returns the backup file path
        """
        try:
            client = MongoClient(self.mongo_uri)
            db = client[self.database_name]
            
            # Get all collections
            backup_data = {}
            collections = db.list_collection_names()
            
            for collection_name in collections:
                collection = db[collection_name]
                # Convert ObjectId to string for JSON serialization
                backup_data[collection_name] = []
                for doc in collection.find():
                    doc['_id'] = str(doc['_id'])
                    # Convert datetime to ISO format
                    for key, value in doc.items():
                        if isinstance(value, datetime):
                            doc[key] = value.isoformat()
                    backup_data[collection_name].append(doc)
            
            client.close()
            
            # Create backup file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"backup_{self.database_name}_{timestamp}.json.gz"
            backup_path = self.backup_dir / backup_filename
            
            # Write compressed backup
            with gzip.open(backup_path, 'wt', encoding='utf-8') as f:
                json.dump(backup_data, f, indent=2, default=str)
            
            print(f"✅ Backup created: {backup_path}")
            return str(backup_path)
        
        except Exception as e:
            print(f"❌ Backup failed: {e}")
            raise
    
    def restore(self, backup_file: str, drop_existing: bool = False) -> bool:
        """
        Restore database from backup file
        
        Args:
            backup_file: Path to backup file
            drop_existing: If True, drops existing collections before restore
        """
        try:
            if not Path(backup_file).exists():
                raise FileNotFoundError(f"Backup file not found: {backup_file}")
            
            client = MongoClient(self.mongo_uri)
            db = client[self.database_name]
            
            # Drop existing collections if requested
            if drop_existing:
                for collection_name in db.list_collection_names():
                    db[collection_name].drop()
                print("⚠️  Existing collections dropped")
            
            # Read backup
            with gzip.open(backup_file, 'rt', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            # Restore data
            for collection_name, documents in backup_data.items():
                collection = db[collection_name]
                if documents:
                    # Convert string IDs back (MongoDB will handle _id)
                    for doc in documents:
                        if '_id' in doc:
                            try:
                                from bson import ObjectId
                                doc['_id'] = ObjectId(doc['_id'])
                            except:
                                pass  # Keep as string if conversion fails
                    
                    collection.insert_many(documents)
            
            client.close()
            print(f"✅ Database restored from: {backup_file}")
            return True
        
        except Exception as e:
            print(f"❌ Restore failed: {e}")
            raise
    
    def list_backups(self) -> list:
        """List all available backups"""
        backups = []
        for file in sorted(self.backup_dir.glob("backup_*.json.gz"), reverse=True):
            file_stat = file.stat()
            backups.append({
                "filename": file.name,
                "path": str(file),
                "size_mb": round(file_stat.st_size / (1024 * 1024), 2),
                "created": datetime.fromtimestamp(file_stat.st_ctime).isoformat(),
            })
        return backups
    
    def cleanup_old_backups(self, keep_days: int = 30, keep_count: int = 10):
        """
        Clean up old backups
        
        Args:
            keep_days: Keep backups newer than this many days
            keep_count: Always keep at least this many recent backups
        """
        import shutil
        from datetime import timedelta
        
        backups = self.list_backups()
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        
        deleted = 0
        for i, backup in enumerate(backups):
            # Don't delete if we're within keep_count recent backups
            if i < keep_count:
                continue
            
            backup_date = datetime.fromisoformat(backup['created'])
            if backup_date < cutoff_date:
                try:
                    Path(backup['path']).unlink()
                    deleted += 1
                    print(f"🗑️  Deleted old backup: {backup['filename']}")
                except Exception as e:
                    print(f"⚠️  Failed to delete {backup['filename']}: {e}")
        
        print(f"✅ Cleanup complete: {deleted} old backup(s) removed")
        return deleted


def backup_database():
    """Convenience function to backup database"""
    backup = DatabaseBackup()
    return backup.backup()


def list_backups():
    """Convenience function to list backups"""
    backup = DatabaseBackup()
    return backup.list_backups()


if __name__ == "__main__":
    import sys
    
    backup = DatabaseBackup()
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "backup":
            backup.backup()
        elif command == "list":
            backups = backup.list_backups()
            for b in backups:
                print(f"{b['filename']} ({b['size_mb']}MB) - {b['created']}")
        elif command == "cleanup":
            backup.cleanup_old_backups()
        else:
            print("Usage: python backup.py [backup|list|cleanup]")
    else:
        print("Usage: python backup.py [backup|list|cleanup]")
