import sys
from logging import getLogger, Formatter, LogRecord, StreamHandler
from logging.handlers import SysLogHandler
from os import environ

RFC_SYSLOG_MAX_MSG_LENGTH = 1024

class TruncatingLogRecord(LogRecord):
    def getMessage(self):
        return super(TruncatingLogRecord, self).getMessage()[:RFC_SYSLOG_MAX_MSG_LENGTH]

def setup():
    if 'RSYSLOG_HOST' in environ:
        log_handler = SysLogHandler(address=(environ['RSYSLOG_HOST'], environ['RSYSLOG_PORT']))
        log_handler.setFormatter(Formatter(fmt='%(levelname)s {%(processName)s[%(process)d]} %(message).900s'))
    else:
        log_handler = streamhandler(sys.stdout)
        log_handler.setformatter(formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

    logger = getLogger()
    logger.setLevel(environ['LOG_LEVEL'])
    logger.addHandler(log_handler)

    from platform import python_version_tuple
    major, minor, _ = python_version_tuple()

    if int(major) > 2 and int(minor) > 1:
        # we need to make sure messages to rsyslog are kept under 1024 bytes
        # per RFC-3164 ('4.1 syslog Message Parts')
        # Not sure why this is not enforced by SysLogHandler
        # In python 3 we can change the logRecord factory.
        # In Python 2 we can only hope the Formatter format string is truncating the 'message' attribute
        # as in this example: "%(message).100s"  => limit is 100 chars
        from logging import setLogRecordFactory
        setLogRecordFactory(TruncatingLogRecord)
    logger.debug('Root logger is setup')
