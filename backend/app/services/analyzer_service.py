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
            'message': 'No se pudo acceder al árbol de archivos.',
            'functions': [],
            'summary': {'ok': 0, 'warning': 0, 'critical': 0}
        }

    def get_files_to_analyze(self,tree,extensions):
        return [
            item for item in tree.tree
            if item.type == 'blob' and self._has_extension(item.path, extensions) and not self._is_ignored(item.path)
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
            return self._analyze_file(source_code, file_item.path)

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
        return sorted(functions, key=lambda x: order[x['status']])
 
    
    def analyze_functions(self, repo, languages):
        languages_to_analize = self.get_supported_languages(languages)
        if not languages_to_analize:
            return self.unsupported_response(languages)
         
        extensions = self._get_extensions(languages_to_analize)
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
        if any(filename.startswith(p) or (p in filename) for p in IGNORED_TEST_PATTERNS):
            return True
        return False
 