import os
import requests
from bs4 import BeautifulSoup
import time
import re

# Test: Only fetch first 5 products from the first brand
BRANDS_URL = 'https://simpletire.com/brands'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_first_brand_url():
    response = requests.get(BRANDS_URL, headers=HEADERS)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    brand_elements = soup.find_all('div', class_='tirebrand-listing-item')
    if not brand_elements:
        return None
    brand_link = brand_elements[0].find('a')
    if brand_link and brand_link.get('href'):
        return 'https://simpletire.com' + brand_link['href']
    return None

def scrape_first_5_products(brand_url):
    response = requests.get(brand_url, headers=HEADERS)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    product_elements = soup.find_all('div', class_='product-listing-item')
    products = []
    count = 0
    for product in product_elements:
        product_link = product.find('a', class_='css-g7q1b3')
        if not product_link or not product_link.get('href'):
            continue
        product_url = 'https://simpletire.com' + product_link['href']
        product_data = scrape_product_details(product_url)
        if product_data:
            products.append(product_data)
            count += 1
        if count >= 5:
            break
        time.sleep(2)
    return products

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

def scrape_product_details(product_url):
    try:
        response = requests.get(product_url, headers=HEADERS)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        product_data = {
            'name': '',
            'per tire price starts from': '',
            'simple_score': '',
            'category': '',
            'vehicle': '',
            'mileage_warranty': '',
            'load_index': '',
            'max_speed': '',
            'sidewall': '',
            'utqg': '',
            'wet_traction': '',
            'inflation_pressure': '',
            'part_number': '',
            'tread_depth': '',
            'tread_design': '',
            'tire_weight': '',
            'section_width': '',
            'rim_range': '',
            'overall_diameter': '',
            'image_url1': '',  # Changed from image_urls array to individual columns
            'image_url2': '',
            'image_url3': '',
            'image_url4': '',
            'image_url5': ''
        }
        
        # Extract and assign image URLs to individual columns
        image_urls = extract_image_urls(soup)
        for i, url in enumerate(image_urls, 1):
            product_data[f'image_url{i}'] = url
        
        # Name
        name_el = soup.find('h1', class_='css-1wkv4b1')
        if name_el:
            product_data['name'] = name_el.text.strip()
        # Price
        price_val = ''
        price_wrapper = soup.find('div', class_='css-1ccm9az')
        if price_wrapper:
            price_block = price_wrapper.find('div', class_='css-13qcamq')
            if price_block:
                price_p = price_block.find('p', class_='css-1wdv3rw')
                if price_p:
                    price_val = price_p.text.strip()
        # Fallback: search for any $ price in the entire HTML
        if not price_val:
            html_text = soup.get_text(separator=' ', strip=True)
            match = re.search(r'\$[0-9,.]+', html_text)
            if match:
                price_val = match.group(0)
        if price_val:
            product_data['per tire price starts from'] = price_val
        else:
            print(f"[WARN] Price not found for {product_url}")
            # Print a snippet of the HTML for debugging
            print(soup.prettify()[:1000])
        # Simple Score
        score_div = soup.find('div', class_='css-1iebk1z')
        if score_div:
            score = score_div.find('p')
            score_rating = score_div.find('p', class_='horizontalScore')
            if score and score_rating:
                product_data['simple_score'] = f"{score.text.strip()} - {score_rating.text.strip()}"
            elif score:
                product_data['simple_score'] = score.text.strip()
        # Category & Vehicle
        catveh_el = soup.find('div', class_='css-1jpc5k3')
        if catveh_el:
            catveh_text = catveh_el.text.strip()
            if ',' in catveh_text:
                cat, veh = catveh_text.split(',', 1)
                product_data['category'] = cat.strip()
                product_data['vehicle'] = veh.replace('tire', '').strip()
            elif ' tire' in catveh_text.lower():
                # e.g. "All Season Passenger tire"
                parts = catveh_text.lower().split(' tire')[0].split()
                if len(parts) > 1:
                    product_data['category'] = ' '.join(parts[:-1]).title()
                    product_data['vehicle'] = parts[-1].title()
                else:
                    product_data['category'] = catveh_text.strip()
            else:
                product_data['category'] = catveh_text.strip()
        # Technical Specs Table
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
                        product_data['mileage_warranty'] = value
                    elif 'load index' in label:
                        product_data['load_index'] = value
                    elif 'max speed' in label:
                        product_data['max_speed'] = value
                    elif 'sidewall' in label:
                        product_data['sidewall'] = value
                    elif 'utqg' in label:
                        product_data['utqg'] = value
                    elif 'wet traction' in label:
                        product_data['wet_traction'] = value
                    elif 'inflation pressure' in label:
                        product_data['inflation_pressure'] = value
                    elif 'part number' in label:
                        product_data['part_number'] = value
                    elif 'tread depth' in label:
                        product_data['tread_depth'] = value
                    elif 'tread design' in label:
                        product_data['tread_design'] = value
                    elif 'tire weight' in label:
                        product_data['tire_weight'] = value
                    elif 'section width' in label:
                        product_data['section_width'] = value
                    elif 'rim range' in label:
                        product_data['rim_range'] = value
                    elif 'overall diameter' in label:
                        product_data['overall_diameter'] = value
        return product_data
    except Exception as e:
        print(f"Error scraping product details: {e}")
        return None

def main():
    print("Testing: Fetching first 5 products from the first brand...")
    brand_url = get_first_brand_url()
    if not brand_url:
        print("No brand found!")
        return
    products = scrape_first_5_products(brand_url)
    for i, prod in enumerate(products, 1):
        print(f"Product {i}:")
        for k, v in prod.items():
            print(f"  {k}: {v}")
        print("-"*40)

if __name__ == '__main__':
    main() 