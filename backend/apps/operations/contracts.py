from dataclasses import dataclass, field

@dataclass(frozen=True)
class JobResult:
    """records: items processed; failed: items that failed; detail: up to 50 {item_id: error_code}."""
    records: int
    failed: int = 0
    detail: dict = field(default_factory=dict)

class JobFailure(Exception):
    CODES={'TIMEOUT','HTTP_ERROR','SCHEMA_ERROR','NOT_CONFIGURED','STORAGE_ERROR','SOURCE_ERROR'}
    def __init__(self,code,*,retryable=True):
        if code not in self.CODES:
            raise ValueError('Invalid sanitized job error code')
        self.code=code
        self.retryable=retryable
        super().__init__(code)

class RetryableExecutionError(RuntimeError):
    """Only sanitized text crosses the transport's log/result boundary."""
