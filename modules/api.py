from flask import Blueprint, current_app, request, jsonify
from bson import ObjectId
import subprocess
from datetime import datetime

from .helpers import (
    resolve_introduction,
    parse_jira_description,
    get_summary_from_ai,
    process_upstream_bugs,
    generate_supported_software_md,
    generate_supported_platforms_md,
    generate_final_markdown,
)

api_bp = Blueprint('api', __name__)


@api_bp.route('/settings', methods=['GET', 'POST'])
def settings():
    app = current_app
    db = app.mongo_db
    app.logger.info(f"Request received for /api/settings, method: {request.method}")
    if request.method == 'POST':
        data = request.get_json()
        db.settings.update_one({'_id': 'global_settings'}, {'$set': data}, upsert=True)
        app.logger.info("Settings saved successfully.")
        return jsonify({"message": "Settings saved successfully."})
    settings_data = db.settings.find_one({'_id': 'global_settings'})
    app.logger.info("Fetched settings successfully.")
    return jsonify(settings_data or {})


@api_bp.route('/releases', methods=['GET', 'POST'])
def releases():
    app = current_app
    db = app.mongo_db
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


@api_bp.route('/releases/<release_id>', methods=['GET', 'PUT', 'DELETE'])
def release_detail(release_id):
    app = current_app
    db = app.mongo_db
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


@api_bp.route('/releases/<release_id>/generate', methods=['POST'])
def generate_release_notes(release_id):
    app = current_app
    db = app.mongo_db
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

    mongo_intro = resolve_introduction(app, release)
    release_highlights = release.get('releaseHighlights', '')
    upstream_bug_urls = release.get('upstreamBugUrls', '')
    upstream_section = ""
    if (release.get('project') or '').upper() == 'PSMDB':
        upstream_section = process_upstream_bugs(app, upstream_bug_urls, release.get('upstreamUrls', ''), gemini_token)

    # Generate operator-specific sections
    supported_software_md = ""
    supported_platforms_md = ""
    certified_images_md = ""
    operator_projects = ['K8SPS', 'K8SPXC', 'K8SPG', 'K8SPSMDB']
    if release.get('project') in operator_projects:
        supported_software_md = generate_supported_software_md(release.get('supportedSoftware', ''))
        supported_platforms_md = generate_supported_platforms_md(release.get('supportedPlatforms', ''), release.get('version', ''))
    # Generate "Percona Certified Images" section for operators
        json_url = release.get('certifiedImagesJsonUrl')
        if json_url:
            app.logger.info(f"Generating certified images markdown from URL: {json_url}")
            exclude_patterns = release.get('excludedImagesPatterns', '')
            sort_patterns = release.get('groupSortPatterns', '')
            
            command = [
                'python', 'modules/gen_markdown.py',
                '--url', json_url,
                '--exclude', exclude_patterns,
                '--sort', sort_patterns
            ]
            
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            if result.returncode == 0:
                certified_images_md = result.stdout.strip()
                app.logger.info("Finished generating certified images markdown.")
            else:
                app.logger.error(f"Error generating certified images markdown. Script stderr:\n{result.stderr.strip()}")
                certified_images_md = "*Error: Could not generate Percona Certified Images section.*"

    all_ticket_keys = set()
    
    # Fetch tickets from JIRA Release ID (Fix Version)
    jira_release_id = release.get('jiraReleaseId')
    if jira_release_id:
        app.logger.info(f"Fetching JIRA tickets for release ID (fixVersion): {jira_release_id}")
        jql = f'fixVersion = "{jira_release_id}" AND (type != "Admin & Maintenance Task" OR "Security Level" is EMPTY OR "Security Level" != "🟥 INTERNAL TASK ONLY 🟥") ORDER BY key ASC'
        release_tickets = fetch_jira_tickets_by_jql(app, domain, email, token, jql)
        all_ticket_keys.update([t['key'] for t in release_tickets])

    # Add additional tickets
    additional_tickets_raw = release.get('additionalJiraTickets', '')
    additional_ticket_keys = set(filter(None, re.split(r'[\,\s\n]+', additional_tickets_raw)))
    all_ticket_keys.update(additional_ticket_keys)
    
    ticket_keys = sorted(list(all_ticket_keys))
    tickets_with_summaries = []
    app.logger.info(f"Processing {len(ticket_keys)} JIRA tickets.")
    for key in ticket_keys:
        ticket_info = fetch_jira_ticket(app, domain, email, token, key.upper())
        if ticket_info:
            title = ticket_info.get("fields", {}).get("summary", "No title")
            description_text = parse_jira_description(ticket_info.get("fields", {}).get("description"))
            summary = get_summary_from_ai(app, title, description_text, gemini_token, is_upstream=False)
            ticket_info['releaseNoteSummary'] = summary
            tickets_with_summaries.append(ticket_info)

    if not tickets_with_summaries and ticket_keys:
        app.logger.warning("Could not fetch data for any provided JIRA tickets.")
        return jsonify({"error": "Could not fetch data for any JIRA tickets."}), 400

    markdown_output = generate_final_markdown(mongo_intro, release_highlights, upstream_section, tickets_with_summaries, release.get('version'), release.get('codename'), domain, supported_software_md, supported_platforms_md, certified_images_md)
    db.releases.update_one({'_id': ObjectId(release_id)}, {'$set': {'generatedMarkdown': markdown_output}})
    app.logger.info(f"Successfully generated and saved markdown for release {release_id}.")
    return jsonify({"markdown": markdown_output})


# External service helpers that need current_app logging
import requests
from requests.auth import HTTPBasicAuth
import re


def fetch_jira_tickets_by_jql(app, domain, email, token, jql):
    url = f"https://{domain}/rest/api/3/search/jql"
    auth = HTTPBasicAuth(email, token)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    
    query = {
        'jql': jql,
        'maxResults': '100',
        "fields": ["summary", "description", "issuetype"]
    }   
    
    try:
        response = requests.request("GET", url, headers=headers, params=query, auth=auth)
        response.raise_for_status()
        data = response.json()
        issues = data.get('issues', [])
        app.logger.info(f"Successfully fetched {len(issues)} JIRA tickets using JQL: '{jql}'")
        return issues
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Error fetching JIRA tickets with JQL '{jql}': {e}")
        return []
    
def fetch_jira_ticket(app, domain, email, token, key):
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
