from app import create_app

app = create_app()

if __name__ == '__main__':
    print('Iniciando GitHub Analyzer...')
    app.run(host='0.0.0.0', debug=app.config['DEBUG'], port=5000)