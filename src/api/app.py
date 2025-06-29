from flask import Flask
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/api/health')
def health():
    return {"status": "healthy", "service": "ANR/Tombstone AI Analyzer"}

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
