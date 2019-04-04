[![Build Status](https://travis-ci.org/VanirLab/VOS.svg?branch=master)

# VOS
## Vanir Operative System


## About

VOS is a cybersecurity system for vulnerability assessment which
allows you to quickly do a security audit of your own websites and network infrastructures from a remote location
without having to set up external pen-testing operating system and with very high-speed network
capability and processing power. It allows
you to scan, enumerate the security loopholes, and vulnerability with full customization of the open-source tools. 

-------------------------------------
## Future Scope
Automation: For future development & research, this os can be used as
an automate vulnerability and penetration testing.

-------------------------------------
## Branch
This is master branch of the VOS core.

--------------------------------------
## Coverage Reports

Running tests and coverage
To the unittests execute the following commands:

    ./manage.py collectstatic --noinput
    ./manage.py test
Running coverage:

    pip install coverage
    coverage run --omit='env*' --source='.' manage.py test
    coverage report

