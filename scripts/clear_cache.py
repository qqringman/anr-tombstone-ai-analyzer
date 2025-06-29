#!/usr/bin/env python3
"""
快取清理腳本
"""
import sys
import os
import shutil
import asyncio
from pathlib import Path
from datetime import datetime, timedelta

# 將專案根目錄加入 Python 路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.cache_manager import CacheManager
from src.storage.result_storage import ResultStorage
from src.config.system_config import get_system_config
from src.utils.logger import get_logger

logger = get_logger(__name__)

class CacheCleaner:
    """快取清理器"""
    
    def __init__(self):
        self.config = get_system_config()
        self.cache_manager = CacheManager(
            cache_dir=self.config.cache.directory,
            ttl_hours=self.config.cache.ttl_hours
        )
        self.storage = ResultStorage()
    
    async def clean_all(self, force: bool = False):
        """清理所有快取"""
        print("🧹 Starting cache cleanup...\n")
        
        # 1. 清理記憶體快取
        await self.clean_memory_cache()
        
        # 2. 清理磁碟快取
        await self.clean_disk_cache(force)
        
        # 3. 清理資料庫快取
        await self.clean_database_cache()
        
        # 4. 清理臨時檔案
        await self.clean_temp_files()
        
        print("\n✅ Cache cleanup completed!")
    
    async def clean_memory_cache(self):
        """清理記憶體快取"""
        print("💾 Cleaning memory cache...")
        
        try:
            # 獲取快取統計
            stats_before = self.cache_manager.get_stats()
            
            # 清理過期項目
            await self.cache_manager.clear_expired()
            
            stats_after = self.cache_manager.get_stats()
            
            print(f"  - Memory items before: {stats_before['memory_items']}")
            print(f"  - Memory items after: {stats_after['memory_items']}")
            print(f"  - Items removed: {stats_before['memory_items'] - stats_after['memory_items']}")
            
        except Exception as e:
            print(f"  ❌ Error cleaning memory cache: {e}")
            logger.error(f"Memory cache cleanup error: {e}")
    
    async def clean_disk_cache(self, force: bool = False):
        """清理磁碟快取"""
        print("\n📁 Cleaning disk cache...")
        
        cache_dir = Path(self.config.cache.directory)
        
        if not cache_dir.exists():
            print("  - Cache directory does not exist")
            return
        
        try:
            total_size = 0
            removed_count = 0
            kept_count = 0
            
            # 遍歷所有快取檔案
            for cache_file in cache_dir.rglob("*.cache"):
                file_size = cache_file.stat().st_size
                total_size += file_size
                
                if force:
                    # 強制刪除所有快取
                    cache_file.unlink()
                    removed_count += 1
                else:
                    # 檢查檔案年齡
                    file_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
                    if file_age > timedelta(hours=self.config.cache.ttl_hours):
                        cache_file.unlink()
                        removed_count += 1
                    else:
                        kept_count += 1
            
            # 清理空目錄
            for subdir in cache_dir.rglob("*"):
                if subdir.is_dir() and not any(subdir.iterdir()):
                    subdir.rmdir()
            
            print(f"  - Total cache size: {self._format_size(total_size)}")
            print(f"  - Files removed: {removed_count}")
            print(f"  - Files kept: {kept_count}")
            
        except Exception as e:
            print(f"  ❌ Error cleaning disk cache: {e}")
            logger.error(f"Disk cache cleanup error: {e}")
    
    async def clean_database_cache(self):
        """清理資料庫中的舊記錄"""
        print("\n🗄️  Cleaning database cache...")
        
        try:
            # 清理超過 30 天的記錄
            await self.storage.cleanup_old_records(days=30)
            
            print("  - Old analysis records cleaned")
            print("  - Old API logs cleaned")
            print("  - Expired sessions cleaned")
            
        except Exception as e:
            print(f"  ❌ Error cleaning database: {e}")
            logger.error(f"Database cleanup error: {e}")
    
    async def clean_temp_files(self):
        """清理臨時檔案"""
        print("\n🗑️  Cleaning temporary files...")
        
        temp_dirs = [
            Path("logs"),
            Path("uploads"),
            Path("/tmp") / "anr_analyzer"  # 系統臨時目錄
        ]
        
        for temp_dir in temp_dirs:
            if not temp_dir.exists():
                continue
            
            try:
                removed_count = 0
                total_size = 0
                
                # 清理舊的日誌檔案
                if temp_dir.name == "logs":
                    for log_file in temp_dir.glob("*.log*"):
                        if "current" not in log_file.name:  # 不刪除當前日誌
                            file_age = datetime.now() - datetime.fromtimestamp(log_file.stat().st_mtime)
                            if file_age > timedelta(days=7):  # 7 天以上的日誌
                                total_size += log_file.stat().st_size
                                log_file.unlink()
                                removed_count += 1
                
                # 清理上傳的檔案
                elif temp_dir.name == "uploads":
                    for upload_file in temp_dir.glob("*"):
                        file_age = datetime.now() - datetime.fromtimestamp(upload_file.stat().st_mtime)
                        if file_age > timedelta(hours=24):  # 24 小時以上的上傳
                            total_size += upload_file.stat().st_size
                            if upload_file.is_file():
                                upload_file.unlink()
                            elif upload_file.is_dir():
                                shutil.rmtree(upload_file)
                            removed_count += 1
                
                if removed_count > 0:
                    print(f"  - {temp_dir}: Removed {removed_count} files ({self._format_size(total_size)})")
                
            except Exception as e:
                print(f"  ❌ Error cleaning {temp_dir}: {e}")
                logger.error(f"Temp file cleanup error in {temp_dir}: {e}")
    
    async def get_cache_report(self) -> dict:
        """獲取快取報告"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'cache_stats': self.cache_manager.get_stats(),
            'disk_usage': {},
            'database_stats': {}
        }
        
        # 計算磁碟使用
        cache_dir = Path(self.config.cache.directory)
        if cache_dir.exists():
            total_size = sum(f.stat().st_size for f in cache_dir.rglob("*") if f.is_file())
            file_count = sum(1 for f in cache_dir.rglob("*") if f.is_file())
            
            report['disk_usage'] = {
                'total_size': total_size,
                'total_size_formatted': self._format_size(total_size),
                'file_count': file_count,
                'cache_directory': str(cache_dir)
            }
        
        return report
    
    def _format_size(self, size_bytes: int) -> str:
        """格式化檔案大小"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} TB"

async def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Clean system cache')
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force clean all cache (ignore TTL)'
    )
    parser.add_argument(
        '--report',
        action='store_true',
        help='Show cache report without cleaning'
    )
    parser.add_argument(
        '--yes',
        '-y',
        action='store_true',
        help='Skip confirmation prompt'
    )
    
    args = parser.parse_args()
    
    cleaner = CacheCleaner()
    
    if args.report:
        # 只顯示報告
        report = await cleaner.get_cache_report()
        
        print("📊 Cache Report")
        print("="*50)
        print(f"Timestamp: {report['timestamp']}")
        print(f"\nMemory Cache:")
        print(f"  - Items: {report['cache_stats']['memory_items']}")
        print(f"  - Hit Rate: {report['cache_stats']['hit_rate']:.1%}")
        
        if report['disk_usage']:
            print(f"\nDisk Cache:")
            print(f"  - Size: {report['disk_usage']['total_size_formatted']}")
            print(f"  - Files: {report['disk_usage']['file_count']}")
            print(f"  - Directory: {report['disk_usage']['cache_directory']}")
        
        return
    
    # 確認清理
    if not args.yes:
        if args.force:
            prompt = "⚠️  This will remove ALL cache files. Continue? (yes/no): "
        else:
            prompt = "This will remove expired cache files. Continue? (yes/no): "
        
        response = input(prompt)
        if response.lower() != 'yes':
            print("Operation cancelled.")
            return
    
    # 執行清理
    await cleaner.clean_all(force=args.force)

if __name__ == "__main__":
    asyncio.run(main())