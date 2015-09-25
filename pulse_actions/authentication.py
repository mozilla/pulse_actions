import os


class AuthenticationError(Exception):
    pass


def get_user_and_password():
    """
    Retrieve user and password environment variables.

    Raise AuthenticationError if either aren't defined.
    """

    user = os.environ.get('PULSE_USER')
    password = os.environ.get('PULSE_PW')

    if user is None and password is None:
        raise AuthenticationError("PULSE_USER and PULSE_PW are not set.")
    elif user is None:
        raise AuthenticationError("PULSE_USER is not set.")
    elif password is None:
        raise AuthenticationError("PULSE_PW is not set.")

    return user, password
