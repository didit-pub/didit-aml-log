import logging
from datetime import datetime, timezone


try:
    import orjson as json
except ImportError:
    import json


BUILTIN_ATTRS = {
    'args',
    'asctime',
    'created',
    'exc_info',
    'exc_text',
    'filename',
    'funcName',
    'levelname',
    'levelno',
    'lineno',
    'module',
    'msecs',
    'message',
    'msg',
    'name',
    'pathname',
    'process',
    'processName',
    'relativeCreated',
    'stack_info',
    'thread',
    'threadName',
}


class LokiFormatter(logging.Formatter):
    json_lib = json

    def format(self, record):
        try:
            message = record.getMessage()
            extra = self.extra_from_record(record)
            json_record = self.json_record(message, extra, record)
            mutated_record = self.mutate_json_record(json_record)
            # Backwards compatibility: Functions that overwrite this but don't
            # return a new value will return None because they modified the
            # argument passed in.
            if mutated_record is None:
                mutated_record = json_record
            return self.to_json(mutated_record)
        except Exception as e:
            return f'{{"level": "ERROR", "name": "didit_aml.log.LokiFormatter", "message": "{str(e)}"}}'

    def to_json(self, record):
        """Converts record dict to a JSON string.

        It makes best effort to serialize a record (represents an object as a string)
        instead of raising TypeError if json library supports default argument.
        Note, ujson doesn't support it.
        ValueError and OverflowError are also caught to avoid crashing an app,
        e.g., due to circular reference.

        Override this method to change the way dict is converted to JSON.

        """
        try:
            return self.json_lib.dumps(record, default=_json_serializable)
        # ujson doesn't support default argument and raises TypeError.
        # "ValueError: Circular reference detected" is raised
        # when there is a reference to object inside the object itself.
        except (TypeError, ValueError, OverflowError):
            try:
                return self.json_lib.dumps(record)
            except (TypeError, ValueError, OverflowError) as e:
                return '{}'

    def extra_from_record(self, record):
        """Returns `extra` dict you passed to logger.

        The `extra` keyword argument is used to populate the `__dict__` of
        the `LogRecord`.

        """
        return {
            attr_name: record.__dict__[attr_name]
            for attr_name in record.__dict__
            if attr_name not in BUILTIN_ATTRS
        }

    def json_record(self, message, extra, record):
        extra['message'] = message

        # Include builtins
        extra['level'] = record.levelname_
        extra['name'] = record.name

        if record.exc_info:
            extra['exc_info'] = self.formatException(record.exc_info)

        extra['filename'] = record.filename
        extra['func_name'] = record.funcName
        extra['lineno'] = record.lineno
        extra['module'] = record.module
        extra['pathname'] = record.pathname

        return extra

    def mutate_json_record(self, json_record):
        """Override it to convert fields of `json_record` to needed types.

        Default implementation converts `datetime` to string in ISO8601 format.

        """
        for attr_name in json_record:
            attr = json_record[attr_name]
            if isinstance(attr, datetime):
                json_record[attr_name] = attr.isoformat()
        return json_record


def _json_serializable(obj):
    try:
        return obj.__dict__
    except AttributeError:
        return str(obj)
