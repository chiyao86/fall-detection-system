# 🛡️ Fall Detection AI — 老人跌倒偵測系統

基於 **Flask + Groq Vision + PostgreSQL** 的老人跌倒偵測系統。上傳街景照片，AI 自動判斷畫面中是否有人跌倒，並透過 LINE / SMS 即時通知。

## Architecture

```mermaid
graph TB
    User([使用者]) -->|上傳圖片/影片| Frontend[Flask Frontend]
    Frontend -->|REST API| Upload[Upload Blueprint]
    Frontend -->|REST API| Analyze[Analyze Blueprint]
    Frontend -->|REST API| Results[Results Blueprint]

    Upload -->|儲存檔案| Disk[(uploads/)]
    Analyze -->|呼叫| VisionSvc[Vision Service]
    VisionSvc -->|Groq API| LLM[LLaMA 4 Scout]
    LLM -->|結構化 JSON| VisionSvc

    Analyze -->|寫入| DB[(PostgreSQL)]
    Analyze -->|通知判斷| NotifySvc[Notification Service]
    NotifySvc -->|LINE Bot| LINE[LINE]
    NotifySvc -->|Twilio| SMS[SMS]
    Analyze -->|選擇性| SheetsSvc[Sheets Service]
    SheetsSvc --> GSheets[Google Sheets]

    Results -->|查詢| DB
```

## 專案結構

```
├── app/
│   ├── __init__.py          # App Factory (create_app)
│   ├── config.py            # .env 設定讀取（支援 DATABASE_URL）
│   ├── extensions.py        # SQLAlchemy / Migrate
│   ├── models.py            # FallEvent ORM
│   ├── utils.py             # 共用工具（時區、時間函數等）
│   ├── api/
│   │   ├── upload.py        # 圖片/影片上傳 + 拆幀
│   │   ├── analyze.py       # 跌倒偵測分析
│   │   └── results.py       # 查詢/匯出/清除/health
│   └── services/
│       ├── vision.py        # Groq Vision 呼叫
│       ├── notification.py  # LINE + SMS + 去重
│       └── sheets.py        # Google Sheets 同步
├── migrations/              # 資料庫遷移（Alembic）
├── templates/index.html     # 前端 UI
├── uploads/                 # 上傳檔案
├── test_images/             # 測試圖片（不納入版本控制）
├── .env / .env.example      # 環境變數
├── requirements.txt
├── run.py                   # 啟動入口
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## 快速開始

### 1. 安裝依賴

```bash
pip install -r requirements.txt
```

### 2. 設定環境變數

```bash
cp .env.example .env
# 編輯 .env，填入 GROQ_API_KEY 和 DB 設定
```

### 3. 建立 PostgreSQL 資料庫

```bash
# 確保 PostgreSQL 已啟動
createdb fall_detection
```

### 4. 初始化資料庫

```bash
flask --app run:app db init
flask --app run:app db migrate -m "initial"
flask --app run:app db upgrade
```

### 5. 啟動

```bash
python run.py
# 打開瀏覽器 http://localhost:5000
```

## Docker 部署

```bash
docker-compose up -d --build
# 初始化 DB migration
docker-compose exec web flask db init
docker-compose exec web flask db migrate -m "initial"
docker-compose exec web flask db upgrade
```

## Render 部署

### 1. 建立 PostgreSQL 資料庫

在 Render 控制台建立一個 PostgreSQL 資料庫，並取得 `DATABASE_URL`。

### 2. 建立 Web Service

- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `bash start.sh`
- **Environment Variables**: 設定以下環境變數
  - `DATABASE_URL`: PostgreSQL 資料庫連線 URL（Render 會自動提供）
  - `SECRET_KEY`: Flask 密鑰
  - `GROQ_API_KEY`: Groq API 金鑰
  - `LINE_CHANNEL_ACCESS_TOKEN`: LINE Bot Token（選填）
  - `LINE_USER_ID`: LINE 使用者 ID（選填）
  - `TWILIO_ACCOUNT_SID`: Twilio SID（選填）
  - `TWILIO_AUTH_TOKEN`: Twilio Token（選填）
  - `TWILIO_FROM_NUMBER`: Twilio 發送號碼（選填）
  - `TWILIO_TO_NUMBER`: Twilio 接收號碼（選填）
  - `GOOGLE_SPREADSHEET_ID`: Google Sheets ID（選填）

### 3. 部署流程

`init_db.py` 腳本會自動：
1. 嘗試使用 Flask-Migrate 執行資料庫遷移
2. 如果遷移失敗，會使用 SQLAlchemy 直接創建資料表
3. 驗證資料表是否正確建立
4. 顯示詳細的執行日誌

部署完成後，檢查 Render 的部署日誌，確認看到：
- `✓ 資料庫初始化完成！`
- `✓ 資料表驗證成功`

### 4. 故障排除

如果部署後仍然出現 "relation fall_events does not exist" 錯誤：

**方案 A: 在 Render Shell 中手動執行**
1. 進入 Render Dashboard → 你的 Web Service
2. 點擊右上角的 "Shell"
3. 執行以下命令：
   ```bash
   python init_db.py
   ```
4. 確認看到成功訊息後，重啟服務

**方案 B: 檢查 migrations 目錄**
1. 確認 `migrations/versions/` 目錄有被推送到 GitHub
2. 執行 `git status` 確認 migrations 檔案已提交
3. 檢查 Render 日誌中是否有找到遷移檔案

**方案 C: 重置資料庫**
1. 在 Render Dashboard 刪除現有的 PostgreSQL 資料庫
2. 創建新的 PostgreSQL 資料庫
3. 更新 Web Service 的 `DATABASE_URL` 環境變數
4. 重新部署

> **注意**: `init_db.py` 會先嘗試使用 Flask-Migrate，失敗時會自動使用 SQLAlchemy 直接創建資料表，確保資料庫一定會被正確初始化。


## API Endpoints

| Method | Path             | 說明               |
| ------ | ---------------- | ------------------ |
| GET    | `/`              | 前端頁面           |
| POST   | `/api/upload`    | 上傳圖片/影片      |
| POST   | `/api/analyze`   | 啟動跌倒偵測分析   |
| GET    | `/api/status`    | 查詢處理進度       |
| GET    | `/api/results`   | 取得辨識結果       |
| GET    | `/api/events`    | 分頁查詢事件       |
| GET    | `/api/export-csv`| 匯出 CSV           |
| POST   | `/api/clear`     | 清除所有資料       |
| GET    | `/api/health`    | 健康檢查           |

## 技術棧

- **Backend**: Flask (App Factory + Blueprints)
- **Database**: PostgreSQL + SQLAlchemy + Flask-Migrate
- **AI Model**: Groq API — LLaMA 4 Scout 17B (Vision)
- **Notification**: LINE Bot SDK + Twilio SMS
- **Export**: Google Sheets API + CSV
- **Deploy**: Docker + Gunicorn