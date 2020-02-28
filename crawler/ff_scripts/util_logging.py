from pymongo import MongoClient
from static import MONGODB, FILEINFO, EMAILINFO
from datetime import datetime
import logging
import logging.handlers
from log4mongo.handlers import BufferedMongoHandler

bmh = BufferedMongoHandler(host=MONGODB["host"],                     # All MongoHandler parameters are valid
                               port=MONGODB["port"],
                               username=MONGODB["user"],
                               password=MONGODB["passwd"],
                               capped=True,
                               buffer_size=100,                           # buffer size.
                               buffer_periodical_flush_timing=10.0,       # periodical flush every 10 seconds
                               buffer_early_flush_level=logging.CRITICAL) # early flush

# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

# create formatter
formatter = logging.Formatter('%(asctime)-15s - %(levelname)s - %(collection_name)s : %(message)s')

# add formatter to ch
ch.setFormatter(formatter)

fh = logging.FileHandler(FILEINFO["loc"])
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)


class CustomizedSMTPHandler(logging.handlers.SMTPHandler):
    def getSubject(self, record):
        # print(record)
        # print(record.name)
        # print(record.levelname)
        # print(record.msg)
        # print(record.args)
        # print(record.exc_info)
        return record.msg

    def emit(self, record):
        # check for record in self.already_send or something
        super(CustomizedSMTPHandler, self).emit(record)


mh = CustomizedSMTPHandler(
    mailhost=(EMAILINFO["host"], EMAILINFO["port"]),
    fromaddr=EMAILINFO["sender"],
    toaddrs=EMAILINFO["receiver"],
    subject= "Critical error",
    credentials=(EMAILINFO["user"], EMAILINFO["passwd"]),
    secure=()
)
mh.setLevel(logging.ERROR)

logger = logging.getLogger('common')
logger.setLevel(logging.DEBUG)
logger.addHandler(bmh)
logger.addHandler(ch)
logger.addHandler(fh)
logger.addHandler(mh)


class Log:
    @staticmethod
    def error(collection_name, message):
        logger.error(message, extra={"collection_name": collection_name})

    @staticmethod
    def debug(collection_name, message):
        logger.debug(message, extra={"collection_name": collection_name})

    @staticmethod
    def info(collection_name, message):
        logger.info(message, extra={"collection_name": collection_name})

    @staticmethod
    def warning(collection_name, message):
        logger.warning(message, extra={"collection_name": collection_name})

    @staticmethod
    def exception(collection_name, message):
        logger.exception(message, extra={"collection_name": collection_name})
