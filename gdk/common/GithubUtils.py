import requests


class GithubUtils:
    def get_latest_release_name(self, owner, repository):
        latest_release_api_url = f"https://api.github.com/repos/{owner}/{repository}/releases/latest"
        response = requests.get(latest_release_api_url)
        if response.status_code != 200:
            if response.status_code == 403:
                if not response.json().get("message").find("API rate limit exceeded"):
                    response.raise_for_status()
        return response.json().get("name", None)  # We typically name our GTF releases by the version.
