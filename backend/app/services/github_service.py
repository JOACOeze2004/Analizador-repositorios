from github import Github, GithubException
from datetime import datetime, timezone
from collections import defaultdict
from datetime import timedelta

MAX_COMMITS = 1000
MAX_CONTRIBUTORS = 10
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


class GithubService:

    def __init__(self, token=None):
        self.client = Github(token) if token else Github()
        # Sin token: 60 requests/hora. Con token: 5000 requests/hora.
        #Como no tenemos token, estamos limitados.
    
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
        years = days // 365
        months = (days % 365) // 30

        if years > 0:
            return f'{years}a {months}m'
        return f'{months} meses'

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
    
    def get_contributors(self, repo):
        try:
            stats = repo.get_stats_contributors()
        except GithubException:
            return {'total': 0, 'bus_factor': 0, 'ranking': []}
 
        if not stats:
            return {'total': 0, 'bus_factor': 0, 'ranking': []}
 
        ranking = []
        for contributor in stats:
            total_additions = sum(w.a for w in contributor.weeks)
            total_deletions = sum(w.d for w in contributor.weeks)
            ranking.append({
                'username':   contributor.author.login,
                'avatar_url': contributor.author.avatar_url,
                'commits':    contributor.total,
                'additions':  total_additions,
                'deletions':  total_deletions,
            })

        ranking.sort(key=lambda x: x['commits'], reverse=True)
        ranking = ranking[:MAX_CONTRIBUTORS]

        total_commits = sum(c['commits'] for c in ranking)
        for contributor in ranking:
            contributor['ownership_pct'] = round(
                (contributor['commits'] / total_commits) * 100, 1
            ) if total_commits > 0 else 0

        bus_factor = 0
        accumulated = 0
        for contributor in ranking:
            accumulated += contributor['ownership_pct']
            bus_factor += 1
            if accumulated >= 80:
                break
 
        return {
            'total': len(ranking),
            'bus_factor': bus_factor,
            'ranking': ranking[:10], 
        }
 
    def get_issues_and_prs(self, repo):
        closed_issues = list(repo.get_issues(state='closed').get_page(0))
        open_issues   = list(repo.get_issues(state='open').get_page(0))
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
 