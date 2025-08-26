import os
import re
import logging # Import the logging module
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import requests
from requests.auth import HTTPBasicAuth
from pymongo import MongoClient
from bson import ObjectId
from bs4 import BeautifulSoup

# --- Flask App Initialization ---
app = Flask(__name__)
CORS(app)

# --- NEW: Logging Configuration ---
# Configure logging to output to the console.
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --- Database Configuration ---
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/release_notes")
client = MongoClient(MONGO_URI)
db = client.get_database()
app.logger.info("Successfully connected to MongoDB.")

# --- Helper Functions ---
def parse_jira_description(description_field):
    if not isinstance(description_field, dict) or "content" not in description_field:
        return ""
    text_content = []
    def recurse(nodes):
        for node in nodes:
            if node.get("type") == "text" and "text" in node:
                text_content.append(node["text"])
            if "content" in node and isinstance(node["content"], list):
                recurse(node["content"])
    recurse(description_field["content"])
    return " ".join(text_content)

# --- API Routes ---

@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    app.logger.info(f"Request received for /api/settings, method: {request.method}")
    if request.method == 'POST':
        data = request.get_json()
        db.settings.update_one({'_id': 'global_settings'}, {'$set': data}, upsert=True)
        app.logger.info("Settings saved successfully.")
        return jsonify({"message": "Settings saved successfully."})
    settings_data = db.settings.find_one({'_id': 'global_settings'})
    app.logger.info("Fetched settings successfully.")
    return jsonify(settings_data or {})

@app.route('/api/releases', methods=['GET', 'POST'])
def releases():
    app.logger.info(f"Request received for /api/releases, method: {request.method}")
    if request.method == 'POST':
        data = request.get_json()
        data['created_at'] = datetime.utcnow()
        result = db.releases.insert_one(data)
        app.logger.info(f"New release created with ID: {result.inserted_id}")
        return jsonify({"message": "Release created.", "id": str(result.inserted_id)}), 201
    all_releases = list(db.releases.find().sort('created_at', -1))
    for release in all_releases:
        release['_id'] = str(release['_id'])
    app.logger.info(f"Fetched {len(all_releases)} releases from the database.")
    return jsonify(all_releases)

@app.route('/api/releases/<release_id>', methods=['GET', 'PUT', 'DELETE'])
def release_detail(release_id):
    app.logger.info(f"Request for /api/releases/{release_id}, method: {request.method}")
    oid = ObjectId(release_id)
    if request.method == 'GET':
        release = db.releases.find_one({'_id': oid})
        if release:
            release['_id'] = str(release['_id'])
            app.logger.info(f"Found release {release_id}.")
            return jsonify(release)
        app.logger.warning(f"Release {release_id} not found.")
        return jsonify({"error": "Release not found"}), 404
    if request.method == 'PUT':
        data = request.get_json()
        db.releases.update_one({'_id': oid}, {'$set': data})
        app.logger.info(f"Release {release_id} updated successfully.")
        return jsonify({"message": "Release updated successfully."})
    if request.method == 'DELETE':
        db.releases.delete_one({'_id': oid})
        app.logger.info(f"Release {release_id} deleted successfully.")
        return jsonify({"message": "Release deleted successfully."})

@app.route('/api/releases/<release_id>/generate', methods=['POST'])
def generate_release_notes(release_id):
    app.logger.info(f"Starting release notes generation for ID: {release_id}")
    settings = db.settings.find_one({'_id': 'global_settings'}) or {}
    release = db.releases.find_one({'_id': ObjectId(release_id)})
    if not release:
        app.logger.error(f"Generation failed: Release {release_id} not found.")
        return jsonify({"error": "Release not found"}), 404

    domain, email, token, gemini_token = settings.get('jiraUrl'), settings.get('jiraEmail'), settings.get('jiraToken'), settings.get('geminiToken')
    if not all([domain, email, token]):
        app.logger.error("Generation failed: JIRA settings are incomplete.")
        return jsonify({"error": "JIRA settings are incomplete. Please configure them on the Settings page."}), 400

    mongo_intro = generate_mongo_intro(release.get('upstreamUrls', ''), release.get('version', ''))
    release_highlights = release.get('releaseHighlights', '')
    upstream_bug_urls = release.get('upstreamBugUrls', '')
    upstream_section = process_upstream_bugs(upstream_bug_urls, release.get('upstreamUrls', ''), gemini_token)

    ticket_keys = sorted(list(set(filter(None, re.split(r'[,\s\n]+', release.get('jiraTickets', ''))))))
    tickets_with_summaries = []
    app.logger.info(f"Processing {len(ticket_keys)} JIRA tickets.")
    for key in ticket_keys:
        ticket_info = fetch_jira_ticket(domain, email, token, key.upper())
        if ticket_info:
            title = ticket_info.get("fields", {}).get("summary", "No title")
            description_text = parse_jira_description(ticket_info.get("fields", {}).get("description"))
            summary = get_summary_from_ai(title, description_text, gemini_token, is_upstream=False)
            ticket_info['releaseNoteSummary'] = summary
            tickets_with_summaries.append(ticket_info)

    if not tickets_with_summaries and ticket_keys:
        app.logger.warning("Could not fetch data for any provided JIRA tickets.")
        return jsonify({"error": "Could not fetch data for any JIRA tickets."}), 400

    markdown_output = generate_final_markdown(mongo_intro, release_highlights, upstream_section, tickets_with_summaries, release.get('version'), release.get('codename'), domain)
    db.releases.update_one({'_id': ObjectId(release_id)}, {'$set': {'generatedMarkdown': markdown_output}})
    app.logger.info(f"Successfully generated and saved markdown for release {release_id}.")
    return jsonify({"markdown": markdown_output})

# --- Business Logic Functions ---

def generate_mongo_intro(urls_raw, version):
    if not urls_raw or not urls_raw.strip(): return ""
    urls = list(set(filter(None, re.split(r'[,\s\n]+', urls_raw))))
    if not urls: return ""
    mongo_links, versions = [], []
    for url in urls:
        match = re.search(r'(\d+\.\d+\.\d+)', url)
        if match:
            mongo_version = match.group(1)
            versions.append(mongo_version)
            mongo_links.append(f"[MongoDB {mongo_version} Community Edition]({url})")
    if not mongo_links: return ""
    mongo_links.sort()
    display_version = version.lstrip('v') if version else "X.Y.Z"
    current_date = datetime.now().strftime("%b %d, %Y")
    return f"""Percona Server for MongoDB {display_version} ({current_date})
[Install](../install/index.md){{.md-button}}
[Upgrade from MongoDB Community](../install/upgrade-from-mongodb.md){{.md-button}}
Percona Server for MongoDB {display_version} is an enhanced, source-available, and highly-scalable database that is a
fully-compatible, drop-in replacement for MongoDB Community Edition.
Percona Server for MongoDB {display_version} includes the improvements and bug fixes of {", ".join(mongo_links)}.
It supports protocols and drivers of MongoDB Community {' through '.join(sorted(versions))}.
"""

def fetch_jira_ticket(domain, email, token, key):
    url = f"https://{domain}/rest/api/3/issue/{key}"
    auth = HTTPBasicAuth(email, token)
    try:
        response = requests.get(url, headers={"Accept": "application/json"}, auth=auth, timeout=10)
        response.raise_for_status()
        app.logger.info(f"Successfully fetched JIRA ticket: {key}")
        return response.json()
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error fetching JIRA ticket {key}: {e}")
        return None

def get_summary_from_ai(title, description, gemini_token, is_upstream=False):
    if not description or not description.strip(): return title
    prompt_intro = "Generate a concise, user-friendly summary for an upstream bug fix. The summary should be a single, clear sentence explaining the fix from an end-user's perspective." if is_upstream else "Generate a concise, user-friendly summary for a software release note based on the following JIRA ticket details. The summary should be a single, clear sentence explaining the change from an end-user's perspective."
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={gemini_token}"
    prompt = f"""{prompt_intro} Do not start with phrases like "This ticket" or "The user can now". Just state the change directly.
Original JIRA Title: "{title}"
JIRA Description: "{description}"
Release Note Summary:"""
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(api_url, json=payload, headers={'Content-Type': 'application/json'}, timeout=20)
        response.raise_for_status()
        result = response.json()
        summary = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        app.logger.info(f"Successfully generated summary for title: '{title[:30]}...'")
        return summary.strip() if summary else title
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error calling Gemini API for title '{title[:30]}...': {e}")
        return title

def process_upstream_bugs(bug_urls_raw, release_urls_raw, gemini_token):
    if not bug_urls_raw or not bug_urls_raw.strip():
        return ""
    bug_urls = list(set(filter(None, re.split(r'[,\s\n]+', bug_urls_raw))))
    if not bug_urls:
        return ""
    
    app.logger.info(f"Processing {len(bug_urls)} upstream bug URLs.")
    summarized_bugs = []
    for url in bug_urls:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            title_element = soup.find('div', id='summary-val')
            description_element = soup.find('div', id='descriptionmodule')
            if not title_element or not description_element:
                app.logger.warning(f"Could not find title or description elements on {url}")
                continue
            title = title_element.get_text(strip=True)
            description = description_element.get_text(strip=True, separator='\n')
            ticket_id = url.split('/')[-1]
            summary = get_summary_from_ai(title, description, gemini_token, is_upstream=True)
            summarized_bugs.append(f"* [{ticket_id}]({url}) - {summary}")
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Could not scrape URL {url}: {e}")
            continue
    
    if not summarized_bugs:
        return ""
    md_lines = ["### Upstream Improvements", "The bug fixes, provided by MongoDB Community Edition and included in Percona Server for MongoDB, are the following:"]
    md_lines.extend(summarized_bugs)
    release_urls = list(set(filter(None, re.split(r'[,\s\n]+', release_urls_raw))))
    if release_urls:
        md_lines.append("\nFind the full list of changes in the following MongoDB Community Edition release notes:")
        release_links = []
        for r_url in sorted(release_urls):
            match = re.search(r'(\d+\.\d+\.\d+)', r_url)
            version = match.group(1) if match else "version"
            release_links.append(f"* [MongoDB {version} Community Edition]({r_url})")
        md_lines.extend(release_links)
    return "\n".join(md_lines)

def generate_final_markdown(mongo_intro, release_highlights, upstream_section, tickets, version, codename, domain):
    md_lines = []
    if mongo_intro:
        md_lines.extend([mongo_intro, "\n---"])
    if release_highlights and release_highlights.strip():
        md_lines.append("## Release Highlights")
        md_lines.append("\nThis release provides the following features and improvements:\n")
        md_lines.append(release_highlights)
        md_lines.append("\n---")
    if upstream_section:
        md_lines.append(upstream_section)
        md_lines.append("\n---")
    title_line = f"# Release {version}" if version else "# Release Notes"
    if codename: title_line += f' - "{codename}"'
    md_lines.extend([title_line, f"*Released on: {datetime.now().strftime('%Y-%m-%d')}*", "---"])
    categories = {"features": [], "fixes": [], "maintenance": []}
    ISSUE_TYPE_MAP = {'Story': 'features', 'New Feature': 'features', 'Improvement': 'features', 'Epic': 'features', 'Bug': 'fixes', 'Defect': 'fixes', 'Task': 'maintenance', 'Sub-task': 'maintenance', 'Chore': 'maintenance', 'Technical Debt': 'maintenance'}
    for ticket in tickets:
        issue_type = ticket.get("fields", {}).get("issuetype", {}).get("name", "Task")
        categories[ISSUE_TYPE_MAP.get(issue_type, "maintenance")].append(ticket)
    section_map = {"features": "## ✨ New Features & Enhancements", "fixes": "## 🐛 Bug Fixes", "maintenance": "## 🔧 Technical & Maintenance"}
    for category, title in section_map.items():
        if categories[category]:
            md_lines.append(title)
            for ticket in categories[category]:
                md_lines.append(f"- [{ticket['key']}](https://{domain}/browse/{ticket['key']}): {ticket['releaseNoteSummary']}")
            md_lines.append("")
    return "\n".join(md_lines)

# --- Main HTML Serving Route ---
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
