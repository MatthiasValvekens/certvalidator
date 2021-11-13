"""
Internal backend-agnostic utilities to help process fetched certificates, CRLs
and OCSP responses.
"""
import asyncio
import logging
import os
from .. import errors
from asn1crypto import x509, pem, cms, ocsp, algos, core

__all__ = [
    'unpack_cert_content', 'format_ocsp_request', 'process_ocsp_response_data',
    'queue_fetch_task',
    'crl_job_results_as_completed',
    'ocsp_job_get_earliest',
    'ACCEPTABLE_STRICT_CERT_CONTENT_TYPES',
    'ACCEPTABLE_CERT_PEM_ALIASES'
]


logger = logging.getLogger(__name__)


ACCEPTABLE_STRICT_CERT_CONTENT_TYPES = (
    'application/pkix-cert', 'application/pkcs7-mime',
    'application/x-x509-ca-cert'
)

ACCEPTABLE_CERT_PEM_ALIASES = (
    'application/x-pem-file', 'text/plain',
)


def unpack_cert_content(response_data: bytes, content_type: str,
                        url: str, permit_pem: bool):

    if content_type in ('application/pkix-cert', 'application/x-x509-ca-cert'):
        yield x509.Certificate.load(response_data)
    elif permit_pem and (content_type in ACCEPTABLE_CERT_PEM_ALIASES):
        # technically, PEM is not allowed here, but of course some people don't
        # bother following the rules
        if pem.detect(response_data):
            for _, _, data in pem.unarmor(response_data, multiple=True):
                yield x509.Certificate.load(data)
        else:
            raise ValueError(
                "Expected PEM data when extracting certs from "
                f"{content_type} payload. Source URL: {url}."
            )
    elif content_type == 'application/pkcs7-mime':
        content_info: cms.ContentInfo = cms.ContentInfo.load(response_data)
        cms_ct = content_info['content_type'].native
        if cms_ct != 'signed_data':
            raise ValueError(
                "Expected CMS SignedData when extracting certs from "
                "application/pkcs7-mime payload, but content type was "
                f"'{cms_ct}'. Source URL: {url}."
            )
        signed_data = content_info['content']
        if isinstance(signed_data['certificates'], cms.CertificateSet):
            for cert_choice in signed_data['certificates']:
                if cert_choice.name == 'certificate':
                    yield cert_choice.chosen


def format_ocsp_request(cert: x509.Certificate, issuer: x509.Certificate,
                        *, certid_hash_algo: str, request_nonces: bool):
    cert_id = ocsp.CertId({
        'hash_algorithm': algos.DigestAlgorithm(
            {'algorithm': certid_hash_algo}
        ),
        'issuer_name_hash': getattr(cert.issuer, certid_hash_algo),
        'issuer_key_hash': getattr(issuer.public_key, certid_hash_algo),
        'serial_number': cert.serial_number,
    })

    request = ocsp.Request({
        'req_cert': cert_id,
    })
    tbs_request = ocsp.TBSRequest({
        'request_list': ocsp.Requests([request]),
    })

    if request_nonces:
        nonce_extension = ocsp.TBSRequestExtension({
            'extn_id': 'nonce',
            'critical': False,
            'extn_value': core.OctetString(
                core.OctetString(os.urandom(16)).dump())
        })
        tbs_request['request_extensions'] = ocsp.TBSRequestExtensions(
            [nonce_extension]
        )

    return ocsp.OCSPRequest({'tbs_request': tbs_request})


def process_ocsp_response_data(response_data: bytes, *,
                               ocsp_request: ocsp.OCSPRequest, ocsp_url: str):
    ocsp_response = ocsp.OCSPResponse.load(response_data)
    status = ocsp_response['response_status'].native
    if status != 'successful':
        raise errors.OCSPValidationError(
            'OCSP server at %s returned an error. Status was \'%s\'.'
            % (ocsp_url, status)
        )

    request_nonce = ocsp_request.nonce_value
    if request_nonce:
        response_nonce = ocsp_response.nonce_value
        # if the response did not contain the nonce extension, there's no
        # point in trying to enforce it, that's the CA's problem.
        #  (I suppose we could give callers the option to mark the nonce
        #  extension as critical in the request, but that's discouraged by the
        #  specification)
        if response_nonce and (request_nonce.native != response_nonce.native):
            raise errors.OCSPValidationError(
                'Unable to verify OCSP response since the request and '
                'response nonces do not match'
            )
    return ocsp_response


async def queue_fetch_task(results, running_jobs, tag, async_fun):
    # use an asyncio events to make sure that we don't attempt to re-fetch
    # the same tag while the job is running
    # Note: this uses asyncio locking, so we only transfer control
    # on 'await'.
    # We use events instead of locks because we don't care about fairness,
    # and events are easier to reason about.
    try:
        result = results[tag]
        logger.debug(
            f"Result for fetch job with tag {repr(tag)} was available in cache."
        )
        return _return_or_raise(result)
    except KeyError:
        pass
    try:
        wait_event: asyncio.Event = running_jobs[tag]
        logger.debug(
            f"Waiting for fetch job with tag {repr(tag)} to return..."
        )
        # there's a fetch job running, wait for it to finish and then
        # return the result
        await wait_event.wait()
        logger.debug(
            f"Received completion signal for job with tag {repr(tag)}."
        )
        return _return_or_raise(results[tag])
    except KeyError:
        logger.debug(
            f"Starting new fetch job with tag {repr(tag)}..."
        )
        # no fetch job running, run the task and store the result
        running_jobs[tag] = wait_event = asyncio.Event()
        try:
            result = await async_fun()
        except Exception as e:
            logger.debug(
                f"New fetch job with tag {repr(tag)} threw an exception: {e}"
            )
            result = e
        results[tag] = result
        logger.debug(
            f"New fetch job with tag {repr(tag)} returned."
        )
        # deregister event, notify waiters
        del running_jobs[tag]
        wait_event.set()
        return _return_or_raise(result)


def _return_or_raise(result):
    if isinstance(result, Exception):
        raise result
    return result


async def crl_job_results_as_completed(jobs):
    last_e = None
    at_least_one_success = False
    for crl_job in asyncio.as_completed(list(jobs)):
        try:
            fetched_crl = await crl_job
            yield fetched_crl
        except errors.CRLFetchError as e:
            last_e = e

    if last_e is not None and not at_least_one_success:
        raise last_e


async def cancel_all(pending_tasks):
    pending = asyncio.gather(*pending_tasks)
    pending.cancel()
    try:
        await pending
    except asyncio.CancelledError:
        pass


async def ocsp_job_get_earliest(jobs):
    queue = [asyncio.create_task(coro) for coro in jobs]
    ocsp_resp = last_e = None
    while queue:
        done, queue = await asyncio.wait(
            queue, return_when=asyncio.FIRST_COMPLETED
        )
        for ocsp_job in done:
            try:
                ocsp_resp = await ocsp_job
                break
            except errors.OCSPFetchError as e:
                last_e = e
    if ocsp_resp is not None:
        # cancel remaining fetch tasks
        await cancel_all(queue)
        return ocsp_resp
    raise last_e or errors.OCSPFetchError("No OCSP results")
