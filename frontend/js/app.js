const API = window.location.hostname === 'localhost' ? 'http://localhost:5000': 'https://analizador-repositorios-production-57ab.up.railway.app';

const WAIT_TIME = 2000 //en ms

let charts = {}

function scoreColor(score) {
    if (score >= 85){
        return '#4ecca3'
    }
    if (score >= 70){
        return '#e8e8f0'
    }
    if (score >= 50){
        return '#f7c948'
    } 
    return '#f76f6f'
}

function destroyCharts() {
    Object.values(charts).forEach(c => c.destroy())
    charts = {}
}

function chartDefaults() {
    return {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
            x: { ticks: { color: '#6b6b80', font: { size: 10 } }, grid: { color: '#1e1e2e' } },
            y: { ticks: { color: '#6b6b80', font: { size: 10 } }, grid: { color: '#1e1e2e' } },
        }
    }
}

function showError(msg) {
    const box = document.getElementById('errorBox')
    box.textContent = '⚠ ' + msg
    box.style.display = 'block'
}

async function fetchWithRetry(url, options, retries = 2) {
    for (let i = 0; i <= retries; i++) {
        try {
            const res = await fetch(url, options)
            if (res.ok) return res
        } catch(e) {
            if (i === retries) throw e
            await new Promise(r => setTimeout(r, 1500))
        }
    }
}

async function analyzeRepo() {
    const url = document.getElementById('repoInput').value.trim()
    if (!url){
        return
    }
 
    document.getElementById('errorBox').style.display = 'none'
    document.getElementById('dashboard').style.display = 'none'
    document.getElementById('spinnerWrap').style.display = 'block'
    document.getElementById('analyzeBtn').disabled = true
    destroyCharts()

    const messages = [
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

    let msgIndex = 0
    const msgInterval = setInterval(() => {
        msgIndex = (msgIndex + 1) % messages.length
        document.getElementById('spinnerMsg').textContent = messages[msgIndex]
    }, WAIT_TIME)
 
    try {
        const res  = await fetchWithRetry(`${API}/analyze`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ repo_url: url })
        })
        clearInterval(msgInterval)
        const data = await res.json()
        if (!res.ok) {
            showError(data.error || 'Error desconocido')
            return
        }
        renderDashboard(data.analysis)
 
    } catch(e) {
        showError('No se pudo conectar con el servidor. ¿Está corriendo el backend?')
    } finally {
        clearInterval(msgInterval)
        document.getElementById('spinnerWrap').style.display = 'none'
        document.getElementById('analyzeBtn').disabled       = false
    }
}

function renderDashboard(analysis) {
    const m = analysis.metrics
    const score = analysis.score
 
    document.getElementById('repoTitle').textContent = analysis.repo_full_name
    document.getElementById('repoLink').href = m.basic_info.url
    document.getElementById('scoreNumber').textContent = `${score}/100`
    document.getElementById('scoreNumber').style.color = scoreColor(score)
    document.getElementById('scoreLabel').textContent = m.score_label
    
    const meta     = document.getElementById('repoMeta')
    meta.innerHTML = ''
    const isActive = m.activity.is_active
    meta.innerHTML += `<span class="tag ${isActive ? 'active' : 'inactive'}">${isActive ? '⚡ Activo' : '💤 Inactivo'}</span>`
    if (m.basic_info.license) meta.innerHTML += `<span class="tag">📄 ${m.basic_info.license}</span>`
    meta.innerHTML += `<span class="tag">🍴 ${m.basic_info.forks} forks</span>`
    meta.innerHTML += `<span class="tag">👁 ${m.basic_info.watchers} watchers</span>`
    meta.innerHTML += `<span class="tag">⭐ ${m.basic_info.stars} stars</span>`
    
    document.getElementById('statCommits').textContent = m.activity.total_commits
    document.getElementById('statContribs').textContent = m.contributors.total
    document.getElementById('statCpw').textContent = m.activity.commits_per_week_avg

    const openPRs = m.issues_prs.prs.open
    document.getElementById('statOpenPRs').textContent = openPRs > 0 ? openPRs : 'No hay'
 
    const ACCENT  = '#e8e8f0'
    const ACCENT2 = '#f76f6f'

    document.getElementById('statLastCommit').textContent = new Date(m.activity.last_commit).toLocaleDateString('es-AR')

    document.getElementById('statActivityTime').textContent = m.activity.activity_time

    const cpm = m.activity.commits_per_month
    charts.commits = new Chart(document.getElementById('chartCommits'), {
        type: 'line',
        data: {
        labels:   cpm.map(e => e.month),
        datasets: [{ data: cpm.map(e => e.count), borderColor: ACCENT, backgroundColor: ACCENT + '22', fill: true, tension: 0.4, pointRadius: 3 }]
    },
    options: chartDefaults()
    })

    const cpw_data = m.activity.commits_per_week
    charts.weeks = new Chart(document.getElementById('chartWeeks'), {
        type: 'bar',
        data: {
            labels:   cpw_data.map(e => e.week),
            datasets: [{ data: cpw_data.map(e => e.count), backgroundColor: ACCENT + '99', borderRadius: 4 }]
        },
        options: chartDefaults()
    })

    const hours = m.activity.commits_by_hour
    charts.hours = new Chart(document.getElementById('chartHours'), {
        type: 'bar',
        data: {
            labels:   Object.keys(hours).map(h => `${h}hs`),
            datasets: [{
                data: Object.values(hours),
                backgroundColor: ACCENT2 + '99',
                borderRadius: 4
            }]
        },
        options: chartDefaults()
    })

    const langs = m.languages
    charts.langs = new Chart(document.getElementById('chartLangs'), {
        type: 'doughnut',
        data: {
        labels:   Object.keys(langs),
        datasets: [{ data: Object.values(langs), backgroundColor: ['#e8e8f0','#f76f6f','#f7c948','#4ecca3','#60a5fa','#fb923c'] }]
    },
    options: {
        responsive: true,
        plugins: { legend: { position: 'right', labels: { color: '#e8e8f0', font: { size: 11 } } } }
    }
    })

    const wd      = m.activity.commits_by_weekday
    const wdOrder = ['Lunes','Martes','Miércoles','Jueves','Viernes','Sábado','Domingo']
    charts.weekday = new Chart(document.getElementById('chartWeekday'), {
        type: 'bar',
        data: {
        labels:   wdOrder, datasets: [{ data: wdOrder.map(d => wd[d] || 0), backgroundColor: ACCENT + '99', borderRadius: 4 }]
    },
    options: chartDefaults()
    })

    const top = m.contributors.ranking.slice(0, 10)
    charts.contribs = new Chart(document.getElementById('chartContribs'), {
    type: 'bar',
    data: {
        labels:   top.map(c => c.username),
        datasets: [{ data: top.map(c => c.commits), label: 'Commits', backgroundColor: ACCENT2 + '99', borderRadius: 4 }]
    },
    options: { ...chartDefaults(), indexAxis: 'y' }
    })
 
    charts.issues = new Chart(document.getElementById('chartIssues'), {
    type: 'bar',
    data: {
        labels: ['Issues abiertas', 'Issues cerradas', 'PRs abiertas', 'PRs cerradas'],
        datasets: [{
            data: [
            m.issues_prs.issues.open,
            m.issues_prs.issues.closed_sample,
            m.issues_prs.prs.open,
            m.issues_prs.prs.closed_sample,
            ],
            backgroundColor: ['#f76f6f99','#e8e8f099','#f7c94899','#4ecca399'],
            borderRadius: 4
        }]
    },
    options: chartDefaults()
    })
 
    document.getElementById('issueTime').textContent = m.issues_prs.issues.avg_close_days ?? 'N/A'
    document.getElementById('prTime').textContent = m.issues_prs.prs.avg_merge_days ?? 'N/A'

    document.getElementById('statSize').textContent =  m.basic_info.size_kb > 1024 ? `${(m.basic_info.size_kb / 1024).toFixed(1)} MB` : `${m.basic_info.size_kb} KB`

    document.getElementById('statFirstCommit').textContent = new Date(m.activity.first_commit).toLocaleDateString('es-AR')

    document.getElementById('statDaysSilent').textContent = m.activity.days_since_last_commit ?? '—'

    const monthCount = Object.keys(m.activity.commits_per_month).length
    const cpmAvg = monthCount > 0 ? (m.activity.total_commits / monthCount).toFixed(1) : '—'
    document.getElementById('statCpm').textContent = cpmAvg
 
    const health = m.health
    const checks = {
    'README':       health.has_readme,
    'Licencia':     health.has_license,
    '.gitignore':   health.has_gitignore,
    'CONTRIBUTING': health.has_contributing,
    'CHANGELOG':    health.has_changelog,
    'Descripción':  health.has_description,
    'Topics/Tags':  health.has_topics,
    }
    const hList    = document.getElementById('healthList')
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
 
    const funcs = m.functions
    if (funcs.supported) {

        const fList = document.getElementById('funcList')
        fList.innerHTML = ''
        const activeFilters = new Set(['warning', 'critical'])

        function render_functions() {
            fList.innerHTML = ''
            const visible = funcs.functions.filter(f => activeFilters.has(f.status))
            if (visible.length == 0){
                fList.innerHTML = `<p style="color:var(--muted);font-size:0.85rem;padding:0.5rem 0">No hay funciones para mostrar.</p>`
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

        function setupFuncStats(){
            const statEls = {
                ok: document.getElementById('funcOk').closest('.func-stat'),
                warning: document.getElementById('funcWarn').closest('.func-stat'),
                critical: document.getElementById('funcCrit').closest('.func-stat'),
            }

            document.getElementById('funcOk').textContent = funcs.summary.ok
            document.getElementById('funcWarn').textContent = funcs.summary.warning
            document.getElementById('funcCrit').textContent = funcs.summary.critical
    
            Object.entries(statEls).forEach(([status, el]) => {
                el.style.cursor = 'pointer'
                el.style.opacity = activeFilters.has(status) ? '1' : '0.35'
                el.style.transition = 'opacity 0.2s'

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
                    render_functions()
                    })
                })
        }
        setupFuncStats()
        render_functions()
    } else {
        document.getElementById('functionsCard').innerHTML = ` <h4>Calidad de código</h4>
        <p style="color:var(--muted);font-size:0.85rem;margin-top:0.5rem">${funcs.message}</p>`
    }
    document.getElementById('dashboard').style.display = 'block'
    document.getElementById('dashboard').scrollIntoView({ behavior: 'smooth' })

}
 
document.getElementById('repoInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') analyzeRepo()
})

fetch(`${API}/health`).catch(() => {})