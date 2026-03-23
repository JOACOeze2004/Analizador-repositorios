const API = 'https://analizador-repositorios-production-57ab.up.railway.app'    // http://localhost:5000 para debugear en local
//const API = 'http://localhost:5000'
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

async function analyzeRepo() {
    const url = document.getElementById('repoInput').value.trim()
    if (!url){
        return
    }
 
    document.getElementById('errorBox').style.display    = 'none'
    document.getElementById('dashboard').style.display   = 'none'
    document.getElementById('spinnerWrap').style.display = 'block'
    document.getElementById('analyzeBtn').disabled       = true
    destroyCharts()
 
    try {
        const res  = await fetch(`${API}/analyze`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify({ repo_url: url })
        })
        const data = await res.json()
        if (!res.ok) {
        showError(data.error || 'Error desconocido')
        return
        }
        renderDashboard(data.analysis)
 
    } catch(e) {
        showError('No se pudo conectar con el servidor. ¿Está corriendo el backend?')
    } finally {
        document.getElementById('spinnerWrap').style.display = 'none'
        document.getElementById('analyzeBtn').disabled       = false
    }
}

function renderDashboard(analysis) {
    const m = analysis.metrics
    const score = analysis.score
 
    document.getElementById('repoTitle').textContent    = analysis.repo_full_name
    document.getElementById('repoLink').href            = m.basic_info.url
    document.getElementById('scoreNumber').textContent  = `${score}/100`
    document.getElementById('scoreNumber').style.color  = scoreColor(score)
    document.getElementById('scoreLabel').textContent   = m.score_label
    
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
    document.getElementById('statBus').textContent = m.contributors.bus_factor
 
    const ACCENT  = '#e8e8f0'
    const ACCENT2 = '#f76f6f'

    const cpm = m.activity.commits_per_month
    charts.commits = new Chart(document.getElementById('chartCommits'), {
        type: 'line',
        data: {
        labels:   Object.keys(cpm),
        datasets: [{ data: Object.values(cpm), borderColor: ACCENT, backgroundColor: ACCENT + '22', fill: true, tension: 0.4, pointRadius: 3 }]
    },
    options: chartDefaults()
    })

    const cpw_data = m.activity.commits_per_week
    charts.weeks = new Chart(document.getElementById('chartWeeks'), {
        type: 'bar',
        data: {
            labels:   Object.keys(cpw_data),
            datasets: [{ 
                data: Object.values(cpw_data), 
                backgroundColor: ACCENT + '99', 
                borderRadius: 4 
            }]
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
        document.getElementById('funcOk').textContent   = funcs.summary.ok
        document.getElementById('funcWarn').textContent = funcs.summary.warning
        document.getElementById('funcCrit').textContent = funcs.summary.critical
 
        const fList = document.getElementById('funcList')
        fList.innerHTML = ''
        const critical_funcs = funcs.functions.filter(f => f.status !== 'ok')
        const all_funcs = funcs.functions
        let show_all = false

        function render_functions(functions) {
            fList.innerHTML = ''
            functions.forEach(f => {
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
        render_functions(critical_funcs)

        const btnToggle = document.createElement('button')
        btnToggle.className = 'btn-toggle-funcs'
        btnToggle.textContent = `Ver todas (${all_funcs.length})`
        btnToggle.onclick = () => {
            show_all = !show_all
            render_functions(show_all ? all_funcs : critical_funcs)
            btnToggle.textContent = show_all 
                ? `Ver solo problemáticas (${critical_funcs.length})`
                : `Ver todas (${all_funcs.length})`
        }
        fList.after(btnToggle)

    } else {
        document.getElementById('functionsCard').innerHTML = `
        <h4>Calidad de código</h4>
        <p style="color:var(--muted);font-size:0.85rem;margin-top:0.5rem">${funcs.message}</p>`
    }
    document.getElementById('dashboard').style.display = 'block'
    document.getElementById('dashboard').scrollIntoView({ behavior: 'smooth' })
}
 
document.getElementById('repoInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') analyzeRepo()
})