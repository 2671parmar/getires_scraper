import os
import json
import requests
from bs4 import BeautifulSoup
import pandas as pd
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import time
import re
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '1itNviaLE7Ra1Lnq2fyMHJ4GbRN-ADuHexxndaHO5D30'  # Replace with your spreadsheet ID

# Configure retry strategy
retry_strategy = Retry(
    total=3,  # number of retries
    backoff_factor=1,  # wait 1, 2, 4 seconds between retries
    status_forcelist=[429, 500, 502, 503, 504],  # HTTP status codes to retry on
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session = requests.Session()
session.mount("https://", adapter)
session.mount("http://", adapter)

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

def clear_google_sheet_tab(sheet_name):
    """Clear all data from a Google Sheet tab."""
    try:
        creds = get_google_sheets_credentials()
        service = build('sheets', 'v4', credentials=creds)
        service.spreadsheets().values().clear(
            spreadsheetId=SPREADSHEET_ID,
            range=f'{sheet_name}!A:Z',
            body={}
        ).execute()
        print(f"Cleared data in {sheet_name} tab.")
    except HttpError as error:
        print(f"An error occurred while clearing {sheet_name}: {error}")

def make_request(url, headers):
    """Make a request with retry logic and proper error handling."""
    try:
        response = session.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print(f"Error making request to {url}: {e}")
        return None

def scrape_simpletire_brands():
    """Scrape brand information from SimpleTire."""
    url = 'https://simpletire.com/brands'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = make_request(url, headers)
        if not response:
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        brands = []
        brand_elements = soup.find_all('div', class_='tirebrand-listing-item')
        for brand in brand_elements:
            brand_link = brand.find('a')
            if brand_link:
                brand_data = {
                    'name': brand_link.find('div', class_='css-x6inrm').text.strip() if brand_link.find('div', class_='css-x6inrm') else '',
                    'url': 'https://simpletire.com' + brand_link['href'] if brand_link.get('href') else '',
                    'image_url': brand_link.find('img')['src'] if brand_link.find('img') else '',
                    'tire_count': brand_link.find('div', class_='css-o5r0nj').text.strip() if brand_link.find('div', class_='css-o5r0nj') else '',
                    'is_top_rated': bool(brand_link.find('div', class_='css-g16zva'))
                }
                brands.append(brand_data)
        return brands
    except Exception as e:
        print(f"Error scraping website: {e}")
        return []

def scrape_brand_products(brand_url, brand_name=None):
    """Scrape product information from a brand's page."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = make_request(brand_url, headers)
        if not response:
            return []
        
        soup = BeautifulSoup(response.text, 'html.parser')
        product_elements = soup.find_all('div', class_='product-listing-item')
        products = []
        for product in product_elements:
            product_link = product.find('a', class_='css-g7q1b3')
            if not product_link or not product_link.get('href'):
                continue
            product_url = 'https://simpletire.com' + product_link['href']
            product_data_list = scrape_product_details(product_url)
            if product_data_list:
                for product_data in product_data_list:
                    if brand_name:
                        product_data['brand'] = brand_name
                    products.append(product_data)
            # Increased delay between requests to be more gentle on the server
            time.sleep(5)
        return products
    except Exception as e:
        print(f"Error scraping brand products: {e}")
        return []

def extract_image_urls(soup):
    image_urls = []
    # Find all image containers in the carousel
    image_containers = soup.find_all('div', class_='tire-image-item-container')
    
    for container in image_containers:
        # Find the img element within each container
        img = container.find('img', {'data-element': 'Image'})
        if img and img.get('src'):
            # Get the highest quality image URL from srcset
            srcset = img.get('srcset', '')
            if srcset:
                # Parse srcset to get the highest resolution image
                urls = [url.strip().split(' ')[0] for url in srcset.split(',')]
                if urls:
                    # Get the last URL which should be the highest resolution
                    url = urls[-1]
                    # Clean the URL by extracting the actual image URL from the _next/image format
                    if '_next/image?url=' in url:
                        # Extract the encoded URL part
                        encoded_url = url.split('_next/image?url=')[1].split('&')[0]
                        # URL decode to get the actual image URL
                        url = requests.utils.unquote(encoded_url)
                    # Ensure it's a full URL
                    if not url.startswith('http'):
                        url = 'https://images.simpletire.com/images/q_auto/' + url.lstrip('/')
                    # Remove h_3840/ from the URL if present
                    url = url.replace('h_3840/', '')
                    image_urls.append(url)
            else:
                # Fallback to src if srcset is not available
                url = img['src']
                # Clean the URL
                if '_next/image?url=' in url:
                    encoded_url = url.split('_next/image?url=')[1].split('&')[0]
                    url = requests.utils.unquote(encoded_url)
                # Ensure it's a full URL
                if not url.startswith('http'):
                    url = 'https://images.simpletire.com/images/q_auto/' + url.lstrip('/')
                # Remove h_3840/ from the URL if present
                url = url.replace('h_3840/', '')
                image_urls.append(url)
    
    # Ensure we have exactly 5 URLs (pad with empty strings if less than 5)
    while len(image_urls) < 5:
        image_urls.append('')
    # Limit to 5 URLs if more than 5
    return image_urls[:5]

def extract_size_details(soup):
    size_details = []
    # Find the sizes list container
    sizes_list = soup.find('ul', class_='css-0')
    if not sizes_list:
        return size_details
    
    # Find all size items
    size_items = sizes_list.find_all('li', class_='css-rtn8uu')
    for item in size_items:
        size_data = {}
        
        # Get size and price
        size_link = item.find('a', class_='css-167ftct')
        if size_link:
            size_data['size'] = size_link.find('span', class_='css-1xh1644').text.strip()
        
        price_el = item.find('p', class_='css-1ojavxu')
        if price_el:
            size_data['price'] = price_el.text.strip()
        
        # Get size-specific specs
        specs_table = item.find('table', class_='css-8bhknh')
        if specs_table:
            # Find all rows in the table body
            spec_rows = specs_table.find('tbody').find_all('tr')
            for row in spec_rows:
                label = row.find('th').text.strip().lower()
                value = row.find('td').text.strip()
                
                if label == 'width':
                    size_data['width'] = value
                elif label == 'ratio':
                    size_data['ratio'] = value
                elif label == 'inflation pressure':
                    size_data['inflation_pressure'] = value
                elif label == 'tread depth':
                    size_data['tread_depth'] = value
                elif label == 'width range':
                    size_data['width_range'] = value
                elif label == 'sidewall':
                    size_data['sidewall'] = value
                elif label == 'tread width':
                    size_data['tread_width'] = value
        
        size_details.append(size_data)
    
    return size_details

def rearrange_columns(product_data):
    """Rearrange columns in the desired order"""
    # Define the desired column order
    column_order = [
        'title',
        'size',
        'per tire price starts from',
        'width',
        'ratio',
        'inflation_pressure',
        'tread_depth',
        'width_range',
        'sidewall',
        'tread_width',
        'simple_score',
        'category',
        'vehicle',
        'mileage_warranty',
        'load_index',
        'max_speed',
        'utqg',
        'wet_traction',
        'part_number',
        'tread_design',
        'tire_weight',
        'section_width',
        'rim_range',
        'overall_diameter',
        'image_url1',
        'image_url2',
        'image_url3',
        'image_url4',
        'image_url5'
    ]
    
    # Create a new dictionary with the desired order
    return {key: product_data[key] for key in column_order if key in product_data}

def scrape_product_details(product_url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = make_request(product_url, headers)
        if not response:
            return None
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Get base product data
        base_product_data = {
            'title': '',  # Changed from 'name' to 'title'
            'simple_score': '',
            'category': '',
            'vehicle': '',
            'mileage_warranty': '',
            'load_index': '',
            'max_speed': '',
            'utqg': '',
            'wet_traction': '',
            'part_number': '',
            'tread_design': '',
            'tire_weight': '',
            'section_width': '',
            'rim_range': '',
            'overall_diameter': '',
            'image_url1': '',
            'image_url2': '',
            'image_url3': '',
            'image_url4': '',
            'image_url5': ''
        }
        
        # Extract and assign image URLs to individual columns
        image_urls = extract_image_urls(soup)
        for i, url in enumerate(image_urls, 1):
            base_product_data[f'image_url{i}'] = url
        
        # Title (previously name)
        name_el = soup.find('h1', class_='css-1wkv4b1')
        if name_el:
            base_product_data['title'] = name_el.text.strip()
        
        # Simple Score
        score_div = soup.find('div', class_='css-1iebk1z')
        if score_div:
            score = score_div.find('p')
            score_rating = score_div.find('p', class_='horizontalScore')
            if score and score_rating:
                base_product_data['simple_score'] = f"{score.text.strip()} - {score_rating.text.strip()}"
            elif score:
                base_product_data['simple_score'] = score.text.strip()
        
        # Category & Vehicle
        catveh_el = soup.find('div', class_='css-1jpc5k3')
        if catveh_el:
            catveh_text = catveh_el.text.strip()
            if ',' in catveh_text:
                cat, veh = catveh_text.split(',', 1)
                base_product_data['category'] = cat.strip()
                base_product_data['vehicle'] = veh.replace('tire', '').strip()
            elif ' tire' in catveh_text.lower():
                parts = catveh_text.lower().split(' tire')[0].split()
                if len(parts) > 1:
                    base_product_data['category'] = ' '.join(parts[:-1]).title()
                    base_product_data['vehicle'] = parts[-1].title()
                else:
                    base_product_data['category'] = catveh_text.strip()
            else:
                base_product_data['category'] = catveh_text.strip()
        
        # Technical Specs Table (non-size specific)
        specs_table = soup.find('table', class_='css-ojpigt')
        if specs_table:
            spec_rows = specs_table.find_all('tr', class_='trAsTab')
            for row in spec_rows:
                label_div = row.find('div', class_='css-1ojsquv')
                value_div = row.find('div', class_='css-4yq70y')
                if label_div and value_div:
                    label = label_div.find('span').text.strip().lower()
                    value = value_div.get_text(separator=' ', strip=True)
                    if 'mileage warranty' in label:
                        base_product_data['mileage_warranty'] = value
                    elif 'load index' in label:
                        base_product_data['load_index'] = value
                    elif 'max speed' in label:
                        base_product_data['max_speed'] = value
                    elif 'utqg' in label:
                        base_product_data['utqg'] = value
                    elif 'wet traction' in label:
                        base_product_data['wet_traction'] = value
                    elif 'part number' in label:
                        base_product_data['part_number'] = value
                    elif 'tread design' in label:
                        base_product_data['tread_design'] = value
                    elif 'tire weight' in label:
                        base_product_data['tire_weight'] = value
                    elif 'section width' in label:
                        base_product_data['section_width'] = value
                    elif 'rim range' in label:
                        base_product_data['rim_range'] = value
                    elif 'overall diameter' in label:
                        base_product_data['overall_diameter'] = value
        
        # Get size-specific details
        size_details = extract_size_details(soup)
        
        # Create a list of products, one for each size
        products = []
        for size_data in size_details:
            product_data = base_product_data.copy()
            # Append size to title
            product_data['title'] = f"{product_data['title']} - {size_data['size']}"
            # Add size-specific fields
            product_data['size'] = size_data['size']
            product_data['per tire price starts from'] = size_data.get('price', '')
            product_data['width'] = size_data.get('width', '')
            product_data['ratio'] = size_data.get('ratio', '')
            product_data['inflation_pressure'] = size_data.get('inflation_pressure', '')
            product_data['tread_depth'] = size_data.get('tread_depth', '')
            product_data['width_range'] = size_data.get('width_range', '')
            product_data['sidewall'] = size_data.get('sidewall', '')
            product_data['tread_width'] = size_data.get('tread_width', '')
            # Rearrange columns
            product_data = rearrange_columns(product_data)
            products.append(product_data)
        
        return products
    except Exception as e:
        print(f"Error scraping product details: {e}")
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

def main():
    print("Starting SimpleTire scraper...")
    # Scrape brand data
    print("Scraping brand information...")
    brands_data = scrape_simpletire_brands()
    if brands_data:
        print(f"Found {len(brands_data)} brands")
        # Clear and update brands sheet
        print("Clearing brands sheet...")
        clear_google_sheet_tab('Brands')
        print("Updating brands sheet...")
        update_google_sheet(brands_data, 'Brands')
        # Scrape products for each brand
        all_products = []
        for brand in brands_data:
            print(f"Scraping products for {brand['name']}...")
            products = scrape_brand_products(brand['url'], brand['name'])
            all_products.extend(products)
            time.sleep(2)  # Be nice to the server
        if all_products:
            print(f"Found {len(all_products)} products")
            print("Clearing products sheet...")
            clear_google_sheet_tab('Products')
            print("Updating products sheet...")
            update_google_sheet(all_products, 'Products')
        print("Done!")
    else:
        print("No brand data found or error occurred during scraping")

if __name__ == '__main__':
    main() 