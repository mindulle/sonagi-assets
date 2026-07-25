#!/usr/bin/env python3
import subprocess
import json
import os
import shutil

def run_harvest(brief, query):
    cmd = [
        "npx", "-y", "opendevbrowser", "inspiredesign", "harvest",
        "--brief", brief,
        "--query", query,
        "--provider", "web/default",
        "--max-references", "3",
        "--visual-evidence", "required",
        "--browser-mode", "managed",
        "--mode", "json",
        "--output-format", "json"
    ]
    
    print(f"Running OpenDevBrowser harvest for: {brief}...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        out_json = json.loads(result.stdout)
        artifact_path = out_json.get("artifact_path")
        
        if artifact_path and os.path.exists(artifact_path):
            vis_file = os.path.join(artifact_path, "screenshot-index.json")
            if os.path.exists(vis_file):
                with open(vis_file) as f:
                    screenshots = json.load(f)
                    for item in screenshots:
                        img_path = item.get("capturePath")
                        url = item.get("url", "")
                        if img_path and os.path.exists(img_path):
                            print(f"Ingesting {img_path} from {url}")
                            # Call the eagle import script
                            import_cmd = [
                                "python3", "import_ai_asset.py",
                                img_path,
                                "--name", f"Harvested: {brief[:20]}",
                                "--tags", "opendevbrowser,harvest,auto-collected",
                                "--annotation", f"Source: {url}"
                            ]
                            subprocess.run(import_cmd)
            else:
                print("No screenshot index found in artifact.")
        else:
            print("Harvest failed or artifact path missing.")
    except Exception as e:
        print("Error during harvest execution:", e)

def main():
    targets = [
        {"brief": "Modern dark mode dashboard", "query": "site:dribbble.com dark mode dashboard UI"},
        {"brief": "Hand drawn UX flow wireframe", "query": "site:dribbble.com hand drawn wireframe ux flow"}
    ]
    
    for t in targets:
        run_harvest(t["brief"], t["query"])

if __name__ == "__main__":
    main()
