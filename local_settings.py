## Debug settings
DEBUG = False
#DEBUG_TOOLBAR = True

## For django debug toolbar
INTERNAL_IPS = ('127.0.0.1',)

## Notification admins
ADMINS = (
   # ('Name Admin', 'name@example.com'),
)

## PostgreSQL Database settings
#DATABASES = {
#    'default': {
#        'ENGINE'  : 'django.db.backends.postgresql_psycopg2',
#        'NAME'    : 'vanir',
#        'USER'    : 'vaniros',
#        'PASSWORD': 'vaniros',
#        'HOST'    : '',
#        'PORT'    : '',
#    },
#}

## Sqlite Database settings
DATABASES = {
    'default': {
        'ENGINE'  : 'django.db.backends.sqlite3',
        'NAME'    : 'database.db',
    },
}

## Define cache settings
CACHES = {
    'default': {
        'BACKEND' : 'django.core.cache.backends.dummy.DummyCache',
        #'BACKEND' : 'django.core.cache.backends.memcached.MemcachedCache',
        #'LOCATION': '127.0.0.1:11211',
    }
}

## Use secure session cookies? Make this true if you want all
## logged-in actions to take place over HTTPS only. If developing
## locally, you will want to use False.
SESSION_COOKIE_SECURE = False

## location for saving dev pictures
MEDIA_ROOT = '/srv/example.com/img/'

## web url for serving image files
MEDIA_URL = '/media/img/'

## Make this unique, and don't share it with anybody.
SECRET_KEY = '00000000000000000000000000000000000000000000000'

# vim: set ts=4 sw=4 et:
