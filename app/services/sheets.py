"""Google Sheets service — 選擇性匯出辨識結果"""

from flask import current_app


def _get_service():
    """建立 Google Sheets API 服務連線"""
    account_file = current_app.config.get("GOOGLE_SERVICE_ACCOUNT_FILE", "")
    if not account_file:
        return None

    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            account_file,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        return build("sheets", "v4", credentials=creds)
    except Exception as e:
        current_app.logger.error(f"Google Sheets 連線失敗: {e}")
        return None


def _get_first_sheet_title(service, spreadsheet_id: str) -> str:
    """取得第一個分頁名稱"""
    try:
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = meta.get("sheets", [])
        if sheets:
            return sheets[0]["properties"]["title"]
    except Exception as e:
        current_app.logger.error(f"取得分頁名稱失敗: {e}")
    return "Sheet1"


def write_to_google_sheet(timestamp: str, filename: str, result: str) -> bool:
    """將辨識結果寫入 Google Sheets"""
    spreadsheet_id = current_app.config.get("GOOGLE_SPREADSHEET_ID", "")
    if not spreadsheet_id:
        return False

    service = _get_service()
    if not service:
        return False

    try:
        sheet_title = _get_first_sheet_title(service, spreadsheet_id)
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_title}!A:C",
            valueInputOption="USER_ENTERED",
            body={"values": [[timestamp, filename, result]]},
        ).execute()
        current_app.logger.info(f"已寫入 Google Sheets: {filename}")
        return True
    except Exception as e:
        current_app.logger.error(f"Google Sheets 寫入失敗: {e}")
        return False
