from ncclient import manager
import sys
import ReadEnvironmentVars
import os, getpass
from git import Repo, InvalidGitRepositoryError, Actor
import datetime
from time import *
import lxml.etree as etree


COMMITS_TO_PRINT = 10

def get_device_config(savedir, device):
    with manager.connect(host=device['host'], port=830, username=device['user'], password=device['password'], hostkey_verify=False) as m:
        c = m.get_config(source='running').data_xml
        print(f'Got config for {device["host"]}.  Saving...', end='')
        with open(f'{savedir}/{device["host"]}.temp.xml', 'w') as f:
            f.write(c)
            print('  Done.')
        etree.parse(f'{savedir}/{device["host"]}.temp.xml').write(f'{savedir}/{device["host"]}.xml', encoding="utf-8", pretty_print=True)
        os.remove(f'{savedir}/{device["host"]}.temp.xml')



def check_repopath_perms(repodir):
    # Check if repodir exists, is owned by the python script executing user and is writable
    from pathlib import Path
    repopath = Path(repodir)
    if not repopath.exists() or os.access(repodir, os.W_OK) != True or repopath.owner() != getpass.getuser():
        sys.exit(f'ERROR - Directory "{repodir}" must exist, be owned and writable by {getpass.getuser()}.')


def create_repo(gitenv):
    new_repo = Repo.init(gitenv['directory'], bare=False)

    with new_repo.config_writer() as git_config:
        git_config.set_value('user', 'email', gitenv["committer_email"])
        git_config.set_value('user', 'name', gitenv["committer_name"])
    
    new_repo.description = gitenv["description"]
    print(f'Set {gitenv["directory"]} git repo description to: {gitenv["description"]}')

    repo = Repo(gitenv['directory'])
    
    dtime = strftime('%Y-%m-%d %H:%M:%S\n', localtime())
    with open(f'{gitenv["directory"]}/lastCommit.txt', 'w') as f:
        f.write(str(dtime))

    index = repo.index
    index.add([f'{gitenv["directory"]}/lastCommit.txt'])  # add a new file to the index

    author = Actor(gitenv["author_name"], gitenv["author_email"])
    committer = Actor(gitenv["committer_name"], gitenv["committer_email"])
    index.commit("Initial commit", author=author)
    # Rename master branch to main
    heads = repo.heads
    master = heads.master
    master.rename('main')
 

def check_repo_status(gitenv):
       # Repo object used to programmatically interact with Git repositories
    try:
        repo = Repo(gitenv['directory'])
    except InvalidGitRepositoryError:
        print('No repo.  Creating one...')
        create_repo(gitenv)
    # check that the repository loaded correctly
    else:
        if not repo.bare:
            print(f'Repo at {gitenv["directory"]} successfully loaded.')
            print_repository(repo)
            # create list of commits then print some of them to stdout
            commits = list(repo.iter_commits('main'))[:COMMITS_TO_PRINT]
            for commit in commits:
                print_commit(commit)
                pass
        else:
            print(f'Could not load repository at {gitenv["directory"]}')


def commit_local_repo(gitenv):
    repo = Repo(gitenv["directory"])
    repo.git.add(all=True)  # add all files to the index

    author = Actor(gitenv["author_name"], gitenv["author_email"])
    committer = Actor(gitenv["committer_name"], gitenv["committer_email"])
    dtime = strftime('%Y-%m-%d %H:%M:%S\n', localtime())
    repo.index.commit(f'Commit from scan on {str(dtime)}', author=author)


def print_commit(commit):
    print('----')
    print(str(commit.hexsha))
    print("\"{}\" by {} ({})".format(commit.summary,
                                     commit.author.name,
                                     commit.author.email))
    print(str(commit.authored_datetime))
    print(str("count: {} and size: {}".format(commit.count(),
                                              commit.size)))


def print_repository(repo):
    print('Repo description: {}'.format(repo.description))
    print('Repo active branch is {}'.format(repo.active_branch))
    for remote in repo.remotes:
        print('Remote named "{}" with URL "{}"'.format(remote, remote.url))
    print('Last commit for repo is {}.'.format(str(repo.head.commit.hexsha)))


if __name__ == "__main__":
    device = {
    "host": "CHANGEME",
    "user": "CHANGEME",
    "password": "CHANGEME"
}
    gitenv = ReadEnvironmentVars.read_config_file("git")
    repodir = gitenv['directory']

    check_repopath_perms(repodir)
    check_repo_status(gitenv)
    get_device_config(repodir, device)
    commit_local_repo(gitenv)
    #commit_remote_repo()
