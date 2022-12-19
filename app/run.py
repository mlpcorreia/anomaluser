from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import utils
from models import create_tables
from utils import *

import configparser
import time
import os

# Configuration read
config = configparser.ConfigParser()
config.read('config.ini')
# Database configuration
# db_engine = create_engine('sqlite:///project.db', echo=True)
DB_NAME = config['Database']['DB_Name']
db_engine = create_engine('sqlite:///' + DB_NAME)
DBSession = sessionmaker(bind=db_engine)
if not os.path.exists(DB_NAME):
    create_tables(db_engine)

# Repository
OWNER = config['Repository']['Owner']
REPO = config['Repository']['Name']


def get_repository_info():
    """
    Get information from the repository
    """
    with DBSession() as session:
        if session.query(Developer).count() == 0:
            get_contributors(OWNER, REPO, session)
        devs = session.query(Developer).all()
        for dev in devs:
            print('\nGetting %s commits' % dev.username)
            get_commits(OWNER, REPO, dev, session)
            session.flush()
            utils.calculate_global_dev_stats(session, dev.id)
        session.commit()
        utils.calculate_repo_stats(session)


def get_dev_commits(username):
    with DBSession() as session:
        dev = session.query(Developer).filter_by(username=username).one_or_none()
        if dev:
            print(dev)
            print('#################################################################################')
            commits = session.query(Commits).filter_by(developer=dev).all()
            for commit in commits:
                print(commit)
                print([tmp.filename for tmp in commit.files])
                print('#################################################################################')


def get_all_dev_daily_stats():
    with DBSession() as session:
        devs = session.query(Developer).all()
        for dev in devs:
            print('#################################################################################')
            print(dev)
            commits_stats = session.query(CommitsStats).filter_by(developer=dev).all()
            for stat in commits_stats:
                print('Day: ' + str(stat.date))
                print('Time interval from ' + str(stat.time_intervals_min) + ' to ' + str(stat.time_intervals_max))
                print('Number of commits: ' + str(stat.number_commits))
                print('Time mean(s): ' + str(stat.time_intervals_mean))
                print('Time variance(s): ' + str(stat.time_intervals_var))
                print('Changed lines min: ' + str(stat.changed_lines_min))
                print('Changed lines max: ' + str(stat.changed_lines_max))
                print('Changed lines mean: ' + str(stat.changed_lines_mean))
                print('Changed lines variance: ' + str(stat.changed_lines_mean))
                print('Changed chars min: ' + str(stat.changed_chars_min))
                print('Changed chars max: ' + str(stat.changed_chars_max))
                print('Changed chars mean: ' + str(stat.changed_chars_mean))
                print('Changed chars variance: ' + str(stat.changed_chars_var))
                print('Commit messages min size: ' + str(stat.comments_size_min))
                print('Commit messages max size: ' + str(stat.comments_size_max))
                print('Commit messages mean: ' + str(stat.comments_size_mean))
                print('Commit messages variance: ' + str(stat.comments_size_var))
                print()
            print('#################################################################################')


def get_commits_user():
    with DBSession() as session:
        dev = session.query(Developer).filter_by(username='tofu-rocketry').one_or_none()
        get_commits(OWNER, REPO, dev, session)


start_time = time.time()
with DBSession() as db_session:
    #calculate_daily_stats(db_session)
    #get_pulls(OWNER, REPO, db_session)
    utils.calculate_repo_stats(db_session)
# get_commits_user()
#get_repository_info()
#get_all_dev_daily_stats()
# get_dev_commits('mlpcorreia')
print('Execution time: %s seconds' % (time.time() - start_time))
