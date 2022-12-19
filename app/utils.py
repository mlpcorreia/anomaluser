from models import Developer, Commits, File, CommitsStats, Pull, CommitsFiles, DeveloperStats, RepoStats
from sqlalchemy import desc, func

from datetime import datetime
import configparser
import sqlalchemy
import statistics
import requests
import math
import json

# Read configs
config = configparser.ConfigParser()
config.read('config.ini')
API_URL = config['Github']['Url']
# Initialize request session
req_session = requests.Session()
req_session.auth = (config['Github']['Username'], config['Github']['Token'])
req_session.headers.update({'Accept': 'application/vnd.github.v3+json'})


def user_contributions(username):
    r = req_session.get(API_URL + 'search/commits?q=author:{}'.format(username))
    resp_json = r.json()
    if 'total_count' in resp_json:
        return resp_json['total_count']
    else:
        return '0'


def get_commit_info(commit_url):
    return req_session.get(commit_url).json()


def get_developer(username, session):
    return session.query(Developer).filter_by(username=username).one_or_none()


def get_file(session, query):
    """
    Get a File from the database based on a filename.

    Parameters
    ----------
    session : sqlalchemy.orm.Session
        DB session used in ORM related operations
    query : string
        Filename to be queried in the File table

    Returns
    -------
    File
        File object or None if there is no object in the DB with the specified filename
    """
    file = session.query(File).filter_by(filename=query).one_or_none()
    if not file:
        file = session.query(File).filter_by(previous_filename=query).one_or_none()
    return file


def save_file_changes(commit_data, commit, db_session, dev):
    languages = {}
    changed_chars = 0
    added = 0
    modified = 0
    removed = 0
    renamed = 0
    for file_data in commit_data['files']:
        filename = file_data['filename']
        file_type = filename[filename.rfind('.') + 1:]
        if file_type not in languages:
            languages[file_type] = 1
        else:
            languages[file_type] = languages[file_type] + 1
        # Count characters changed per file
        if 'patch' in file_data:
            commit_changes = file_data['patch'].split('\n')
            for line_change in commit_changes:
                if line_change[0] == '+' or line_change[0] == '-':
                    changed_chars += len(line_change)
        file = get_file(db_session, filename)
        if not file:
            file = File(filename=filename)
            file.commit.status = file_data['status']
        if file_data['status'] == 'renamed':
            # Check if there was a file with the same name in a most recent commit
            previous_file = db_session.query(File).filter_by(previous_filename=file_data['previous_filename']).one_or_none()
            if previous_file:
                previous_file.previous_filename = ''
                db_session.add(previous_file)
                db_session.commit()
            file.previous_filename = file_data['previous_filename']
        if file and file_data['status'] == 'added':
            file.owner = dev
            file.commit.status = file_data['status']
        if file:
            if not any(obj.file.filename == file.filename for obj in commit.files):
                commit.files.append(CommitsFiles(file=file, status=file_data['status']))
        added += (1 if file_data['status'] == 'added' else 0)
        modified += (1 if file_data['status'] == 'modified' else 0)
        removed += (1 if file_data['status'] == 'removed' else 0)
        renamed += (1 if file_data['status'] == 'renamed' else 0)
    commit.languages = json.dumps(languages)
    return changed_chars, added, modified, removed, renamed


def get_mean_and_variance(values):
    mean = 0
    var = 0
    if len(values) > 0:
        mean = sum(values) / len(values)
        if len(values) > 1:
            var = statistics.variance(values)
    return mean, var


def daily_commit_stats(session, date, developer_id, lines_changed, changed_chars, commits_time, commits_messages_len,
                       added_files, modified_files, removed_files):
    # Lines changed mean and variance
    lines_mean, lines_variance = get_mean_and_variance(lines_changed)
    # Chars changed mean and variance
    chars_mean, chars_variance = get_mean_and_variance(changed_chars)
    # Calculate time intervals between commits made in the same day
    time_intervals = []
    if len(commits_time) > 1:
        for i in range(0, len(commits_time)):
            if len(commits_time) == i + 1:
                break
            delta = commits_time[i] - commits_time[i + 1]
            time_intervals.append(delta.total_seconds())
    times_mean, times_variance = get_mean_and_variance(time_intervals)
    comments_size_mean, comments_size_var = get_mean_and_variance(commits_messages_len)
    added_files_mean, added_files_var = get_mean_and_variance(added_files)
    modified_files_mean, modified_files_var = get_mean_and_variance(modified_files)
    removed_files_mean, removed_files_var = get_mean_and_variance(removed_files)
    commit_stats = CommitsStats(date=date, number_commits=len(lines_changed), time_intervals_min=min(commits_time),
                                time_intervals_max=max(commits_time), time_intervals_mean=times_mean,
                                time_intervals_var=times_variance, changed_lines_min=min(lines_changed),
                                changed_lines_max=max(lines_changed), changed_lines_mean=lines_mean,
                                changed_lines_var=lines_variance, changed_chars_min=min(changed_chars),
                                changed_chars_max=max(changed_chars), changed_chars_mean=chars_mean,
                                changed_chars_var=chars_variance, comments_size_min=min(commits_messages_len),
                                comments_size_max=max(commits_messages_len), comments_size_mean=comments_size_mean,
                                comments_size_var=comments_size_var, added_files_mean=added_files_mean,
                                added_files_var=added_files_var, modified_files_mean=modified_files_mean,
                                modified_files_var=modified_files_var, removed_files_mean=removed_files_mean,
                                removed_files_var=removed_files_var, developer_id=developer_id)
    session.add(commit_stats)
    session.commit()


def calculate_daily_stats(db_session):
    day = None
    lines_changed = []
    changed_chars = []
    commits_time = []
    commits_messages_len = []
    added_files = []
    modified_files = []
    removed_files = []
    devs_id = db_session.query(Developer.id).all()
    for dev_id in devs_id:
        commits = db_session.query(Commits).filter_by(developer_id=dev_id[0]).order_by(desc(Commits.day)).all()
        for commit in commits:
            if day is None:
                day = commit.day
            elif day is not None and day != commit.day:
                daily_commit_stats(db_session, day, dev_id[0], lines_changed, changed_chars, commits_time,
                                   commits_messages_len, added_files, modified_files, removed_files)
                day = commit.day
                lines_changed = []
                changed_chars = []
                commits_time = []
                commits_messages_len = []
                added_files = []
                modified_files = []
                removed_files = []
            lines_changed.append(commit.new_lines + commit.removed_lines)
            commits_time.append(commit.timestamp)
            commits_messages_len.append(len(commit.message))
            changed_chars.append(commit.changed_chars)
            added_files.append(commit.added_files)
            modified_files.append(commit.modified_files)
            removed_files.append(commit.removed_files)
        daily_commit_stats(db_session, day, dev_id[0], lines_changed, changed_chars, commits_time, commits_messages_len,
                           added_files, modified_files, removed_files)


def get_commits(owner, repo, dev, db_session):
    page = 1
    author = dev.username
    while True:
        r = req_session.get(
            API_URL + 'repos/{}/{}/commits?author={}&per_page=100&page={}'.format(owner, repo, author, page))
        print('Page %s' % page, end='\r')
        page += 1
        data = r.json()
        if not data:
            break
        for tmp in data:
            # Check if a merge occurred and act accordingly
            if len(tmp['parents']) > 1:
                for parent in tmp['parents']:
                    url = parent['url']
                    commit_data = req_session.get(url).json()
                    if not commit_data['author']:
                        continue
                    username = commit_data['author']['login']
                    developer = get_developer(username, db_session)
                    if developer == None:
                        continue
                    dev_tmp = developer
                    developer_id = developer.id
            else:
                url = tmp['url']
                commit_data = req_session.get(url).json()
                dev_tmp = dev
                developer_id = dev.id

            commit_timestamp = commit_data['commit']['author']['date']
            commit_timestamp = datetime.fromisoformat(commit_timestamp[:-1])
            new_lines = commit_data['stats']['additions']
            removed_lines = commit_data['stats']['deletions']
            commit_message = commit_data['commit']['message']
            commit = Commits(timestamp=commit_timestamp, day=commit_timestamp.date(), new_lines=new_lines,
                             message=commit_message, removed_lines=removed_lines, developer_id=developer_id)
            db_session.add(commit)
            db_session.flush()
            commit.changed_chars, commit.added_files, commit.modified_files, commit.removed_files, commit.renamed_files\
                = save_file_changes(commit_data, commit, db_session, dev_tmp)
            db_session.add(commit)
        if len(data) < 100:
            break
        db_session.commit()


def create_user(username, contributions, db_session):
    r = req_session.get(API_URL + 'users/' + username)
    print('Creating user %s' % username, end='\033[K\r')
    response = r.json()
    dev = Developer(username=response['login'], contributions=contributions,
                    account_creation=datetime.fromisoformat(response['created_at'][:-1]),
                    follower_number=response['followers'])
    db_session.add(dev)
    db_session.commit()


def get_contributors(owner, repo, db_session):
    """
    To improve performance, only the first 500 author email addresses in the repository link to GitHub users.
    The rest will appear as anonymous contributors without associated GitHub user information.
    https://github.community/t/api-github-list-contributors/13520/4
    https://github.com/php/php-src/graphs/contributors?from=1999-04-04&to=2021-12-08&type=c
    """
    page = 1
    while True:
        r = req_session.get(API_URL + 'repos/{}/{}/contributors?per_page=100&page={}'.format(owner, repo, page))
        page += 1
        data = r.json()
        for tmp in data:
            create_user(tmp['login'], tmp['contributions'], db_session)
        if len(data) < 100:
            break


def get_pulls(owner, repo, db_session):
    # diff url (https://patch-diff.githubusercontent.com/raw/torvalds/linux/pull/805.diff)
    page = 1
    while True:
        r = req_session.get(API_URL + 'repos/{}/{}/pulls?state=all&per_page=100&page={}'.format(owner, repo, page))
        page += 1
        data = r.json()
        for pull in data:
            tmp_pull = req_session.get(pull['url']).json()
            dev = get_developer(pull['user']['login'], db_session)
            pull_obj = Pull(merged=tmp_pull['merged'], state=tmp_pull['state'], author=dev)
            db_session.add(pull_obj)
        db_session.commit()
        if len(data) < 100:
            break


def get_languages(owner, repo):
    r = req_session.get(API_URL + 'repos/{}/{}/languages'.format(owner, repo))
    print(r.json())


def calculate_lines_variance_dev(session, attr, dev):
    query = f'''SELECT 
    SUM(({attr}-(SELECT AVG({attr}) FROM commits JOIN developer ON developer_id = developer.id WHERE developer_id = {dev}))
    *({attr}-(SELECT AVG({attr}) FROM commits JOIN developer ON developer_id = developer.id WHERE developer_id = {dev}))) / (COUNT({attr})-1) 
    AS Variance FROM commits JOIN developer ON developer_id = developer.id WHERE developer_id = {dev}
    '''
    to_execute = sqlalchemy.text(query)
    cursor = session.execute(to_execute)
    return cursor.fetchall()[0][0]


def calculate_lines_variance_repo(session, attr):
    query = f'''SELECT SUM(({attr}-(SELECT AVG({attr}) FROM commits))*({attr}-(SELECT AVG({attr}) FROM commits))) 
    / (COUNT({attr})-1) AS Variance FROM commits
    '''
    to_execute = sqlalchemy.text(query)
    cursor = session.execute(to_execute)
    return cursor.fetchall()[0][0]


def calculate_files_variance_dev(session, attr, dev):
    query = f'''
    SELECT SUM(({attr}-(SELECT AVG({attr}) FROM commits JOIN developer ON developer_id = developer.id WHERE developer_id = {dev}))*
    ({attr}-(SELECT AVG({attr}) FROM commits JOIN developer ON developer_id = developer.id WHERE developer_id = {dev})))
     / (COUNT({attr})-1) AS Variance FROM commits JOIN developer ON developer_id = developer.id WHERE developer_id = {dev}
    '''
    to_execute = sqlalchemy.text(query)
    cursor = session.execute(to_execute)
    return cursor.fetchall()[0][0]


def calculate_files_variance_repo(session, attr):
    query = f'''SELECT SUM(({attr}-(SELECT AVG({attr}) FROM commits))*({attr}-(SELECT AVG({attr}) FROM commits))) 
    / (COUNT({attr})-1) AS Variance FROM commits
    '''
    to_execute = sqlalchemy.text(query)
    cursor = session.execute(to_execute)
    return cursor.fetchall()[0][0]


def calculate_global_dev_stats(session, dev_id):
    new_lines_var = calculate_lines_variance_dev(session, 'new_lines', dev_id)
    removed_lines_var = calculate_lines_variance_dev(session, 'removed_lines', dev_id)
    added_files_var = calculate_files_variance_dev(session, 'added_files', dev_id)
    modified_files_var = calculate_files_variance_dev(session, 'modified_files', dev_id)
    removed_files_var = calculate_files_variance_dev(session, 'removed_files', dev_id)
    new_lines_var = new_lines_var if new_lines_var else 0
    removed_lines_var = removed_lines_var if removed_lines_var else 0
    added_files_var = added_files_var if added_files_var else 0
    modified_files_var = modified_files_var if modified_files_var else 0
    removed_files_var = removed_files_var if removed_files_var else 0
    dev_stats = DeveloperStats()
    dev_stats.developer_id = dev_id
    dev_stats.new_lines_avg = session.query(func.avg(Commits.new_lines)).join(Developer).filter(Developer.id == dev_id).one()[0]
    dev_stats.new_lines_std = math.sqrt(new_lines_var)
    dev_stats.new_lines_var = new_lines_var
    dev_stats.removed_lines_avg = session.query(func.avg(Commits.removed_lines)).join(Developer).filter(
                Developer.id == dev_id).one()[0]
    dev_stats.removed_lines_std = math.sqrt(removed_lines_var)
    dev_stats.removed_lines_var = removed_lines_var
    dev_stats.added_files_avg = session.query(func.avg(Commits.added_files)).join(Developer).filter(
                Developer.id == dev_id).one()[0]
    dev_stats.added_files_var = added_files_var
    dev_stats.added_files_std = math.sqrt(added_files_var)
    dev_stats.modified_files_avg = session.query(func.avg(Commits.modified_files)).join(Developer).filter(
                Developer.id == dev_id).one()[0]
    dev_stats.modified_files_var = modified_files_var
    dev_stats.modified_files_std = math.sqrt(modified_files_var)
    dev_stats.removed_files_avg = session.query(func.avg(Commits.removed_files)).join(Developer).filter(
                Developer.id == dev_id).one()[0]
    dev_stats.removed_files_var = removed_files_var
    dev_stats.removed_files_std = math.sqrt(removed_files_var)
    session.add(dev_stats)
    session.commit()


def calculate_repo_stats(session):
    repo_new_lines_var = calculate_lines_variance_repo(session, 'new_lines')
    repo_removed_lines_var = calculate_lines_variance_repo(session, 'removed_lines')
    repo_added_files_var = calculate_files_variance_repo(session, 'added_files')
    repo_modified_files_var = calculate_files_variance_repo(session, 'modified_files')
    repo_removed_files_var = calculate_files_variance_repo(session, 'removed_files')
    repo_stats = RepoStats()
    repo_stats.new_lines_avg = session.query(func.avg(Commits.new_lines)).one()[0]
    repo_stats.new_lines_var = repo_new_lines_var
    repo_stats.new_lines_std = math.sqrt(repo_new_lines_var)
    repo_stats.removed_lines_avg = session.query(func.avg(Commits.removed_lines)).one()[0]
    repo_stats.removed_lines_var = repo_removed_lines_var
    repo_stats.removed_lines_std = math.sqrt(repo_removed_lines_var)
    repo_stats.added_files_avg = session.query(func.avg(Commits.added_files)).one()[0]
    repo_stats.added_files_var = repo_added_files_var
    repo_stats.added_files_std = math.sqrt(repo_added_files_var)
    repo_stats.modified_files_avg = session.query(func.avg(Commits.modified_files)).one()[0]
    repo_stats.modified_files_var = repo_modified_files_var
    repo_stats.modified_files_std = math.sqrt(repo_modified_files_var)
    repo_stats.removed_files_avg = session.query(func.avg(Commits.removed_files)).one()[0]
    repo_stats.removed_files_var = repo_removed_files_var
    repo_stats.removed_files_std = math.sqrt(repo_removed_files_var)
    session.add(repo_stats)
    session.commit()
