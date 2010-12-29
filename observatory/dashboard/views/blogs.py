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

import datetime
from dashboard.forms import BlogPostForm
from dashboard.models import BlogPost, Blog, Project
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.core.urlresolvers import reverse
from django.http import Http404, HttpResponseRedirect
from django.template import RequestContext
from django.shortcuts import render_to_response, get_object_or_404
from lib.markdown import markdown

# the number of posts per page
POSTS_PER_PAGE = 5

# alias for the first page of blog posts
def posts(request):
  return posts_page(request, 1)

# shows a page of blog posts, the number of posts is set by PAGE_PER_POSTS
def posts_page(request, page_num):
  paginator = Paginator(BlogPost.objects.all().order_by('date').reverse(),
                        POSTS_PER_PAGE)
  
  # if the page requested does not exist, 404
  if int(page_num) not in paginator.page_range:
    raise Http404
  
  # otherwise, render
  return render_to_response('blogs/posts.html', {
      'page': paginator.page(page_num),
      'disable_content': True
    }, context_instance = RequestContext(request))

# shows a project's internally hosted blog, or redirects to an external one
def show_blog(request, project_id):
  project = get_object_or_404(Project, id = project_id)
  if project.blog.external:
    return HttpResponseRedirect(project.blog.url)
  else:
    return render_to_response('blogs/show-blog.html', {
        'project': project,
        'posts': project.blog.blogpost_set.all(),
      }, context_instance = RequestContext(request))

# shows a specific blog post
def show_post(request, post_id):
  post = get_object_or_404(BlogPost, id = int(post_id))
  if post.external:
    return HttpResponseRedirect(post.external_link)
  else:
    return render_to_response('blogs/show-post.html', {
        'post': post
      }, context_instance = RequestContext(request))

# write a new post
@login_required
def write_post(request, project_id):
  project = get_object_or_404(Project, id = int(project_id))
  if request.user not in project.authors.all():
    return HttpResponseRedirect(reverse('dashboard.views.projects.show',
                                        args = (project.id,)))
  
  return render_to_response('blogs/edit.html', {
      'project': project,
      'form': BlogPostForm()
    }, context_instance = RequestContext(request))

# edit an existing post
@login_required
def edit_post(request, post_id):
  post = get_object_or_404(BlogPost, id = int(post_id))
  
  if request.user not in post.blog.project.authors.all():
    return HttpResponseRedirect(reverse('dashboard.views.projects.show',
                                        args = (project.id,)))
  
  return render_to_response('blogs/edit.html', {
      'project': post.blog.project,
      'post': post,
      'form': BlogPostForm(instance = post)
    }, context_instance = RequestContext(request))

# creates a new post
@login_required
def create_post(request, project_id):
  form = BlogPostForm(request.POST)
  project = get_object_or_404(Project, id = int(project_id))
  
  if request.user not in project.authors.all():
    return HttpResponseRedirect(reverse('dashboard.views.projects.show',
                                        args = (project.id,)))
  
  # validate the form
  if form.is_valid():
    html = markdown(request.POST['markdown'])
    post = BlogPost(title = request.POST['title'],
                    markdown = request.POST['markdown'],
                    description = html,
                    summary = html,
                    external = False,
                    author = request.user,
                    date = datetime.datetime.now())
    post.blog = project.blog
    post.save()
    
    return HttpResponseRedirect(reverse('dashboard.views.blogs.show_post',
                                        args = (post.id,)))
  else:
    return render_to_response('blogs/edit.html', {
        'project': project,
        'form': form
      }, context_instance = RequestContext(request)) 

# updates a previously posted post, and redirects to the management page
@login_required
def update_post(request, post_id):
  form = BlogPostForm(request.POST)
  post = get_object_or_404(BlogPost, id = int(post_id))
  
  # validate the form
  if form.is_valid():
    # update the post
    html = markdown(request.POST['markdown'])
    post.title = request.POST['title']
    post.markdown = request.POST['markdown']
    post.description = html
    post.summary = html
    post.save()
    
    return HttpResponseRedirect(reverse('dashboard.views.blogs.show_post',
                                        args = (post.id,)))
  else:
    return render_to_response('blogs/edit.html', {
        'project': post.blog.project,
        'form': form
      }, context_instance = RequestContext(request))

# deletes a post
@login_required
def delete_post(request, post_id):
  post = get_object_or_404(BlogPost, id = int(post_id))
  blog = post.blog
  
  if request.user not in post.blog.project.authors.all():
    return HttpResponseRedirect(reverse('dashboard.views.projects.show',
                                        args = (project.id,)))
  post.delete()
  return HttpResponseRedirect(reverse('dashboard.views.blogs.show_blog',
                                      args = (blog.id,)))