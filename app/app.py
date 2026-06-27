from flask import Flask

app = Flask(__name__)

@app.route("/")
def hello():
    return """
    <html>
      <body style="font-family: sans-serif; text-align: center; padding: 50px;">
        <h1>Hello from ProjectView!</h1>
        <p>The stack is working.</p>
      </body>
    </html>
    """

@app.route("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
