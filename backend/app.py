from flask import Flask

app = Flask(__name__)

@app.route("/health")
def health():
    return {"status": "ok"}

@app.route("/")
def home():
    return "Hello, Content Planner!"

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5001)

