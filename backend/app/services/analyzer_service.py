from radon.visitors import ComplexityVisitor
from github import GithubException
from flask import Blueprint, request, jsonify, make_response
import re
import lizard
from github import GithubException
 
IGNORED_PATHS = {
    'node_modules', 'vendor', 'dist', 'build', 'venv', '.venv'
}

IGNORED_FILENAME_PATTERNS = [
    'bootstrap', 'jquery', 'popper', 'fontawesome', 'lodash', 'moment'
]

SUPPORTED_LANGUAGES = {'Python', 'JavaScript', 'TypeScript', 'Java', 'C', 'C++', 'C#', 'Rust', 'Go', }

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
}

FUNCTION_LENGTH = {
    'ok': 20, 
    'warning':30, 
}

class AnalyzerService:
    
    def analyze_functions(self, repo, languages):
        repo_languages = set(languages.keys())
        langs_to_analyze = repo_languages & SUPPORTED_LANGUAGES
        print(f'Lenguajes del repo: {repo_languages}')
        print(f'SUPPORTED_LANGUAGES: {SUPPORTED_LANGUAGES}')
        print(f'Lenguajes a analizar: {langs_to_analyze}')
        extensions = self._get_extensions(langs_to_analyze)
        print(f'Extensiones: {extensions}')
 
        if not langs_to_analyze:
            return {
                'supported': False,
                'message': f'Análisis de funciones no soportado para: {", ".join(repo_languages)}',
                'functions': [],
                'summary': {'ok': 0, 'warning': 0, 'critical': 0}
            }
 
        extensions = self._get_extensions(langs_to_analyze)
 
        try:
            tree = repo.get_git_tree(repo.default_branch, recursive=True)
        except GithubException:
            return {
                'supported': False,
                'message': 'No se pudo acceder al árbol de archivos.',
                'functions': [],
                'summary': {'ok': 0, 'warning': 0, 'critical': 0}
            }
        
        files_to_analyze = [
            item for item in tree.tree
            if item.type == 'blob' 
            and self._has_extension(item.path, extensions)
            and not self._is_ignored(item.path)
        ][:50]
 
        functions = []
        summary   = {'ok': 0, 'warning': 0, 'critical': 0}
 
        for file_item in files_to_analyze:
            try:
                content = repo.get_contents(file_item.path)
                source_code = content.decoded_content.decode('utf-8', errors='ignore')
            except Exception:
                continue
 
            file_functions = self._analyze_file(source_code, file_item.path)
            functions.extend(file_functions)
            for f in file_functions:
                summary[f['status']] += 1
 
        order = {'critical': 0, 'warning': 1, 'ok': 2}
        functions.sort(key=lambda x: order[x['status']])
 
        return {
            'supported': True,
            'functions': functions,
            'summary': summary,
            'files_analyzed': len(files_to_analyze),
        }

    # Calcula un score del 0 al 100 
        # Pesos:
        #     Salud/estructura   35 pts
        #     Calidad de código  25 pts
        #     Colaboración       20 pts
        #     Issues & PRs       20 pts

    def calculate_score(self, activity, contributors, health, issues_prs, functions_summary):
        score = 0
        
        health_checks = {
            'has_readme': 10, 'has_license': 8, 'has_gitignore': 6,
            'has_contributing': 5, 'has_changelog': 3, 'has_description': 2, 'has_topics': 1,
        }
        score += min(sum(pts for k, pts in health_checks.items() if health.get(k)), 35)


        total = contributors.get('total', 0)
        if total >= 10: score += 10
        elif total >= 5: score += 7
        elif total >= 2: score += 4
        else: score += 1

        bf = contributors.get('bus_factor', 1)
        if bf >= 4:   score += 10
        elif bf >= 2: score += 6
        else:         score += 2

        issues_score = 0
        avg_close = issues_prs.get('issues', {}).get('avg_close_days')
        if avg_close is not None:
            if avg_close <= 3: issues_score += 10
            elif avg_close <= 7: issues_score += 7
            elif avg_close <= 30: issues_score += 3
 
        avg_merge = issues_prs.get('prs', {}).get('avg_merge_days')
        if avg_merge is not None:
            if avg_merge <= 3: issues_score += 10
            elif avg_merge <= 7: issues_score += 7
            elif avg_merge <= 14: issues_score += 3
 
        if avg_close is None and avg_merge is None:
            issues_score = 10
        
        score += min(issues_score, 20)
    
        total_funcs = sum(functions_summary.values())
        if total_funcs > 0:
            ok_pct = functions_summary.get('ok', 0) / total_funcs
            if ok_pct >= 0.9:   score += 25
            elif ok_pct >= 0.7: score += 18
            elif ok_pct >= 0.5: score += 10
            elif ok_pct > 0: score += 5
        else:
            score += 12

        return min(score, 100)
 
    def get_score_label(self, score):
        if score >= 85: return 'Excelente'
        if score >= 70: return 'Bueno'
        if score >= 50: return 'Regular'
        if score >= 30: return 'Necesita mejoras'
        return 'Crítico'
 
    def _analyze_file(self, source_code, filepath):
        functions = []
        try:
            analysis = lizard.analyze_file.analyze_source_code(filepath, source_code)
            for func in analysis.function_list:
                functions.append(self._build_function_entry( name=func.name, filepath=filepath, line=func.start_line, length=func.length, ))
        except Exception:
            pass
        return functions        
 
    def _build_function_entry(self, name, filepath, line, length):
        if length <= FUNCTION_LENGTH['ok']:       status = 'ok'
        elif length <= FUNCTION_LENGTH['warning']: status = 'warning'
        else:                                      status = 'critical'
        return {'name': name, 'file': filepath, 'line': line, 'length': length, 'status': status}
 
    def _get_extensions(self, languages):
        extensions = []
        for lang in languages:
            extensions.extend(LANGUAGE_EXTENSIONS.get(lang, []))
        return extensions
 
    def _has_extension(self, path, extensions):
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
        return False
 