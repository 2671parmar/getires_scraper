import os
import time
import pandas as pd
from bs4 import BeautifulSoup
from firecrawl import FirecrawlApp
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '1itNviaLE7Ra1Lnq2fyMHJ4GbRN-ADuHexxndaHO5D30'  # Replace with your spreadsheet ID
FIRECRAWL_API_KEY = 'fc-5f57218a82f540ae8e4e59cd37ae6320'  # Your Firecrawl API key

def get_google_sheets_credentials():
    """Get Google Sheets API credentials using service account."""
    try:
        credentials = service_account.Credentials.from_service_account_file(
            'credentials.json',
            scopes=SCOPES
        )
        return credentials
    except Exception as e:
        print(f"Error loading credentials: {e}")
        return None

def update_google_sheet(data, sheet_name):
    """Update Google Sheet with scraped data."""
    try:
        creds = get_google_sheets_credentials()
        service = build('sheets', 'v4', credentials=creds)
        df = pd.DataFrame(data)
        values = [df.columns.tolist()] + df.values.tolist()
        body = {'values': values}
        result = service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f'{sheet_name}!A1',
            valueInputOption='RAW',
            body=body
        ).execute()
        print(f"Updated {result.get('updatedCells')} cells in {sheet_name}")
    except HttpError as error:
        print(f"An error occurred: {error}")

def scrape_prioritytire_products():
    """Scrape product information from all pages of PriorityTire's shop-all section using Firecrawl."""
    base_url = 'https://www.prioritytire.com/shop-all?p={}'
    products = []
    page = 1

    # Initialize Firecrawl with the API key
    app = FirecrawlApp(api_key=FIRECRAWL_API_KEY)

    try:
        while True:
            url = base_url.format(page)
            print(f"Scraping PriorityTire page {page}...")

            # First attempt: Scrape without stealth mode
            try:
                scrape_result = app.scrape_url(url)
                status_code = scrape_result.get("metadata", {}).get("statusCode", 200)
                if status_code in [401, 403, 500]:
                    print(f"Got status code {status_code} on page {page}, retrying with stealth proxy...")
                    # Retry with stealth proxy
                    scrape_result = app.scrape_url(url, proxy="stealth")
                    print(f"Stealth proxy used for page {page} (5 credits).")
                
                if 'content' not in scrape_result:
                    print(f"Failed to scrape page {page}: No content returned.")
                    break
                html_content = scrape_result['content']
            except Exception as e:
                print(f"Initial scrape failed for page {page}: {e}, retrying with stealth proxy...")
                try:
                    scrape_result = app.scrape_url(url, proxy="stealth")
                    print(f"Stealth proxy used for page {page} (5 credits).")
                    if 'content' not in scrape_result:
                        print(f"Failed to scrape page {page} with stealth proxy: No content returned.")
                        break
                    html_content = scrape_result['content']
                except Exception as e:
                    print(f"Stealth proxy also failed for page {page}: {e}")
                    break

            # Parse the HTML content with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            product_elements = soup.find_all('li', class_='item product product-item')

            if not product_elements:
                print(f"No products found on page {page}. Stopping.")
                break

            for product in product_elements:
                # Product Photo
                img_tag = product.find('img', class_='product-image-photo')
                product_photo = img_tag['src'] if img_tag else ''
                # Product Name (contains Brand, Model, Size)
                name_tag = product.find('strong', class_='product name product-item-name')
                name_text = name_tag.text.strip() if name_tag else ''
                # Brand (from logo alt or table)
                brand = ''
                brand_img = product.find('div', class_='product-brand')
                if brand_img and brand_img.find('img'):
                    brand = brand_img.find('img').get('alt', '').replace(' Logo', '').strip()
                # Model, Size (from table or name)
                model = ''
                size = ''
                # Price
                price = ''
                price_span = product.find('span', class_='price')
                if price_span:
                    price = price_span.text.strip()
                # Table attributes
                specs = {}
                specs_table = product.find('table', class_='data table additional-attributes')
                if specs_table:
                    for row in specs_table.find_all('tr'):
                        th = row.find('th')
                        td = row.find('td')
                        if th and td:
                            specs[th.text.strip()] = td.text.strip()
                # Extract fields from specs
                sku = specs.get('SKU', '')
                model = specs.get('Model', '')
                size = specs.get('Size', '')
                load_index = specs.get('Load Index', '')
                speed_rating = specs.get('Speed Rating', '')
                season = specs.get('Season', '')
                performance = specs.get('Performance', '')
                treadlife = specs.get('Treadlife/Mileage', '')
                # Fallbacks if not in table
                if not brand:
                    brand = specs.get('Brand', '')
                if not model and name_text:
                    parts = name_text.split()
                    if len(parts) > 2:
                        model = ' '.join(parts[1:-1])
                if not size and name_text:
                    size = name_text.split()[-1]
                product_data = {
                    'SKU': sku,
                    'Brand': brand,
                    'Model': model,
                    'Size': size,
                    'Price': price,
                    'Product Photo': product_photo,
                    'Load Index': load_index,
                    'Speed Rating': speed_rating,
                    'Season': season,
                    'Performance': performance,
                    'Treadlife/Mileage': treadlife
                }
                products.append(product_data)

            page += 1
            time.sleep(2)  # Add delay between pages to respect rate limits

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        print(f"Scraped {len(products)} products.")

    return products

def main():
    print("Scraping PriorityTire products using Firecrawl...")
    prioritytire_products = scrape_prioritytire_products()
    if prioritytire_products:
        print(f"Found {len(prioritytire_products)} PriorityTire products")
        print("Updating PriorityTire sheet...")
        update_google_sheet(prioritytire_products, 'PriorityTire')
        print("PriorityTire data updated!")
    else:
        print("No PriorityTire data found or error occurred during scraping")

if __name__ == '__main__':
    main()