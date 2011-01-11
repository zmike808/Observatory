# Copyright (c) 2010, Nate Stedman <natesm@gmail.com>
#
# Permission to use, copy, modify, and/or distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

import os
import settings
import stat
import subprocess
from dashboard.util import format_diff
from django.db import models
from exceptions import Exception
from lib import feedparser, dateutil, pyvcs
from lib.pyvcs.backends import get_backend
from EventSet import EventSet

# a version control repository
class Repository(EventSet):
  class Meta:
    app_label = 'dashboard'
  
  # web access to the repository
  web_url = models.URLField("Repository Web Address", max_length = 128)
  
  # cloned repository fields
  clone_url = models.CharField("Repository Clone Address", max_length = 128)
  vcs = models.CharField("Version Control System", max_length = 3,
                         default = 'git',
                         choices = (('git', 'git'),
                                    ('svn', 'Subversion'),
                                    ('hg',  'Mercurial'),
                                    ('bzr', 'Bazaar')))
  
  # non-cloned repository fields
  repo_rss = models.URLField("Repository RSS Feed", max_length = 128)
  cmd = models.CharField("Clone Command", max_length = 128)
  
  def fetch(self):
    import Commit
    events = []
    
    if not self.from_feed:
      # this is a cloned repository
      fresh_clone = True

      # ensure that REPO_ROOT already exists
      try:
        os.makedirs(settings.REPO_ROOT, 0770)
      except OSError as e:
        pass
      
      # construct the name of the directory into which to clone the repository
      dest_dir = os.path.join(settings.REPO_ROOT, self.project.url_path)

      # check if we've already cloned this project
      if os.path.isdir(dest_dir):
        fresh_clone = False

      # clone the repository, or update our copy
      clone_repo_function(self.vcs)(self.clone_url, dest_dir, fresh_clone)

      # add the commits
      backend = get_backend(self.vcs if self.vcs != 'svn' else 'git')
      repository = backend.Repository(dest_dir)

      # inspect the last five days of commits
      for commit in repository.get_recent_commits():
        date = commit.time
        try:
          date = (date - date.utcoffset()).replace(tzinfo=None)
        except:
          pass
        
        # extract the first line for the title of the commit
        try:
          commit_title = commit.message.split("\n")[0]
        except:
          commit_title = commit.message
        
        events.append(self.add_event(Commit.Commit,
          title = commit_title,
          description = commit.message,
          date = date,
          author_name = commit.author,
          from_feed = False,
          extra_args = {
            "diff": format_diff(commit.diff),
            "repository_id": self.id,
          }))
    else:
      # this is a feed-driven repository
      for commit in feedparser.parse(self.repo_rss).entries:
        date = dateutil.parser.parse(commit.date)
        try:
          date = (date - date.utcoffset()).replace(tzinfo=None)
        except:
          pass
        
        events.append(self.add_event(Commit.Commit, 
          title = commit.title, 
          description = commit.description,
          date = date,
          author_name = commit.author_detail['name'],
          from_feed = True, 
          extra_args = { "repository_id": self.id }
        ))
    
    # find the new most recent date
    dates = [event.date for event in events if event is not None]
    dates.append(self.most_recent_date)
    self.most_recent_date = max(dates)
    self.save()
  
  def clone_cmd(self):
    if not self.from_feed:
      cmds = { 'git': 'clone', 'svn': 'co', 'hg': 'clone', 'bzr': 'branch' }
      return '{0} {1} {2}'.format(self.vcs, cmds[self.vcs], self.clone_url)
    else:
      return self.cmd

  def __unicode__(self):
    return self.web_url

def clone_git_repo(clone_url, destination_dir, fresh_clone = False):
  if fresh_clone:
    clone_cmdline = ["git", "clone", "--mirror", "--bare",
                     clone_url, destination_dir]
  else:
    clone_cmdline = ["git", "--git-dir", destination_dir, "fetch"]

  clone_subprocess = subprocess.Popen(clone_cmdline)

  if clone_subprocess.wait() != 0:
    # TODO: handle this better
    print "failed to clone from {0}".format(clone_url)

  # do something with the repos

def clone_svn_repo(clone_url, destination_dir, fresh_clone = False):
  if fresh_clone:
    # make the repo's directory
    try:
      os.makedirs(destination_dir, 0770)
    except OSError as e:
      pass
    
    clone_cmdline = ["git", "svn", "clone", clone_url, destination_dir]
  else:
    clone_cmdline = ["git", "svn", "fetch"]
  
  if subprocess.call(clone_cmdline, cwd = destination_dir) != 0:
    print "failed to clone from {0}".format(clone_url)

def clone_repo_function(vcs):
  clone_repo_functions = {
    'git': clone_git_repo,
    'svn': clone_svn_repo
  }

  if not vcs in clone_repo_functions:
    print "don't know how to clone {0}".format(vcs)
    return None

  return clone_repo_functions[vcs]