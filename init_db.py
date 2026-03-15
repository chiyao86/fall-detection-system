"""資料庫初始化腳本 - 在應用程式啟動前執行"""

import sys
import time
from flask_migrate import upgrade
from app import create_app

def init_database():
    """初始化資料庫，執行所有遷移"""
    print("=" * 60)
    print("開始資料庫初始化...")
    print("=" * 60)
    
    app = create_app()
    
    with app.app_context():
        try:
            # 執行資料庫遷移
            print("正在執行資料庫遷移...")
            upgrade()
            print("✓ 資料庫遷移成功完成")
            
            # 驗證資料表是否存在
            from app.extensions import db
            from app.models import FallEvent
            
            # 嘗試查詢以驗證資料表存在
            count = FallEvent.query.count()
            print(f"✓ 資料表驗證成功 - 目前有 {count} 筆記錄")
            
            print("=" * 60)
            print("資料庫初始化完成！")
            print("=" * 60)
            return 0
            
        except Exception as e:
            print(f"✗ 資料庫初始化失敗: {e}")
            print("=" * 60)
            import traceback
            traceback.print_exc()
            return 1

if __name__ == "__main__":
    exit_code = init_database()
    sys.exit(exit_code)
