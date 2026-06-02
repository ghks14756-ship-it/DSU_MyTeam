import asyncio
import logging
from services.gsheet_service import GoogleSheetService

logging.basicConfig(level=logging.INFO)

async def main():
    print("Connecting to Google Sheets...")
    gs = GoogleSheetService()
    if not gs._is_configured():
        print("Google Sheet is not configured.")
        return

    loop = asyncio.get_running_loop()
    client = await loop.run_in_executor(None, gs._get_client)
    sheet = client.open_by_key(gs.spreadsheet_id).worksheet(gs.worksheet_programs)
    
    headers = sheet.row_values(1)
    col_name = "카테고리별 분류"
    
    if col_name not in headers:
        print(f"Adding '{col_name}' column...")
        col_index = len(headers) + 1
        # Add column if needed
        if col_index > sheet.col_count:
            sheet.add_cols(col_index - sheet.col_count)
        sheet.update_cell(1, col_index, col_name)
    else:
        col_index = headers.index(col_name) + 1
        print(f"'{col_name}' already exists at column {col_index}.")

    # Populate the existing rows with dummy categories so the UI can render them
    records = sheet.get_all_values()
    if len(records) > 1:
        categories = ["가장 활발한 프로그램", "디자인 관련", "AI 관련"]
        for i in range(1, len(records)):
            row_idx = i + 1
            existing_val = ""
            if len(records[i]) >= col_index:
                existing_val = records[i][col_index - 1]
            
            if not existing_val or existing_val.strip() == "":
                cat = categories[i % 3]
                sheet.update_cell(row_idx, col_index, cat)
                print(f"Row {row_idx}: Set category to '{cat}'")

    print("Google Sheet category update complete.")

if __name__ == "__main__":
    asyncio.run(main())
