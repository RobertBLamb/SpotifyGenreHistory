from flask import Flask, request, url_for, session, redirect, render_template
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
from math import ceil
import pandas as pd
import os
import io
import base64
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure

application = Flask(__name__)

application.secret_key = "asdasdasd"
application.config['SESSION_COOKIE_NAME'] = 'cookie'
TOKEN_INFO = "token_info"


@application.route('/')
def login():  # login to spotify
    sp_oauth = create_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)


@application.route('/redirect')
def redirect_page():  # move user to the graph generation page
    sp_oauth = create_spotify_oauth()
    session.clear()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session[TOKEN_INFO] = token_info
    return redirect(url_for('plot_png', _external=True))


@application.route('/plot.png')
def plot_png():

    try:  # verify token is good
        token_info = get_token()
    except:
        print("user not logged in >:(")
        return redirect(url_for('login', _external=False))

    sp = spotipy.Spotify(auth=token_info['access_token'])

    all_songs = get_song_list(sp)   # all songs in your liked list

    genre_likes, artists_genres = get_total_genre_likes(sp, all_songs)  # total number of likes each genre has

    top_genres = get_top_genres(genre_likes)

    monthly_likes = get_likes_per_month(all_songs, top_genres, artists_genres)

    graph = input_data(monthly_likes)

    return render_template("index.html", image=graph)


def get_token():
    token_info = session.get(TOKEN_INFO, None)
    if not token_info:
        raise "exception"

    now = int(time.time())
    is_expired = token_info['expires_at'] - now < 60

    if is_expired:
        sp_oauth = create_spotify_oauth()
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])

    return token_info


def get_song_list(sp):
    all_songs = []
    # prevMonth = str(sp.current_user_saved_tracks(limit=1, offset=0)['items'][0]['added_at'])[0:7]  # gets most recent year and month song was added
    loop = 0
    while True:
        items = sp.current_user_saved_tracks(limit=50, offset=loop * 50)['items']
        loop += 1
        all_songs += items
        if len(items) < 50:
            break
    return all_songs


def get_total_genre_likes(sp, all_songs):   # new
    artists_ids = set()
    total_genre_likes = {}
    artist_genre = {}

    # region get unique artist ids and make list of them
    for song in all_songs:  # get all of the artist ids
        artists_ids.add(song['track']['artists'][0]['id'])
    id_strings = list(artists_ids)
    # endregion

    # region add genres to dict with id as key
    limit = ceil(len(artists_ids)/50)
    for i in range(limit):  # todo: there has to be an alternative to this mess
        tmp = sp.artists(artists=id_strings[(50 * i):(50 * (i + 1))])['artists']
        for j in range(len(tmp)):
            artist_genre[tmp[j]['id']] = tmp[j]['genres']
    # endregion

    # region get the number of times each genre appears
    for song in all_songs:
        # todo: this is being called at the wrong time
        genres = artist_genre[song['track']['artists'][0]['id']]

        for genre in genres:
            if genre in total_genre_likes:
                total_genre_likes[genre] += 1
            else:
                total_genre_likes[genre] = 1
    # endregion

    return total_genre_likes, artist_genre


def get_top_genres(all_genre_likes):
    genres_to_return = 4
    top_genres = set()
    temp = sorted(all_genre_likes, key=all_genre_likes.get, reverse=True)[:genres_to_return]
    for i in range(genres_to_return):
        top_genres.add(temp[i])

    return top_genres


def get_likes_per_month(all_songs, top_genres, artists_genre):
    # 1 sort all songs by date
    all_songs.reverse()    # todo: remove useless info from the array before sorting

    # 2 make dictionary of top genres
    currrent_likes = {}
    for genre in top_genres:
        currrent_likes[genre] = 0

    # 3 increase dictionary of songs by 1 when the appear
    each_months_likes = {}
    month = all_songs[0]['added_at'][0:7]

    for song in all_songs:
        # region change month
        if month != (song['added_at'])[0:7]:    # todo: maybe make lists here, consider a list for the month also
            each_months_likes[month] = currrent_likes.copy()
            # print(each_months_likes[month])
            month = (song['added_at'])[0:7]
        # endregion

        if not set(artists_genre[song['track']['artists'][0]['id']]).isdisjoint(top_genres):    # if overlap between sets
            genres_to_increase = set(artists_genre[song['track']['artists'][0]['id']]).intersection(top_genres)
            for genre in genres_to_increase:
                currrent_likes[genre] += 1

    return each_months_likes


def input_data(monthly_likes):

    # region graph settings
    fig = Figure()
    axis = fig.add_subplot(1, 1, 1)
    axis.grid()

    axis.set_title("Spotify Top Genre Like History")
    axis.set_xlabel("Months")
    axis.set_ylabel("Total Songs Liked Per Genre")

    df = pd.DataFrame(monthly_likes)
    df2 = df.transpose()
    axis.set_xticks([0, 12.5, 25, 37.5, 50, 62.5, 75])

    axis.legend(df.index)
    axis.plot(df2, label=df.index)
    axis.legend()

    # endregion

    # region prep graph for frontend
    # Convert plot to PNG image
    pngImage = io.BytesIO()
    FigureCanvas(fig).print_png(pngImage)

    # Encode PNG image to base64 string
    pngImageB64String = "data:image/png;base64,"
    pngImageB64String += base64.b64encode(pngImage.getvalue()).decode('utf8')
    return pngImageB64String
    # endregion


def create_spotify_oauth():
    return SpotifyOAuth(
        # todo: move into a system variable before pushing to github
        client_id=os.environ['SPOTIFY_CLIENT_ID'],
        client_secret=os.environ['SPOTIFY_CLIENT_SECRET'],
        redirect_uri=url_for('redirect_page', _external=True),
        scope="user-library-read"
    )
