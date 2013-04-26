import gittip
import logging
import requests
import os
import md5
import time
from aspen import json, log, Response
from aspen.website import Website
from aspen.utils import typecheck
from gittip.models import Participant
from gittip.elsewhere import ACTIONS, AccountElsewhere, _resolve

# BASE_API_URL = "https://api.bountysource.com/"
# BASE_WWW_URL = "https://www.bountysource.com/"
BASE_API_URL = "http://api.bountysource.dev/"
BASE_WWW_URL = "http://www.bountysource.dev/"

class BountysourceAccount(AccountElsewhere):
    platform = u'bountysource'

    def get_url(self):
        url = "https://www.bountysource.com/#users/%s" % self.user_info["slug"]
        return url

def create_access_token(participant):
    """Return an access token for the Bountysource API for this user.
    """
    time_now = int(time.time())
    token = "%s.%s.%s" % (participant.id, time_now, hash_access_token(participant.id, time_now))
    return token


def hash_access_token(user_id, time_now):
    """Create hash for access token.
    :param user_id:
        ID of the user.

    :param time_now:
        Current time, in seconds, as an integer.

    :returns:
        MD5 hash of user_id, time, and Bountysource API secret
    """
    raw = "%s.%s.%s" % (user_id, time_now, os.environ['BOUNTYSOURCE_API_SECRET'].decode('ASCII'))
    return md5.new(raw).hexdigest()


def resolve(login):
    return _resolve(u'bountysource', u'login', login)


def oauth_url(website, participant, redirect_url=None):
    """Return a URL to authenticate with Bountysource.

    Creates an accesstoken from the participant, used at Bountysource to associate accounts.
    
    :param participant:
        The participant whose account is being linked
    
    :param redirect_url:
        Optional redirect URL after authentication. Defaults to value defined in local.env
    
    :returns:
        URL for Bountysource account authorization
    """
    return "/on/bountysource/redirect?username=%s&external_access_token=%s&redirect_url=%s" % (participant.username, create_access_token(participant), (redirect_url or website.bountysource_callback))


def search_url(query):
    """Return search URL at Bountysource for query
    """
    url = "%s#search?query=%s"
    return url % (BASE_WWW_URL, query)


def access_token_valid(access_token):
    """Helper method to check validity of access token.
    """
    parts = (access_token or '').split('.')
    return len(parts) == 3 and parts[2] == hash_access_token(parts[0], parts[1])


def get_participant_via_access_token(username, access_token):
    """From a Gittip access token, attempt to find an external account
    """
    if access_token_valid(access_token):
        participant = Participant.query.get(username)
        parts = (access_token or '').split('.')
        
        if participant.id == int(parts[0]):
            return participant


def get_user_info(username):
    """Get the given user's information from the DB or failing that, Bountysource.

    :param username:
        A unicode string representing at username in bitbucket.

    :returns:
        A dictionary containing bitbucket specific information for the user.
    """
    typecheck(username, unicode)
    rec = gittip.db.fetchone( "SELECT user_info FROM elsewhere "
                              "WHERE platform='bountysource' "
                              "AND user_info->'display_name' = %s"
                            , (username,)
                             )
    if rec is not None:
        user_info = rec['user_info']
    else:
        url = "%s/users/%s"
        user_info = requests.get(url % (BASE_API_URL, username))
        status = user_info.status_code
        content = user_info.content
        if status == 200:
            user_info = json.loads(content)
        elif status == 404:
            raise Response(404,
                           "Bountysource identity '{0}' not found.".format(username))
        else:
            log("Bountysource api responded with {0}: {1}".format(status, content),
                level=logging.WARNING)
            raise Response(502, "Bountysource lookup failed with %d." % status)

    return user_info
