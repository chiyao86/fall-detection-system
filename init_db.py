"""資料庫初始化腳本 - 在應用程式啟動前執行"""

import sys
import os
from flask_migrate import upgrade
from app import create_app

def init_database():
    """初始化資料庫，執行所有遷移"""
    print("=" * 60)
    print("開始資料庫初始化...")
    print("=" * 60)
    
    # 顯示環境資訊
    print(f"Python 版本: {sys.version}")
    print(f"工作目錄: {os.getcwd()}")
    print(f"DATABASE_URL 存在: {'DATABASE_URL' in os.environ}")
    
    app = create_app()
    
    with app.app_context():
        from app.extensions import db
        from app.models import FallEvent
        
        try:
            # 方法 1: 嘗試使用 Flask-Migrate 執行遷移
            print("\n[方法 1] 嘗試執行 Flask-Migrate 遷移...")
            try:
                upgrade()
                print("✓ Flask-Migrate 遷移成功")
            except Exception as migrate_error:
                print(f"⚠ Flask-Migrate 遷移失敗: {migrate_error}")
                print("\n[方法 2] 使用 SQLAlchemy 直接創建資料表...")
                
                # 方法 2: 直接使用 SQLAlchemy 創建資料表
                db.create_all()
                print("✓ 使用 SQLAlchemy 創建資料表成功")
            
            # 驗證資料表是否存在
            print("\n正在驗證資料表...")
            
            # 檢查資料表是否存在
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            print(f"資料庫中的資料表: {tables}")
            
            if 'fall_events' not in tables:
                raise Exception("fall_events 資料表未建立成功")
            
            # 嘗試查詢以驗證資料表可用
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
