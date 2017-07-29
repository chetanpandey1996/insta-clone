# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from datetime import timedelta

from django.core.serializers import json
from django.http import HttpResponse
from imgurpython import ImgurClient
from instaclone.settings import BASE_DIR
from django.shortcuts import render, redirect
from django.utils import timezone
import urllib
from forms import SignUpForm, LoginForm, PostForm, LikeForm, CommentForm, UpvoteForm
from models import UserModel, SessionToken, PostModel, LikeModel, CommentModel, UpvoteModel
from django.contrib.auth.hashers import make_password, check_password
from clarifai.rest import ClarifaiApp
from collections import OrderedDict

app = ClarifaiApp(api_key="cb9a1545abae4564b05f09ed29184530")

YOUR_CLIENT_ID = 'a8e20f3bf815329'
YOUR_CLIENT_SECRET = '3863df53283968a0e35040e1bdacb55fc3c43853'
api = OrderedDict()
api['celebrities'] = 'celeb-v1.3'
api['vehicles'] = 'general-v1.3'

tra = ['water', 'adventure', 'city', 'sand', 'no person', 'snow', 'travel', 'fog', 'tree', 'trees']
vec = ['car', 'truck', 'vehicle', 'shipment']

drop = [' ', 'celebrity', 'bikes', 'vehicles', 'traveling', 'others', 'logos']

import sendgrid
import os
from sendgrid.helpers.mail import *

sg = sendgrid.SendGridAPIClient(apikey='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')

from_email = Email("chetan.pandey.779@outlook.com.com")

def signup_view(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            if len(username)<4:
                form = "Us"
                return render(request, 'index.html', {'form': form})
            if len(password)<5:
                form = "Ps"
                return render(request, 'index.html', {'form': form})
            # saving data to DB
            user = UserModel(name=name, password=make_password(password), email=email, username=username)
            user.save()
            to_email = Email(email)
            subject = "Insta-clone Community"
            content = Content("text/plain", "Hi "+ username + " \n You have successfully signed-Up with insta-clone")
            mail = Mail(from_email, subject, to_email, content)
            response = sg.client.mail.send.post(request_body=mail.get())
            print(response.status_code)
            print(response.body)
            print(response.headers)
            return render(request, 'sucess.html')
        else:
            form = "fillempty"
            return render(request, 'index.html', {'form': form})
    form = SignUpForm()
    return render(request, 'index.html', {'form': form})


def login_view(request):
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = UserModel.objects.filter(username=username).first()

            if user:
                if check_password(password, user.password):
                    token = SessionToken(user=user)
                    token.create_token()
                    token.save()
                    response = redirect('feed/', {'drop': drop})
                    response.set_cookie(key='session_token', value=token.session_token)
                    return response
                else:
                    form = 'Incorrect Password! Please try again!'
            else:
                form ='usernot'
        else:
            form = 'Fill all the fields!'
    elif request.method == 'GET':
        form = LoginForm()

    return render(request, 'login.html', {'message': form})


def logout_view(request):
    if request.COOKIES.get('session_token'):
        session = SessionToken.objects.filter(session_token=request.COOKIES.get('session_token')).first()
        session.delete()
    return redirect('/login/')


def post_view(request):
    user = check_validation(request)

    if user:
        if request.method == 'POST':
            form = PostForm(request.POST, request.FILES)
            if form.is_valid():
                image = form.cleaned_data.get('image')
                caption = form.cleaned_data.get('caption')
                post = PostModel(user=user, image=image, caption=caption)
                post.save()

                path = str(BASE_DIR + '/' + post.image.url)

                client = ImgurClient(YOUR_CLIENT_ID, YOUR_CLIENT_SECRET)
                post.image_url = client.upload_from_path(path, anon=True)['link']
                post.save()

                model = app.models.get(api.values()[1])
                response = model.predict_by_url(url=client.upload_from_path(path, anon=True)['link'])
                if response["outputs"][0]["data"]["concepts"][0]['name'] == "symbol" or \
                                response["outputs"][0]["data"]["concepts"][0]['name'] == "illustration":
                    post.interest = 'logo'
                elif response["outputs"][0]["data"]['concepts'][0]['name'] == 'bike':
                    post.interest = 'bike'
                elif any(response["outputs"][0]["data"]['concepts'][0]['name'] in s for s in vec):
                    post.interest = 'vehicles'
                elif any(response["outputs"][0]["data"]['concepts'][0]['name'] in s for s in tra):
                    post.interest = 'traveling'
                else:
                    post.interest = 'others'
                post.save();
                return redirect('/feed/', {'drop': drop})

        else:
            form = PostForm()
        return render(request, 'post.html', {'form': form})
    else:
        return redirect('/login/')


def feed_view(request, slug=None, *args, **kwargs):
    user = check_validation(request)
    if user:
        post = UserModel.objects.filter(username=slug)
        if len(post) == 0:
            print('NONE')
            selected = request.POST.get('dropdown1')
            if selected == ' ' or selected == None:
                posts = PostModel.objects.all().order_by('-created_on')
            elif selected == "celebrity":
                posts = PostModel.objects.filter(interest="celebrity").order_by('-created_on')
            elif selected == "bikes":
                posts = PostModel.objects.filter(interest="bike").order_by('-created_on')
            elif selected == "vehicles":
                posts = PostModel.objects.filter(interest="vehicles").order_by('-created_on')
            elif selected == "logos":
                posts = PostModel.objects.filter(interest="logos").order_by('-created_on')
            elif selected == "traveling":
                posts = PostModel.objects.filter(interest="traveling").order_by('-created_on')
            else:
                posts = PostModel.objects.filter(interest="others").order_by('-created_on')
        else:
            print 'NOT NONE'
            selected = request.POST.get('dropdown1')
            if selected == ' ' or selected == None:
                posts = PostModel.objects.filter(user=user).order_by('-created_on')
            elif selected == "celebrity":
                posts = PostModel.objects.filter(interest="celebrity", username=slug).order_by('-created_on')
            elif selected == "bikes":
                posts = PostModel.objects.filter(interest="bike", username=slug).order_by('-created_on')
            elif selected == "vehicles":
                posts = PostModel.objects.filter(interest="vehicles", username=slug).order_by('-created_on')
            elif selected == "logos":
                posts = PostModel.objects.filter(interest="logos", username=slug).order_by('-created_on')
            elif selected == "traveling":
                posts = PostModel.objects.filter(interest="traveling", username=slug).order_by('-created_on')
            else:
                posts = PostModel.objects.filter(interest="others", username=slug).order_by('-created_on')

        for post in posts:
            comments = CommentModel.objects.filter(post=post)
            existing_like = LikeModel.objects.filter(post_id=post.id, user=user).first()
            if existing_like:
                post.has_liked = True
            for comment in comments:
                existing_vote = UpvoteModel.objects.filter(post_id=post.id, user=user, comment_id=comment.id).first()
                if existing_vote:
                    print('upvoted')
                    comment.has_upvoted = True

        return render(request, 'feed.html', {'posts': posts, 'drop': drop, 'comment': comments})
    else:

        return redirect('/login/')


def like_view(request):
    user = check_validation(request)
    if user and request.method == 'POST':
        form = LikeForm(request.POST)
        if form.is_valid():
            post_id = form.cleaned_data.get('post').id
            puser = request.POST.get('pusername')
            pemail = request.POST.get('pemail')
            existing_like = LikeModel.objects.filter(post_id=post_id, user=user).first()
            if not existing_like:
                LikeModel.objects.create(post_id=post_id, user=user)
                print
                print pemail
                print puser

                to_email = Email(pemail)
                subject = "like"
                content = Content("text/plain", "Hi ,\n "+ "  user - "+ user.username +" has liked your post.")
                mail = Mail(from_email, subject, to_email, content)
                response = sg.client.mail.send.post(request_body=mail.get())
                print(response.status_code)
                print(response.body)
                print(response.headers)
            else:
                existing_like.delete()
            return redirect('/feed/', {'drop': drop})
    else:
        return redirect('/login/')


def upvote_view(request):
    user = check_validation(request)
    if user and request.method == 'POST':
        form = UpvoteForm(request.POST)
        if form.is_valid():
            post_id = form.cleaned_data.get('post').id
            comm_id = form.cleaned_data.get('comment').id
            existing_vote = UpvoteModel.objects.filter(post_id=post_id, user=user, comment_id=comm_id).first()
            if not existing_vote:
                print('created')
                UpvoteModel.objects.create(post_id=post_id, user=user, comment_id=comm_id)
            else:
                print('deleted')
                existing_vote.delete()
            return redirect('/feed/', {'drop': drop})
    else:
        return redirect('/login/')


def download_view(request):
    user = check_validation(request)
    if user and request.method == 'POST':
        image_url = request.POST.get('post1')
        image_name = request.POST.get('post') + ".png"
        urllib.urlretrieve(image_url, image_name)
        return redirect('/feed/', {'drop': drop})
    return redirect('/login/')


def comment_view(request):
    user = check_validation(request)
    if user and request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            post_id = form.cleaned_data.get('post').id
            comment_text = form.cleaned_data.get('comment_text')
            comment = CommentModel.objects.create(user=user, post_id=post_id, comment_text=comment_text)
            comment.save()
            comment = CommentModel.objects.filter(user=user, post_id=post_id, comment_text=comment_text).first()
            to_email = Email(comment.post.user.email)
            subject = "Insta-clone Community"
            content = Content("text/plain", "Hi "+comment.post.user.username +",\n      "+ user.username+" has commented - "+comment_text+" on your post.")
            mail = Mail(from_email, subject, to_email, content)
            response = sg.client.mail.send.post(request_body=mail.get())
            print(response.status_code)
            print(response.body)
            print(response.headers)
            return redirect('/feed/')
        else:
            return redirect('/feed/')
    else:
        return redirect('/login')


# For validating the session
def check_validation(request):
    if request.COOKIES.get('session_token'):
        session = SessionToken.objects.filter(session_token=request.COOKIES.get('session_token')).first()
        if session:
            time_to_live = session.created_on + timedelta(days=1)
            if time_to_live > timezone.now():
                return session.user
    else:
        return None
