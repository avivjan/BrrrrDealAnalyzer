"""ARV estimates as background jobs.

A real estimate takes one to several minutes (Claude runs many web searches),
but production reaches the API through Netlify's `/api/*` proxy, which drops a
request after about 30 seconds. So `POST /arv-estimate` only starts a job and
returns its id, and the popup polls `GET /arv-estimate/{arv_estimate_job_id}`.

Jobs live in this process's memory: the service runs a single Render instance,
and an estimate is not worth persisting (it is never saved with the deal). A
redeploy loses running jobs; the poll then gets a 404 and the popup asks the user
to try again. Finished jobs are forgotten after `FINISHED_JOB_RETENTION_SECONDS`.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Optional

from BL.arvEstimate import estimateArv
from BL.arvEstimate.common.anthropic_arv_client import ArvEstimateFailedError, ArvEstimateNotConfiguredError
from ReqRes.common.arv_estimate_schemas import ArvEstimateJobRes, ArvEstimateReq, ArvEstimateRes

logger = logging.getLogger(__name__)

MAXIMUM_CONCURRENT_ARV_ESTIMATES = 2
FINISHED_JOB_RETENTION_SECONDS = 30 * 60
UNEXPECTED_FAILURE_MESSAGE = "The ARV estimate failed unexpectedly; try again."

arv_estimate_job_executor = ThreadPoolExecutor(
    max_workers=MAXIMUM_CONCURRENT_ARV_ESTIMATES, thread_name_prefix="arv-estimate"
)


@dataclass
class ArvEstimateJob:
    arv_estimate_job_id: str
    status: str = "RUNNING"
    arv_estimate: Optional[ArvEstimateRes] = None
    failure_message: Optional[str] = None
    finished_at_monotonic_seconds: Optional[float] = None
    created_at_monotonic_seconds: float = field(default_factory=time.monotonic)

    def to_response(self) -> ArvEstimateJobRes:
        return ArvEstimateJobRes(
            arv_estimate_job_id=self.arv_estimate_job_id,
            status=self.status,
            arv_estimate=self.arv_estimate,
            failure_message=self.failure_message,
        )


_arv_estimate_jobs_by_id: dict[str, ArvEstimateJob] = {}
_arv_estimate_jobs_lock = threading.Lock()


def _forget_long_finished_jobs() -> None:
    oldest_kept_finish = time.monotonic() - FINISHED_JOB_RETENTION_SECONDS
    with _arv_estimate_jobs_lock:
        for job_id in [
            job_id
            for job_id, job in _arv_estimate_jobs_by_id.items()
            if job.finished_at_monotonic_seconds is not None and job.finished_at_monotonic_seconds < oldest_kept_finish
        ]:
            del _arv_estimate_jobs_by_id[job_id]


def _finish_job(job: ArvEstimateJob, *, arv_estimate: ArvEstimateRes | None = None, failure_message: str | None = None) -> None:
    with _arv_estimate_jobs_lock:
        job.arv_estimate = arv_estimate
        job.failure_message = failure_message
        job.status = "SUCCEEDED" if arv_estimate is not None else "FAILED"
        job.finished_at_monotonic_seconds = time.monotonic()


def _run_arv_estimate_job(job: ArvEstimateJob, arv_estimate_request: ArvEstimateReq) -> None:
    try:
        arv_estimate = estimateArv.estimate_arv_with_claude(arv_estimate_request)
    except (ArvEstimateFailedError, ArvEstimateNotConfiguredError) as error:
        _finish_job(job, failure_message=str(error))
        logger.info("ARV estimate job %s failed: %s", job.arv_estimate_job_id, error)
    except Exception:  # noqa: BLE001 - a worker thread must always finish its job
        logger.exception("ARV estimate job %s failed unexpectedly", job.arv_estimate_job_id)
        _finish_job(job, failure_message=UNEXPECTED_FAILURE_MESSAGE)
    else:
        _finish_job(job, arv_estimate=arv_estimate)
        logger.info("ARV estimate job %s succeeded", job.arv_estimate_job_id)


def start_arv_estimate_job(arv_estimate_request: ArvEstimateReq) -> ArvEstimateJob:
    _forget_long_finished_jobs()
    job = ArvEstimateJob(arv_estimate_job_id=uuid.uuid4().hex)
    with _arv_estimate_jobs_lock:
        _arv_estimate_jobs_by_id[job.arv_estimate_job_id] = job
    arv_estimate_job_executor.submit(_run_arv_estimate_job, job, arv_estimate_request)
    return job


def find_arv_estimate_job(arv_estimate_job_id: str) -> ArvEstimateJob | None:
    _forget_long_finished_jobs()
    with _arv_estimate_jobs_lock:
        return _arv_estimate_jobs_by_id.get(arv_estimate_job_id)
