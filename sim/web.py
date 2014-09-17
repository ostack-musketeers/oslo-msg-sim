from flask import Flask, render_template, request, jsonify, abort, redirect

app = Flask('msgsim')


@app.route("/")
def index():
    return render_template('index.j2')


@app.route("/stems")
def stems():
    pass


@app.route("/stats")
def stats():
    pass
