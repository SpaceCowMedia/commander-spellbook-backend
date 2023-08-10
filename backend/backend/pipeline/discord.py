import requests
from social_core.exceptions import AuthException

PIPELINE = [
    # Get the information we can about the user and return it in a simple
    # format to create the user instance later. In some cases the details are
    # already part of the auth response from the provider, but sometimes this
    # could hit a provider API.
    'social_core.pipeline.social_auth.social_details',

    # Get the social uid from whichever service we're authing thru. The uid is
    # the unique identifier of the given user in the provider.
    'social_core.pipeline.social_auth.social_uid',

    # Verifies that the current auth process is valid within the current
    # project, this is where emails and domains whitelists are applied (if
    # defined).
    'social_core.pipeline.social_auth.auth_allowed',

    # Checks if the discord user has joined the Commander Spellbook server.
    'backend.pipeline.discord.is_member_of_guild',

    # Checks if the current social-account is already associated in the site.
    'social_core.pipeline.social_auth.social_user',

    # Make up a username for this person, appends a random string at the end if
    # there's any collision.
    'social_core.pipeline.user.get_username',

    # Send a validation email to the user to verify its email address.
    # Disabled by default.
    # 'social_core.pipeline.mail.mail_validation',

    # Associates the current social details with another user account with
    # a similar email address.
    'social_core.pipeline.social_auth.associate_by_email',

    # Create a user account if we haven't found one yet.
    'social_core.pipeline.user.create_user',

    # Create the record that associates the social account with the user.
    'social_core.pipeline.social_auth.associate_user',

    # Populate the extra_data field in the social record with the values
    # specified by settings (and the default ones like access_token, etc).
    'social_core.pipeline.social_auth.load_extra_data',

    # Update the user record with any changed info from the auth service.
    'social_core.pipeline.user.user_details',
]


def is_member_of_guild(backend, details, response, uid, user, *args, **kwargs):
    if backend.name == 'discord':
        api = f'https://{backend.HOSTNAME}/api/users/@me/guilds'
        headers = {
            'Authorization': f'Bearer {response["access_token"]}'
        }
        r = requests.get(api, headers=headers)
        if r.status_code == 200:
            guilds = r.json()
            for guild in guilds:
                if guild['id'] == '673601282946236417':  # Commander Spellbook
                    return
            raise AuthException(backend, 'You must join the Commander Spellbook Discord server to use this site.')
        else:
            raise AuthException(backend, 'Could not reach Discord API.')
