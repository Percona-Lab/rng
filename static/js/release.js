const appContainer = document.getElementById('app-container');
const converter = new showdown.Converter();
converter.setOption('tables', true);
let currentReleaseId = null;
const API_BASE_URL = 'http://127.0.0.1:8080';

// Router for release operations
const router = () => {
    const hash = window.location.hash || '#new-release';
    const [path, id] = hash.split('/');
    currentReleaseId = id;
    appContainer.innerHTML = '';
    switch(path) {
        case '#new-release': renderReleaseForm(); break;
        case '#edit-release': renderReleaseForm(currentReleaseId); break;
        case '#release-details': renderReleaseDetails(currentReleaseId); break;
        default: renderReleaseForm();
    }
};

// Page Renderers
const renderReleaseForm = async (id = null) => {
    const template = document.getElementById('release-form-template').content.cloneNode(true);
    appContainer.appendChild(template);
    appContainer.querySelector('[data-page]').classList.add('active');

    const form = document.getElementById('release-form');
    const formTitle = document.getElementById('form-title');
    const introTemplateEl = document.getElementById('introTemplate');
    const customIntroEl = document.getElementById('customIntroduction');
    const projectEl = document.getElementById('project');
    const upstreamUrlsEl = document.getElementById('upstreamUrls');
    const upstreamBugUrlsEl = document.getElementById('upstreamBugUrls');
    const certifiedImagesSectionEl = document.getElementById('certified-images-section');

    const PRESET_INTRODUCTIONS = {
        PBM: "Percona Backup for MongoDB is a distributed, low-impact solution for creating consistent backups of MongoDB sharded clusters and replica sets, and for restoring those backups to a specific point in time.",
        PLM: `# {{ plm.full_name }} 0.6.0 ({{ date.v0_6_0 }}) (Technical preview)

        Percona Link for MongoDB (PLM) is a powerful and open-source tool that addresses one of the challenging tasks DBAs have: migration of mission-critical MongoDB deployments with minimized downtime and ensured data consistency. Percona Link for MongoDB aims to simplify this process, being a solution for zero-downtime data migration and real-time replication between MongoDB deployments that are either Percona Server for MongoDB instances, MongoDB Community/Advanced versions, or even cloud-based Atlas clusters.
      
        --8<-- "plm-description.md"

        [Get started with PLM](../installation.md){.md-button}
        `,
        PSMDB: "Percona Server for MongoDB is an enhanced, source-available, and highly-scalable database that is a fully-compatible, drop-in replacement for MongoDB Community Edition.",
        K8SPS: "Percona Operator for MySQL allows users to deploy MySQL clusters with both asynchronous and group replication topology. This release includes various stability improvements and bug fixes, getting the Operator closer to the General Availability stage. Version 0.11.0 of the Percona Operator for MySQL is still a tech preview release, and it is not recommended for production environments.",
        K8SPSMDB: "",
        K8SPXC: "",
        P8SPG: "",
    };

    const applyIntroTemplate = (templateKey) => {
        if (templateKey in PRESET_INTRODUCTIONS) {
            customIntroEl.value = PRESET_INTRODUCTIONS[templateKey];
        } else {
            if (!customIntroEl.value) customIntroEl.value = '';
        }
    };

    const toggleUpstreamFields = () => {
        const isPSMDB = projectEl.value === 'PSMDB';
        upstreamUrlsEl.disabled = !isPSMDB;
        upstreamBugUrlsEl.disabled = !isPSMDB;
        upstreamUrlsEl.parentElement.classList.toggle('opacity-50', !isPSMDB);
        upstreamBugUrlsEl.parentElement.classList.toggle('opacity-50', !isPSMDB);
    };

    const toggleCertifiedImagesSection = () => {
        const operatorProjects = ['K8SPS', 'K8SPXC', 'K8SPG', 'K8SPSMDB'];
        const isOperator = operatorProjects.includes(projectEl.value);
        certifiedImagesSectionEl.classList.toggle('hidden', !isOperator);
    };

    introTemplateEl.addEventListener('change', (e) => {
        applyIntroTemplate(e.target.value);
    });
    projectEl.addEventListener('change', (e) => {
        introTemplateEl.value = e.target.value;
        applyIntroTemplate(introTemplateEl.value);
        toggleUpstreamFields();
        toggleCertifiedImagesSection();
    });

    if (id) {
        formTitle.textContent = 'Edit Release';
        const res = await fetch(`${API_BASE_URL}/api/releases/${id}`);
        const data = await res.json();
        document.getElementById('release-id').value = data._id;
        document.getElementById('version').value = data.version;
        document.getElementById('project').value = data.project;
        document.getElementById('plannedDate').value = data.plannedDate;
        document.getElementById('jiraReleaseId').value = data.jiraReleaseId || '';
        document.getElementById('additionalJiraTickets').value = data.additionalJiraTickets || '';
        document.getElementById('upstreamUrls').value = data.upstreamUrls;
        document.getElementById('releaseHighlights').value = data.releaseHighlights || '';
        document.getElementById('upstreamBugUrls').value = data.upstreamBugUrls || '';
        introTemplateEl.value = data.introTemplate || data.project || 'PSMDB';
        customIntroEl.value = data.customIntroduction || '';
        document.getElementById('supportedSoftware').value = data.supportedSoftware || '';
        document.getElementById('supportedPlatforms').value = data.supportedPlatforms || '';
        document.getElementById('certifiedImagesJsonUrl').value = data.certifiedImagesJsonUrl || '';
        document.getElementById('excludedImagesPatterns').value = data.excludedImagesPatterns || '';
        document.getElementById('groupSortPatterns').value = data.groupSortPatterns || '';
        toggleUpstreamFields();
        toggleCertifiedImagesSection();
    } else {
        introTemplateEl.value = 'PSMDB';
        customIntroEl.value = '';
        toggleUpstreamFields();
    }

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const releaseId = document.getElementById('release-id').value;
        const selectedProject = document.getElementById('project').value;
        const payload = {
            version: document.getElementById('version').value,
            project: selectedProject,
            plannedDate: document.getElementById('plannedDate').value,
            jiraReleaseId: document.getElementById('jiraReleaseId').value,
            additionalJiraTickets: document.getElementById('additionalJiraTickets').value,
            upstreamUrls: selectedProject === 'PSMDB' ? document.getElementById('upstreamUrls').value : '',
            releaseHighlights: document.getElementById('releaseHighlights').value,
            upstreamBugUrls: selectedProject === 'PSMDB' ? document.getElementById('upstreamBugUrls').value : '',
            introTemplate: document.getElementById('introTemplate').value,
            customIntroduction: document.getElementById('customIntroduction').value,
            supportedSoftware: document.getElementById('supportedSoftware').value,
            supportedPlatforms: document.getElementById('supportedPlatforms').value,
            certifiedImagesJsonUrl: document.getElementById('certifiedImagesJsonUrl').value,
            excludedImagesPatterns: document.getElementById('excludedImagesPatterns').value,
            groupSortPatterns: document.getElementById('groupSortPatterns').value,
        };

        const url = releaseId ? `${API_BASE_URL}/api/releases/${releaseId}` : `${API_BASE_URL}/api/releases`;
        const method = releaseId ? 'PUT' : 'POST';

        await fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        window.location.href = '/release#release-details/' + releaseId;
    });

    applyIntroTemplate(introTemplateEl.value);
    toggleUpstreamFields();
    toggleCertifiedImagesSection();
};

const renderReleaseDetails = async (id) => {
    const template = document.getElementById('release-details-template').content.cloneNode(true);
    appContainer.appendChild(template);
    appContainer.querySelector('[data-page]').classList.add('active');

    const res = await fetch(`${API_BASE_URL}/api/releases/${id}`);
    const data = await res.json();
    document.getElementById('details-version').textContent = `Version ${data.version}`;
    document.getElementById('details-project-date').textContent = `${data.project} - Planned for ${data.plannedDate}`;
    document.getElementById('edit-release-btn').href = `#edit-release/${id}`;

    if (data.generatedMarkdown) {
        document.getElementById('result-container').classList.remove('hidden');
        document.getElementById('result-output').textContent = data.generatedMarkdown;
        document.getElementById('result-preview').innerHTML = converter.makeHtml(data.generatedMarkdown);
    }

    document.getElementById('generate-btn').addEventListener('click', async () => {
        const btn = document.getElementById('generate-btn');
        const btnText = document.getElementById('generate-btn-text');
        const spinner = document.getElementById('generate-spinner');
        btn.disabled = true;
        btnText.textContent = 'Generating...';
        spinner.classList.remove('hidden');
        const genRes = await fetch(`${API_BASE_URL}/api/releases/${id}/generate`, { method: 'POST' });
        const genData = await genRes.json();
        if (genRes.ok) {
            document.getElementById('result-container').classList.remove('hidden');
            document.getElementById('result-output').textContent = genData.markdown;
            document.getElementById('result-preview').innerHTML = converter.makeHtml(genData.markdown);
        } else {
            alert(`Error: ${genData.error}`);
        }
        btn.disabled = false;
        btnText.textContent = 'Generate';
        spinner.classList.add('hidden');
    });

    document.getElementById('tab-markdown').addEventListener('click', () => showView('markdown'));
    document.getElementById('tab-preview').addEventListener('click', () => showView('preview'));
    document.getElementById('copy-btn').addEventListener('click', () => {
        navigator.clipboard.writeText(document.getElementById('result-output').textContent);
    });
};

const showView = (view) => {
    const tabMarkdown = document.getElementById('tab-markdown');
    const tabPreview = document.getElementById('tab-preview');
    const resultOutput = document.getElementById('result-output');
    const resultPreview = document.getElementById('result-preview');
    if (view === 'markdown') {
        tabMarkdown.classList.add('active');
        tabPreview.classList.remove('active');
        resultOutput.classList.remove('hidden');
        resultPreview.classList.add('hidden');
    } else {
        tabMarkdown.classList.remove('active');
        tabPreview.classList.add('active');
        resultOutput.classList.add('hidden');
        resultPreview.classList.remove('hidden');
    }
}

window.addEventListener('hashchange', router);
window.addEventListener('load', router);
