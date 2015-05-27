import requests

TH_ARTIFACT_URL = 'https://treeherder.mozilla.org/api/project/{}/artifact/'


def get_request_id_from_job_id(repo_name, job_id):
    """Get buildapi's request_id from Treeherder's artifact API."""
    artifact_url = TH_ARTIFACT_URL.format(repo_name)
    query_params = {'job_id': job_id,
                    'name': 'buildapi'}
    artifact_content = requests.get(artifact_url, params=query_params).json()
    return artifact_content[0]["blob"]["request_id"]
