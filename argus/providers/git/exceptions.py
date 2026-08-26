from __future__ import annotations

from argus.core.errors import ArgusError, ProviderTimeoutError, ProviderUnavailableError, ProviderUnconfiguredError


class GitError(ArgusError):
    code = "git_error"


class GitHubError(GitError):
    code = "github_error"


class GitHubUnconfiguredError(GitHubError, ProviderUnconfiguredError):
    code = "github_unconfigured"


class GitHubUnavailableError(GitHubError, ProviderUnavailableError):
    code = "github_unavailable"


class GitHubTimeoutError(GitHubError, ProviderTimeoutError):
    code = "github_timeout"


class GitHubNotFoundError(GitHubError):
    code = "github_not_found"


class GitLabError(GitError):
    code = "gitlab_error"


class GitLabUnconfiguredError(GitLabError, ProviderUnconfiguredError):
    code = "gitlab_unconfigured"


class GitLabUnavailableError(GitLabError, ProviderUnavailableError):
    code = "gitlab_unavailable"


class GitLabTimeoutError(GitLabError, ProviderTimeoutError):
    code = "gitlab_timeout"


class GitLabNotFoundError(GitLabError):
    code = "gitlab_not_found"


class UnsupportedGitHostError(GitError):
    """Raised when no provider adapter is configured for a repository host."""

    code = "unsupported_git_host"
