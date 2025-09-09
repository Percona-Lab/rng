const appContainer = document.getElementById('app-container');
const converter = new showdown.Converter();
let currentReleaseId = null;
const API_BASE_URL = 'http://127.0.0.1:8080';

// --- Router ---
const router = () => {
    const hash = window.location.hash || '#dashboard';
    const [path, id] = hash.split('/');
    currentReleaseId = id;
    
    appContainer.innerHTML = '';
    
    switch(path) {
        case '#dashboard': renderDashboard(); break;
        case '#settings': renderSettings(); break;
        default: renderDashboard();
    }
};

// --- Page Renderers ---
const renderDashboard = async () => {
    const template = document.getElementById('dashboard-template').content.cloneNode(true);
    appContainer.appendChild(template);
    appContainer.querySelector('[data-page]').classList.add('active');
    
    const releasesListEl = document.getElementById('releases-list');
    const projectFilterEl = document.getElementById('project-filter');
    releasesListEl.innerHTML = '<p>Loading releases...</p>';
    
    const response = await fetch(`${API_BASE_URL}/api/releases`);
    const allReleases = await response.json();

    // --- Populate Filter ---
    const projects = [...new Set(allReleases.map(r => r.project))].sort();
    projectFilterEl.innerHTML = '<option value="all">All Projects</option>' + projects.map(p => `<option value="${p}">${p}</option>`).join('');

    // --- Render Function ---
    const renderFilteredReleases = (filterValue) => {
        const filteredReleases = filterValue === 'all' 
            ? allReleases 
            : allReleases.filter(r => r.project === filterValue);

        if (filteredReleases.length === 0) {
            releasesListEl.innerHTML = '<p>No releases found for this project.</p>';
        } else {
            releasesListEl.innerHTML = filteredReleases.map(r => `
                <div class="flex justify-between items-center p-4 border-b last:border-b-0">
                    <div>
                        <a href="/release#release-details/${r._id}" class="text-lg font-semibold text-blue-600 hover:underline">${r.project} ${r.version}</a>
                        <p class="text-sm text-gray-500">Planned for: ${r.plannedDate}</p>
                    </div>
                    <a href="/release#edit-release/${r._id}" class="text-sm text-gray-500 hover:text-gray-800">Edit</a>
                </div>
            `).join('');
        }
        
        // Re-generate timeline with filtered releases
        generateTimeline(filteredReleases);
    };

    // --- Event Listener ---
    projectFilterEl.addEventListener('change', (e) => {
        renderFilteredReleases(e.target.value);
    });

    // --- Initial Render ---
    if (allReleases.length === 0) {
        releasesListEl.innerHTML = '<p>No releases found. Create one to get started!</p>';
    } else {
        renderFilteredReleases('all');
    }
};

// Timeline generation function
const generateTimeline = (releases) => {
  const timelineContainer = document.getElementById('timeline-container');
  timelineContainer.innerHTML = ''; // Clear previous timeline

  const releasesWithDates = releases.filter(r => r.plannedDate);

  if (releasesWithDates.length === 0) {
    timelineContainer.innerHTML = '<p class="text-gray-500 text-center py-8">No releases with planned dates</p>';
    return;
  }

  // Format data for Timeline3.js
  const timelineData = {
    title: {
      text: {
        headline: "Product Release Schedule",
        text: "<p>An overview of all planned product releases.</p>"
      }
    },
    events: releasesWithDates.map(release => {
      const projectConfig = {
          'PSMDB': { color: '#186d49', thumbnail: '/static/icons/mongodb.png' },
          'PBM':   { color: '#186d49', thumbnail: '/static/icons/mongodb.png' },
          'PLM':   { color: '#186d49', thumbnail: '/static/icons/mongodb.png' },
          'K8SPS':    { color: '#0b278c', thumbnail: '/static/icons/kubernetes.png' },
          'K8SPG':    { color: '#0b278c', thumbnail: '/static/icons/kubernetes.png' },
          'K8SPSMDB': { color: '#0b278c', thumbnail: '/static/icons/kubernetes.png' },
          'K8SPXC':   { color: '#0b278c', thumbnail: '/static/icons/kubernetes.png' }
      };

      const config = projectConfig[release.project] || { color: '#7f8c8d', thumbnail: '' };

      const date = new Date(release.plannedDate);
      return {
        start_date: {
          year: date.getFullYear(),
          month: date.getMonth() + 1,
          day: date.getDate()
        },
        text: {
          headline: `${release.project} ${release.version}`,
          text: `Planned release for ${release.project}. <a href="/release#release-details/${release._id}">View Details</a>`
        },
        background: {
            color: config.color
        },
        media: {
            thumbnail: config.thumbnail
        },
        group: release.project
      };
    })
  };

  const options = {
    hash_bookmark: true,
    initial_zoom: 2,
    timenav_position: 'top',
  };

  // Initialize Timeline
  window.timeline = new TL.Timeline('timeline-container', timelineData, options);
};

const renderSettings = async () => {
    const template = document.getElementById('settings-template').content.cloneNode(true);
    appContainer.appendChild(template);
    appContainer.querySelector('[data-page]').classList.add('active');

    const res = await fetch(`${API_BASE_URL}/api/settings`);
    const data = await res.json();
    document.getElementById('jiraUrl').value = data.jiraUrl || '';
    document.getElementById('jiraEmail').value = data.jiraEmail || '';
    document.getElementById('jiraToken').value = data.jiraToken || '';
    document.getElementById('geminiToken').value = data.geminiToken || '';

    document.getElementById('settings-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            jiraUrl: document.getElementById('jiraUrl').value,
            jiraEmail: document.getElementById('jiraEmail').value,
            jiraToken: document.getElementById('jiraToken').value,
            geminiToken: document.getElementById('geminiToken').value,
        };
        await fetch(`${API_BASE_URL}/api/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        alert('Settings saved!');
    });
};

// --- Initial Load and Navigation ---
window.addEventListener('hashchange', router);
window.addEventListener('load', router);
document.body.addEventListener('click', e => {
    if (e.target.matches('.nav-link')) {
        e.preventDefault();
        window.location.hash = e.target.getAttribute('href');
    }
});
