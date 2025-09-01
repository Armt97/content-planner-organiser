from flask import Flask, render_template
import os

app = Flask(__name__, template_folder="../frontend")

@app.route("/health")
def health():
    return {"status": "ok"}

@app.route("/")
def home():
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5001)
