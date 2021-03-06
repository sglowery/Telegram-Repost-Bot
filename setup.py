from setuptools import setup

setup(
    name='reeepostbot',
    version='0.6',
    url='',
    modules=['repostbot'],
    license='GNU General Public License v3.0',
    author='Stephen Lowery',
    author_email='stephen.g.lowery@gmail.com',
    description='A Telegram bot to track images sent in a group chat and call out reposts.',
    install_requires=['imagehash', 'python-telegram-bot', 'telegram', 'Pillow', 'pyyaml']
)
