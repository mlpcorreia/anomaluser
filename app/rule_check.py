import utils
from models import Developer, CommitsStats, Commits, File, Pull, DeveloperStats, RepoStats
from sqlalchemy import func
from utils import user_contributions

import datetime
import configparser

# Configuration read
rules = configparser.ConfigParser()
rules.read('rules.ini')


# Decision Rules
def rules_violated(session, username, added_files, touched_files, day, commit_data):
    tmp = 0
    tmp += 1 if touched_sensitive_files(touched_files.union(set(added_files))) else 0
    tmp += 1 if not_first_never_touched(session, username, touched_files) else 0
    tmp += 1 if not_first_owned_files(session, username, touched_files) else 0
    tmp += 1 if adds_and_does_not_touch(session, username, added_files, touched_files) else 0
    tmp += 1 if outlier_check(session, username, commit_data) else 0
    trusted = is_trusted(session, username, day)
    tmp += 1 if not trusted else 0
    return (tmp / 7) * 100, trusted


def touched_sensitive_files(touched_files):
    extensions = [i.split('.')[-1] for i in touched_files]
    sensitive_files = rules['Rules']['Sensitive_Files'].split(',')
    total = 0
    for tmp in extensions:
        if tmp in sensitive_files:
            total += 1
    return total >= int(rules['Rules']['Sensitive_Files_Threshold'])


def not_first_never_touched(session, username, touched_files):
    commits_dev = session.query(Commits).join(Developer).filter(Developer.username == username).all()
    user_touched_files = set()
    touched = set(touched_files)
    for commit in commits_dev:
        for commit_file in commit.files:
            user_touched_files.add(commit_file.file.filename)
    prev_touched = user_touched_files.intersection(touched)
    diff = prev_touched - touched
    return not first_commit(session, username) and round(len(diff) / len(touched), 2) >= float(
        rules['Rules']['Not_Touched_Files'])


def not_first_owned_files(session, username, touched_files):
    owned_count = session.query(File).join(Developer).filter(Developer.username == username)\
        .filter(File.filename.in_(touched_files)).count()
    number_files = session.query(File).count()
    return not first_commit(session, username) and \
           round(owned_count / number_files, 2) >= float(rules['Rules']['Owned_Majority_Files'])


def adds_and_does_not_touch(session, username, added_files, touched_files):
    major_contributions = set(is_major_contributor_to_files(session, username))
    diff = major_contributions.intersection(touched_files)
    return len(added_files) >= float(rules['Rules']['New_Files_Outlier']) and len(diff) == 0


def is_major_contributor_to_files(session, username):
    tmp = {}
    query_result = session.query(Commits.new_lines, Commits.removed_lines, File.filename).join(File.commit)\
        .join(Developer).join(Commits).filter(Developer.username == username).all()
    for new_lines, removed_lines, filename in query_result:
        if filename in tmp:
            tmp[filename] += new_lines + removed_lines
        else:
            tmp[filename] = new_lines + removed_lines
    return [i for i in tmp if tmp[i] >= int(rules['Rules']['Contributions'])]


def count_files_by_status(files):
    # Count files per status
    added = 0
    modified = 0
    removed = 0
    for file in files:
        if file['status'] == 'added':
            added += 1
        if file['status'] == 'modified':
            modified += 1
        if file['status'] == 'removed':
            removed += 1
    return {'added': added, 'modified': modified, 'removed': removed}


def outlier_stats_check(stats, commit_data, file_status):
    new_lines_upper_limit = stats.new_lines_avg + stats.new_lines_std
    new_lines_lower_limit = stats.new_lines_avg - stats.new_lines_std
    if new_lines_upper_limit < commit_data['stats']['additions'] \
            or new_lines_lower_limit > commit_data['stats']['additions']:
        return True
    removed_lines_upper_limit = stats.removed_lines_avg + stats.removed_lines_std
    removed_lines_lower_limit = stats.removed_lines_avg - stats.removed_lines_std
    if removed_lines_upper_limit < commit_data['stats']['deletions'] \
            or removed_lines_lower_limit > commit_data['stats']['deletions']:
        return True
    added_files_upper_limit = stats.added_files_avg + stats.added_files_std
    added_files_lower_limit = stats.added_files_avg - stats.added_files_std
    if added_files_upper_limit < file_status['added'] or added_files_lower_limit > file_status['added']:
        return True
    modified_files_upper_limit = stats.modified_files_avg + stats.modified_files_std
    modified_files_lower_limit = stats.modified_files_avg - stats.modified_files_std
    if modified_files_upper_limit < file_status['modified'] or modified_files_lower_limit > file_status['modified']:
        return True
    removed_files_upper_limit = stats.removed_files_avg + stats.removed_files_std
    removed_files_lower_limit = stats.removed_files_avg - stats.removed_files_std
    if removed_files_upper_limit < file_status['removed'] or removed_files_lower_limit > file_status['removed']:
        return True
    return False


def outlier_check(session, username, commit_data):
    files_status = count_files_by_status(commit_data['files'])
    if not first_commit(session, username):
        dev_id = session.query(Developer.id).filter(Developer.username == username).one()[0]
        dev_stats = session.query(DeveloperStats).filter(DeveloperStats.developer_id == dev_id).one()
        if outlier_stats_check(dev_stats, commit_data, files_status):
            return True
    repo_stats = session.query(RepoStats).one()
    if outlier_stats_check(repo_stats, commit_data, files_status):
        return True
    return False


def files_already_touched(session, username):
    return [i[0] for i in session.query(File.filename).join(Commits, File.commit).join(Developer).filter(
        Developer.username == username).all()]


def owned_files(session, username):
    return [i[0] for i in session.query(File.filename).join(Developer).filter(Developer.username == username).all()]


# Trust Rules
def is_trusted(session, username, day):
    tmp = 0
    tmp += 1 if is_contributor(username) else 0
    tmp += 1 if not recent_account(session, username) else 0
    tmp += 1 if commits_threshold(session, username) else 0
    tmp += 1 if not first_commit(session, username) else 0
    tmp += 1 if commits_per_day(session, username, day) else 0
    tmp += 1 if rejected_pulls(session, username) else 0
    return round(tmp / 6, 1) >= float(rules['Trust']['Trust_Threshold'])


def is_contributor(username):
    return int(user_contributions(username)) != 0


def recent_account(session, username):
    dev = session.query(Developer).filter_by(username=username).one_or_none()
    if dev:
        date_diff = datetime.date.today() - dev.account_creation.date()
        return date_diff.days <= int(rules['Trust']['Min_Time_Contributor'])


def commits_threshold(session, username):
    number_commits = session.query(Commits).join(Developer).filter(Developer.username == username).count()
    total_commits = session.query(Commits).count()
    return round(number_commits / total_commits, 2) >= float(rules['Trust']['Few_Commits_Threshold'])


def first_commit(session, username):
    dev = session.query(Developer).filter_by(username=username).one_or_none()
    return dev is None


def commits_per_day(session, username, day):
    total = session.query(func.sum(CommitsStats.number_commits)).filter(CommitsStats.date == day).one()
    commits_stats = session.query(CommitsStats.number_commits).join(Developer).filter(Developer.username == username,
                                                                                      CommitsStats.date == day).one_or_none()
    if commits_stats:
        return round(commits_stats[0] / total[0], 1) >= float(rules['Trust']['Same_Day_Commits'])
    return False


def rejected_pulls(session, username):
    pulls = session.query(Pull).join(Developer).filter(Developer.username == username).count()
    pulls_rejected = session.query(Pull).join(Developer).filter(Developer.username == username, Pull.state == 'closed',
                                                                Pull.merged == False).count()
    if pulls > 0:
        return round(pulls_rejected / pulls) <= float(rules['Trust']['Rejected_PR'])
    else:
        return True
