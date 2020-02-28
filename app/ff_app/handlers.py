from django.utils.log import AdminEmailHandler
from django.conf import settings

class FFAdminEmailHandler(AdminEmailHandler):
    
    def format_subject(self, subject):
        """
        Escape CR and LF characters.
        """
        return settings.SERVER_NAME + ", " + subject.replace('\n', '\\n').replace('\r', '\\r')
