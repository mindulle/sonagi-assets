#!/usr/bin/env python3
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

import firecrawl

# Configure paths and API keys
COLLECTION_PATH = Path(os.environ.get("BEHANCE_ASSETS_PATH", "/app/data/behance-assets/images"))
FIRECRAWL_API_KEY = os.environ.get("FIRECRAWL_API_KEY")

def generate_id():
    return str(uuid.uuid4()).upper()

def download_image(url, dest_path):
    # Using bash to download
    subprocess.run(["curl", "-L", url, "-o", str(dest_path)], check=True)

def import_behance_asset(asset_data, name, tags, annotation):
    asset_id = generate_id()
    info_dir = COLLECTION_PATH / f"{asset_id}.info"
    info_dir.mkdir(parents=True, exist_ok=True)

    # Download image
    image_url = asset_data.get("image_url")
    ext = "jpg" # Default
    dest_original = info_dir / f"{name.replace(' ', '_')}.{ext}"
    if image_url:
        download_image(image_url, dest_original)

    metadata = {
        "id": asset_id,
        "name": name,
        "tags": tags,
        "url": asset_data.get("url", ""),
        "annotation": annotation,
        "modificationTime": int(time.time() * 1000),
    }

    with open(info_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"Imported {name}")

def scrape_behance_profile(profile_url):
    app = firecrawl.FirecrawlApp(api_key=FIRECRAWL_API_KEY)

    print(f"Scraping profile: {profile_url}")
    # Using 'scrape_url' (or 'crawl_url' if needed)
    scrape_result = app.scrape_url(profile_url, params={'formats': ['links']})

    project_links = []
    if 'links' in scrape_result:
        for link in scrape_result['links']:
            if "/gallery/" in link:
                project_links.append(link)

    return list(set(project_links))

def scrape_project_details(project_url):
    app = firecrawl.FirecrawlApp(api_key=FIRECRAWL_API_KEY)
    print(f"Scraping project: {project_url}")

    scrape_result = app.scrape_url(project_url, params={
        'formats': ['json'],
        'jsonOptions': {
            'prompt': 'Extract project title and main image URL',
            'schema': {
                'type': 'object',
                'properties': {
                    'title': {'type': 'string'},
                    'image_url': {'type': 'string'}
                },
                'required': ['title', 'image_url']
            }
        }
    })

    # Firecrawl returns structured data inside a 'json' key
    data = scrape_result.get('json', {})
    data['url'] = project_url
    return data

def run_pipeline(profile_url):
    print("Starting Behance collection pipeline...")
    project_links = scrape_behance_profile(profile_url)

    for link in project_links[:5]: # Process top 5 for prototype
        try:
            details = scrape_project_details(link)
            if details:
                import_behance_asset(details, details.get('title', 'Unknown Project'), ['behance', 'ui-ux'], 'Imported from Behance')
        except Exception as e:
            print(f"Failed to process {link}: {e}")

if __name__ == "__main__":
    if not FIRECRAWL_API_KEY:
        print("Error: FIRECRAWL_API_KEY not set")
    else:
        profile_url = os.environ.get("BEHANCE_PROFILE_URL", "https://www.behance.net/adobe")
        run_pipeline(profile_url)
