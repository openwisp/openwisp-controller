VERSION = (1, 0, 3, 'final')
__version__ = VERSION  # alias


def get_version():
    version = f'{VERSION[0]}.{VERSION[1]}'
    if VERSION[2]:
        version = f'{version}.{VERSION[2]}'
    if VERSION[3:] == ('alpha', 0):
        version = f'{version} pre-alpha'
    if 'post' in VERSION[3]:
        version = f'{version}.{VERSION[3]}'
    else:
        if VERSION[3] != 'final':
            try:
                rev = VERSION[4]
            except IndexError:
                rev = 0
            version = f'{version}{VERSION[3][0:1]}{rev}'
    return version
