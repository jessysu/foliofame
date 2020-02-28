# -*- coding: utf-8 -*-
"""
Created on Thu Oct  5 23:46:48 2017

@author: jsu
"""


#DB = {"host" : "localhost", "user" : "", "passwd" : "", "db" : "ff_dev"}
DB = {"host" : "",
      "user" : "",
      "passwd" : "",
      "db" : "ff_dev",
      "tables" : ["auth_group", "auth_group_permissions", "auth_permission", "auth_user",
                  "auth_user_groups", "auth_user_user_permissions", "authtoken_token", "django_admin_access_ip_whitelist",
                  "django_admin_log",
                  "django_content_type", "django_migrations", "django_session", "ff_app_watchlist", "ff_bestever_session_log",
                  "ff_logging_besteversessionlog", "ff_logging_clicklog", "ff_logging_hindsightrequestlog",
                  "registration_registrationprofile", "social_auth_association", "social_auth_code",
                  "social_auth_nonce", "social_auth_partial", "social_auth_usersocialauth"
                 ],
      "port": 3306}

MONGODB = {
    "host": "",
    "port": 27017,
    "user": "",
    "passwd": ""
}


FILEINFO = {
    "loc": ""
}


EMAILINFO = {
    "host": "",
    "port": 587,
    "user": "",
    "passwd": "",
    "sender": "",
    "receiver": []
}

ForceRefreshTable = False
