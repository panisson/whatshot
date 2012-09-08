# coding: utf-8
#
#  Copyright (C) 2012 André Panisson
#  You can contact me by email (panisson@gmail.com) or write to:
#  Via Alassio 11/c - 10126 Torino - Italy
#
import sqlalchemy as sa
import sqlalchemy.orm
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.exc import NoResultFound
import config

url = 'mysql://%s:%s@%s/%s?charset=utf8&use_unicode=0' %(config.USERNAME,config.PASSWORD,config.HOST,config.DB)

engine = sa.create_engine(url, pool_recycle=3600, max_overflow=-1)
Session = sqlalchemy.orm.scoped_session(sqlalchemy.orm.sessionmaker(bind=engine, autocommit=True))


def transactional(fn):
    """add transactional semantics to a method."""

    def transact(*args, **kwargs):
        session = Session()
        try:
            result = fn(*args, **kwargs)
            session.commit()
            return result
        except:
            session.rollback()
            raise
        finally:
            Session.remove()
    return transact


Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id                  = sa.Column('id', sa.Integer, primary_key=True)
    screen_name         = sa.Column('screen_name', sa.String(45))
    blocked             = sa.Column('blocked', sa.String(1))
    name                = sa.Column('name', sa.String(45))
    description         = sa.Column('description', sa.String(1000))
    created_at          = sa.Column('created_at', sa.DateTime)
    friends_count       = sa.Column('friends_count', sa.Integer)
    followers_count     = sa.Column('followers_count', sa.Integer)
    statuses_count      = sa.Column('statuses_count', sa.Integer)
    profile_image_url   = sa.Column('profile_image_url', sa.String(255))
    lang                = sa.Column('lang', sa.String(20))
    location            = sa.Column('location', sa.String(100))
    oauth_token         = sa.Column('oauth_token', sa.String(200))
    oauth_token_secret  = sa.Column('oauth_token_secret', sa.String(200))
    
    @staticmethod
    def select_by_id(user_id):
        try:
            user = Session().query(User).filter_by(id=user_id).one()
        except NoResultFound, e:
            return None
        
        return user
    
    @staticmethod
    def select_by_screen_name(screen_name):
        try:
            user = Session().query(User).filter_by(screen_name=screen_name).one()
        except NoResultFound:
            return None
        
        return user
    
    @staticmethod
    def add(user):
        Session().add(user)
        Session().flush()
        
    @staticmethod
    def is_blocked(user_id):
        query = "SELECT 1 FROM users WHERE id = :user_id AND blocked = 'Y'"
        result = Session().execute(query, {'user_id':user_id}).fetchone()
        if result:
            return True
        else:
            return False

    @staticmethod
    def set_blocked(user_id, blocked):
        sql = "INSERT INTO users (id, blocked) VALUES (:user_id, :blocked) ON DUPLICATE KEY UPDATE blocked = :blocked"
        Session().execute(sql, {'user_id':user_id, 'blocked':'Y' if blocked else 'N'})

class Followers(Base):
    __tablename__ = 'followers'
    
    source = sa.Column('source', sa.Integer, primary_key=True)
    target = sa.Column('target', sa.Integer, primary_key=True)
    
    @staticmethod
    def insert_many(source, target_list):
        inserter = Followers.__table__.insert().prefix_with("IGNORE")
        Session().execute(inserter, [{'source':source, 'target':target} for target in target_list])
    
    @staticmethod
    def select_by_id(user_id):
        followers = Session().query(Followers).filter_by(source=user_id).all()
        return [f.target for f in followers]

    @staticmethod
    def select_top_n(user_id, n):
        query = """
        SELECT COUNT(1), f2.target 
        FROM followers AS f 
        JOIN followers AS f2 ON (f.target=f2.source)
        WHERE f.source = :user_id AND f2.target <> :user_id
        GROUP BY f2.target
        ORDER BY COUNT(1) DESC
        LIMIT """ + str(n) 
        followers = Session().execute(query, {'user_id':user_id}).fetchall()
        return [(f[1], f[0]) for f in followers]
    
def commit():
    Session().flush() #FIXME: using autocommit for now
    #Session().commit()
