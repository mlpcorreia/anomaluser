from sqlalchemy import Column, Integer, String, DateTime, Date, Boolean, Float, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# Commits and files association table
class CommitsFiles(Base):
    __tablename__ = 'commits_files'
    commit_id = Column(ForeignKey('commits.id'), primary_key=True)
    file_id = Column(ForeignKey('file.id'), primary_key=True)
    status = Column(String)

    commit = relationship('Commits', back_populates='files')
    file = relationship('File', back_populates='commit')


class Developer(Base):
    __tablename__ = 'developer'

    id = Column(Integer, primary_key=True)
    username = Column(String)
    contributions = Column(Integer)
    account_creation = Column(DateTime)
    follower_number = Column(Integer)

    commits = relationship('Commits', back_populates='developer')
    commits_stats = relationship('CommitsStats', back_populates='developer')
    global_stats = relationship('DeveloperStats', back_populates='developer')
    files = relationship('File', back_populates='owner')
    pull = relationship('Pull', back_populates='author')

    def __repr__(self):
        return "Developer account: %s | created_at %s | %s followers | contributions: %s " % (
            self.username, self.account_creation, self.follower_number, self.contributions)


class Commits(Base):
    __tablename__ = 'commits'

    id = Column(Integer, primary_key=True)
    day = Column(Date)
    timestamp = Column(DateTime)
    languages = Column(String)
    message = Column(String)
    new_lines = Column(Integer)
    removed_lines = Column(Integer)
    changed_chars = Column(Integer)
    added_files = Column(Integer)
    modified_files = Column(Integer)
    removed_files = Column(Integer)
    renamed_files = Column(Integer)
    developer_id = Column(Integer, ForeignKey('developer.id'))

    developer = relationship('Developer', back_populates='commits')
    files = relationship('CommitsFiles', back_populates='commit')

    def __repr__(self):
        return "Id %s | Timestamp %s | New lines %s | Removed lines %s | Languages %s" % (self.id, self.timestamp, self.new_lines,
                                                                                  self.removed_lines, self.languages)


class File(Base):
    __tablename__ = 'file'

    id = Column(Integer, primary_key=True)
    filename = Column(String)
    previous_filename = Column(String)
    developer_id = Column(Integer, ForeignKey('developer.id'))  # file author/owner

    commit = relationship('CommitsFiles', back_populates='file')
    owner = relationship('Developer', back_populates='files')
    
    def __repr__(self):
        return "Id %s | Filename %s | Previous filename %s" % (self.id, self.filename, self.previous_filename)


class CommitsStats(Base):
    __tablename__ = 'commits_stats'

    id = Column(Integer, primary_key=True)
    date = Column(Date)
    number_commits = Column(Integer)
    time_intervals_min = Column(DateTime)
    time_intervals_max = Column(DateTime)
    time_intervals_mean = Column(Integer)  # seconds
    time_intervals_var = Column(Integer)  # seconds
    changed_lines_min = Column(Integer)
    changed_lines_max = Column(Integer)
    changed_lines_mean = Column(Integer)
    changed_lines_var = Column(Integer)
    changed_chars_min = Column(Integer)
    changed_chars_max = Column(Integer)
    changed_chars_mean = Column(Integer)
    changed_chars_var = Column(Integer)
    comments_size_min = Column(Integer)
    comments_size_max = Column(Integer)
    comments_size_mean = Column(Integer)
    comments_size_var = Column(Integer)
    added_files_mean = Column(Integer)
    added_files_var = Column(Integer)
    modified_files_mean = Column(Integer)
    modified_files_var = Column(Integer)
    removed_files_mean = Column(Integer)
    removed_files_var = Column(Integer)
    developer_id = Column(Integer, ForeignKey('developer.id'))

    developer = relationship('Developer', back_populates='commits_stats')


class DeveloperStats(Base):
    __tablename__ = 'developer_stats'

    developer_id = Column(Integer, ForeignKey('developer.id'), primary_key=True)
    new_lines_avg = Column(Float)
    new_lines_std = Column(Float)
    new_lines_var = Column(Float)
    removed_lines_avg = Column(Float)
    removed_lines_std = Column(Float)
    removed_lines_var = Column(Float)
    added_files_avg = Column(Float)
    added_files_std = Column(Float)
    added_files_var = Column(Float)
    modified_files_avg = Column(Float)
    modified_files_std = Column(Float)
    modified_files_var = Column(Float)
    removed_files_avg = Column(Float)
    removed_files_std = Column(Float)
    removed_files_var = Column(Float)

    developer = relationship('Developer', back_populates='global_stats')


class RepoStats(Base):
    __tablename__ = 'repo_stats'

    id = Column(Integer, primary_key=True)
    new_lines_avg = Column(Float)
    new_lines_std = Column(Float)
    new_lines_var = Column(Float)
    removed_lines_avg = Column(Float)
    removed_lines_std = Column(Float)
    removed_lines_var = Column(Float)
    added_files_avg = Column(Float)
    added_files_std = Column(Float)
    added_files_var = Column(Float)
    modified_files_avg = Column(Float)
    modified_files_std = Column(Float)
    modified_files_var = Column(Float)
    removed_files_avg = Column(Float)
    removed_files_std = Column(Float)
    removed_files_var = Column(Float)


class Pull(Base):
    __tablename__ = 'pull'

    id = Column(Integer, primary_key=True)
    merged = Column(Boolean)
    state = Column(String)
    developer_id = Column(Integer, ForeignKey('developer.id'))

    author = relationship('Developer', back_populates='pull')


def create_tables(db_engine):
    Base.metadata.create_all(db_engine)
