from datetime import datetime
from app import db
import json
 
class Analysis(db.Model):
    __tablename__ = 'analyses'
 
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    repo_url = db.Column(db.String(500), nullable=False)
    repo_name = db.Column(db.String(200), nullable=False)  
    repo_owner = db.Column(db.String(200), nullable=False)  
    repo_full_name = db.Column(db.String(400), nullable=False)  

    analyzed_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
 
    score = db.Column(db.Integer)
 
    metrics = db.Column(db.Text, nullable=False)
 
    def set_metrics(self, metrics_dict):
        self.metrics = json.dumps(metrics_dict)
 
    def get_metrics(self):
        return json.loads(self.metrics) if self.metrics else {}
 
    def is_outdated(self, max_age_hours=6):
        age = datetime.now() - self.analyzed_at
        return (age.total_seconds() / 3600) > max_age_hours
 
    def to_dict(self):
        return {
            'id':             self.id,
            'repo_url':       self.repo_url,
            'repo_name':      self.repo_name,
            'repo_owner':     self.repo_owner,
            'repo_full_name': self.repo_full_name,
            'analyzed_at':    self.analyzed_at.isoformat(),
            'score':          self.score,
            'metrics':        self.get_metrics()
        }
 
    def __repr__(self):
        return f'<Analysis {self.repo_full_name} @ {self.analyzed_at}>'
 