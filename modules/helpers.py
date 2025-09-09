import re
from datetime import datetime
import requests
from bs4 import BeautifulSoup


PBM_INTRO = (
    "Percona Backup for MongoDB is a distributed, low-impact solution for creating consistent backups of MongoDB sharded clusters and replica sets, and for restoring those backups to a specific point in time."
)

PLM_INTRO = (
    """# {{ plm.full_name }} 0.6.0 ({{ date.v0_6_0 }}) (Technical preview)

        Percona Link for MongoDB (PLM) is a powerful and open-source tool that addresses one of the challenging tasks DBAs have: migration of mission-critical MongoDB deployments with minimized downtime and ensured data consistency. Percona Link for MongoDB aims to simplify this process, being a solution for zero-downtime data migration and real-time replication between MongoDB deployments that are either Percona Server for MongoDB instances, MongoDB Community/Advanced versions, or even cloud-based Atlas clusters.
      
        --8<-- "plm-description.md"

        [Get started with PLM](../installation.md){.md-button}
    """
)

PSMDB_INTRO = (
    "Percona Server for MongoDB is an enhanced, source-available, and highly-scalable database that is a fully-compatible, drop-in replacement for MongoDB Community Edition."
)

K8SPS_INTRO = (
    "Percona Operator for MySQL allows users to deploy MySQL clusters with both asynchronous and group replication topology. This release includes various stability improvements and bug fixes, getting the Operator closer to the General Availability stage. Version 0.11.0 of the Percona Operator for MySQL is still a tech preview release, and it is not recommended for production environments."
)


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


def resolve_introduction(app, release: dict) -> str:
    custom_intro = (release.get('customIntroduction') or '').strip()
    if custom_intro:
        return custom_intro

    template_key = (release.get('introTemplate') or 'PSMDB').upper()

    if template_key == 'PBM':
        return PBM_INTRO
    if template_key == 'PLM':
        return PLM_INTRO
    if template_key == 'K8SPS':
        return K8SPS_INTRO
    if template_key == 'PSMDB':
        return generate_mongo_intro(release.get('upstreamUrls', ''), release.get('version', '')) or PSMDB_INTRO

    return ""


def generate_mongo_intro(urls_raw, version):
    if not urls_raw or not urls_raw.strip(): return ""
    urls = list(set(filter(None, re.split(r'[\,\s\n]+', urls_raw))))
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


def get_summary_from_ai(app, title, description, gemini_token, is_upstream=False):
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


def process_upstream_bugs(app, bug_urls_raw, release_urls_raw, gemini_token):
    if not bug_urls_raw or not bug_urls_raw.strip():
        return ""
    bug_urls = list(set(filter(None, re.split(r'[\,\s\n]+', bug_urls_raw))))
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
            summary = get_summary_from_ai(app, title, description, gemini_token, is_upstream=True)
            summarized_bugs.append(f"* [{ticket_id}]({url}) - {summary}")
        except requests.exceptions.RequestException as e:
            app.logger.error(f"Could not scrape URL {url}: {e}")
            continue
    
    if not summarized_bugs:
        return ""
    md_lines = ["### Upstream Improvements", "The bug fixes, provided by MongoDB Community Edition and included in Percona Server for MongoDB, are the following:"]
    md_lines.extend(summarized_bugs)
    release_urls = list(set(filter(None, re.split(r'[\,\s\n]+', release_urls_raw))))
    if release_urls:
        md_lines.append("\nFind the full list of changes in the following MongoDB Community Edition release notes:")
        release_links = []
        for r_url in sorted(release_urls):
            match = re.search(r'(\d+\.\d+\.\d+)', r_url)
            version = match.group(1) if match else "version"
            release_links.append(f"* [MongoDB {version} Community Edition]({r_url})")
        md_lines.extend(release_links)
    return "\n".join(md_lines)


def generate_supported_software_md(software_raw):
    if not software_raw or not software_raw.strip():
        return ""

    software_map = {
        "PS": "Percona Server for MySQL",
        "XtraBackup-8.4": "XtraBackup",
        "XtraBackup-8.0": "XtraBackup",
        "XtraBackup": "XtraBackup",
        "MySQL Router-8.4": "MySQL Router",
        "MySQL Router-8.0": "MySQL Router",
        "MySQL Router": "MySQL Router",
        "HAProxy": "HAProxy",
        "Orchestrator": "Orchestrator",
        "Percona Toolkit": "Percona Toolkit",
        "PMM Client": "PMM Client",
        "Cert Manager": "Cert Manager",
        "PSMDB": "Percona Server for MongoDB",
        "PG": "Percona Distribution for PostgreSQL",
        "PBM": "Percona Backup for MongoDB",
        "PXC": "Percona XtraDB Cluster",
        "PXB": "Percona XtraBackup",
        "LogCollector": "LogCollector based on fluent-bit",
    }

    intro = "The Operator was developed and tested with the following software:"
    software_lines = []
    for line in software_raw.strip().split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            mapped_key = software_map.get(key.strip(), key.strip())
            software_lines.append(f"* {mapped_key}: {value.strip()}")
    
    footer = "Other options may also work but have not been tested."
    return "\n".join([intro] + software_lines + ["", footer])

def generate_supported_platforms_md(platforms_raw, version):
    if not platforms_raw or not platforms_raw.strip():
        return ""

    platform_map = {
        "GKE": "[Google Kubernetes Engine (GKE) :octicons-link-external-16:](https://cloud.google.com/kubernetes-engine)",
        "EKS": "[Amazon Elastic Container Service for Kubernetes (EKS) :octicons-link-external-16:](https://aws.amazon.com)",
        "Openshift": "[OpenShift Container Platform :octicons-link-external-16:](https://www.redhat.com/en/technologies/cloud-computing/openshift)",
        "AKS": "[Azure Kubernetes Service (AKS) :octicons-link-external-16:](https://azure.microsoft.com/en-us/services/kubernetes-service/)",
        "Minikube": "[Minikube :octicons-link-external-16:](https://github.com/kubernetes/minikube)"
    }

    intro = f"""Percona Operators are designed for compatibility with all [CNCF-certified :octicons-link-external-16:](https://www.cncf.io/training/certification/software-conformance/) Kubernetes distributions. Our release process includes targeted testing and validation on major cloud provider platforms and OpenShift, as detailed below for Operator version {version}:

--8<-- [start:platforms]"""

    platform_lines = []
    for line in platforms_raw.strip().split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            if key in platform_map:
                platform_lines.append(f"* {platform_map[key]}: {value.strip()}")
    return "\n".join([intro] + platform_lines)

def generate_final_markdown(mongo_intro, release_highlights, upstream_section, tickets, version, codename, domain, supported_software_md="", supported_platforms_md="", certified_images_md=""):
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
    section_map = {"features": "## Improvements", "fixes": "## Fixed bugs", "maintenance": "## Technical & Maintenance"}
    for category, title in section_map.items():
        if categories[category]:
            md_lines.append(title)
            for ticket in categories[category]:
                md_lines.append(f"- [{ticket['key']}](https://{domain}/browse/{ticket['key']}): {ticket['releaseNoteSummary']}")
            md_lines.append("")
    
    if supported_software_md:
        md_lines.append("## Supported software")
        md_lines.append(supported_software_md)
        md_lines.append("")

    if supported_platforms_md:
        md_lines.append("## Supported platforms")
        md_lines.append(supported_platforms_md)
        md_lines.append("")

    if certified_images_md:
        md_lines.append("## Percona Certified Images")
        md_lines.append(certified_images_md)
        md_lines.append("")

    return "\n".join(md_lines)
