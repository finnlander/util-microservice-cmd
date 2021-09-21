#!/usr/bin/env python3

"""
Fabric 2 fabfile for Python 3.x.

Description:
    The script contains tasks for managing actions in microservice platform
    that has multiple git repositories working as micro services.

Dependencies:
    - fabric (pip3 install fabric)
    - invoke (pip3 install invoke)
    - gitpython (pip3 install gitpython)
    - termcolor (pip3 install termcolor)


Note for linux users:
    pip install fab may install the binaries into $HOME/.local/bin that may
    note be included in the $PATH variable by default. If the fab command does
    not work, make sure the location is included in "PATH" env variable.

    version: 0.4
    License information: (MIT-license)

    Copyright (c) 2020 Janne Suomalainen

    Permission is hereby granted, free of charge, to any person obtaining
    a copy of this software and associated documentation files (the
    "Software"), to deal in the Software without restriction, including
    without limitation the rights to use, copy, modify, merge, publish,
    distribute, sublicense, and/or sell copies of the Software, and to
    permit persons to whom the Software is furnished to do so, subject to
    the following conditions:

    The above copyright notice and this permission notice shall be included
    in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
    EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
    MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
    IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
    CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
    TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
    SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

import os
import traceback
from termcolor import colored
from invoke import task, run

from git import Repo

# Constants #

# Environment variable name for passing JVM arguments to Spring boot processes.
ENV_JVM_ARGS_KEY = 'PLATFORM_JVMARGS'

# Default maven profile used, if none provided
DEFAULT_MVN_PROFILE = 'local-dev'

# Expected 'remote' name that is used in GIT operations (fetch, pull, etc)
DEFAULT_GIT_REMOTE_NAME = 'origin'

# Enable debug mode to print exception traceback information
DEBUG_MODE = False

# Tasks #
"""
Note in Fabric2 the tasks are executed by task name AND by replacing
underscore (_) values with dash (-).
The first parameter for task is always "context" (mandatory or the task is not
valid) and other parameters are used as named parameters (mandatory by default)
in command line having format --[param-name]=[param value]
Note: the underscores are replaced with dashes in named parameters as well.

Example usage: `fab pull-all`
Run: `fab --help [task-name]` for more information about params.
Run: `fab -l` to list all available tasks.
"""


@task(optional=["branch"])
def fetch_all(ctx, branch=None):
    """
    Fetch all git repositories.

    The included repositories exists in direct sub-directories of the current
    directory (or from current directory, if none exists in sub directories).
    :param ctx:     (implicit fabric context param).
    :param branch:  Use specific branch instead of the current active branch in
                    the operation.
    """
    current_directory = os.getcwd()
    git_repo_dirs = _get_git_repo_paths(current_directory)
    if not git_repo_dirs:
        _run_action_if_is_repo(current_directory, lambda repo_dir,
                               repo: _fetch_repo(repo_dir, repo, branch))
    else:
        _run_action_for_each_repo(
            git_repo_dirs,
            lambda repo_dir, repo: _fetch_repo(repo_dir, repo, branch))


@task
def pull_all(ctx):
    """
    Pull all git repositories.

    The included repositories exists in direct sub-directories of the
    current directory (or from current directory, if none exists in
    sub-directories).
    :param ctx:   (implicit fabric context param).
    :information: This method skips any repositories having non-committed
                    changes compared to HEAD.
    """
    current_directory = os.getcwd()
    git_repo_dirs = _get_git_repo_paths(current_directory)
    if not git_repo_dirs:
        _run_action_if_is_repo(
            current_directory,
            lambda repo_dir, repo: _pull_repo(repo_dir, repo))
    else:
        _run_action_for_each_repo(
            git_repo_dirs,
            lambda repo_dir, repo: _pull_repo(repo_dir, repo))


@task(optional=["branch"])
def check_repo_states(ctx, branch=None):
    """
    Check status of git repositories comparing origin with local branch.

    The included repositories exists in direct sub-directories of the current
    directory (or from current directory, if none exists in sub directories)
    :information:   This method skips any repositories having non-committed
                    changes compared to HEAD.
    :param ctx:     (implicit fabric context param).
    :param branch:  Use specific branch instead of the current active branch in
                    the operation.
    """
    current_directory = os.getcwd()
    git_repo_dirs = _get_git_repo_paths(current_directory)
    if not git_repo_dirs:
        _run_action_if_is_repo(
            current_directory,
            lambda repo_dir, repo:
                _check_is_repo_up_to_date(repo_dir, repo, branch))
    else:
        _run_action_for_each_repo(
            git_repo_dirs,
            lambda repo_dir, repo:
                _check_is_repo_up_to_date(repo_dir, repo, branch))


@task
def list_repos(ctx):
    """
    List all git repositories with current branch.

    The included repositories exists in direct sub-directories of the current
    directory (or from current directory, if none exists in sub directories).
    :param ctx:     (implicit fabric context param).
    """
    current_directory = os.getcwd()
    git_repo_dirs = _get_git_repo_paths(current_directory)
    if not git_repo_dirs:
        if _has_git_repo(current_directory):
            print(_get_git_repo_str(
                current_directory,
                Repo(current_directory)))
            _print_info('(repo is in current directory)')
        else:
            _print_info('No GIT repos found from "{}"'.format(
                current_directory))
    else:
        _run_action_for_each_repo(git_repo_dirs, lambda repo_dir, repo: print(
            _get_git_repo_str(repo_dir, repo)))


@task(optional=["list", "fetch", "pull", "update", "branch"])
def git(ctx, list=False, fetch=False, pull=False, update=False, branch=None):
    """
    Run batch operations for each git repositories.

    The included repositories exists in direct sub directories of the current
    directory). The task supports providing multiple actions at once.
    :param ctx:     (implicit fabric context param).
    :param list:    List all git repository directories with current branch and
                    dirty state.
    :param fetch:   Run `git fetch` for all repositories.
    :param pull:    Run `git pull` for all repositories.
    :param update:  Run `git remote update` and check if the remote branch is
                    ahead of the current for all repositories.
    :param branch:  Use specific branch instead of the current active branch in
                    the operation.
    """
    if not list and not fetch and not pull and not update:
        _print_info(
            'Add at least one action as parameter: '
            + '["--list", "--fetch", "--pull", "--update"]')
        return

    if list:
        _print_info('listing GIT repositories...\n')
        if branch is not None:
            _print_warn(
                '-- omitting parameter "--branch": '
                + 'it is not supported by the list action')
        list_repos(ctx)

    if fetch:
        _print_info('fetching GIT repositories...\n')
        fetch_all(ctx, branch)

    if pull:
        _print_info('pulling GIT repositories...\n')
        if branch is not None:
            _print_warn(
                '-- omitting parameter "--branch": '
                + 'it is not supported by the list action')
        pull_all(ctx)

    if update:
        _print_info('checking GIT repositories'' HEAD states...\n')
        check_repo_states(ctx, branch)


@task
def list_docker_repos(ctx):
    """
    List all git repositories that has docker compose file in the root.

    The included repositories exists in direct sub-directories of the
    current directory (or from current directory, if none exists in sub
    directories).
    :param ctx:     (implicit fabric context param).
    """
    current_directory = os.getcwd()
    git_repo_dirs = _get_repo_paths_containing_dockers(current_directory)
    if not git_repo_dirs:
        if _has_docker_compose_file(current_directory):
            print(_get_git_repo_str(
                current_directory,
                Repo(current_directory)))
            print('(repo is in current directory)')
        else:
            print('no GIT repos with dockers found from "{}"'.format(
                current_directory))
    else:
        _run_action_for_each_repo(git_repo_dirs, lambda repo_dir, repo: print(
            _get_git_repo_str(repo_dir, repo)))


@task(optional=["up", "down", "restart", "list"])
def docker(ctx, up=False, down=False, restart=False, list=False):
    """
    Run docker compose related action in each repository.

    The included repositories have docker compose file in their root. The task
    supports providing multiple actions at once.
    :param ctx:     (implicit fabric context param).
    :param up:      [action] Run `docker-compose up -d`
                    (creating and starting docker containers as daemons)
    :param down:    [action] Run `docker-compose down`
                    (stopping docker containers)
    :param restart: [action] Run `docker-compose restart`
                    (restarting services inside docker containers)
    :param list:    [action] List all repositories having docker
    """
    if not up and not down and not restart and not list:
        _print_info(
            'Add at least one action as parameter: '
            + '["--up", "--down", "--restart", "--list"]')
        return

    current_directory = os.getcwd()
    git_repo_dirs = _get_repo_paths_containing_dockers(current_directory)

    if not git_repo_dirs:
        if _has_docker_compose_file(current_directory):
            _print_info('--> applying action to current directory')
            git_repo_dirs.append(current_directory)
        else:
            print('No docker repos found =(')
            return

    if list:
        _print_info('Listing all repos that have dockers...\n')
        list_docker_repos(ctx)

    if down:
        _print_info('Stopping all dockers...\n')
        _run_action_for_each_repo(
            git_repo_dirs,
            lambda repo_dir, repo: _stop_dockers(repo_dir, repo))

    if up:
        _print_info('Starting all dockers\n')
        _run_action_for_each_repo(
            git_repo_dirs,
            lambda repo_dir, repo: _start_dockers(repo_dir, repo))

    if restart:
        _print_info('Restarting all dockers...\n')
        _run_action_for_each_repo(
            git_repo_dirs,
            lambda repo_dir, repo: _re_start_dockers(repo_dir, repo))
        return


@task
def list_mvn_repos(ctx):
    """
    List all git repositories that has maven project file in the root.

    The maven project file (pom.xml) is expected to exist in the repository
    root directory. The included repositories exists as direct sub-directories
    of the current directory (or in the current directory, if none exists in
    sub-directories).
    :param ctx:     (implicit fabric context param).
    """
    current_directory = os.getcwd()
    git_repo_dirs = _get_repo_paths_containing_maven_project(current_directory)
    if not git_repo_dirs:
        if _has_mvn_file(current_directory):
            print(_get_git_repo_str(
                current_directory,
                Repo(current_directory)))
            print('(repo is in current directory)')
        else:
            print('no GIT repos with mvn projects found from "{}"'.format(
                current_directory))
    else:
        _run_action_for_each_repo(git_repo_dirs, lambda repo_dir, repo: print(
            _get_git_repo_str(repo_dir, repo)))


@task(optional=["run", "install", "build", "build-all", "repo", "profile"])
def mvn(ctx,
        run=False,
        install=False,
        build=False,
        build_all=False,
        repo=None,
        profile=None):
    """
    Manage maven (Spring Boot) related actions.

    The operation is targeting each repository having maven configuration file
    (pom.xml) in their root directory.
    :param ctx:       (implicit fabric context param).
    :param run:       (--run) Start Spring boot in specificied repository.
    :param install:   (--install) Run `mvn install` in specified repository.
    :param build:     (--build) Run `mvn clean compile` in specified
                      repository.
    :param build-all: (--build-all) Run `mvn clean compile`for all
                      repositories containing maven project.
    :param repo:      (--repo=[repo-dir-name]) Define target repository for
                      single-repository actions.
    :param profile:   (--profile=[mvn profile]) Define maven profile used in
                      action (default='local-dev').
    """
    if not repo and not build_all:
        _print_error(
            'target repository must be defined with --repo=[repository-name]')
        return

    if not build and not build_all and not install and not run:
        _print_info(
            'Add at least one action as parameter: '
            + '["--build", "--install", "--boot"]')
        return

    current_directory = os.getcwd()
    repo_dir = os.path.join(current_directory, repo or '')

    if build_all:
        if build:
            _print_warn(
                "omitting action 'build' (all mvn repositories are built)")

        _build_all_mvn_repos(profile)
    elif build:
        _print_info(f"Trying to build repo in {repo_dir}...\n")
        _build_maven_project(repo_dir, profile)

    if install:
        _install_maven_project(repo_dir, profile)
        pass

    if run:
        if not profile:
            _print_warn(
                "No profile defined for maven task - using default "
                + f"'{DEFAULT_MVN_PROFILE}'")
            profile = DEFAULT_MVN_PROFILE

        jvm_args = os.environ.get(ENV_JVM_ARGS_KEY) or ''
        _print_info(f"Trying to start Spring Boot in dir '{repo_dir}'...\n")
        _start_spring_boot(repo_dir, jvm_args, profile)

# Helper Functions #

# - Git repository related functions #


def _fetch_repo(repo_dir, repo, branch):
    if _is_repo_head_detached(repo):
        _print_warn('-- skipping repo: '
                    + f'{_get_git_repo_identifier_str(repo_dir)}'
                    + ' (HEAD is currently detached)\n')
        return

    remote_name = _get_remote_name(repo)
    if not _has_remote_branch(remote_name, repo):
        remote_repo_identifier = _as_bolded_white_str(repo.active_branch)
        _print_warn('-- skipping repo: '
                    + f'{_get_git_repo_identifier_str(repo_dir)}'
                    + ' (no matching remote repository '
                    + f'"{remote_repo_identifier}")\n')
        return

    target_branch = branch or repo.active_branch

    _print_info(
        f'Fetching branch "{target_branch}" (from {remote_name}) in repo: '
        + f'{_get_git_repo_str(repo_dir, repo)}')
    output = repo.git.fetch('origin', target_branch)

    if output:
        print(f'--> {output}')
    # print empty line after the operation
    print('')


def _pull_repo(repo_dir, repo):

    if repo.is_dirty(untracked_files=True):
        _print_warn(
            f'-- skipping repo: {_get_git_repo_identifier_str(repo_dir)} '
            + '(repo state is DIRTY)\n')
        return

    if _is_repo_head_detached(repo):
        _print_warn('-- skipping repo: '
                    + f'{_get_git_repo_identifier_str(repo_dir)} '
                    + '(HEAD is currently detached)\n')
        return

    if not _is_tracking_remote_branch(repo):
        _print_warn('-- skipping repo: '
                    + f'{_get_git_repo_identifier_str(repo_dir)} '
                    + '(no upstream branch is set)\n')
        return

    remote_name = _get_remote_name(repo)
    if not _has_remote_branch(remote_name, repo):
        _print_warn('-- skipping repo: '
                    + f'{_get_git_repo_identifier_str(repo_dir)} '
                    + '(matching remote branch do not exist in the '
                    + 'references)\n')
        return

    _print_info(f'Pulling repo: {_get_git_repo_str(repo_dir, repo)}')
    output = repo.git.pull()

    if output:
        print(f'--> {output}')
    # print empty line after the operation
    print('')


def _update_remotes_in_repo(repo_dir, repo):
    _print_info(
        f'Updating remotes in repo: {_get_git_repo_str(repo_dir, repo)}\n')
    repo.remotes.origin.update()


def _has_branch(repo, branch):
    for ref in repo.references:
        if str(ref) == str(branch):
            return True

    return False


def _has_remote_branch(remote_name, repo):
    if _is_repo_head_detached(repo):
        # Do not consider detached heads as branches -> False
        return False

    remote_branch_name = f'{remote_name}/{repo.active_branch}'
    for ref in repo.references:
        if str(ref) == remote_branch_name:
            return True

    return False


def _is_repo_head_detached(repo):
    return repo.head.is_detached


def _is_tracking_remote_branch(repo):
    if _is_repo_head_detached(repo):
        return False

    if not repo.remotes:
        # No remotes configures
        return False

    remote = repo.remote()
    if not remote:
        return False

    branch_name = repo.active_branch.name
    remote_branch_name = f'{remote.name}/{branch_name}'

    # example output cases:
    # status='## master...origin/master' -> remote upstream branch IS set
    # status='## master' -> remote upstream branch IS NOT set
    # status='## HEAD (no branch)' -> ... IS NOT set (detached HEAD)
    status = repo.git.status('-sb')
    is_tracking_remote = f'{branch_name}...{remote_branch_name}' in status
    return is_tracking_remote


def _check_is_repo_up_to_date(repo_dir, repo, branch):

    if _is_repo_head_detached(repo):
        _print_warn(
            f'-- Skipping repo {_get_git_repo_identifier_str(repo_dir)}'
            + ' (currently HEAD is detached from any branches) ')
        return

    remote_name = _get_remote_name(repo)
    target_branch = branch or repo.active_branch
    if not _has_branch(repo, target_branch):
        _print_warn(
            f'-- Skipping repo {_get_git_repo_identifier_str(repo_dir)}'
            + f'(no matching branch "{target_branch}")')
        return

    remote_branch = f'{remote_name}/{target_branch}'

    if not _has_remote_branch(remote_name, repo):
        remote_branch_name = colored(remote_branch, 'blue')
        _print_warn(
            f'-- Skipping repo {_get_git_repo_identifier_str(repo_dir)}'
            + f'(no matching remote branch "{remote_branch_name}")')
        return

    _update_remotes_in_repo(repo_dir, repo)
    print(f'Checking repository state {_get_git_repo_str(repo_dir, repo)}')
    commits_ahead = repo.iter_commits(f'{remote_branch}..{target_branch}')
    commits_behind = repo.iter_commits(f'{target_branch}..{remote_branch}')

    behind_commit_count = sum(1 for c in commits_behind)
    forward_commit_count = sum(1 for c in commits_ahead)

    branch_str = colored(target_branch, 'blue')
    remote_branch_str = colored(remote_branch, 'blue')

    if behind_commit_count == 0 and forward_commit_count == 0:
        up_to_date_str = colored('up-to-date', 'green')
        print(
            f'--> Origin ({remote_branch_str}) is {up_to_date_str}'
            + ' with local branch')
        return

    if behind_commit_count > 0:
        behind_str = colored(
            f'ahead by {behind_commit_count} commit(s)', 'green')
        print(f'--> Origin ({remote_branch_str}) is {behind_str}')

    if forward_commit_count > 0:
        ahead_str = colored(
            f'ahead by {forward_commit_count} commit(s)', 'green')
        print(f'--> Local branch ({branch_str}) is {ahead_str}')


def _run_action_for_each_repo(git_repo_dirs, func):
    for repo_dir in git_repo_dirs:
        repo = Repo(repo_dir)
        _try_run(lambda: func(repo_dir, repo))


def _run_action_if_is_repo(dir_path, action_func):
    if _has_git_repo(dir_path):
        repo = Repo(dir_path)
        _try_run(lambda: action_func(dir_path, repo))

    else:
        _print_error(f'No GIT repos found from "{dir_path}"')


def _execute_cmd_in_repo(cmd, operationTitle, repo_dir, repo=None):
    repo_obj = repo or Repo(repo_dir)
    print(f'{operationTitle} in repo: '
          + f'{_get_git_repo_str(repo_dir, repo_obj)}...\n')

    result = run(cmd, warn=True)

    repo_str = colored(repo_dir, 'blue')
    if result.failed:
        _print_warn(f'{operationTitle} failed (repo: {repo_str})')
    else:
        _print_info(f'{operationTitle} completed (repo: {repo_str})')

    print('')


def _get_remote_name(repo):
    remote = repo.remote()
    return remote.name if remote else DEFAULT_GIT_REMOTE_NAME


def _get_git_repo_str(repo_dir, repo):
    repo_identifier = _get_git_repo_identifier_str(repo_dir)

    dirty_state = '({})'.format(colored('DIRTY', 'red'))\
        if repo.is_dirty(untracked_files=True) else ''

    branch_text = '(detached HEAD)'\
        if _is_repo_head_detached(repo) else repo.active_branch
    branch = colored(branch_text, 'green')

    return f'[{branch}] "{repo_identifier}" {dirty_state}'


def _get_git_repo_identifier_str(repo_dir):
    return _as_bolded_white_str(os.path.relpath(repo_dir))


def _get_git_repo_paths(dir_path):
    repo_paths = []

    sub_directories = next(os.walk(dir_path))[1]
    for sub_dir in sub_directories:
        if sub_dir.startswith('.'):
            # skip hidden directories
            continue

        repo_path = os.path.join(dir_path, sub_dir)
        if _has_git_repo(repo_path):
            repo_paths.append(repo_path)

    return repo_paths


def _has_git_repo(path):
    git_db_dir = os.path.join(path, '.git')
    return os.path.isdir(git_db_dir)


# - Docker related functions #

def _re_start_dockers(repo_dir, repo):
    cmd = f"cd {repo_dir} && docker-compose restart"
    _execute_cmd_in_repo(cmd, 'Restarting dockers', repo_dir, repo)


def _stop_dockers(repo_dir, repo):
    cmd = f"cd {repo_dir} && docker-compose down"
    _execute_cmd_in_repo(cmd, 'Stopping dockers', repo_dir, repo)


def _start_dockers(repo_dir, repo):
    cmd = f"cd {repo_dir} && docker-compose up -d"
    _execute_cmd_in_repo(cmd, 'Starting dockers', repo_dir, repo)


def _get_repo_paths_containing_dockers(dir_path):
    repo_paths = []

    sub_directories = next(os.walk(dir_path))[1]
    for sub_dir in sub_directories:
        if sub_dir.startswith('.'):
            # skip hidden directories
            continue

        repo_path = os.path.join(dir_path, sub_dir)
        if _has_docker_compose_file(repo_path):
            repo_paths.append(repo_path)

    return repo_paths


def _has_docker_compose_file(path):
    docker_compose_file = os.path.join(path, 'docker-compose.yml')
    return os.path.isfile(docker_compose_file)


# - Maven related functions #

def _build_all_mvn_repos(profile):
    current_directory = os.getcwd()
    git_repo_dirs = _get_repo_paths_containing_maven_project(current_directory)
    if not git_repo_dirs:
        if _has_mvn_file(current_directory):
            git_repo_dirs.append(current_directory)
        else:
            return

    print('Building all maven repositories...\n')
    _run_action_for_each_repo(
        git_repo_dirs,
        lambda repo_dir, repo: _build_maven_project(repo_dir, profile))


def _build_maven_project(repo_dir, profile):
    mvn_tasks = 'clean compile'
    profile_str = _get_mvn_profile_str(profile)

    cmd = f"cd {repo_dir} && mvn {mvn_tasks}{profile_str}"
    _execute_cmd_in_repo(cmd, "Running 'mvn clean compile'", repo_dir)


def _install_maven_project(repo_dir, profile):
    mvn_task = 'install'
    profile_str = _get_mvn_profile_str(profile)

    cmd = f"cd {repo_dir} && mvn {mvn_task}{profile_str}"
    _execute_cmd_in_repo(cmd, "Running 'mvn install'", repo_dir)


def _start_spring_boot(repo_dir, jvm_args, profile):
    mvn_task = 'spring-boot:run'
    profile_str = _get_mvn_profile_str(profile)
    jvm_args_str = f'"-Dspring-boot.run.jvmArguments={jvm_args}"'\
        if jvm_args else ''

    cmd = f"cd {repo_dir} && mvn {mvn_task} {jvm_args_str}{profile_str}"
    _execute_cmd_in_repo(cmd, "Starting Spring Boot", repo_dir)


def _get_mvn_profile_str(profile):
    return f' -P{profile}' if profile else ''


def _get_repo_paths_containing_maven_project(dir_path):
    repo_paths = []

    sub_directories = next(os.walk(dir_path))[1]
    for sub_dir in sub_directories:
        if sub_dir.startswith('.'):
            # skip hidden directories
            continue

        repo_path = os.path.join(dir_path, sub_dir)
        if _has_mvn_file(repo_path):
            repo_paths.append(repo_path)

    return repo_paths


def _has_mvn_file(path):
    mvn_file = os.path.join(path, 'pom.xml')
    return os.path.isfile(mvn_file)


# - Other functions #

def _try_run(func):
    try:
        func()
    except Exception as error:
        _print_error('Message: ' + str(error))
        # verbose details
        if DEBUG_MODE:
            _print_error(traceback.format_exc())


def _print_info(print_str):
    print('[{}] {}'.format(colored('info', 'green'), print_str))


def _print_warn(print_str):
    print('[{}] {}'.format(colored('warn', 'yellow'), print_str))


def _print_error(print_str):
    print('[{}] {}'.format(colored('error', 'red'), print_str))


def _as_bolded_white_str(str_value):
    return colored(
        str_value,
        'white',
        attrs=['bold'])
