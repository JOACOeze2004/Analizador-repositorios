from github import Github, GithubException
from datetime import datetime, timezone
from collections import defaultdict
from datetime import timedelta

MAX_COMMITS = 5000
MAX_CONTRIBUTORS = 50
ERROR_NOT_FOUND = 404
EMPTY_ACTIVITY = {
    'total_commits': 0,
    'commits_per_month': [],
    'commits_by_weekday': {},
    'commits_by_hour': {},
    'first_commit': None,
    'last_commit': None,
    'is_active': False,
    'commits_per_week_avg': 0,
}

EMPTY_CONTRIBUTORS = {
    'total': 0,
    'bus_factor': 0,
    'ranking': []
}

WEEKDAY_NAMES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

ACTIVITY_ACTIVE_DAYS_THRESHOLD = 90
BUS_FACTOR_THRESHOLD = 80
HOURS_RANGE = range(24)
DAYS_PER_YEAR = 365
DAYS_PER_MONTH = 30
MAX_DAYS_PER_MONTH = 31
MONTHS_PER_YEAR = 12


class GithubService:

    def __init__(self, token=None):
        self.client = Github(token) if token else Github()
        # Sin token: 60 requests/hora. Con token: 5000 requests/hora.
    
    def get_repo(self, repo_url):
        full_name = self.parse_repo_url(repo_url)
        try:
            return self.client.get_repo(full_name)
        except GithubException as e:
            if e.status == ERROR_NOT_FOUND:
                raise ValueError(f"Repositorio '{full_name}' no encontrado.")
            raise Exception(f"Error al conectar con GitHub: {e.data.get('message', str(e))}")
        
    def get_basic_info(self, repo):
        return {
            'name':          repo.name,
            'owner':         repo.owner.login,
            'full_name':     repo.full_name,
            'url':           repo.html_url,
            'description':   repo.description,
            'created_at':    repo.created_at.isoformat(),
            'updated_at':    repo.updated_at.isoformat(),
            'stars':         repo.stargazers_count,
            'forks':         repo.forks_count,
            'watchers':      repo.subscribers_count,
            'open_issues':   repo.open_issues_count,
            'default_branch':repo.default_branch,
            'license':       repo.license.name if repo.license else None,
            'size_kb':       repo.size,
        }
    
    def get_languages(self, repo):
        raw = repo.get_languages()
        total = sum(raw.values())
        if total == 0:
            return {}
        return {
            lang: round((bytes_ / total) * 100, 1)
            for lang, bytes_ in sorted(raw.items(), key=lambda x: x[1], reverse=True)
        }
    

    def process_commit_dates(self, commits):
        commits_per_month = defaultdict(int)
        commits_by_weekday = defaultdict(int)
        commits_by_hour = defaultdict(int)
        commits_per_week = defaultdict(int)

        for commit in commits:
            date = commit.commit.author.date

            month_key = date.replace(day=1).date()
            commits_per_month[month_key] += 1
            commits_by_weekday[WEEKDAY_NAMES[date.weekday()]] += 1
            commits_by_hour[date.hour] += 1

            monday = date - timedelta(days=date.weekday())
            commits_per_week[monday.date()] += 1

        return commits_per_month, commits_by_weekday, commits_by_hour, commits_per_week
    
    def calculate_activity_stats(self, commits):
        dates = [c.commit.author.date for c in commits]

        first = min(dates)
        last = max(dates)

        now = datetime.now(timezone.utc)
        last_aware = last if last.tzinfo else last.replace(tzinfo=timezone.utc)
        days_since_last = (now - last_aware).days
        is_active = days_since_last < ACTIVITY_ACTIVE_DAYS_THRESHOLD

        total_weeks = max((last_aware - first.replace(tzinfo=timezone.utc)).days / 7, 1)
        commits_per_week_avg = round(len(commits) / total_weeks, 1)

        return first, last, is_active, days_since_last, commits_per_week_avg
    
    def format_activity_time(self, first, last):
        first = first if first.tzinfo else first.replace(tzinfo=timezone.utc)
        last = last if last.tzinfo else last.replace(tzinfo=timezone.utc)

        delta = last - first
        days = delta.days
        years = days // DAYS_PER_YEAR
        months = (days % DAYS_PER_YEAR) // DAYS_PER_MONTH
        remaining_days = days % DAYS_PER_MONTH

        if years >= 1 and months > 0:
            return f'{years}a {months}m {remaining_days}d'
        if years >= 1:
            return f'{years}a {remaining_days}d'        
        if months > 0 :
            return f'{months} m {remaining_days} d'
        return f'{days} días'

    def get_commit_activity(self, repo):
        commits = list(repo.get_commits()[:MAX_COMMITS])

        if not commits:
            return EMPTY_ACTIVITY.copy()

        (cpm, cwd, ch, cpw) = self.process_commit_dates(commits)

        first, last, is_active, days_since_last, avg = self.calculate_activity_stats(commits)

        activity_time = self.format_activity_time(first, last)

        return {
            'total_commits': len(commits),
            'commits_per_month': [
                {'month': k.strftime('%Y-%m'), 'count': v}
                for k, v in sorted(cpm.items())
            ],
            'commits_by_weekday': dict(cwd),
            'commits_by_hour': {str(h): ch[h] for h in HOURS_RANGE},
            'first_commit': first.isoformat(),
            'last_commit': last.isoformat(),
            'activity_time': activity_time,
            'is_active': is_active,
            'days_since_last_commit': days_since_last,
            'commits_per_week_avg': avg,
            'commits_per_week': [ {'week': k.strftime('%d/%m/%y'), 'count': v} for k, v in sorted(cpw.items())
            ],
        }
    
    def build_contributor(self, c):
        additions = sum(w.a for w in c.weeks)
        deletions = sum(w.d for w in c.weeks)

        return {
            'username': c.author.login,
            'avatar_url': c.author.avatar_url,
            'commits': c.total,
            'additions': additions,
            'deletions': deletions,
        }
    
    def calculate_bus_factor(self, ranking):
        accumulated = 0
        count = 0
        for c in ranking:
            accumulated += c['ownership_pct']
            count += 1
            if accumulated >= BUS_FACTOR_THRESHOLD:
                break
        return count
    
    def get_contributors(self, repo):
        try:
            contributors = list(repo.get_contributors()[:MAX_CONTRIBUTORS])
        except GithubException:
            return EMPTY_CONTRIBUTORS.copy()

        if not contributors:
            return EMPTY_CONTRIBUTORS.copy()

        ranking = []
        for c in contributors:
            ranking.append({
                'username': c.login,
                'avatar_url': c.avatar_url,
                'commits': c.contributions,
                'additions': 0,
                'deletions': 0,
            })

        try:
            import requests as req
            token = Config.GITHUB_TOKEN
            headers = {'Authorization': f'token {token}'} if token else {}
            url = f'https://api.github.com/repos/{repo.full_name}/stats/contributors'
            r = req.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                stats_map = {s['author']['login']: s for s in r.json()}
                for c in ranking:
                    if c['username'] in stats_map:
                        weeks = stats_map[c['username']]['weeks']
                        c['additions'] = sum(w['a'] for w in weeks)
                        c['deletions'] = sum(w['d'] for w in weeks)
        except:
            pass

        total_commits = sum(c['commits'] for c in ranking)
        for c in ranking:
            c['ownership_pct'] = round((c['commits'] / total_commits) * 100, 1) if total_commits > 0 else 0

        bus_factor = self.calculate_bus_factor(ranking)
        return {
            'total': len(ranking),
            'bus_factor': bus_factor,
            'ranking': ranking[:10],
        }
 
    def get_issues_and_prs(self, repo):
        closed_issues = [i for i in repo.get_issues(state='closed').get_page(0) if not i.pull_request]
        open_issues   = [i for i in repo.get_issues(state='open').get_page(0)   if not i.pull_request]
        close_times = []
        for issue in closed_issues:
            if issue.pull_request:
                continue 
            if issue.closed_at and issue.created_at:
                delta = issue.closed_at - issue.created_at
                close_times.append(delta.total_seconds() / 3600 / 24)
 
        avg_close_days = round(sum(close_times) / len(close_times), 1) if close_times else None
 
        closed_prs = list(repo.get_pulls(state='closed').get_page(0))
        open_prs   = list(repo.get_pulls(state='open').get_page(0))
        
        merge_times = []
        for pr in closed_prs:
            if pr.merged_at and pr.created_at:
                delta = pr.merged_at - pr.created_at
                merge_times.append(delta.total_seconds() / 3600 / 24)
 
        avg_merge_days = round(sum(merge_times) / len(merge_times), 1) if merge_times else None
 
        return {
            'issues': {
                'open':           len(open_issues),
                'closed_sample':  len(closed_issues),
                'avg_close_days': avg_close_days,
            },
            'prs': {
                'open':           len(open_prs),
                'closed_sample':  len(closed_prs),
                'avg_merge_days': avg_merge_days,
            }
        }
 
    def get_health_checklist(self, repo):
        important_files = {
            'has_readme':      ['README.md', 'README.rst', 'README.txt', 'README'],
            'has_license':     ['LICENSE', 'LICENSE.md', 'LICENSE.txt'],
            'has_gitignore':   ['.gitignore'],
            'has_contributing':['CONTRIBUTING.md', 'CONTRIBUTING.rst', 'CONTRIBUTING'],
            'has_changelog':   ['CHANGELOG.md', 'CHANGELOG.rst', 'CHANGELOG', 'HISTORY.md'],
        }
 
        try:
            contents = [f.name for f in repo.get_contents('')]
        except GithubException:
            contents = []
 
        result = {}
        for key, filenames in important_files.items():
            result[key] = any(f in contents for f in filenames)
 
        result['has_description'] = bool(repo.description)
        result['has_topics'] = len(repo.get_topics()) > 0
 
        return result

    def parse_repo_url(self, url):
        url = url.strip().rstrip('/')
        if url.endswith('.git'):
            url = url[:-4]
        if 'github.com/' in url:
            parts = url.split('github.com/')[-1].split('/')
            if len(parts) >= 2:
                return f"{parts[0]}/{parts[1]}"
        return url
 
