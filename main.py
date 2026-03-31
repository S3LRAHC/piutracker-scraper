import gspread
from playwright.sync_api import sync_playwright
import difflib
import time

def run_piu_scraper(tasks):
    # ==========================================
    # 1. GSPREAD: PULL DATA ONCE
    # ==========================================
    print("Connecting to Google Sheets...")
    gc = gspread.service_account(filename='credentials.json')
    sh = gc.open("Pump It Up Score Tracker").sheet1 
    
    # We download the sheet once so we don't spam Google's API
    all_rows = sh.get_all_records()
    sheet_song_names = [str(row['Song Name']) for row in all_rows if row.get('Song Name')]
    
    updates = [] # This will hold all our final sheet edits

    # ==========================================
    # 2. PLAYWRIGHT: LOOP THROUGH TASKS
    # ==========================================
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) 
        page = browser.new_page()
        
        print("Navigating to PIU Tracker...")
        page.goto("https://www.piutracker.app/user/CHARLEY/3085/breakdown")
        
        input_xpath = '//*[@id="navtabs-tabpane-breakdown"]/div[1]/div[3]/div/input'
        select_xpath = '//*[@id="navtabs-tabpane-breakdown"]/div[1]/div[2]/div/select'
        sort_header_xpath = '//*[@id="navtabs-tabpane-breakdown"]/div[4]/div/div/div/div/div/div/div/div/div/div[1]/div[2]/div[1]/div[2]/div/div[1]/div[3]/div[3]/div/div'
        
        page.wait_for_selector(f'xpath={input_xpath}')
        
        # Loop through whatever the user told us to do
        for task in tasks:
            mode = task['mode']    # 'Doubles' or 'Singles'
            level = str(task['level']) # e.g. '21'
            
            print(f"\n--- Scraping {mode} Level {level} ---")
            
            # 1. Apply filters for this specific task
            page.fill(f'xpath={input_xpath}', level)
            page.select_option(f'xpath={select_xpath}', label=mode)
            
            # 2. Click header to force table refresh and wait
            page.click(f'xpath={sort_header_xpath}')
            page.wait_for_timeout(2500) 
            
            # 3. Extract the scores
            scraped_data = {}
            rows = page.locator('div[role="row"]').all() 
            
            for row in rows[1:]: 
                text_content = row.inner_text().split('\n')
                if len(text_content) >= 3:
                    raw_score = text_content[1].replace(',', '').strip()
                    song_name = text_content[2].strip()
                    
                    if raw_score.isdigit():
                        scraped_data[song_name] = int(raw_score)

            print(f"Scraped {len(scraped_data)} scores. Matching to spreadsheet...")

            # 4. Determine what "Chart Type" we are looking for in the sheet
            expected_chart_types = ['D', 'HD'] if mode == 'Doubles' else ['S']
            
            # 5. Match the data for this specific task
            for scraped_song, scraped_score in scraped_data.items():
                matches = difflib.get_close_matches(scraped_song, sheet_song_names, n=1, cutoff=0.7)
                
                if matches:
                    best_match = matches[0]
                    
                    # Search the sheet rows for this song AND the correct mode/level
                    for i, row in enumerate(all_rows):
                        if row.get('Song Name') == best_match:
                            chart_type = str(row.get('Chart Type', '')).strip()
                            difficulty = str(row.get('Difficulty', '')).strip()
                            
                            # Check if it's the correct difficulty AND the correct S/D/HD type
                            if difficulty == level and chart_type in expected_chart_types:
                                row_number = i + 2  
                                updates.append({'range': f'E{row_number}', 'values': [[scraped_score]]})
                                print(f"✅ Match: '{scraped_song}' -> Row {row_number} | Score: {scraped_score}")
                                break # Stop searching the sheet, we found the exact row
                else:
                    print(f"❌ No close match found for: {scraped_song}")

        # Finished all tasks, close the browser
        browser.close()

    # ==========================================
    # 3. GSPREAD: BATCH UPDATE ALL AT ONCE
    # ==========================================
    if updates:
        print(f"\nSending {len(updates)} total updates to Google Sheets...")
        sh.batch_update(updates)
        print("Update completely finished!")
    else:
        print("\nNo new scores to update.")

# ==========================================
# RUN THE SCRIPT
# ==========================================
if __name__ == "__main__":
    
    # EDIT THIS LIST TO DO WHATEVER SEQUENCE YOU WANT!
    tasks_to_run = [
        {'mode': 'Doubles', 'level': 22},
        {'mode': 'Doubles', 'level': 23},
        {'mode': 'Doubles', 'level': 24},
        {'mode': 'Singles', 'level': 21},
        {'mode': 'Singles', 'level': 22},
        {'mode': 'Singles', 'level': 23},
        {'mode': 'Singles', 'level': 24}
    ]
    
    run_piu_scraper(tasks_to_run)
