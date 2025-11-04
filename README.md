# Collaborative Release Notes Generator

A full-stack web application designed to streamline the process of creating, managing, and generating software release notes. This service provides a collaborative environment where users can define release metadata, automatically summarize JIRA tickets using AI, and scrape upstream bug fixes to produce comprehensive, well-formatted Markdown documents.

The application supports multiple Percona projects including PSMDB, PBM, PLM, and various Kubernetes operators (K8SPSMDB, K8SPS, K8SPXC, P8SPG), with specialized handling for upstream integration (MongoDB release notes and bug fixes) for PSMDB projects.

![Application Dashboard](/static/img/dashboard.png)

## Features

- **Collaborative Dashboard**: View all releases in a central dashboard.
- **Persistent Storage**: All release metadata is stored in a MongoDB database, allowing for collaborative editing and management.
- **AI-Powered Summaries**: Integrates with the Gemini API to automatically generate user-friendly summaries from technical JIRA ticket descriptions.
- **Upstream Bug Scraping**: Automatically visits MongoDB JIRA URLs, scrapes the content, and uses AI to summarize the bug fixes.
- **Dynamic Markdown Generation**: Produces clean, well-structured Markdown with dedicated sections for release highlights, upstream improvements, and categorized JIRA tickets.
- **Markdown Preview**: A built-in preview tab renders the generated Markdown as HTML, showing exactly how it will look.
- **Configuration Management**: A dedicated settings page to securely store API keys and service URLs.
- **Containerized Deployment**: The entire stack (Flask backend, MongoDB) is containerized with Docker for easy setup and consistent deployment.

## Tech Stack

- **Backend**: Python with Flask (modular architecture with blueprints)
- **Database**: MongoDB
- **Frontend**: Vanilla JavaScript (modular SPA), HTML5, Tailwind CSS
- **AI Integration**: Google Gemini API
- **Web Scraping**: BeautifulSoup4, lxml
- **Containerization**: Docker, Docker Compose

---

## Project Structure

```
/release-notes-generator/
├── docker-compose.yml      # Orchestrates the web and db containers
├── Dockerfile              # Defines the build steps for the Flask container
├── requirements.txt        # Python dependencies for the backend
├── app.py                  # Flask app factory and entry point
├── /modules/               # Backend modules
│   ├── __init__.py         # Package initializer
│   ├── api.py              # API routes blueprint (/api/*)
│   ├── views.py            # View routes blueprint (/, /release)
│   └── helpers.py          # Business logic and utility functions
│   ├── api.py              # API routes for data handling
│   ├── views.py            # View routes for serving HTML pages
│   ├── helpers.py          # Business logic and utility functions
│   └── gen_markdown.py     # Script to generate certified images table
├── /static/
│   ├── /css/
│   │   └── style.css       # Custom CSS styles
│   ├── /icons/             # Project-specific icons for the timeline
│   │   ├── kubernetes.png
│   │   └── mongodb.png
│   ├── /img/
│   │   └── dashboard.png   # Dashboard image for README.md
│   └── /js/
│       ├── main.js         # Dashboard and settings JavaScript
│       └── release.js      # Release management JavaScript
└── /templates/
    ├── index.html          # Main dashboard and settings page
    └── release.html        # Release creation and details page
```
---

## Setup and Running the Application

### Prerequisites

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)

### Instructions

1.  **Clone the Repository**:
    Clone or download all the project files into a single directory named `release-notes-generator`.

2.  **Build and Run the Containers**:
    Open a terminal, navigate to the root of the `release-notes-generator` directory, and run the following command:
    ```bash
    docker-compose up --build
    ```
    This command will:
    - Build the Flask application image based on the `Dockerfile`.
    - Pull the latest MongoDB image.
    - Create and start both the `web` and `db` containers.
    - Set up a network for the containers to communicate.

3.  **Access the Application**:
    Once the containers are running, open your web browser and navigate to:
    [http://127.0.0.1:8080](http://127.0.0.1:8080)

---

## Running Tests

To run the unit tests for this project, follow these steps:

1.  **Install Dependencies**:
    Make sure you have Python 3 and pip installed. Then, install the required packages:
    ```bash
    pip3 install -r requirements.txt
    ```

2.  **Run Tests**:
    Execute the following command from the root of the project directory:
    ```bash
    python3 -m unittest discover tests
    ```

---

## How to Use

1.  **Configure Settings**:
    - Navigate to the **Settings** page using the top navigation bar.
    - Enter your JIRA URL (e.g., `your-company.atlassian.net`), JIRA email, JIRA API Token, and your Gemini API Token.
    - Click **Save Settings**. These are stored in the database and are required for the generation features.

2.  **Create a New Release**:
    - Go to the **Dashboard**.
    - Click the **New Release** button (opens the dedicated release page).
    - Fill in the release details:
        - **Version**: The version number of your release (e.g., `2.15.0`).
        - **Project**: Select the project (PSMDB, PBM, PLM, K8SPSMDB, K8SPS, K8SPXC, P8SPG).
        - **Introduction Template**: Choose a preset introduction or use custom text.
        - **Introduction**: Auto-generated for PSMDB based on upstream URLs, or editable for other projects.
        - **Planned Release Date**: The target date for the release.
        - **Release Highlights**: (Optional) Add custom Markdown for key features or announcements.
        - **JIRA Ticket Keys**: A comma or space-separated list of your project's JIRA tickets.
        - **Upstream Release URLs**: (PSMDB only) URLs to the official MongoDB Community Edition release notes.
        - **Upstream Bug Fix URLs**: (PSMDB only) URLs to specific bug tickets on `jira.mongodb.org`.
    - Click **Save Release**.

3.  **Generate Release Notes**:
    - From the dashboard, click on the release you just created to go to the **Release Details** page.
    - Click the **Generate** button.
    - The application will contact the JIRA and Gemini APIs, perform any necessary web scraping, and generate the complete Markdown document.
    - The result will be displayed in both raw **Markdown** and a rendered **Preview** tab.
    - Use the **Copy** button to copy the generated Markdown to your clipboard.

4.  **Edit and Manage**:
    - You can edit any release by clicking the **Edit** button on the dashboard or the details page.
    - The generated Markdown is saved to the database, so it will be available immediately the next time you visit the details page.
    - Navigation between dashboard and release pages is seamless with the modular page structure.
