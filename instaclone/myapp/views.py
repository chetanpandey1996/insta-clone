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
from forms import SignUpForm, LoginForm, PostForm, LikeForm, CommentForm, DownloadForm
from models import UserModel, SessionToken, PostModel, LikeModel, CommentModel
from django.contrib.auth.hashers import make_password, check_password
from clarifai.rest import ClarifaiApp
from collections import OrderedDict

app = ClarifaiApp(api_key="cb9a1545abae4564b05f09ed29184530")

YOUR_CLIENT_ID = 'a8e20f3bf815329'
YOUR_CLIENT_SECRET = '3863df53283968a0e35040e1bdacb55fc3c43853'
api = OrderedDict()
api['celebrities'] = 'celeb-v1.3'
api['vehicles'] = 'general-v1.3'

tra = ['water', 'adventure', 'city', 'sand', 'no person', 'snow', 'travel','fog','tree','trees']
vec = ['car', 'truck', 'vehicle', 'shipment']

drop = [' ','celebrity','bikes','vehicles','traveling','others','logos']

def signup_view(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            # saving data to DB
            user = UserModel(name=name, password=make_password(password), email=email, username=username)
            user.save()
            return redirect('login/')
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
                    response = redirect('feed/',{'drop': drop})
                    response.set_cookie(key='session_token', value=token.session_token)
                    return response
                else:
                    form = 'Incorrect Password! Please try again!'
        else:
            form = 'Fill all the fields!'
    elif request.method == 'GET':
        form = LoginForm()

    return render(request, 'login.html', {'message': form })


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


def feed_view(request):
    user = check_validation(request)
    if user:
        selected = request.POST.get('dropdown1')
        if selected == ' ' or selected == None:
            posts = PostModel.objects.all().order_by('-created_on')
        elif selected =="celebrity":
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

        for post in posts:
            existing_like = LikeModel.objects.filter(post_id=post.id, user=user).first()
            if existing_like:
                post.has_liked = True

        return render(request, 'feed.html', {'posts': posts, 'drop': drop})
    else:

        return redirect('/login/')


def like_view(request):
    user = check_validation(request)
    if user and request.method == 'POST':
        form = LikeForm(request.POST)
        if form.is_valid():
            post_id = form.cleaned_data.get('post').id
            existing_like = LikeModel.objects.filter(post_id=post_id, user=user).first()
            if not existing_like:
                LikeModel.objects.create(post_id=post_id, user=user)
            else:
                existing_like.delete()
            return redirect('/feed/', {'drop': drop})
    else:
        return redirect('/login/')


def download_view(request):
    user = check_validation(request)
    if user and request.method == 'POST':
        image_url = request.POST.get('post1')
        image_name = request.POST.get('post') + ".png"
        urllib.urlretrieve(image_url, image_name)
        return redirect('/feed/',{'drop': drop})
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
