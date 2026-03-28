const API = window.location.hostname === 'localhost' ? 'http://localhost:5000': 'https://analizador-repositorios-production-57ab.up.railway.app';

const WAIT_TIME = 2000 //en ms
const HIGH_SCORE = 85
const GOOD_SCORE = 70
const REGULAR_SCORE = 50
const MAX_TIMEOUT = 1500 // en ms

const WAITING_MESSAGES = [
    'Conectando con GitHub...',
    'Obteniendo información del repo...',
    'Analizando commits...',
    'Analizando contributors...',
    'Calculando tamaño del repo...',
    'Calculando Commits por mes...',
    'Calculando Commits por semana...',
    'Armando gráfico con lenguajes usados...',
    'Calculando Commits por dia de la semana...',
    'Calculando Commits por hora del dia...',
    'Armando gráfico con contributors...',
    'Calculando salud del repo...',
    'Analizando issues y PRS...',
    'Armando gráfico issues y PRS...',
    'Analizando código...',
    'Analizando longitud de funciones...'
]
const MB_SIZE = 1024
const CHART_SIZE = 10
const CHART_COLOR = '#6b6b80'
const GRID_COLOR = '#1e1e2e'
const ERROR_BOX_ID = 'errorBox'
const WARNING_ICON = '⚠ '
const REPO_INPUT_ID = 'repoInput'
const DASHBOARD_ID = 'dashboard'
const ANALIZEBTN_ID = 'analyzeBtn'
const SPINNER_WRAP_ID = 'spinnerWrap'
const SPINNER_MESSAGE_ID = 'spinnerMsg'
const ERROR_UNKNON_MESSAGE = 'Error desconocido'
const STANDARD_ERROR_MESSAGE = 'No se pudo conectar con el servidor. ¿Está corriendo el backend?'
const NONE_DISPLAY_SYLE = 'none'
const FUNC_OK = 'funcOk'
const FUNC_WARN = 'funcWarn'
const FUNC_CRIT = 'funcCrit'
const FUNC_STATUS = '.func-stat'
const CHART_BORDER_RADIOUS = 4
const CHART_BACKGROUND_COLOR = '99'

const WEEK_DAYS = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']

const ACCENT  = '#e8e8f0'
const ACCENT2 = '#f76f6f'

let charts = {}

function scoreColor(score) {
    if (score >= HIGH_SCORE){
        return '#4ecca3'
    }
    if (score >= GOOD_SCORE){
        return '#e8e8f0'
    }
    if (score >= REGULAR_SCORE){
        return '#f7c948'
    } 
    return '#f76f6f'
}

function toggleModal() {
    const overlay = document.getElementById('modalOverlay')
    overlay.classList.toggle('active')
}

document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
        document.getElementById('modalOverlay').classList.remove('active')
    }
})

function destroyCharts() {
    Object.values(charts).forEach(c => c.destroy())
    charts = {}
}

function chartDefaults() {
    return {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
            x: { ticks: { color: CHART_COLOR, font: { size: CHART_SIZE } }, grid: { color: GRID_COLOR } },
            y: { ticks: { color: CHART_COLOR, font: { size: CHART_SIZE } }, grid: { color: GRID_COLOR } },
        }
    }
}

function showError(msg) {
    const box = document.getElementById(ERROR_BOX_ID)
    box.textContent = WARNING_ICON + msg
    box.style.display = 'block'
}

async function fetchWithRetry(url, options, retries = 2) {
    for (let i = 0; i <= retries; i++) {
        try {
            const res = await fetch(url, options)
            if (res.ok) return res
        } catch(e) {
            if (i === retries) throw e
            await new Promise(r => setTimeout(r, MAX_TIMEOUT))
        }
    }
}

async function analyzeRepo() {
    const url = document.getElementById(REPO_INPUT_ID).value.trim()
    if (!url){
        return
    }
 
    document.getElementById(ERROR_BOX_ID).style.display = NONE_DISPLAY_SYLE
    document.getElementById(DASHBOARD_ID).style.display = NONE_DISPLAY_SYLE
    document.getElementById(SPINNER_WRAP_ID).style.display = 'block'
    document.getElementById(ANALIZEBTN_ID).disabled = true
    destroyCharts()

    let msgIndex = 0
    const msgInterval = setInterval(() => {
        msgIndex = (msgIndex + 1) % WAITING_MESSAGES.length
        document.getElementById(SPINNER_MESSAGE_ID).textContent = WAITING_MESSAGES[msgIndex]
    }, WAIT_TIME)
 
    try {
        const res  = await fetchWithRetry(`${API}/analyze`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ repo_url: url }) })
        clearInterval(msgInterval)
        const data = await res.json()
        if (!res.ok) {
            showError(data.error || ERROR_UNKNON_MESSAGE)
            return
        }
        renderDashboard(data.analysis)
 
    } catch(e) {
        showError(STANDARD_ERROR_MESSAGE)
    } finally {
        clearInterval(msgInterval)
        document.getElementById(SPINNER_WRAP_ID).style.display = NONE_DISPLAY_SYLE
        document.getElementById(ANALIZEBTN_ID).disabled = false
    }
}

function renderHeader(analysis, m, score){
    document.getElementById('repoTitle').textContent = analysis.repo_full_name
    document.getElementById('repoLink').href = m.basic_info.url
    document.getElementById('scoreNumber').textContent = `${score}/100`
    document.getElementById('scoreNumber').style.color = scoreColor(score)
    document.getElementById('scoreLabel').textContent = m.score_label
}

function renderMeta(m) {
    const meta = document.getElementById('repoMeta')
    meta.innerHTML = ''
    const isActive = m.activity.is_active
    meta.innerHTML += `<span class="tag ${isActive ? 'active' : 'inactive'}"> ${isActive ? '⚡ Activo' : '💤 Inactivo'} </span>`
    
    if (m.basic_info.license) {
        meta.innerHTML += `<span class="tag">📄 ${m.basic_info.license}</span>`
    }

    meta.innerHTML += `<span class="tag">🍴 ${m.basic_info.forks} forks</span>`
    meta.innerHTML += `<span class="tag">👁 ${m.basic_info.watchers} watchers</span>`
    meta.innerHTML += `<span class="tag">⭐ ${m.basic_info.stars} stars</span>`
    meta.innerHTML += `<span class="tag">👥 ${m.contributors.total} contributors</span>`
}

function renderStats(m) {
    document.getElementById('statCommits').textContent = m.activity.total_commits
    document.getElementById('statContribs').textContent = m.issues_prs.issues.open || 'No hay'
    document.getElementById('statCpw').textContent = m.activity.commits_per_week_avg

    const openPRs = m.issues_prs.prs.open
    document.getElementById('statOpenPRs').textContent = openPRs > 0 ? openPRs : 'No hay'
}

function renderExtraStats(m) {
    document.getElementById('statLastCommit').textContent = new Date(m.activity.last_commit).toLocaleDateString('es-AR')

    document.getElementById('statActivityTime').textContent = m.activity.activity_time

    document.getElementById('issueTime').textContent = m.issues_prs.issues.avg_close_days ?? 'N/A'

    document.getElementById('prTime').textContent = m.issues_prs.prs.avg_merge_days ?? 'N/A'

    document.getElementById('statSize').textContent = m.basic_info.size_kb > MB_SIZE ? `${(m.basic_info.size_kb / MB_SIZE).toFixed(1)} MB` : `${m.basic_info.size_kb} KB`

    document.getElementById('statFirstCommit').textContent = new Date(m.activity.first_commit).toLocaleDateString('es-AR')

    document.getElementById('statDaysSilent').textContent = m.activity.days_since_last_commit ?? '—'

    const monthCount = m.activity.commits_per_month.length
    const cpmAvg = monthCount > 0 ? (m.activity.total_commits / monthCount).toFixed(1) : '—'

    document.getElementById('statCpm').textContent = cpmAvg
}

function renderHealth(health) {
    const checks = {
        'README': health.has_readme,
        'Licencia': health.has_license,
        '.gitignore': health.has_gitignore,
        'CONTRIBUTING': health.has_contributing,
        'CHANGELOG': health.has_changelog,
        'Descripción': health.has_description,
        'Topics/Tags': health.has_topics,
        }
    const hList = document.getElementById('healthList')
    hList.innerHTML = ''

    Object.entries(checks).forEach(([label, val]) => {
        hList.innerHTML += `
        <div class="check-item">
            <div class="dot ${val ? 'yes' : 'no'}"></div>
            <span style="color:${val ? 'var(--text)' : 'var(--muted)'}">${label}</span>
            <span style="margin-left:auto;font-size:0.75rem;color:${val ? 'var(--ok)' : 'var(--critical)'}">
                ${val ? '✓' : '✗'}
            </span>
        </div>`
    })
}

function renderContributors(contributors) {
    const existingList = document.querySelector('.contrib-list')
    if (existingList) {
        const canvas = document.createElement('canvas')
        canvas.id = 'chartContribs'
        existingList.replaceWith(canvas)
    }

    const top = contributors.ranking.slice(0, 10)
    const contribCanvas = document.getElementById('chartContribs')
    const contribList = document.createElement('div')
    contribList.className = 'contrib-list'

    top.forEach(c => {
        const addFmt = c.additions > 999 ? `+${(c.additions/1000).toFixed(1)}k` : `+${c.additions}`
        const delFmt = c.deletions > 999 ? `-${(c.deletions/1000).toFixed(1)}k` : `-${c.deletions}`
        contribList.innerHTML += `
        <div class="contrib-item" data-tooltip="${c.ownership_pct}% de los commits">
            <a href="https://github.com/${c.username}" target="_blank" class="contrib-avatar-link">
                <img src="${c.avatar_url}" alt="${c.username}" class="contrib-avatar"/>
            </a>
            <div class="contrib-info">
                <a href="https://github.com/${c.username}" target="_blank" class="contrib-name">${c.username}</a>
                <div class="contrib-bar-wrap">
                    <div class="contrib-bar" style="width:${c.ownership_pct}%"></div>
                </div>
            </div>
            <div class="contrib-stats">
                <span class="contrib-commits">${c.commits} commits</span>
                <span class="contrib-lines">
                    <span class="contrib-add">${addFmt}</span>
                    <span class="contrib-del">${delFmt}</span>
                </span>
            </div>
        </div>`
    })
    contribCanvas.replaceWith(contribList)
}

function renderCharts(m) {
    const cpm = m.activity.commits_per_month
    charts.commits = new Chart(document.getElementById('chartCommits'), {
        type: 'line',
        data: {
            labels: cpm.map(e => e.month),
            datasets: [{
                data: cpm.map(e => e.count),
                borderColor: ACCENT,
                backgroundColor: ACCENT + '22',
                fill: true,
                tension: 0.4,
                pointRadius: 3
            }]
        },
        options: chartDefaults()
    })

    const cpw = m.activity.commits_per_week
    charts.weeks = new Chart(document.getElementById('chartWeeks'), {
        type: 'bar',
        data: {
            labels: cpw.map(e => e.week),
            datasets: [{
                data: cpw.map(e => e.count),
                backgroundColor: ACCENT + CHART_BACKGROUND_COLOR,
                borderRadius: CHART_BORDER_RADIOUS
            }]
        },
        options: chartDefaults()
    })

    const hours = m.activity.commits_by_hour
    charts.hours = new Chart(document.getElementById('chartHours'), {
        type: 'bar',
        data: {
            labels: Object.keys(hours).map(h => `${h}hs`),
            datasets: [{
                data: Object.values(hours),
                backgroundColor: ACCENT2 + CHART_BACKGROUND_COLOR,
                borderRadius: CHART_BORDER_RADIOUS
            }]
        },
        options: chartDefaults()
    })

    const langs = m.languages
    charts.langs = new Chart(document.getElementById('chartLangs'), {
        type: 'doughnut',
        data: {
            labels: Object.keys(langs),
            datasets: [{
                data: Object.values(langs),
                backgroundColor: ['#e8e8f0','#f76f6f','#f7c948','#4ecca3','#60a5fa','#fb923c']
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'right',
                    labels: { color: '#e8e8f0', font: { size: 11 } }
                }
            }
        }
    })

    const wd = m.activity.commits_by_weekday

    charts.weekday = new Chart(document.getElementById('chartWeekday'), {
        type: 'bar',
        data: {
            labels: WEEK_DAYS,
            datasets: [{
                data: WEEK_DAYS.map(d => wd[d] || 0),
                backgroundColor: ACCENT + CHART_BACKGROUND_COLOR,
                borderRadius: CHART_BORDER_RADIOUS
            }]
        },
        options: chartDefaults()
    })

    charts.issues = new Chart(document.getElementById('chartIssues'), {
        type: 'bar',
        data: {
            labels: ['Issues aun abiertos', 'Issues cerrados', 'PRs aun abiertos', 'PRs cerrados'],
            datasets: [{
                data: [
                    m.issues_prs.issues.open,
                    m.issues_prs.issues.closed_sample,
                    m.issues_prs.prs.open,
                    m.issues_prs.prs.closed_sample
                ],
                backgroundColor: ['#f76f6f99','#e8e8f099','#f7c94899','#4ecca399'],
                borderRadius: CHART_BORDER_RADIOUS
            }]
        },
        options: chartDefaults()
    })
}

function renderFunctions(funcs) {
    if (!funcs.supported) {
        document.getElementById('functionsCard').innerHTML = `
            <h4>Calidad de código</h4>
            <p style="color:var(--muted);font-size:0.85rem;margin-top:0.5rem">
                ${funcs.message}
            </p>`
        return
    }

    const fList = document.getElementById('funcList')
    const activeFilters = new Set(['warning', 'critical'])

    function renderList() {
        fList.innerHTML = ''
        const visible = funcs.functions.filter(f => activeFilters.has(f.status))

        if (visible.length === 0) {
            fList.innerHTML += `<p style="color:var(--muted);font-size:0.85rem;padding:0.5rem 0">
                No hay funciones para mostrar.
            </p>`
            return
        }

        visible.forEach(f => {
            fList.innerHTML += `
                <div class="func-item">
                    <div>
                        <div class="fname">${f.name}</div>
                        <div class="ffile">${f.file} · línea ${f.line}</div>
                    </div>
                    <span class="func-badge ${f.status}">${f.length} líneas</span>
                </div>`
        })
    }

    function setupStats() {
        const statEls = {
            ok: document.getElementById(FUNC_OK).closest(FUNC_STATUS),
            warning: document.getElementById(FUNC_WARN).closest(FUNC_STATUS),
            critical: document.getElementById(FUNC_CRIT).closest(FUNC_STATUS),
        }

        document.getElementById(FUNC_OK).textContent = funcs.summary.ok
        document.getElementById(FUNC_WARN).textContent = funcs.summary.warning
        document.getElementById(FUNC_CRIT).textContent = funcs.summary.critical
        Object.entries(statEls).forEach(([status, el]) => {
            el.style.cursor = 'pointer'
            el.style.opacity = activeFilters.has(status) ? '1' : '0.35'
            const fresh = el.cloneNode(true)
            el.parentNode.replaceChild(fresh, el)
            fresh.addEventListener('click', () => {
                if (activeFilters.has(status)) {
                    activeFilters.delete(status)
                    fresh.style.opacity = '0.35'
                } else {
                    activeFilters.add(status)
                    fresh.style.opacity = '1'
                }
                renderList()
                })
            })
    }
    setupStats()
    renderList()
}

function renderDashboard(analysis) {
    const { metrics: m, score } = analysis
    renderHeader(analysis, m, score)
    renderMeta(m)
    renderStats(m)
    renderExtraStats(m)
    renderCharts(m)
    renderContributors(m.contributors)
    renderHealth(m.health)
    renderFunctions(m.functions)

    document.getElementById(DASHBOARD_ID).style.display = 'block'
    document.getElementById(DASHBOARD_ID).scrollIntoView({ behavior: 'smooth' })
}
 
document.getElementById('repoInput').addEventListener('keydown', e => {
    if (e.key === 'Enter'){
        analyzeRepo()
    } 
})

fetch(`${API}/health`).catch(() => {})