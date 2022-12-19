import json
import sqlite3

from sklearn.svm import OneClassSVM
from sklearn.metrics import f1_score
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from numpy import where
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import func
from datetime import datetime

from models import CommitsStats, Developer
from rule_simulation import clever_commit

import matplotlib.pyplot as plt
import numpy as np
import configparser
import statistics

# Configuration read
config = configparser.ConfigParser()
config.read('simulations.ini')
# Database configuration
DB_NAMES = config['Repository']['DB_Names'].split(',')
print('Choose the database: ')
print(DB_NAMES)
DB_NAME = str(input('Database name: '))
db_engine = create_engine('sqlite:///../' + DB_NAME)
DBSession = sessionmaker(bind=db_engine)
np.set_printoptions(suppress=True)


def get_mean_and_variance(values):
    mean = 0
    var = 0
    if len(values) > 0:
        mean = sum(values) / len(values)
        if len(values) > 1:
            var = statistics.variance(values)
    return mean, var


def parse_commits(commits):
    changed_chars = []
    changed_lines = []
    commits_messages_len = []
    timestamps = []
    added_files = []
    modified_files = []
    removed_files = []
    for commit in commits:
        # timestamps.append(datetime.fromisoformat(commit['commit']['author']['date'][:-1]))
        timestamps.append(datetime.fromisoformat(commit['commit']['author']['date']))
        added = 0
        modified = 0
        removed = 0
        for file in commit['files']:
            if file['status'] == 'added':
                added += 1
            elif file['status'] == 'modified':
                modified += 1
            elif file['status'] == 'removed':
                removed += 1
            if 'patch' in file:
                file_changes = file['patch'].split('\n')
                for line_change in file_changes:
                    if line_change[0] == '+' or line_change[0] == '-':
                        changed_chars.append(len(line_change))
        added_files.append(added)
        modified_files.append(modified)
        removed_files.append(removed)
        commits_messages_len.append(len(commit['commit']['message']))
        changed_lines.append(commit['stats']['total'])

    lines_mean, lines_var = get_mean_and_variance(changed_lines)
    changed_chars_mean, changed_chars_var = get_mean_and_variance(changed_chars)
    time_intervals = []
    if len(timestamps) > 1:
        for i in range(0, len(timestamps)):
            if len(timestamps) == i + 1:
                break
            delta = timestamps[i] - timestamps[i + 1]
            time_intervals.append(delta.total_seconds())
    times_mean, times_variance = get_mean_and_variance(time_intervals)
    comments_size_mean, comments_size_var = get_mean_and_variance(commits_messages_len)
    added_files_mean, added_files_var = get_mean_and_variance(added_files)
    modified_files_mean, modified_files_var = get_mean_and_variance(modified_files)
    removed_files_mean, removed_files_var = get_mean_and_variance(removed_files)
    return np.asarray([(times_mean, len(commits), changed_chars_mean, changed_chars_var, lines_mean, lines_var,
                        min(changed_lines), max(changed_lines), comments_size_mean, comments_size_var, added_files_mean,
                        added_files_var, modified_files_mean, modified_files_var, removed_files_mean, removed_files_var)])


def create_graph_commits(username):
    with DBSession() as session:
        stats = session.query(CommitsStats.number_commits, CommitsStats.date, CommitsStats.changed_lines_mean,
                              CommitsStats.added_files_mean, CommitsStats.modified_files_mean,
                              CommitsStats.removed_files_mean).join(Developer).filter(Developer.username == username)\
            .order_by(CommitsStats.date).all()
    dates = []
    commits = []
    changed_lines = []
    added_files = []
    modified_files = []
    removed_files = []
    for stat in stats:
        commits.append(stat[0])
        dates.append(stat[1])
        changed_lines.append(stat[2])
        added_files.append(stat[3])
        modified_files.append(stat[4])
        removed_files.append(stat[5])

    plt.style.use('ggplot')
    fig, ax = plt.subplots()
    ax.scatter(dates, commits, color='b')
    ax.set_title('Number of commits (per day) for the user ' + username)
    ax.set(xlabel='Days', ylabel='Commits')

    fig, (ax1, ax2) = plt.subplots(2, 2)
    fig.suptitle('Some mean stats (per day) for the user ' + username)
    ax1[0].set_title('Changed lines')
    ax1[0].scatter(dates, changed_lines, color='b')
    ax1[0].set(ylabel='Lines')
    ax1[1].set_title('Added files')
    ax1[1].scatter(dates, added_files, color='b')
    ax1[1].set(ylabel='Files')
    ax2[0].set_title('Modified files')
    ax2[0].scatter(dates, modified_files, color='b')
    ax2[0].set(xlabel='Days', ylabel='Files')
    ax2[1].set_title('Removed files')
    ax2[1].scatter(dates, removed_files, color='b')
    ax2[1].set(xlabel='Days', ylabel='Files')
    plt.show()


def get_dev_commits_stats(username):
    with DBSession() as session:
        stats = session.query(func.round(CommitsStats.time_intervals_mean, 4), CommitsStats.number_commits,
                              func.round(CommitsStats.changed_chars_mean), func.round(CommitsStats.changed_chars_var),
                              func.round(CommitsStats.changed_lines_mean), func.round(CommitsStats.changed_lines_var),
                              func.round(CommitsStats.changed_lines_min), func.round(CommitsStats.changed_lines_max),
                              func.round(CommitsStats.comments_size_mean), func.round(CommitsStats.comments_size_var),
                              func.round(CommitsStats.added_files_mean), func.round(CommitsStats.added_files_var),
                              func.round(CommitsStats.modified_files_mean), func.round(CommitsStats.modified_files_var),
                              func.round(CommitsStats.removed_files_mean), func.round(CommitsStats.removed_files_var))\
            .join(Developer).filter(Developer.username == username).order_by(CommitsStats.date).all()
    data = np.asarray(stats)
    #scaler = StandardScaler()
    scaler = MinMaxScaler()
    scaler.fit(data)
    return scaler, scaler.transform(data)


def analyze_user_behaviour(username, data):
    dev_stats = get_dev_commits_stats(username)
    # Create user model
    svm_user = OneClassSVM(kernel='poly', gamma='auto', nu=0.1)
    svm_user.fit(dev_stats)
    result = svm_user.predict(data)
    print('This commit is ' + ('an ANOMALY' if result == -1 else 'NOT an ANOMALY') + ' within the ' + username + ' user behaviour on the repository.')
    return result


def predict_over_rules(username):
    forged_commit = [clever_commit(username)]
    parsed_commit = parse_commits(forged_commit)
    return analyze_user_behaviour(username, parsed_commit)


def model(train, predict, kernel, gamma, nu):
    svm_user = OneClassSVM(kernel=kernel, gamma=gamma, nu=nu)
    print('Training ...')
    svm_user.fit(train)
    print('Predict ...')
    predict = svm_user.predict(predict)
    tp = len(where(predict == 1)[0])
    fp = len(where(predict == -1)[0])
    train_pred = svm_user.predict(train)
    print('Accuracy: ' + str((tp / predict.shape[0]) * 100))
    print('FP rate: ' + str((fp / predict.shape[0]) * 100))
    print('F1 Score: ' + str(f1_score(train_pred, predict) * 100))


def split_array(data):
    split_stats = None
    if len(data) > 3:
        try:
            split_stats = np.split(data, 2)
        except ValueError:
            rows = data.shape[0]
            index = int(rows/2)
            split_stats = [data[:index][:]]
            split_stats.append(data[index:-1][:])
    else:
        split_stats = [data]
        split_stats.append(data)
    return split_stats


def divide_train_predict(username):
    _, dev_stats = get_dev_commits_stats(username)
    split_stats = None
    if len(dev_stats) > 3:
        try:
            split_stats = np.split(dev_stats, 2)
        except ValueError:
            rows = dev_stats.shape[0]
            index = int(rows/2)
            split_stats = [dev_stats[:index][:]]
            split_stats.append(dev_stats[index:-1][:])
    else:
        split_stats = [dev_stats]
        split_stats.append(dev_stats)
    print('########## Gamma auto and nu 0.1')
    print('#################################')
    print('Kernel RBF, gamma auto, nu 0.1')
    model(split_stats[0], split_stats[1], 'rbf', 'auto', 0.1)

    print('#################################')
    print('Kernel Polynomial, gamma auto, nu 0.1')
    model(split_stats[0], split_stats[1], 'poly', 'auto', 0.1)

    print('#################################')
    print('Kernel Sigmoid, gamma auto, nu 0.1')
    model(split_stats[0], split_stats[1], 'sigmoid', 'auto', 0.1)

    print('#################################')
    print('Kernel Linear, gamma auto, nu 0.1')
    model(split_stats[0], split_stats[1], 'linear', 'auto', 0.1)

    print('########## Gamma scale and nu 0.1')
    print('#################################')
    print('Kernel RBF, gamma scale, nu 0.1')
    model(split_stats[0], split_stats[1], 'rbf', 'scale', 0.1)

    print('#################################')
    print('Kernel Polynomial, gamma scale, nu 0.1')
    model(split_stats[0], split_stats[1], 'poly', 'scale', 0.1)

    print('#################################')
    print('Kernel Sigmoid, gamma scale, nu 0.1')
    model(split_stats[0], split_stats[1], 'sigmoid', 'scale', 0.1)

    print('#################################')
    print('Kernel Linear, gamma scale, nu 0.2')
    model(split_stats[0], split_stats[1], 'linear', 'scale', 0.2)


usernames = ['Lukasa']

for username in usernames:
    print('User: ' + username)
    scaler, dev_stats = get_dev_commits_stats(username)
    # Create user model
    svm_user = OneClassSVM(kernel='poly', gamma='auto', nu=0.1)
    print('Training...')
    svm_user.fit(dev_stats)

    con = sqlite3.connect('results/forged_commits-clever-' + username + '.db')
    #con = sqlite3.connect('results/forged_commits-dumb-' + username + '.db')
    cursor = con.cursor()
    cursor.execute('SELECT commit_data FROM forged_commits')
    all_obj = cursor.fetchall()

    fp = []
    tp = []
    predict = []

    print('Predict..')
    for tmp in all_obj:
        forged_commit = json.loads(tmp[0])
        parsed_commit = parse_commits([forged_commit])
        result = svm_user.predict(scaler.transform(parsed_commit))
        predict.append(result)

    predict = np.array(predict)
    tp = len(where(predict == -1)[0])
    fp = len(where(predict == 1)[0])
    print('Accuracy: ' + str(tp/500 * 100))
    print('FP rate: ' + str(fp/500 * 100))
    print('F1 Score: ' + str(f1_score(np.full(500, 1), predict) * 100))

