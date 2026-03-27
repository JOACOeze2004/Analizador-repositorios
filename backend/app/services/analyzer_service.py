from radon.visitors import ComplexityVisitor
from github import GithubException
from flask import Blueprint, request, jsonify, make_response
import re
import lizard
from github import GithubException
from concurrent.futures import ThreadPoolExecutor, as_completed
 
IGNORED_PATHS = {
    'node_modules', 'vendor', 'dist', 'build', 'venv', '.venv', 'tests','test','__tests__','spec','specs'
}

IGNORED_FILENAME_PATTERNS = [ 'bootstrap', 'jquery', 'popper', 'fontawesome', 'lodash', 'moment' ]

IGNORED_TEST_PATTERNS = [ 'test_', '_test.', '.test.', '.spec.', ]

SUPPORTED_LANGUAGES = {'Python', 'JavaScript', 'TypeScript', 'Java', 'C', 'C++', 'C#', 'Rust', 'Go','Ruby','Swift','Kotlin' }

LANGUAGE_EXTENSIONS = {
    'Python':     ['.py'],
    'JavaScript': ['.js', '.jsx'],
    'TypeScript': ['.ts', '.tsx'],
    'Java' : ['.java'],
    'C' : ['.c', '.h'],
    'C++' : ['.cpp', '.cc','.cxx'],
    'C#' : ['.cs'],
    'Rust' : ['.rs'],
    'Go' : ['.go'],
    'Ruby':       ['.rb'],
    'Swift':      ['.swift'],
    'Kotlin':     ['.kt'],
}

FUNCTION_LENGTH = {
    'ok': 20, 
    'warning':30, 
}

MAX_FILES_TO_ANALIZE = 30
TREE_ERROR_RESPONSE = 'No se pudo acceder al árbol de archivos.'
MAX_HEALTH_SCORE = 35
MAX_ISSUES_SCORE = 20
CODE_SCORE_NO_FUNCS = 12

HEALTH_CHECK_SCORES = {
    'has_readme': 10,
    'has_license': 8,
    'has_gitignore': 6,
    'has_contributing': 5,
    'has_changelog': 3,
    'has_description': 2,
    'has_topics': 1,
}

CONTRIBUTOR_THRESHOLDS = {
    'total': [(10, 10), (5, 7), (2, 4), (0, 1)],
    'bus_factor': [(4, 10), (2, 6), (0, 2)],
}

ISSUE_TIME_THRESHOLDS = [
    (3, 10),
    (7, 7),
    (30, 3),
]

PR_TIME_THRESHOLDS = [
    (3, 10),
    (7, 7),
    (14, 3),
]

CODE_SCORE_THRESHOLDS = [
    (0.9, 25),
    (0.7, 18),
    (0.5, 10),
    (0.0, 5),
]
CODE_SCORE_NO_FUNCS = 12
FUNCTION_STATUSES = ('ok', 'warning', 'critical')
FUNCTION_ORDER = {'critical': 0, 'warning': 1, 'ok': 2}

EXCELLENT_SCORE = 85
EXCELLENT_SCORE_MESSAGE = 'Excelente'

GOOD_SCORE = 75
GOOD_SCORE_MESSAGE = 'Bueno'

REGULAR_SCORE = 50
REGULAR_SCORE_MESSAGE = 'Regular'

BAD_SCORE = 30
BAD_SCORE_MESSAGE = 'Necesita mejoras'

CRITICAL_MESSAGE = 'critico'



class AnalyzerService:

    def get_supported_languages(self,languages):
        repo_languages = set(languages.keys())
        return repo_languages & SUPPORTED_LANGUAGES
    
    def unsupported_response(self,languages):
        repo_languages = languages.keys()
        return {
            'supported': False,
            'message': f'Análisis de funciones no soportado para: {", ".join(repo_languages)}',
            'functions': [],
            'summary': {'ok': 0, 'warning': 0, 'critical': 0}
        } 
    
    def get_repo_tree(self,repo):
        try:
            return repo.get_git_tree(repo.default_branch, recursive=True)
        except GithubException:
            return None
        
    def tree_error_response(self):
        return {
            'supported': False,
            'message': TREE_ERROR_RESPONSE,
            'functions': [],
            'summary': {'ok': 0, 'warning': 0, 'critical': 0}
        }

    def get_files_to_analyze(self,tree,extensions):
        return [
            item for item in tree.tree
            if item.type == 'blob' and self.has_extension(item.path, extensions) and not self._is_ignored(item.path)
        ][:MAX_FILES_TO_ANALIZE]
        
    def process_files(self,repo,files):
        functions = []
        summary = {'ok': 0, 'warning': 0, 'critical': 0}

        def fetch_and_analyze(file_item):
            try:
                content = repo.get_contents(file_item.path)
                source_code = content.decoded_content.decode('utf-8', errors='ignore')
            except:
                return []
            return self.analyze_file(source_code, file_item.path)

        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(fetch_and_analyze, f) for f in files]
            for future in futures:
                file_functions = future.result()
                functions.extend(file_functions)

                for f in file_functions:
                    summary[f['status']] += 1
        return functions, summary
    
    def sort_functions(self, functions):
        order = {'critical': 0, 'warning': 1, 'ok': 2}
        return sorted(functions, key=lambda x: FUNCTION_ORDER[x['status']])
 
    
    def analyze_functions(self, repo, languages):
        languages_to_analize = self.get_supported_languages(languages)
        if not languages_to_analize:
            return self.unsupported_response(languages)
         
        extensions = self.get_extensions(languages_to_analize)
        tree = self.get_repo_tree(repo)
        if not tree:
            return self.tree_error_response()
        
        files = self.get_files_to_analyze(tree, extensions)

        functions, summary = self.process_files(repo, files)

        functions = self.sort_functions(functions)

        return {
            'supported': True,
            'functions': functions,
            'summary': summary,
            'files_analyzed': len(files),
        }

    # Calcula un score del 0 al 100 
        # Pesos:
        #     Salud/estructura   35 pts
        #     Calidad de código  25 pts
        #     Colaboración       20 pts
        #     Issues & PRs       20 pts

    def health_score(self,health):
        score = sum(
            pts for k, pts in HEALTH_CHECK_SCORES.items()
            if health.get(k)
        )
        return min(score, MAX_HEALTH_SCORE)
    
    def contributors_score(self,contributors):
        score = 0
        total = contributors.get('total', 0)
        score = 0

        total = contributors.get('total', 0)
        for threshold, pts in CONTRIBUTOR_THRESHOLDS['total']:
            if total >= threshold:
                score += pts
                break

        bf = contributors.get('bus_factor', 1)
        for threshold, pts in CONTRIBUTOR_THRESHOLDS['bus_factor']:
            if bf >= threshold:
                score += pts
                break
        return score
    
    def issues_score(self,issues_prs):
        score = 0
        avg_close = issues_prs.get('issues', {}).get('avg_close_days')
        if avg_close is not None:
            for t, pts in ISSUE_TIME_THRESHOLDS:
                if avg_close <= t:
                    score += pts
                    break
 
        avg_merge = issues_prs.get('prs', {}).get('avg_merge_days')
        if avg_merge is not None:
            for t, pts in PR_TIME_THRESHOLDS:
                if avg_merge <= t:
                    score += pts
                    break

 
        if avg_close is None and avg_merge is None:
            return 10
        return min(score,MAX_ISSUES_SCORE)
    
    def code_score(self,functions_summary):
        total = sum(functions_summary.get(k, 0) for k in FUNCTION_STATUSES)
        if total == 0:
            return CODE_SCORE_NO_FUNCS

        ok_pct = functions_summary.get('ok', 0) / total

        for threshold, pts in CODE_SCORE_THRESHOLDS:
            if ok_pct >= threshold:
                return pts
        return 0

    def calculate_score(self, contributors, health, issues_prs, functions_summary):
        score = 0
        score += self.health_score(health)
        score += self.contributors_score(contributors)
        score += self.issues_score(issues_prs)
        score += self.code_score(functions_summary)

        return min(score, 100)
 
    def get_score_label(self, score):
        if score >= EXCELLENT_SCORE: return EXCELLENT_SCORE_MESSAGE
        if score >= GOOD_SCORE: return GOOD_SCORE_MESSAGE
        if score >= REGULAR_SCORE: return REGULAR_SCORE_MESSAGE
        if score >= BAD_SCORE: return BAD_SCORE_MESSAGE
        return CRITICAL_MESSAGE
 
    def analyze_file(self, source_code, filepath):
        functions = []
        try:
            analysis = lizard.analyze_file.analyze_source_code(filepath, source_code)
            for func in analysis.function_list:
                functions.append(self.build_function_entry( name=func.name, filepath=filepath, line=func.start_line, length=func.length, ))
        except Exception:
            pass
        return functions        
 
    def build_function_entry(self, name, filepath, line, length):
        if length <= FUNCTION_LENGTH['ok']:
            status = 'ok'
        elif length <= FUNCTION_LENGTH['warning']:
            status = 'warning'
        else:
            status = 'critical'
        return {'name': name, 'file': filepath, 'line': line, 'length': length, 'status': status}
 
    def get_extensions(self, languages):
        extensions = []
        for lang in languages:
            extensions.extend(LANGUAGE_EXTENSIONS.get(lang, []))
        return extensions
 
    def has_extension(self, path, extensions):
        return any(path.endswith(ext) for ext in extensions)
    
    def _is_ignored(self, path):
        if path.endswith('.min.js'):
            return True
        parts = path.split('/')
        if any(part in IGNORED_PATHS for part in parts):
            return True
        filename = parts[-1].lower()
        if any(pattern in filename for pattern in IGNORED_FILENAME_PATTERNS):
            return True
        if any(filename.startswith(p) or (p in filename) for p in IGNORED_TEST_PATTERNS):
            return True
        return False
 