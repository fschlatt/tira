"""
Django settings for django_admin project.

Generated by 'django-admin startproject' using Django 3.1.3.

For more information on this file, see
https://docs.djangoproject.com/en/3.1/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/3.1/ref/settings/
"""

from pathlib import Path
import os
import yaml

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

custom_settings = {}
for cfg in (BASE_DIR / "config").glob("*.yml"):
    custom_settings.update(yaml.load(open(cfg, "r").read(), Loader=yaml.FullLoader))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = custom_settings.get("django_secret")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = custom_settings.get("debug", True)
ALLOWED_HOSTS = custom_settings.get("allowed_hosts", [])

TIRA_ROOT = Path(custom_settings.get("tira_root", "/mnt/ceph/tira"))
DEPLOYMENT = custom_settings.get("deployment", "legacy")
LEGACY_USER_FILE = Path(custom_settings.get("legacy_users_file", ""))
HOST_GRPC_PORT = custom_settings.get("host_grpc_port", "50051")
APPLICATION_GRPC_PORT = custom_settings.get("application_grpc_port", "50052")
GRPC_HOST = custom_settings.get("grpc_host", "local")  # can be local or remote

# Application definition

INSTALLED_APPS = [
    'tira.apps.TiraConfig',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'django_admin.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates']
        ,
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'django_admin.wsgi.application'

# Database
# https://docs.djangoproject.com/en/3.1/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"


def logger_config(log_dir: Path):
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
                'style': '{',
            },
            'default': {
                'format': '{levelname} {asctime} {module}: {message}',
                'style': '{',
            },
            'simple': {
                'format': '{levelname} {message}',
                'style': '{',
            },
        },
        'filters': {
            'require_debug_true': {
                '()': 'django.utils.log.RequireDebugTrue',
            },
        },
        'handlers': {
            'console': {
                'level': 'DEBUG',
                'filters': ['require_debug_true'],
                'class': 'logging.StreamHandler',
                'formatter': 'default'
            },
            'file': {
                'level': 'DEBUG',
                'filters': ['require_debug_true'],
                'class': 'logging.FileHandler',
                'filename': BASE_DIR / 'debug.log',
                'formatter': 'simple'
            },
            'ceph_debug_file': {
                'level': 'DEBUG',
                'class': 'logging.FileHandler',
                'filters': ['require_debug_true'],
                'filename': log_dir / 'debug.log',
                'formatter': 'default'
            },
            'ceph_info_file': {
                'level': 'INFO',
                'class': 'logging.FileHandler',
                'filename': log_dir / 'info.log',
                'formatter': 'default'
            },
            'ceph_warn_file': {
                'level': 'WARNING',
                'class': 'logging.FileHandler',
                'filename': log_dir / 'warnings.log',
                'formatter': 'default'
            },
        },
        'loggers': {
            'django': {
                'handlers': ['console', 'ceph_debug_file'],
                'propagate': True,
            },
            'django.requests': {
                'handlers': ['console', 'ceph_warn_file', 'ceph_info_file'],
                'propagate': True,
            },
            'django.server': {
                'handlers': ['console', 'ceph_warn_file', 'ceph_info_file'],
                'propagate': True,
            },
            'tira': {
                'handlers': ['console', 'ceph_warn_file', 'ceph_info_file'],
                'propagate': True,
            },
        }
    }


# Logging
ld = Path(custom_settings.get("logging_dir", BASE_DIR))
if os.access(ld, os.W_OK):
    LOGGING = logger_config(ld)
else:
    print(f"failed to initialize logging in {ld}")
    if DEBUG:
        print(f"Logging to {BASE_DIR}")
        LOGGING = logger_config(Path(BASE_DIR))
    else:
        raise PermissionError(f"Can not write to {ld} in production mode.")


# Password validation
# https://docs.djangoproject.com/en/3.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/3.1/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Europe/Berlin'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/3.1/howto/static-files/

STATIC_URL = '/public/'

STATICFILES_DIRS = [
    BASE_DIR / "static/",
    BASE_DIR / "tira/static/"
]

STATIC_ROOT = "/var/www/public"
