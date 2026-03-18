from flask import Blueprint, request, jsonify
from app import db
from app.models.analysis import Analysis
from app.services.github_service import GithubService
from app.services.analyzer_service import AnalyzerService
from config import Config

analyzer_bp = Blueprint('analyzer', __name__)

github_service   = GithubService(token=Config.GITHUB_TOKEN)
analyzer_service = AnalyzerService()

@analyzer_bp.route('/analyze', methods=['POST'])
def analyze():
    data     = request.get_json()
    repo_url = data.get('repo_url', '').strip() if data else ''
 
    if not repo_url:
        return jsonify({'error': 'repo_url es requerido'}), 400
 
    existing = Analysis.query.filter_by(repo_url=repo_url).order_by(Analysis.analyzed_at.desc()).first()
    if existing and not existing.is_outdated():
        return jsonify({
            'source': 'cache',
            'analysis': existing.to_dict()
        }), 200

    try:
        repo = github_service.get_repo(repo_url)
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 502
    
    try:
        basic_info   = github_service.get_basic_info(repo)
        languages    = github_service.get_languages(repo)
        activity     = github_service.get_commit_activity(repo)
        contributors = github_service.get_contributors(repo)
        issues_prs   = github_service.get_issues_and_prs(repo)
        health       = github_service.get_health_checklist(repo)
        functions    = analyzer_service.analyze_functions(repo, languages)
    except Exception as e:
        return jsonify({'error': f'Error al analizar el repositorio: {str(e)}'}), 500
 
    score = analyzer_service.calculate_score(
        activity=activity,
        contributors=contributors,
        health=health,
        issues_prs=issues_prs,
        functions_summary=functions.get('summary', {}),
    )
 
    metrics = {
        'basic_info':   basic_info,
        'languages':    languages,
        'activity':     activity,
        'contributors': contributors,
        'issues_prs':   issues_prs,
        'health':       health,
        'functions':    functions,
        'score_label':  analyzer_service.get_score_label(score),
    }
 
    analysis = Analysis(
        repo_url       = repo_url,
        repo_name      = basic_info['name'],
        repo_owner     = basic_info['owner'],
        repo_full_name = basic_info['full_name'],
        score          = score,
    )
    analysis.set_metrics(metrics)
    db.session.add(analysis)
    db.session.commit()
 
    return jsonify({
        'source':   'fresh',
        'analysis': analysis.to_dict()
    }), 200
 
 
@analyzer_bp.route('/history', methods=['GET'])
def history():
    analyses = Analysis.query.order_by(Analysis.analyzed_at.desc()).limit(20).all()
    return jsonify({
        'history': [
            {
                'id':            a.id,
                'repo_full_name': a.repo_full_name,
                'repo_url':      a.repo_url,
                'score':         a.score,
                'score_label':   analyzer_service.get_score_label(a.score) if a.score else None,
                'analyzed_at':   a.analyzed_at.isoformat(),
                'is_outdated':   a.is_outdated(),
            }
            for a in analyses
        ]
    }), 200
 
 
@analyzer_bp.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok'}), 200