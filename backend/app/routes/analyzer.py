from flask import Blueprint, request, jsonify
from app import db
from app.models.analysis import Analysis
from app.services.github_service import GithubService
from app.services.analyzer_service import AnalyzerService
from config import Config
from concurrent.futures import ThreadPoolExecutor

analyzer_bp = Blueprint('analyzer', __name__)

github_service   = GithubService(token=Config.GITHUB_TOKEN)
analyzer_service = AnalyzerService()

ERRORS = {'MISSING_REPO_URL': 'repo_url es requerido', 'ANALYSIS_FAILED': 'Error al analizar el repositorio'}
ERROR_BAD_REQUEST = 400
ERROR_NOT_FOUND = 404
ERROR_BAD_GATEWAY = 502
OK_RESPONSE = 200


def get_repo_url(request):
    data = request.get_json() 
    return data.get('repo_url', '').strip() if data else ''

def success_response(analysis, source): return jsonify({
        'source': source,
        'analysis': analysis.to_dict()
    }), OK_RESPONSE


def error_response(message, status): 
    return jsonify({'error': message}), status

def get_cached_analysis(repo_url):
    existing = (
        Analysis.query
        .filter_by(repo_url=repo_url)
        .order_by(Analysis.analyzed_at.desc())
        .first()
    )
    if existing and not existing.is_outdated():
        return existing
    return None

def fetch_repo_data_concurrently(repo, languages):
    with ThreadPoolExecutor() as executor:
        futures = {
            'basic_info': executor.submit(github_service.get_basic_info, repo),
            'activity': executor.submit(github_service.get_commit_activity, repo),
            'contributors': executor.submit(github_service.get_contributors, repo),
            'issues_prs': executor.submit(github_service.get_issues_and_prs, repo),
            'health': executor.submit(github_service.get_health_checklist, repo),
            'functions': executor.submit(
                analyzer_service.analyze_functions, repo, languages
            )
        }
        return {key: future.result() for key, future in futures.items()}

def build_metrics(results, languages, score):
    return {
        'basic_info': results['basic_info'],
        'languages': languages,
        'activity': results['activity'],
        'contributors': results['contributors'],
        'issues_prs': results['issues_prs'],
        'health': results['health'],
        'functions': results['functions'],
        'score_label': analyzer_service.get_score_label(score),
    }

def analyze_repository(repo_url):
    repo = github_service.get_repo(repo_url)
    languages = github_service.get_languages(repo) 
    results = fetch_repo_data_concurrently(repo,languages)
    
    score = analyzer_service.calculate_score(
        activity=results['activity'],
        contributors=results['contributors'],
        health=results['health'],
        issues_prs=results['issues_prs'],
        functions_summary=results['functions'].get('summary', {})
    )
    metrics = build_metrics(results, languages, score)

    return {
        'metrics': metrics,
        'score': score,
        'repo_full_name': results['basic_info']['full_name']
    }

def save_analysis(repo_url, data):
    metrics = data['metrics']
    basic_info = metrics['basic_info']

    analysis = Analysis(
        repo_url=repo_url,
        repo_name=basic_info['name'],
        repo_owner=basic_info['owner'],
        repo_full_name=basic_info['full_name'],
        score=data['score'],
    )
    analysis.set_metrics(metrics)
    db.session.add(analysis)
    db.session.commit()

    return analysis

@analyzer_bp.route('/analyze', methods=['POST'])
def analyze():
    repo_url = get_repo_url(request)
    if not repo_url:
        return error_response(ERRORS['MISSING_REPO_URL'], ERROR_BAD_REQUEST)
    
    cached = get_cached_analysis(repo_url)
    if cached:
        return success_response(cached, source='cache')

    try:
        analysis_data = analyze_repository(repo_url)
        saved = save_analysis(repo_url, analysis_data)
        return success_response(saved, source='fresh')
    except ValueError as e:
        return error_response(str(e), ERROR_NOT_FOUND)
    except Exception as e:
        return error_response(str(e), ERROR_BAD_GATEWAY)
 
def get_recent_analyses(limit=20):
    return (
        Analysis.query
        .order_by(Analysis.analyzed_at.desc())
        .limit(limit)
        .all()
    )

def serialize_analysis(a):
    return {
        'id': a.id,
        'repo_full_name': a.repo_full_name,
        'repo_url': a.repo_url,
        'score': a.score,
        'score_label': analyzer_service.get_score_label(a.score) if a.score else None,
        'analyzed_at': a.analyzed_at.isoformat(),
        'is_outdated': a.is_outdated(),
    } 

@analyzer_bp.route('/history', methods=['GET'])
def history():
    analyses = get_recent_analyses()
    return jsonify({'history': [serialize_analysis(a) for a in analyses]}), OK_RESPONSE
 
 
@analyzer_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'}), OK_RESPONSE