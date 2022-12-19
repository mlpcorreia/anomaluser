import sqlite3
import json

from flask import Flask, request
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from rule_check import *


app = Flask(__name__)

# Configuration read
config = configparser.ConfigParser()
config.read('config.ini')
# Database configuration
DB_NAME = config['Database']['DB_Name']
db_engine = create_engine('sqlite:///' + DB_NAME)
DBSession = sessionmaker(bind=db_engine)


def write_file(commit, violations):
    username = commit['author']['username']
    filename = 'reports/report_' + username + '_' + commit['id']
    with open(filename, 'a') as f:
        f.write('Commit: ' + commit['id'] + '\n\n')
        f.write('URL: ' + commit['url'] + '\n\n')
        f.write('Authored on ' + commit['timestamp'] + ' by ' + commit['author']['name'] + '\n')
        f.write('Committed on ' + commit['timestamp'] + ' by ' + commit['committer']['name'] + '\n')
        f.write('Commit Message: ' + commit['message'] + '\n\n')
        f.write('This commit added ' + str(len(commit['added'])) + ' files.\n')
        f.write('This commit modified ' + str(len(commit['modified'])) + ' files.\n')
        f.write('This commit removed ' + str(len(commit['removed'])) + ' files.\n\n')
        f.write(username + ' is ' + ('TRUSTED\n\n' if violations[1] else 'NOT TRUSTED\n\n'))
        f.write('This commit violated ' + str(violations[0]) + '% of the rules.\n')


@app.route('/push-payload', methods=['POST'])
def push_payload():
    payload = request.get_json()
    if 'commits' not in payload:
        return '', 201
    touched_files = set()
    with DBSession() as session:
        for commit in payload['commits']:
            # My rules (lines changed, time...)
            commit_data = utils.get_commit_info(commit['url'])
            username = commit['author']['username']
            touched_files.update(commit['removed'] + commit['modified'])
        write_file(commit, rules_violated(session, username, commit['added'], touched_files, commit['timestamp'][:10], commit_data))
    return '', 201


@app.route('/pull-payload', methods=['POST'])
def pull_payload():
    payload = request.get_json()
    print(payload)
    return '', 201


@app.route('/commit/<commit_id>')
def get_commit(commit_id):
    # con = sqlite3.connect('simulations/forged_commits.db')
    con = sqlite3.connect('simulations/results/forged_commits-dum-domi.db')
    cursor = con.cursor()
    cursor.execute('SELECT commit_data FROM forged_commits WHERE id = ?', (commit_id,))
    return json.loads(cursor.fetchall()[0][0])


if __name__ == '__main__':
    # app.run('0.0.0.0', 8080)
    app.run(port=8080)

